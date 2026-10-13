"""Consolidación de la evaluación de la Fase 4: los criterios se deciden con reglas fijas."""

import pytest

from eval.fase4 import bundle, run


def _stats(p50=1.0, p95=2.0):
    return {
        "n": 10,
        "media": 1,
        "de": 0.1,
        "min": 0,
        "p50": p50,
        "p95": p95,
        "p99": p95,
        "max": p95,
    }


def _datos(ttfa_p95=80.0, desfase_p95=16.0, cobertura=100.0, carga_mb=0.12):
    perfil = {
        "frio": _stats(p95=ttfa_p95),
        "caliente": _stats(),
        "arranque_completo_frio": _stats(p95=900),
        "arranque_completo_caliente": _stats(),
    }
    caso = {
        "noticias": 30,
        "completas": 30,
        "huecos_ms": _stats(p50=2, p95=5),
        "desfase_resaltado_ms": {**_stats(), "abs_p95": desfase_p95, "abs_max": desfase_p95 + 1},
        "cobertura_pct": cobertura,
    }
    return {
        "carga": {"resumen": {c: {"inicial_max_mb": carga_mb} for c in ("C1", "C2", "C3", "C4")}},
        "ttfa": {"resultados": {"sin-limite": perfil, "movil-4x-4g": perfil}},
        "reproduccion": {"C3/sin-limite": caso, "C4/movil-4x-4g": caso},
    }


def test_todo_cumple_con_los_valores_medidos():
    c = run.criterios(_datos())
    for k in (
        "carga_inicial_menor_3mb",
        "ttfa_p95_menor_2s_por_lotes",
        "desfase_resaltado_p95_le_80ms",
        "cobertura_resaltado_100",
        "hueco_entre_segmentos",
        "reproduccion_completa",
    ):
        assert c[k]["cumple"] is True, k


@pytest.mark.parametrize(
    ("campo", "valor", "criterio"),
    [
        ("ttfa_p95", 2500.0, "ttfa_p95_menor_2s_por_lotes"),
        ("desfase_p95", 95.0, "desfase_resaltado_p95_le_80ms"),
        ("cobertura", 97.0, "cobertura_resaltado_100"),
        ("carga_mb", 3.2, "carga_inicial_menor_3mb"),
    ],
)
def test_un_incumplimiento_se_reporta_como_falso(campo, valor, criterio):
    c = run.criterios(_datos(**{campo: valor}))
    assert c[criterio]["cumple"] is False


def test_lo_que_no_se_midio_queda_pendiente_y_android_siempre_pendiente():
    c = run.criterios({})
    assert "ttfa_p95_menor_2s_por_lotes" not in c  # no se inventa un valor
    assert c["android_gama_media_real"]["cumple"] == "pendiente"


def test_degradacion_exige_los_tres_casos():
    caso = lambda n, modo, razon: {  # noqa: E731
        "nombre": n,
        "modo": modo,
        "eventos": [{"tipo": "degradacion" if razon else "avatar-ok", "razon": razon, "fps": 1}],
    }
    ok = {
        "casos": [
            caso("A-sin-webgl", "fijo", "sin-webgl"),
            caso("B-cpu-20x-software", "fijo", "fps-bajos"),
            caso("C-normal-gpu", "avatar", None),
        ]
    }
    assert run.criterios({"degradacion": ok})["degradacion_probada"]["cumple"] is True
    mal = {"casos": [caso("A-sin-webgl", "avatar", None), *ok["casos"][1:]]}
    assert run.criterios({"degradacion": mal})["degradacion_probada"]["cumple"] is False


def test_cola_de_eventos_con_duplicados_no_cumple():
    base = {"entregados_pct": 100, "nuevos_al_reenviar": 0, "pendientes_al_volver": 0}
    assert run.criterios({"eventos": base})["cola_de_eventos"]["cumple"] is True
    assert (
        run.criterios({"eventos": {**base, "nuevos_al_reenviar": 2}})["cola_de_eventos"]["cumple"]
        is False
    )


def test_estatico_recorre_solo_las_importaciones_estaticas():
    m = {
        "index.html": {
            "file": "a.js",
            "isEntry": True,
            "imports": ["_h.js"],
            "css": ["a.css"],
            "dynamicImports": ["avatar.js"],
        },
        "_h.js": {"file": "h.js"},
        "avatar.js": {"file": "avatar.js", "imports": ["three.js"]},
        "three.js": {"file": "three.js"},
    }
    assert bundle.estatico(m, "index.html", set()) == {"a.js", "a.css", "h.js"}
