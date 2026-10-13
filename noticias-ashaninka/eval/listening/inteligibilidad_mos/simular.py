"""Oyentes SIMULADOS con acierto y MOS verdaderos conocidos, para probar el kit de punta a punta.

NO es una medición: demuestra que ``build`` + hoja de respuestas + ``score`` recuperan valores
conocidos. La inteligibilidad y el MOS reales requieren a un hablante y siguen pendientes.
"""

from __future__ import annotations

import random

from eval.listening.inteligibilidad_mos import diseno as dz

VERDAD = {
    "mms_vits": {"p_acierto": 0.85, "mos": 3.6},
    "espeak_ng": {"p_acierto": 0.55, "mos": 2.2},
}
SD_OYENTE_ACIERTO = 0.05
SD_OYENTE_MOS = 0.3
SD_RUIDO_MOS = 0.8
VARIANTES_SIM = ("asháninka", "ashéninka", "alto_perene")


def _estropear(palabra: str, rng: random.Random) -> str:
    """Una palabra mal entendida: cambia una letra (así el CER por palabra no es 0 ni 1)."""
    i = rng.randrange(len(palabra))
    return palabra[:i] + rng.choice("xzqw") + palabra[i + 1 :]


def simular_oyentes(
    clave_rows: list[dict], n_oyentes: int, semilla: int, verdad: dict = VERDAD
) -> list[dict]:
    """Filas ``oyente,variante,item,transcripcion,mos,comentario`` de ``n_oyentes`` oyentes."""
    rng = random.Random(semilla)
    filas: list[dict] = []
    for k in range(n_oyentes):
        oyente = f"O{k + 1:02d}"
        variante = VARIANTES_SIM[k % len(VARIANTES_SIM)]
        dp = rng.gauss(0, SD_OYENTE_ACIERTO)
        dm = rng.gauss(0, SD_OYENTE_MOS)
        for r in clave_rows:
            v = verdad[r["motor"]]
            p = min(0.99, max(0.01, v["p_acierto"] + dp))
            palabras = [
                w if rng.random() < p else _estropear(w, rng) for w in r["claves"].split("|")
            ]
            mos = round(min(dz.MOS_MAX, max(dz.MOS_MIN, rng.gauss(v["mos"] + dm, SD_RUIDO_MOS))))
            filas.append(
                {
                    "oyente": oyente,
                    "variante": variante,
                    "item": r["item"],
                    "transcripcion": " ".join(["ya", *palabras]),
                    "mos": str(mos),
                    "comentario": "",
                }
            )
    return filas
