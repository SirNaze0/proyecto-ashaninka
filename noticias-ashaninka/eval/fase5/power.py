"""Potencia y cobertura por simulación, sobre el MISMO modelo de análisis (``analysis.py``).

- ``potencia``: para cada N, proporción de réplicas en que el contraste C3−C1 del modelo mixto es
  significativo (α = 0,05, bilateral) con un efecto de d = 0,5 (en desviaciones típicas de la
  comprensión de un bloque). Devuelve el N mínimo de la rejilla con potencia ≥ 0,80.
- ``cobertura``: con los efectos de ``modelo.PARAMETROS``, proporción de réplicas en que el IC 95 %
  de cada contraste contiene su valor verdadero (recuperación de parámetros; esperada ≈ 0,95).

La rejilla, las réplicas y las semillas están declaradas aquí, antes de ejecutar.
"""

from __future__ import annotations

import argparse
import json
import warnings

import numpy as np

from eval.fase5 import analysis
from eval.fase5.modelo import (
    CONTRASTES,
    PARAMETROS,
    SEMILLA,
    a_dataframe,
    con_efecto_c3,
    contrastes_verdaderos,
    generar,
)

REJILLA_N = (16, 24, 32, 48, 64, 96, 128)
REPLICAS = 200
D_OBJETIVO = 0.5
POTENCIA_META = 0.80
ALFA = 0.05


def sd_bloque(params: dict = PARAMETROS) -> float:
    """Desviación típica de la comprensión de un bloque (sin efectos de condición), con N grande."""
    sin_efectos = con_efecto_c3(params, 0.0)
    df = a_dataframe(generar(4000, SEMILLA, sin_efectos))
    return float(df["comprension"].std())


def _replica(n: int, seed: int, params: dict):
    df, _ = analysis.preparar(a_dataframe(generar(n, seed, params)), incluir_piloto=True)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = analysis.ajustar(df)
    nombre = 'C(condicion, Treatment("C1"))[T.C3]'
    return res, float(res.pvalues[nombre]), analysis.contrastes_mixto(res)


def potencia(rejilla=REJILLA_N, replicas: int = REPLICAS, d: float = D_OBJETIVO) -> dict:
    sd = sd_bloque()
    delta = d * sd
    params = con_efecto_c3(PARAMETROS, delta)
    filas = []
    for n in rejilla:
        sig = fallos = 0
        for r in range(replicas):
            try:
                _, p, _ = _replica(n, SEMILLA + 7919 * n + r, params)
            except Exception:
                fallos += 1
                continue
            sig += p < ALFA
        validas = replicas - fallos
        filas.append({"n": n, "potencia": sig / validas if validas else None, "fallos": fallos})
    minimo = next(
        (f["n"] for f in filas if f["potencia"] is not None and f["potencia"] >= POTENCIA_META),
        None,
    )
    return {
        "d": d,
        "sd_bloque": sd,
        "delta_c3_c1": delta,
        "alfa": ALFA,
        "replicas": replicas,
        "meta_potencia": POTENCIA_META,
        "curva": filas,
        "n_minimo": minimo,
        "nota": f"con abandono simulado (p = {PARAMETROS['p_abandono']:.2f}) y el mismo modelo "
        "del análisis primario",
    }


def cobertura(n: int = 32, replicas: int = REPLICAS) -> dict:
    verdaderos = contrastes_verdaderos()
    dentro = {k: 0 for k in verdaderos}
    sesgo = {k: [] for k in verdaderos}
    fallos = 0
    for r in range(replicas):
        try:
            _, _, cs = _replica(n, SEMILLA + 104729 + r, PARAMETROS)
        except Exception:
            fallos += 1
            continue
        for c in cs:
            lo, hi = c["ic95"]
            dentro[c["contraste"]] += lo <= verdaderos[c["contraste"]] <= hi
            sesgo[c["contraste"]].append(c["estimado"] - verdaderos[c["contraste"]])
    validas = replicas - fallos
    return {
        "n": n,
        "replicas": replicas,
        "fallos": fallos,
        "verdaderos": verdaderos,
        "cobertura_ic95": {k: v / validas for k, v in dentro.items()},
        "sesgo_medio": {k: float(np.mean(v)) for k, v in sesgo.items()},
        "contrastes": [f"{a}-{b}" for a, b in CONTRASTES],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--replicas", type=int, default=REPLICAS)
    a = ap.parse_args()
    print(
        json.dumps(
            {
                "potencia": potencia(replicas=a.replicas),
                "cobertura": cobertura(replicas=a.replicas),
            },
            indent=1,
        )
    )


if __name__ == "__main__":
    main()
