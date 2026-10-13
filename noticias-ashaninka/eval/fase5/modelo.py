"""Modelo generativo DECLARADO de la simulación sintética (Fase 5).

No es un resultado científico: define efectos verdaderos conocidos para comprobar que la
exportación y el análisis los recuperan (``docs/metrics.md``, «Criterios de la simulación»). Los
valores son supuestos de prueba, fijados antes de ejecutar y sin ajustarlos a ningún resultado.

Comprensión de un bloque = media de 4 ítems Bernoulli con probabilidad
``p = base + efecto(condición) + efecto(posición) + efecto(noticia) + efecto(alfabetización) + u``,
con ``u ~ N(0, sd_participante)`` (intercepto aleatorio) y ``p`` acotada a [0,02; 0,98].
"""

from __future__ import annotations

import copy
from typing import Any

import numpy as np
import pandas as pd
from app.experiment import latin

CONDS = latin.CONDICIONES
SEMILLA = 20261012  # fecha de la sesión; fija y declarada antes de ejecutar

PARAMETROS: dict[str, Any] = {
    "base": 0.50,
    "efecto_cond": {"C1": 0.00, "C2": 0.05, "C3": 0.15, "C4": 0.17},
    "efecto_orden": [0.00, 0.02, 0.04, 0.06],  # aprendizaje por posición
    "efecto_noticia": [0.00, 0.03, -0.03, 0.02],
    "efecto_alfabetizacion": {"no_lee": -0.05, "lee_con_dificultad": -0.02, "lee_bien": 0.0},
    "alfabetizacion_probs": {"no_lee": 0.25, "lee_con_dificultad": 0.35, "lee_bien": 0.40},
    "sd_participante": 0.08,
    "p_abandono": 0.06,
    "p_degradacion_c4": 0.10,
    "esfuerzo": {
        "base": 5.5,
        "C1": 0.0,
        "C2": -0.3,
        "C3": -0.8,
        "C4": -1.0,
        "sd_part": 0.7,
        "sd": 0.8,
    },
    "aceptabilidad": {
        "base": 3.2,
        "C1": 0.0,
        "C2": 0.1,
        "C3": 0.4,
        "C4": 0.7,
        "sd_part": 0.4,
        "sd": 0.7,
    },
}

VARIANTES = ["asháninka", "ashéninka", "alto_perene", "otra", "no_sabe"]
VARIANTES_P = [0.35, 0.25, 0.25, 0.10, 0.05]
EDADES = ["18-29", "30-44", "45-59", "60+"]
FAMILIARIDAD = ["ninguna", "poca", "media", "alta"]
CONTRASTES = (("C2", "C1"), ("C3", "C2"), ("C4", "C3"))


def con_efecto_c3(params: dict, delta: float) -> dict:
    """Copia de ``params`` con un efecto de C3 sobre C1 de ``delta`` (análisis de potencia)."""
    p = copy.deepcopy(params)
    p["efecto_cond"] = {"C1": 0.0, "C2": 0.0, "C3": delta, "C4": delta}
    return p


def contrastes_verdaderos(params: dict = PARAMETROS) -> dict[str, float]:
    e = params["efecto_cond"]
    return {f"{a}-{b}": round(e[a] - e[b], 6) for a, b in CONTRASTES}


def generar(n: int, seed: int = SEMILLA, params: dict = PARAMETROS) -> list[dict]:
    """Participantes sintéticos con todo lo que luego se envía por la API (o se tabula directo)."""
    rng = np.random.default_rng(seed)
    alf_k = list(params["alfabetizacion_probs"])
    alf_p = list(params["alfabetizacion_probs"].values())
    out: list[dict] = []
    for i in range(n):
        u = rng.normal(0, params["sd_participante"])
        u_esf = rng.normal(0, params["esfuerzo"]["sd_part"])
        u_ace = rng.normal(0, params["aceptabilidad"]["sd_part"])
        alfa = str(rng.choice(alf_k, p=alf_p))
        abandona_en = int(rng.integers(0, 4)) if rng.random() < params["p_abandono"] else None
        bloques: list[dict] = []
        for b in latin.secuencia(i):
            if abandona_en is not None and b.posicion >= abandona_en:
                break
            c = b.condicion
            p = (
                params["base"]
                + params["efecto_cond"][c]
                + params["efecto_orden"][b.posicion]
                + params["efecto_noticia"][b.slot_noticia]
                + params["efecto_alfabetizacion"][alfa]
                + u
            )
            p = float(np.clip(p, 0.02, 0.98))
            audio = c != "C1"
            e, a = params["esfuerzo"], params["aceptabilidad"]
            bloques.append(
                {
                    "posicion": b.posicion,
                    "condicion": c,
                    "slot_noticia": b.slot_noticia,
                    "comp": [int(x) for x in (rng.random(4) < p)],
                    "esfuerzo": int(
                        np.clip(round(e["base"] + e[c] + u_esf + rng.normal(0, e["sd"])), 1, 9)
                    ),
                    "acep": [
                        int(np.clip(round(a["base"] + a[c] + u_ace + rng.normal(0, a["sd"])), 1, 5))
                        for _ in range(3)
                    ],
                    "degradacion": bool(c == "C4" and rng.random() < params["p_degradacion_c4"]),
                    "repeticiones": int(rng.poisson(0.3)) if audio else 0,
                    "pausas": int(rng.poisson(0.6)) if audio else 0,
                    "cambios_velocidad": int(rng.poisson(0.2)) if audio else 0,
                    "t_total_s": float(
                        max(10.0, rng.normal(60, 10) if not audio else rng.normal(45, 5))
                    ),
                }
            )
        final = None
        if abandona_en is None:
            # ranking de preferencia: depende de la aceptabilidad media de cada condición + ruido
            media = {x["condicion"]: np.mean(x["acep"]) + rng.normal(0, 0.3) for x in bloques}
            orden = sorted(CONDS, key=lambda c: -media[c])
            final = {
                "variante": str(rng.choice(VARIANTES, p=VARIANTES_P)),
                "edad_rango": str(rng.choice(EDADES)),
                "alfabetizacion": alfa,
                "familiaridad_tec": str(rng.choice(FAMILIARIDAD)),
                **{f"rank_{c}": orden.index(c) + 1 for c in CONDS},
            }
        out.append(
            {
                "codigo": f"P{i + 1:03d}",
                "indice": i,
                "alfabetizacion": alfa,
                "abandona_en": abandona_en,
                "bloques": bloques,
                "final": final,
            }
        )
    return out


def a_dataframe(participantes: list[dict]) -> pd.DataFrame:
    """Tabla equivalente a ``bloques.csv`` (para las réplicas rápidas sin pasar por la API)."""
    filas = []
    for p in participantes:
        completos = len(p["bloques"]) == 4 and p["final"] is not None
        for b in p["bloques"]:
            filas.append(
                {
                    "participante": p["codigo"],
                    "piloto": 1,
                    "posicion": b["posicion"],
                    "condicion": b["condicion"],
                    "slot_noticia": b["slot_noticia"],
                    "bloqueados_prop": 0.0,
                    "degradacion_avatar": int(b["degradacion"]),
                    "completado": int(completos),
                    "comprension": sum(b["comp"]) / 4,
                    "esfuerzo": b["esfuerzo"],
                    "aceptabilidad": sum(b["acep"]) / 3,
                    "alfabetizacion": p["alfabetizacion"],
                }
            )
    return pd.DataFrame(filas)
