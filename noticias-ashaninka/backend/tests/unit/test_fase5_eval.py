"""Fase 5: simulación sintética, análisis estadístico y consolidación (eval/fase5)."""

import pytest

pytest.importorskip("pandas")
pytest.importorskip("statsmodels")
pytest.importorskip("scipy")

from app.experiment import export, latin  # noqa: E402

from eval.fase5 import analysis, modelo, power, run  # noqa: E402
from eval.fase5.simulate import simular  # noqa: E402

pytestmark = pytest.mark.eval


def test_generador_determinista_y_sigue_la_asignacion():
    a, b = modelo.generar(20, 7), modelo.generar(20, 7)
    assert a == b
    assert modelo.generar(20, 8) != a
    for p in a:
        esperado = latin.secuencia(p["indice"])
        for blq in p["bloques"]:
            assert blq["condicion"] == esperado[blq["posicion"]].condicion
            assert blq["slot_noticia"] == esperado[blq["posicion"]].slot_noticia
        assert (p["final"] is None) == (p["abandona_en"] is not None)
        if p["final"]:
            assert sorted(p["final"][f"rank_{c}"] for c in latin.CONDICIONES) == [1, 2, 3, 4]


def test_contrastes_verdaderos():
    assert modelo.contrastes_verdaderos() == {"C2-C1": 0.05, "C3-C2": 0.10, "C4-C3": 0.02}


def test_preparar_aplica_las_exclusiones_fijadas_de_antemano():
    df = modelo.a_dataframe(modelo.generar(40, 3))
    sin = analysis.preparar(df, incluir_piloto=False)[0]
    assert sin.empty  # la simulación es piloto: nunca entra en el análisis confirmatorio
    con, resumen = analysis.preparar(df, incluir_piloto=True)
    assert resumen["excluidos_menos_de_4_bloques"]  # con semilla 3 hay abandonos
    assert con.groupby("participante")["completado"].sum().eq(4).all()
    assert resumen["participantes_analizados"] == con["participante"].nunique()


def test_el_modelo_mixto_recupera_los_efectos_con_muestra_grande():
    df = modelo.a_dataframe(modelo.generar(300, 11))
    res = analysis.analizar(df, incluir_piloto=True, completo=False)
    ver = modelo.contrastes_verdaderos()
    assert res["primario"]["converge"]
    for c in res["primario"]["contrastes"]:
        assert abs(c["estimado"] - ver[c["contraste"]]) < 3.5 * c["ee"], c
        assert c["p_holm"] >= c["p"] - 1e-12  # Holm nunca baja un p
    c32 = {c["contraste"]: c for c in res["primario"]["contrastes"]}
    assert c32["C3-C2"]["p_holm"] < 0.05  # el efecto de 0,10 es detectable con 300 participantes


def test_no_parametricos_y_bootstrap_son_reproducibles():
    df = analysis.preparar(modelo.a_dataframe(modelo.generar(60, 5)), incluir_piloto=True)[0]
    npar = analysis.no_parametricos(df)
    for var in analysis.VARIABLES:
        assert npar[var]["friedman"]["p"] < 0.05  # el esfuerzo y la aceptabilidad difieren mucho
        assert len(npar[var]["wilcoxon"]) == 3
    assert analysis.bootstrap(df, b=300) == analysis.bootstrap(df, b=300)
    boot = analysis.bootstrap(df, b=300)["comprension"]
    for fila in boot:
        assert fila["ic95"][0] <= fila["dif_media"] <= fila["ic95"][1]


def test_la_potencia_crece_con_n():
    pot = power.potencia(rejilla=(16, 64), replicas=12)
    p16, p64 = (f["potencia"] for f in pot["curva"])
    assert p64 >= p16
    assert pot["delta_c3_c1"] == pytest.approx(0.5 * pot["sd_bloque"])
    assert 0.2 < pot["sd_bloque"] < 0.35


def test_simulacion_por_la_api_real_y_exportacion_coincide_con_la_verdad(tmp_path, monkeypatch):
    monkeypatch.setenv("NA_EXPERIMENT_PILOTO", "false")  # simular() lo fuerza y luego lo restaura
    sim = simular(10, modelo.SEMILLA, out=tmp_path / "x")
    import os

    assert os.environ["NA_EXPERIMENT_PILOTO"] == "false"
    assert sim["sesiones_creadas"] == 10 and sim["sesion_repetida_idempotente"]
    assert sim["eventos_nuevos_en_reenvio"] == 0 and sim["respuestas_nuevas_en_reenvio"] == 0
    ver = run.verificar_exportacion(tmp_path / "x", sim, 10, modelo.SEMILLA)
    assert ver["filas_ok"] and ver["bloques_con_valores_distintos"] == 0
    assert max(ver["peor_diferencia_ms"].values()) <= run.TOLERANCIA_MS
    priv = run.verificar_privacidad(tmp_path / "x")
    assert priv["problemas"] == [] and priv["control_negativo_detectado"]
    dic = run.verificar_diccionario(tmp_path / "x")
    assert dic["cobertura"] == 1.0


def test_el_diccionario_de_datos_publicado_esta_al_dia():
    publicado = (run.ROOT / "data" / "DATA_DICTIONARY.md").read_text(encoding="utf-8")
    assert publicado.replace("\r\n", "\n") == export.diccionario_md().replace("\r\n", "\n"), (
        "regenerar con: uv run python -m app.cli experiment dictionary"
    )


def test_los_criterios_pendientes_dependen_de_personas_y_no_se_inventan():
    d = {
        "balance": run.balance(),
        "simulacion": {
            "eventos_nuevos_en_reenvio": 0,
            "respuestas_nuevas_en_reenvio": 0,
            "sesion_repetida_idempotente": True,
        },
        "verificacion_exportacion": {
            "filas_exportadas": {},
            "filas_ok": True,
            "bloques_con_valores_distintos": 0,
            "peor_diferencia_ms": {"t_escucha_ms": 1, "t_pantalla_ms": 0},
        },
        "privacidad": {"problemas": [], "control_negativo_detectado": True},
        "diccionario": {
            "cobertura": 1.0,
            "total": 3,
            "archivo_al_dia": True,
            "columnas": {"x": {"coinciden": True}},
        },
        "analisis": {
            "primario": {
                "converge": True,
                "contrastes": [
                    {"contraste": k, "ic95": [v - 1, v + 1]}
                    for k, v in modelo.contrastes_verdaderos().items()
                ],
            }
        },
        "recuperacion": {
            "replicas": 200,
            "verdaderos": modelo.contrastes_verdaderos(),
            "cobertura_ic95": {"a": 0.95, "b": 0.93, "c": 0.97},
        },
        "potencia": {"meta_potencia": 0.8, "d": 0.5, "n_minimo": 40},
        "paquete": None,
        "pruebas": {},
    }
    c = run.criterios(d)
    auto = [
        "balance_williams",
        "idempotencia",
        "exportacion_sin_errores",
        "tiempos_exportados",
        "privacidad",
        "diccionario_100pct",
        "recuperacion_un_ajuste",
        "cobertura_replicas",
        "potencia",
    ]
    assert all(c[k]["cumple"] is True for k in auto)
    for k in [
        "consentimiento_comite",
        "items_comprension_hablante",
        "noticias_revisadas_p4",
        "piloto_con_personas",
        "escucha_mos_inteligibilidad",
        "carga_inicial",
        "pruebas_e2e",
    ]:
        assert c[k]["cumple"] == "pendiente", k
    # un fallo se detecta
    d["recuperacion"]["cobertura_ic95"]["b"] = 0.80
    d["simulacion"]["eventos_nuevos_en_reenvio"] = 3
    c = run.criterios(d)
    assert c["cobertura_replicas"]["cumple"] is False and c["idempotencia"]["cumple"] is False
