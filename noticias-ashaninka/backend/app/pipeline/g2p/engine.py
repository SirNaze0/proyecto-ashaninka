"""G2P basado en reglas sobre la ortografía CANÓNICA (tarea 1.6).

Algoritmo, por palabra y de izquierda a derecha:

1. se prueban las reglas de contexto de ``cni.yaml`` en orden (regex anclada en la posición);
2. si ninguna aplica, se busca en el inventario el grafema más largo que coincide
   (los dígrafos ganan a las letras sueltas);
3. si nada coincide, el carácter va a ``unknown`` y se sigue (no se lanza excepción).

Cada fonema emitido guarda su ``char_span`` (qué caracteres de la palabra lo produjeron): la
Fase 3 lo usa para agrupar las duraciones de VITS por fonema.

Mientras el inventario no esté validado (``phoneme: null``) se emite la etiqueta ``<grafema>``:
es una segmentación grafémica explícita, no una transcripción fonémica.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from app.config import G2P_RULES
from app.pipeline.resources import Resource, get_resource
from app.pipeline.types import G2PResult, PhonemizedWord, Unresolved

WORD_RX = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)?")


@dataclass(frozen=True)
class _ContextRule:
    id: str
    rx: re.Pattern[str]
    phonemes: list[str]


class G2P:
    def __init__(self, inventory: Resource, context_rules: Resource, allow_candidates: bool = True):
        # El inventario candidato se usa por defecto para segmentar; las etiquetas lo hacen visible.
        self.units: dict[str, tuple[str, str]] = {}
        for e in inventory.usable_entries(allow_candidates=allow_candidates):
            g = getattr(e, "grapheme", None)
            if not g:
                continue
            ph = getattr(e, "phoneme", None)
            self.units[g] = (ph if (ph and e.status == "validado") else f"<{g}>", e.id)
        self.max_len = max((len(g) for g in self.units), default=1)
        self.rules = [
            _ContextRule(e.id, re.compile(e.pattern or ""), (e.replacement or "").split())
            for e in context_rules.usable_entries(allow_candidates=allow_candidates)
            if e.pattern
        ]
        self.validated = all(e.status == "validado" for e in inventory.entries) and bool(
            inventory.entries
        )

    @classmethod
    def from_files(cls, rules_dir: Path = G2P_RULES, allow_candidates: bool = True) -> G2P:
        return cls(
            get_resource(rules_dir / "inventory.yaml"),
            get_resource(rules_dir / "cni.yaml"),
            allow_candidates=allow_candidates,
        )

    def word(self, word: str, offset: int = 0) -> tuple[PhonemizedWord, list[Unresolved]]:
        w = word.lower()
        phonemes: list[str] = []
        spans: list[tuple[int, int]] = []
        rule_ids: list[str] = []
        unknown: list[Unresolved] = []
        i = 0
        while i < len(w):
            for rule in self.rules:
                m = rule.rx.match(w, i)
                if m and m.end() > i:
                    for ph in rule.phonemes:
                        phonemes.append(ph)
                        spans.append((i, m.end()))
                    rule_ids.append(rule.id)
                    i = m.end()
                    break
            else:
                for size in range(min(self.max_len, len(w) - i), 0, -1):
                    g = w[i : i + size]
                    if g in self.units:
                        ph, rid = self.units[g]
                        phonemes.append(ph)
                        spans.append((i, i + size))
                        rule_ids.append(rid)
                        i += size
                        break
                else:
                    unknown.append(
                        Unresolved(offset + i, offset + i + 1, w[i], "grafema fuera del inventario")
                    )
                    i += 1
        return PhonemizedWord(word, phonemes, spans, rule_ids), unknown

    def text(self, text: str) -> G2PResult:
        words: list[PhonemizedWord] = []
        unknown: list[Unresolved] = []
        for m in WORD_RX.finditer(text):
            pw, unk = self.word(m.group(0), offset=m.start())
            words.append(pw)
            unknown.extend(unk)
        return G2PResult(words, unknown)
