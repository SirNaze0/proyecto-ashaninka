"""Fase 5: cuadrado latino, instrumentos, privacidad y métricas de bloque (funciones puras)."""

from datetime import datetime, timedelta

import pytest
from app.experiment import export, instrumentos, latin
from app.experiment.privacy import columna_sospechosa, verificar_sin_pii

pytestmark = pytest.mark.smoke

COMPLETA = dict(
    comp_1=1,
    comp_2=0,
    comp_3=1,
    comp_4=1,
    esfuerzo=5,
    acep_facilidad=4,
    acep_agrado=3,
    acep_confianza=5,
)
FINAL = dict(
    variante="otra",
    edad_rango="30-44",
    alfabetizacion="lee_bien",
    familiaridad_tec="media",
    rank_C1=4,
    rank_C2=3,
    rank_C3=1,
    rank_C4=2,
)


# ------------------------------------------------------------------ cuadrado latino
def test_williams_es_latino_y_balancea_el_arrastre():
    filas = latin.WILLIAMS_4
    for k in range(4):  # cada condición una vez por fila y por columna
        assert sorted(f[k] for f in filas) == list(latin.CONDICIONES)
    for f in filas:
        assert sorted(f) == list(latin.CONDICIONES)
    transiciones = [(f[k], f[k + 1]) for f in filas for k in range(3)]
    assert len(set(transiciones)) == 12  # las 12 transiciones ordenadas A->B, una sola vez


@pytest.mark.parametrize("n", [16, 32, 48])
def test_balance_exacto_en_ciclos_de_16(n):
    b = latin.verificar_balance(n)
    assert b["condicion_x_posicion"] and b["condicion_x_noticia"] and b["noticia_x_posicion"]
    assert b["arrastre"]
    assert set(b["conteo_condicion_x_posicion"].values()) == {n // 4}


def test_cada_participante_ve_4_condiciones_y_4_noticias_distintas():
    for i in range(40):
        seq = latin.secuencia(i)
        assert sorted(b.condicion for b in seq) == list(latin.CONDICIONES)
        assert sorted(b.slot_noticia for b in seq) == [0, 1, 2, 3]
        assert [b.posicion for b in seq] == [0, 1, 2, 3]


def test_asignacion_determinista_y_periodica():
    assert latin.secuencia(6) == latin.secuencia(6)
    assert latin.secuencia(3) == latin.secuencia(19)  # el patrón se repite cada 16
    assert latin.secuencia(0) != latin.secuencia(4)  # misma fila, otra rotación de noticias
    with pytest.raises(ValueError):
        latin.secuencia(-1)


def test_codigo_de_participante():
    assert latin.indice_participante("P007") == 6
    assert latin.indice_participante(" p-007 ") == 6
    assert latin.normalizar_codigo("ab-0123") == "AB0123"
    for malo in ["", "7", "Pedro Perez", "P00", "P000", "P-12345", "juan@correo.com"]:
        with pytest.raises(ValueError):
            latin.indice_participante(malo)


# ------------------------------------------------------------------ instrumentos
def test_validar_post_noticia_ok_y_derivadas():
    r = instrumentos.validar("post_noticia", dict(COMPLETA))
    assert instrumentos.comprension(r) == 0.75
    assert instrumentos.aceptabilidad(r) == 4.0


@pytest.mark.parametrize(
    "cambio",
    [
        {"esfuerzo": 0},
        {"esfuerzo": 10},
        {"acep_agrado": 6},
        {"comp_1": 2},
        {"comp_2": True},
        {"esfuerzo": 5.5},
        {"extra": 1},
        {"esfuerzo": None},
    ],
)
def test_validar_rechaza_valores_invalidos(cambio):
    with pytest.raises(ValueError):
        instrumentos.validar("post_noticia", {**COMPLETA, **cambio})


def test_validar_final_ranking_y_pii():
    assert instrumentos.validar("final", dict(FINAL))["rank_C3"] == 1
    with pytest.raises(ValueError, match="ranking"):
        instrumentos.validar("final", {**FINAL, "rank_C1": 1})
    with pytest.raises(ValueError):
        instrumentos.validar("final", {**FINAL, "variante": "inventada"})
    for pii in ["escríbeme a juan@correo.com", "llama al 987 654 321", "mi dni 12345678"]:
        with pytest.raises(ValueError, match="datos personales"):
            instrumentos.validar("final", {**FINAL, "comentario": pii})
    ok = instrumentos.validar("final", {**FINAL, "comentario": "Me gustó la voz."})
    assert ok["comentario"] == "Me gustó la voz."


def test_cuestionarios_sin_texto_cni_inventado():
    # los ítems de comprensión son marcadores pendientes del hablante, no texto en asháninka
    comp = [i for i in instrumentos.items("post_noticia") if i["id"].startswith("comp_")]
    assert len(comp) == 4 and {i["status"] for i in comp} == {"PENDIENTE-HABLANTE"}


# ------------------------------------------------------------------ privacidad
def test_columnas_sospechosas():
    for c in ["nombre", "dni", "telefono_movil", "session_id", "edad", "user_agent", "ip", "lat"]:
        assert columna_sospechosa(c), c
    for c in ["participante", "edad_rango", "t_pantalla_ms", "alfabetizacion", "valor"]:
        assert not columna_sospechosa(c), c


def test_verificar_sin_pii_detecta_columnas_y_valores():
    limpio = {"t": [{"participante": "P001", "valor": "me gustó"}]}
    assert verificar_sin_pii(limpio) == []
    sucio = {"t": [{"participante": "P001", "valor": "juan@correo.com", "dni": "1"}]}
    assert len(verificar_sin_pii(sucio)) == 2
    uuid = {"t": [{"participante": "P001", "valor": "a3c1f0e2-1b2c-4d5e-8f90-123456789abc"}]}
    assert verificar_sin_pii(uuid)


# ------------------------------------------------------------------ métricas de bloque
T0 = datetime(2026, 10, 12, 10, 0, 0)


def _ev(tipo, seg, **payload):
    return (tipo, T0 + timedelta(seconds=seg), payload)


def test_metricas_de_bloque_con_pausa():
    ev = [
        _ev("block-start", 0),
        _ev("play", 1),
        _ev("segment-start", 1),
        _ev("segment-end", 5),
        _ev("segment-start", 5),
        _ev("pause", 7),  # 6 s de audio (1->7)
        _ev("play", 20),
        _ev("segment-end", 23),
        _ev("rate", 21, rate=1.25),
        _ev("repeat-paragraph", 22),
        _ev("block-end", 25, reason="completo"),  # el audio acabó en 23: 3 s más
    ]
    m = export.metricas_bloque(ev)
    assert m["t_pantalla_ms"] == 25_000
    assert m["t_escucha_ms"] == 6_000 + 3_000
    assert (m["pausas"], m["repeticiones"], m["cambios_velocidad"]) == (1, 1, 1)
    assert m["fin_completo"] and not m["degradacion_avatar"]


def test_metricas_c1_sin_audio_y_degradacion():
    c1 = export.metricas_bloque(
        [_ev("block-start", 0), _ev("read-done", 30), _ev("block-end", 31, reason="completo")]
    )
    assert c1["t_escucha_ms"] == 0 and c1["t_pantalla_ms"] == 31_000
    c4 = export.metricas_bloque([_ev("block-start", 0), _ev("degradacion", 3, reason="fps-bajos")])
    assert c4["degradacion_avatar"] == 1 and not c4["fin_completo"]


def test_recarga_a_mitad_de_bloque_no_duplica_tiempo():
    ev = [_ev("block-start", 0), _ev("block-start", 10), _ev("block-end", 20, reason="completo")]
    assert export.metricas_bloque(ev)["t_pantalla_ms"] == 20_000


def test_diccionario_cubre_todas_las_columnas_y_los_items():
    md = export.diccionario_md()
    for tabla, cols in export.COLUMNAS.items():
        assert f"`{tabla}.csv`" in md
        for c in cols:
            assert f"`{c[0]}`" in md
    for kind in instrumentos.KINDS:
        for it in instrumentos.items(kind):
            assert f"`{it['id']}`" in md
