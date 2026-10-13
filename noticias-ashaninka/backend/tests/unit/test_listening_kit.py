"""Fase 6: kit de escucha (5.7): reglas, estadística, construcción y puntuación con oyentes simulados."""

import csv
import json
import zipfile

import numpy as np
import pytest

from eval.listening.inteligibilidad_mos import build, score
from eval.listening.inteligibilidad_mos import diseno as dz
from eval.listening.inteligibilidad_mos.simular import VERDAD, simular_oyentes

# Oraciones de PRUEBA (no son datos lingüísticos): solo necesitan 3 palabras de 5 o más letras
PALABRAS = [
    "okantzi",
    "kemetsa",
    "tzimatsi",
    "kitaiteri",
    "irotake",
    "otimimotena",
    "katsini",
    "ayotari",
]


def _oraciones(n=10):
    out = []
    for i in range(n):
        w = [PALABRAS[(i + k) % len(PALABRAS)] for k in range(5)]
        out.append({"ref": f"t{i:03d}", "canonical": " ".join(w) + ".", "text_tts": " ".join(w)})
    return out


@pytest.fixture(scope="module")
def kit(tmp_path_factory):
    salida = tmp_path_factory.mktemp("kit")
    resumen = build.construir(_oraciones(10), salida, build.MOTORES_FAKE, semilla=7)
    with (salida / "clave.csv").open(encoding="utf-8", newline="") as f:
        clave = list(csv.DictReader(f))
    return salida, resumen, clave


# ------------------------------------------------------------------ reglas
def test_palabras_clave_son_las_tres_primeras_de_cinco_o_mas_letras():
    assert dz.palabras_clave("Okantzi kemetsa irotake tzimatsi Pablo") == [
        "okantzi",
        "kemetsa",
        "irotake",
    ]
    assert dz.palabras_clave("Tee ya okantzi 2026 okantzi kemetsa, tzimatsi!") == [
        "okantzi",
        "kemetsa",
        "tzimatsi",
    ]
    assert dz.palabras_clave("solo okantzi kemetsa") == [
        "okantzi",
        "kemetsa",
    ]  # menos de 3: no sirve para el kit


def test_comparacion_ignora_mayusculas_tildes_y_signos_pero_no_la_enye():
    assert dz.palabras("¡Okántzi, KEMETSA!") == ["okantzi", "kemetsa"]
    assert dz.palabras("ñaantsi") == ["ñaantsi"]
    assert dz.evaluar_transcripcion(["ñaantsi"], "naantsi")["aciertos"] == 0  # n ≠ ñ


def test_acierto_y_cer_de_palabra_clave():
    ev = dz.evaluar_transcripcion(["okantzi", "kemetsa", "irotake"], "ya OKANTZI kemetza irotake")
    assert ev["hits"] == [True, False, True] and ev["aciertos"] == 2
    assert ev["ediciones"] == 1 and ev["letras"] == 7 + 7 + 7  # kemetza vs kemetsa: 1 edición
    vacio = dz.evaluar_transcripcion(["okantzi"], "")
    assert vacio["aciertos"] == 0 and vacio["ediciones"] == 7  # no escribir nada = error total


def test_elegir_oraciones_exige_tres_claves_y_longitud():
    cand = _oraciones(10) + [{"ref": "corta", "canonical": "tee ya", "text_tts": "x"}]
    elegidas = dz.elegir_oraciones(cand, 5, 1)
    assert len(elegidas) == 5 and all(e["ref"] != "corta" for e in elegidas)
    assert elegidas == dz.elegir_oraciones(cand, 5, 1) != dz.elegir_oraciones(cand, 5, 2)


# ------------------------------------------------------------------ alfa de Krippendorff
def _krippendorff_2011():
    a = [1, 2, 3, 3, 2, 1, 4, 1, 2, None, None, None]
    b = [1, 2, 3, 3, 2, 2, 4, 1, 2, 5, None, 3]
    c = [None, 3, 3, 3, 2, 3, 4, 2, 2, 5, 1, None]
    d = [1, 2, 3, 3, 2, 4, 4, 1, 2, 5, 1, None]
    return {i: [x for x in (a[i], b[i], c[i], d[i]) if x is not None] for i in range(12)}


def test_alfa_de_krippendorff_reproduce_el_ejemplo_publicado():
    u = _krippendorff_2011()  # Krippendorff (2011): nominal 0,743, ordinal 0,815, intervalo 0,849
    assert dz.krippendorff_alpha(u, "nominal") == pytest.approx(0.743, abs=0.001)
    assert dz.krippendorff_alpha(u, "ordinal") == pytest.approx(0.815, abs=0.001)
    assert dz.krippendorff_alpha(u, "intervalo") == pytest.approx(0.849, abs=0.001)


def test_alfa_casos_limite():
    assert dz.krippendorff_alpha(
        {i: [v, v] for i, v in enumerate([1, 2, 3, 4, 5, 3])}
    ) == pytest.approx(1.0)
    assert dz.krippendorff_alpha({0: [3, 3], 1: [3, 3]}) is None  # sin variación: indefinido
    assert dz.krippendorff_alpha({0: [3]}) is None  # nadie coincide con nadie
    rng = np.random.default_rng(1)
    ruido = {i: [int(rng.integers(1, 6)), int(rng.integers(1, 6))] for i in range(400)}
    assert abs(dz.krippendorff_alpha(ruido)) < 0.1  # respuestas independientes: ≈ 0


def test_acuerdo_por_pares_y_bootstrap_de_oyentes():
    assert (
        dz.acuerdo_medio_por_pares({0: {"a": True, "b": True}, 1: {"a": True, "b": False}}) == 0.5
    )
    assert dz.acuerdo_medio_por_pares({0: {"a": True}}) is None
    assert dz.bootstrap_oyentes({"a": 0.5}) is None  # con un solo oyente no hay IC
    r = dz.bootstrap_oyentes({f"o{i}": 0.5 + 0.01 * i for i in range(10)})
    assert r["ic95"][0] < r["media"] < r["ic95"][1]
    assert r == dz.bootstrap_oyentes({f"o{i}": 0.5 + 0.01 * i for i in range(10)})  # reproducible


# ------------------------------------------------------------------ audio
def test_normalizar_rms_iguala_el_volumen_sin_recortar():
    t = np.linspace(0, 1, 16000, dtype=np.float32)
    suave, fuerte = 0.01 * np.sin(2 * np.pi * 200 * t), 0.9 * np.sin(2 * np.pi * 200 * t)
    for x in (suave, fuerte):
        y = build.normalizar_rms(x)
        assert np.sqrt(np.mean(y**2)) == pytest.approx(build.RMS_OBJETIVO, rel=0.01)
        assert np.max(np.abs(y)) <= build.PICO_MAX
    picudo = np.zeros(1000, dtype=np.float32)
    picudo[10] = 1.0
    assert (
        np.max(np.abs(build.normalizar_rms(picudo))) <= build.PICO_MAX
    )  # el pico manda sobre el RMS
    assert build.normalizar_rms(np.zeros(10, dtype=np.float32)).tolist() == [0.0] * 10


# ------------------------------------------------------------------ construcción
def test_el_kit_tiene_ambos_motores_por_oracion_y_repetidos(kit):
    salida, resumen, clave = kit
    assert resumen["oraciones"] == 10 and resumen["repetidos"] >= 2
    base = [c for c in clave if not c["repite_de"]]
    assert len(base) == 20 and len(clave) == 20 + resumen["repetidos"]
    for ref in {c["oracion"] for c in base}:
        assert {c["motor"] for c in base if c["oracion"] == ref} == set(dz.MOTORES)
    assert [c["item"] for c in clave] == [f"i{i:03d}" for i in range(1, len(clave) + 1)]
    assert all(len(c["claves"].split("|")) == 3 for c in clave)


def test_los_repetidos_aparecen_mas_tarde_con_otro_nombre_y_el_mismo_audio(kit):
    salida, _, clave = kit
    orden = {c["item"]: i for i, c in enumerate(clave)}
    audios = {c["item"]: c for c in clave}
    for c in clave:
        if c["repite_de"]:
            o = audios[c["repite_de"]]
            assert orden[c["item"]] > orden[o["item"]] and c["audio"] != o["audio"]
            assert c["motor"] == o["motor"] and c["claves"] == o["claves"]
            assert (salida / "audio" / c["audio"]).read_bytes() == (
                salida / "audio" / o["audio"]
            ).read_bytes()


def test_la_misma_oracion_no_va_seguida(kit):
    _, _, clave = kit
    assert all(a["oracion"] != b["oracion"] for a, b in zip(clave, clave[1:], strict=False))


def test_el_zip_no_lleva_la_clave_y_nada_delata_el_motor(kit):
    salida, _, clave = kit
    with zipfile.ZipFile(salida / "kit_escucha.zip") as z:
        nombres = z.namelist()
        assert "hoja_escucha.html" in nombres and "hoja_escucha.csv" in nombres
        assert not any("clave" in n.lower() for n in nombres)
        textos = z.read("hoja_escucha.html").decode() + z.read("hoja_escucha.csv").decode()
    for secreto in ("mms", "espeak", "clave.csv", "vits"):
        assert secreto not in textos.lower() and not any(secreto in n.lower() for n in nombres)
    # la hoja lista cada audio una sola vez y todos existen
    for c in clave:
        assert f"audio/{c['audio']}" in nombres


def test_los_audios_tienen_el_mismo_volumen(kit):
    import soundfile as sf

    salida, _, clave = kit
    rms = []
    for c in clave:
        wav, _sr = sf.read(salida / "audio" / c["audio"])
        rms.append(float(np.sqrt(np.mean(wav**2))))
    assert max(rms) / min(rms) < 1.05


def test_construccion_reproducible_y_la_semilla_cambia_el_orden(tmp_path):
    a = build.construir(
        _oraciones(8), tmp_path / "a", build.MOTORES_FAKE, semilla=3, sin_audio=True
    )
    b = build.construir(
        _oraciones(8), tmp_path / "b", build.MOTORES_FAKE, semilla=3, sin_audio=True
    )
    build.construir(_oraciones(8), tmp_path / "c", build.MOTORES_FAKE, semilla=4, sin_audio=True)
    leer = lambda d: (d / "clave.csv").read_text(encoding="utf-8")  # noqa: E731
    assert a["items"] == b["items"] and leer(tmp_path / "a") == leer(tmp_path / "b")
    assert leer(tmp_path / "a") != leer(tmp_path / "c")


def test_la_hoja_html_valida_el_identificador_y_descarga_csv(kit):
    html = (kit[0] / "hoja_escucha.html").read_text(encoding="utf-8")
    assert html.count("<audio") == len(kit[2]) and "respuestas_" in html
    assert "oyente,variante,item,transcripcion,mos,comentario" in html
    for v in dz.VARIANTES:
        assert f'value="{v}"' in html


# ------------------------------------------------------------------ puntuación con oyentes simulados
def _puntuar(kit, n, semilla=11):
    _, _, clave = kit
    return score.puntuar(clave, simular_oyentes(clave, n, semilla))


def test_recupera_acierto_y_mos_verdaderos_dentro_del_ic(kit):
    r = _puntuar(kit, 30)
    assert r["n_oyentes"] == 30
    for motor, v in VERDAD.items():
        a = r["motores"][motor]["acierto_palabra"]
        assert a["ic95"][0] <= v["p_acierto"] <= a["ic95"][1], (motor, a)
        m = r["motores"][motor]["mos"]
        assert abs(m["media"] - v["mos"]) < 0.2 and m["ic95"][0] < m["media"] < m["ic95"][1]
    d = r["diferencia_mms_menos_espeak"]
    verdad = VERDAD["mms_vits"]["p_acierto"] - VERDAD["espeak_ng"]["p_acierto"]
    assert d["acierto_palabra"]["ic95"][0] <= verdad <= d["acierto_palabra"]["ic95"][1]
    assert d["acierto_palabra"]["ic95"][0] > 0 and d["mos"]["ic95"][0] > 0  # MMS claramente mejor
    assert d["cer_palabra"]["ic95"][1] < 0  # y con menos error de letras


def test_acuerdo_entre_oyentes_y_fiabilidad_de_los_repetidos(kit):
    r = _puntuar(kit, 30)
    alfa = r["acuerdo"]["alfa_krippendorff_ordinal_mos"]
    assert (
        isinstance(alfa, float) and 0.2 < alfa < 0.9
    )  # las dos voces difieren; hay acuerdo moderado
    assert 0.5 < r["acuerdo"]["acuerdo_medio_por_pares_aciertos"] <= 1
    f = r["fiabilidad_repetidos"]
    assert f["pares_mos"] > 0 and 0 <= f["diferencia_absoluta_media_mos"] < 2
    assert f["concordancia_aciertos"] > 0.6


def test_desglose_por_variante_marca_las_insuficientes(kit):
    r6 = _puntuar(kit, 6)  # 2 oyentes por variante
    assert all(v["insuficiente"] for v in r6["por_variante"].values())
    r30 = _puntuar(kit, 30)  # 10 por variante
    assert set(r30["por_variante"]) == {"asháninka", "ashéninka", "alto_perene"}
    assert not any(v["insuficiente"] for v in r30["por_variante"].values())


def test_un_solo_oyente_no_calcula_intervalos_ni_acuerdo(kit):
    r = _puntuar(kit, 1)
    a = r["motores"]["mms_vits"]["acierto_palabra"]
    assert a["ic95"] is None and a["media"] is not None and "nota" in a
    assert r["acuerdo"]["alfa_krippendorff_ordinal_mos"] == dz.NO_CALCULABLE
    assert any("un solo oyente" in w for w in r["advertencias"])


def test_filas_invalidas_se_ignoran_y_se_avisa(kit):
    _, _, clave = kit
    filas = simular_oyentes(clave, 3, 5)
    filas.append(
        {
            "oyente": "Pedro Perez con apellidos",
            "variante": "otra",
            "item": "i001",
            "transcripcion": "x",
            "mos": "3",
        }
    )
    filas.append(
        {"oyente": "O01", "variante": "otra", "item": "i999", "transcripcion": "x", "mos": "3"}
    )
    filas.append(
        {"oyente": "O01", "variante": "otra", "item": "i001", "transcripcion": "x", "mos": "9"}
    )  # MOS fuera de rango
    r = score.puntuar(clave, filas)
    assert r["n_oyentes"] == 3
    adv = " ".join(r["advertencias"])
    assert "identificador" in adv and "no están en la clave" in adv and "duplicadas" in adv


def test_sin_respuestas_validas_no_inventa_nada(kit):
    r = score.puntuar(kit[2], [])
    assert r["n_oyentes"] == 0 and "no hay respuestas válidas" in r["advertencias"]


def test_el_script_lee_los_csv_y_escribe_el_json(kit, tmp_path):
    salida, _, clave = kit
    ruta = tmp_path / "respuestas_sim.csv"
    filas = simular_oyentes(clave, 8, 3)
    with ruta.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)
    destino = tmp_path / "res.json"
    assert score.main([str(ruta), "--clave", str(salida / "clave.csv"), "--out", str(destino)]) == 0
    data = json.loads(destino.read_text(encoding="utf-8"))
    assert data["n_oyentes"] == 8 and "mms_vits" in data["motores"]
