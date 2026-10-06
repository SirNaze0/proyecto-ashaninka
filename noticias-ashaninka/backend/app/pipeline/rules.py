"""Motor genérico de reescritura con reglas ordenadas y mapa de caracteres.

Lo usan la unificación ortográfica (2-0), la reescritura fonética (2d) y el
adaptador ortográfico del TTS (2e). Recorre el texto de izquierda a derecha; en
cada posición prueba las reglas en orden y aplica la primera que coincide
(el orden del archivo YAML es significativo: las reglas más específicas van
primero). Si ninguna coincide, copia el carácter.

Cada aplicación produce una entrada de mapa origen→destino, de modo que
siempre se puede volver del texto de destino al de origen.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.pipeline.types import CharMapEntry


@dataclass(frozen=True)
class RewriteRule:
    id: str
    pattern: str  # expresión regular; puede usar lookahead/lookbehind para el contexto
    replacement: str
    description: str = ""

    def compiled(self) -> re.Pattern[str]:
        return re.compile(self.pattern)


class RewriteEngine:
    def __init__(self, rules: list[RewriteRule]):
        self.rules = list(rules)
        self._compiled = [(r, r.compiled()) for r in self.rules]

    def apply(self, text: str) -> tuple[str, list[CharMapEntry]]:
        out: list[str] = []
        cmap: list[CharMapEntry] = []
        i = 0
        dst = 0
        n = len(text)
        while i < n:
            for rule, rx in self._compiled:
                m = rx.match(text, i)
                if m and m.end() > i:
                    rep = m.expand(rule.replacement)
                    out.append(rep)
                    cmap.append(CharMapEntry(i, m.end(), dst, dst + len(rep), rule.id))
                    dst += len(rep)
                    i = m.end()
                    break
            else:
                out.append(text[i])
                cmap.append(CharMapEntry(i, i + 1, dst, dst + 1, None))
                dst += 1
                i += 1
        return "".join(out), merge_identity(cmap)


def merge_identity(cmap: list[CharMapEntry]) -> list[CharMapEntry]:
    """Fusiona entradas de identidad contiguas para que el mapa sea compacto."""
    merged: list[CharMapEntry] = []
    for e in cmap:
        if (
            merged
            and e.rule_id is None
            and merged[-1].rule_id is None
            and merged[-1].src_end == e.src_start
            and merged[-1].dst_end == e.dst_start
        ):
            last = merged.pop()
            merged.append(CharMapEntry(last.src_start, e.src_end, last.dst_start, e.dst_end, None))
        else:
            merged.append(e)
    return merged


def check_map(cmap: list[CharMapEntry], src: str, dst: str) -> list[str]:
    """Verifica las propiedades del mapa. Devuelve la lista de problemas (vacía si es válido)."""
    problems = []
    pos_s, pos_d = 0, 0
    for e in cmap:
        if e.src_start != pos_s:
            problems.append(f"hueco o solape en origen en {pos_s}->{e.src_start}")
        if e.dst_start != pos_d:
            problems.append(f"hueco o solape en destino en {pos_d}->{e.dst_start}")
        pos_s, pos_d = e.src_end, e.dst_end
    if pos_s != len(src):
        problems.append(f"el origen no se cubre completo ({pos_s}/{len(src)})")
    if pos_d != len(dst):
        problems.append(f"el destino no se cubre completo ({pos_d}/{len(dst)})")
    return problems
