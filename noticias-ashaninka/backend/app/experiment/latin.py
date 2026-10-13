"""Asignación experimental: cuadrado latino de Williams 4×4 y rotación de noticias.

Definido en ``docs/metrics.md`` (sección «Fase 5») antes de cualquier medición. Funciones puras y
deterministas: el mismo código de participante produce siempre la misma secuencia, sin estado.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import asdict, dataclass

CONDICIONES = ("C1", "C2", "C3", "C4")

# Williams 4×4: cada transición ordenada A→B aparece exactamente una vez (balance de arrastre)
WILLIAMS_4: tuple[tuple[str, ...], ...] = (
    ("C1", "C2", "C4", "C3"),
    ("C2", "C3", "C1", "C4"),
    ("C3", "C4", "C2", "C1"),
    ("C4", "C1", "C3", "C2"),
)
N_BLOQUES = 4
CICLO = 16  # el patrón completo (condición × noticia × posición) se repite cada 16 participantes

# Código anónimo: 1–3 letras, guion opcional y 3–4 dígitos (P007, AB-0123). Sin datos personales.
_CODIGO = re.compile(r"^([A-Z]{1,3})-?(\d{3,4})$")


@dataclass(frozen=True)
class Bloque:
    posicion: int  # 0..3
    condicion: str  # C1..C4
    slot_noticia: int  # 0..3: índice dentro del conjunto fijo de 4 noticias


def normalizar_codigo(codigo: str) -> str:
    """Devuelve el código en forma canónica (mayúsculas, sin guion) o lanza ``ValueError``."""
    m = _CODIGO.match(codigo.strip().upper())
    if not m:
        raise ValueError("código de participante inválido: use p. ej. P007 (letras y 3-4 dígitos)")
    return f"{m.group(1)}{m.group(2)}"


def indice_participante(codigo: str) -> int:
    """``P007`` -> 6: el número del código menos 1 (el primer participante es el 001)."""
    m = _CODIGO.match(normalizar_codigo(codigo))
    assert m is not None
    n = int(m.group(2))
    if n < 1:
        raise ValueError("el número del código debe ser ≥ 001")
    return n - 1


def secuencia(indice: int) -> list[Bloque]:
    """Secuencia de 4 bloques del participante ``indice`` (0, 1, 2…)."""
    if indice < 0:
        raise ValueError("el índice del participante no puede ser negativo")
    fila = WILLIAMS_4[indice % 4]
    desplazamiento = (indice // 4) % 4
    return [Bloque(k, fila[k], (k + desplazamiento) % N_BLOQUES) for k in range(N_BLOQUES)]


def secuencia_json(indice: int) -> list[dict]:
    return [asdict(b) for b in secuencia(indice)]


def verificar_balance(n: int) -> dict:
    """Cuenta los pares y transiciones de ``n`` participantes consecutivos (0..n-1).

    Con ``n`` múltiplo de 16 todos los conteos deben ser iguales (balance exacto).
    """
    cond_pos: Counter = Counter()
    cond_news: Counter = Counter()
    news_pos: Counter = Counter()
    trans: Counter = Counter()
    for i in range(n):
        seq = secuencia(i)
        for b in seq:
            cond_pos[(b.condicion, b.posicion)] += 1
            cond_news[(b.condicion, b.slot_noticia)] += 1
            news_pos[(b.slot_noticia, b.posicion)] += 1
        for a, b in zip(seq, seq[1:], strict=False):
            trans[(a.condicion, b.condicion)] += 1

    def parejo(c: Counter, esperados: int) -> bool:
        return len(c) == esperados and len(set(c.values())) == 1

    exacto = n > 0 and n % CICLO == 0
    return {
        "n": n,
        "ciclo_completo": exacto,
        "condicion_x_posicion": parejo(cond_pos, 16) if exacto else None,
        "condicion_x_noticia": parejo(cond_news, 16) if exacto else None,
        "noticia_x_posicion": parejo(news_pos, 16) if exacto else None,
        "arrastre": parejo(trans, 12) if n % 4 == 0 and n > 0 else None,
        "conteo_condicion_x_posicion": {f"{c}@{p}": v for (c, p), v in sorted(cond_pos.items())},
    }
