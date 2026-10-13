"""Reglas y estadística del kit de escucha (5.7), sin modelos ni audio: se prueban solas.

Definido en ``docs/metrics.md`` («Fase 6», «Pruebas de escucha») ANTES de construir el kit:
- palabras clave = las 3 primeras palabras de 5 o más letras de la oración (regla fija);
- acierto = la palabra clave aparece entre las palabras escritas por el oyente, tras pasar ambas por
  ``typographic`` (minúsculas, sin tildes ni puntuación; la ñ se conserva);
- CER de palabra clave = distancia de edición mínima contra las palabras escritas / longitud;
- MOS de 1 a 5; ítems repetidos para la fiabilidad del propio oyente;
- alfa de Krippendorff para el acuerdo entre oyentes.
"""

from __future__ import annotations

import math
import random
import re
from collections import Counter, defaultdict
from collections.abc import Callable, Hashable, Sequence

from eval.fase1.mms_orthography.run import edit_distance, typographic

MOTORES = ("mms_vits", "espeak_ng")
N_CLAVE = 3
LARGO_MIN = 5
FRACCION_REPETIDOS = 0.10
VARIANTES = ("asháninka", "ashéninka", "alto_perene", "otra", "no_sabe")  # SUPUESTO-LING (P3)
MIN_OYENTES_VARIANTE = 3
B_BOOTSTRAP = 2000
SEMILLA_BOOTSTRAP = 20261012
MOS_MIN, MOS_MAX = 1, 5


# ------------------------------------------------------------------ palabras
def palabras(texto: str) -> list[str]:
    """Palabras comparables de un texto (minúsculas, sin tildes ni puntuación, ñ conservada)."""
    return [w for w in typographic(texto).split() if w]


def palabras_clave(canonico: str) -> list[str]:
    """Las 3 primeras palabras de 5 o más letras, sin cifras ni repetidas (regla fija)."""
    out: list[str] = []
    for w in palabras(canonico):
        if len(w) >= LARGO_MIN and not any(c.isdigit() for c in w) and w not in out:
            out.append(w)
        if len(out) == N_CLAVE:
            break
    return out


def acierta(clave: str, escritas: Sequence[str]) -> bool:
    return clave in escritas


def cer_palabra(clave: str, escritas: Sequence[str]) -> int:
    """Mínima distancia de edición entre la clave y alguna palabra escrita (len si no escribió)."""
    if not escritas:
        return len(clave)
    return min(edit_distance(clave, w) for w in escritas)


def evaluar_transcripcion(claves: Sequence[str], transcripcion: str) -> dict:
    """Aciertos y ediciones de una transcripción frente a las palabras clave del ítem."""
    escritas = palabras(transcripcion)
    hits = [acierta(c, escritas) for c in claves]
    ediciones = [0 if h else cer_palabra(c, escritas) for c, h in zip(claves, hits, strict=True)]
    return {
        "hits": hits,
        "palabras": len(claves),
        "aciertos": sum(hits),
        "ediciones": sum(ediciones),
        "letras": sum(len(c) for c in claves),
    }


# ------------------------------------------------------------------ diseño de la hoja
def elegir_oraciones(candidatas: list[dict], n: int, semilla: int) -> list[dict]:
    """Oraciones con al menos 3 palabras clave y de longitud moderada, en orden aleatorio fijo."""
    buenas = [
        c
        for c in candidatas
        if 20 <= len(c["canonical"]) <= 140 and len(palabras_clave(c["canonical"])) == N_CLAVE
    ]
    random.Random(semilla).shuffle(buenas)
    return buenas[:n]


def ordenar_items(items: list[dict], semilla: int) -> list[dict]:
    """Orden aleatorio fijo que evita presentar la misma oración (con distinto motor) seguida."""
    rng = random.Random(semilla)
    mejor = list(items)
    for _ in range(200):
        rng.shuffle(mejor)
        if all(a["oracion"] != b["oracion"] for a, b in zip(mejor, mejor[1:], strict=False)):
            break
    return mejor


def elegir_repetidos(items: list[dict], semilla: int) -> list[dict]:
    """El 10 % de los ítems se repite más adelante (mínimo 10 puestos después del original)."""
    n = max(2, math.ceil(FRACCION_REPETIDOS * len(items)))
    rng = random.Random(semilla + 1)
    return rng.sample(items, min(n, len(items)))


def insertar_repetidos(orden: list[dict], repetidos: list[dict], semilla: int) -> list[dict]:
    rng = random.Random(semilla + 2)
    out = list(orden)
    for r in repetidos:
        pos_orig = next(i for i, it in enumerate(out) if it["id"] == r["id"])
        lo = min(pos_orig + 10, len(out))
        out.insert(rng.randint(lo, len(out)), r["copia"])
    return out


# ------------------------------------------------------------------ estadística
def media(xs: Sequence[float]) -> float | None:
    return sum(xs) / len(xs) if xs else None


def percentil(xs: Sequence[float], q: float) -> float:
    s = sorted(xs)
    k = (len(s) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def bootstrap_oyentes(
    por_oyente: dict[str, float], b: int = B_BOOTSTRAP, semilla: int = SEMILLA_BOOTSTRAP
) -> dict | None:
    """IC 95 % percentil de la media remuestreando OYENTES. ``None`` con menos de 2 oyentes."""
    vals = [v for v in por_oyente.values() if v is not None]
    if len(vals) < 2:
        return None
    rng = random.Random(semilla)
    n = len(vals)
    medias = [sum(vals[rng.randrange(n)] for _ in range(n)) / n for _ in range(b)]
    m = sum(vals) / n
    # p bilateral del bootstrap contra 0 (útil para diferencias pareadas)
    p = min(1.0, 2 * min(sum(x <= 0 for x in medias), sum(x >= 0 for x in medias)) / b)
    return {
        "media": m,
        "ic95": [percentil(medias, 0.025), percentil(medias, 0.975)],
        "p_bootstrap": p,
        "n_oyentes": n,
    }


def krippendorff_alpha(
    unidades: dict[Hashable, list[float]],
    metrica: str = "ordinal",
    categorias: Sequence[float] = tuple(range(MOS_MIN, MOS_MAX + 1)),
) -> float | None:
    """Alfa de Krippendorff (matriz de coincidencias). ``unidades``: valores de cada unidad (un
    valor por oyente que la calificó). ``None`` si no hay al menos 2 valores en alguna unidad o
    si todos los valores son iguales (alfa indefinido)."""
    o: dict[tuple, float] = defaultdict(float)
    for vals in unidades.values():
        m = len(vals)
        if m < 2:
            continue
        for i in range(m):
            for j in range(m):
                if i != j:
                    o[(vals[i], vals[j])] += 1.0 / (m - 1)
    n_c: Counter = Counter()
    for (c, _k), v in o.items():
        n_c[c] += v
    n = sum(n_c.values())
    if n <= 1:
        return None
    cats = [c for c in categorias if n_c.get(c, 0) > 0] or list(categorias)

    def delta2(c, k) -> float:
        if c == k:
            return 0.0
        if metrica == "nominal":
            return 1.0
        if metrica == "intervalo":
            return float((c - k) ** 2)
        lo, hi = min(c, k), max(c, k)  # ordinal
        s = (
            sum(n_c.get(g, 0.0) for g in cats if lo <= g <= hi)
            - (n_c.get(c, 0) + n_c.get(k, 0)) / 2
        )
        return s * s

    d_o = sum(v * delta2(c, k) for (c, k), v in o.items()) / n
    d_e = sum(n_c.get(c, 0) * n_c.get(k, 0) * delta2(c, k) for c in cats for k in cats) / (
        n * (n - 1)
    )
    if d_e == 0:
        return None
    return 1.0 - d_o / d_e


def acuerdo_medio_por_pares(unidades: dict[Hashable, dict[str, bool]]) -> float | None:
    """Proporción media de coincidencia entre pares de oyentes sobre las mismas unidades."""
    iguales = total = 0
    for votos in unidades.values():
        v = list(votos.values())
        for i in range(len(v)):
            for j in range(i + 1, len(v)):
                total += 1
                iguales += v[i] == v[j]
    return iguales / total if total else None


def agrupar(items: Sequence, clave: Callable) -> dict:
    out: dict = defaultdict(list)
    for it in items:
        out[clave(it)].append(it)
    return out


def limpiar_variante(v: str | None) -> str:
    v = (v or "").strip()
    return v if v in VARIANTES else "no_sabe"


NO_CALCULABLE = "no_calculable (menos de 2 oyentes)"
RE_ID = re.compile(
    r"^[A-Za-z0-9_-]{1,40}$"
)  # el identificador del oyente no puede ser un nombre libre largo
