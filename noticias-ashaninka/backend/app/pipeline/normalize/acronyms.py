"""2c — Siglas: glosa en asháninka + sigla en la primera mención del documento; luego solo la sigla.

Cada entrada de ``acronyms.yaml`` tiene ``source_form`` (la sigla), ``gloss_cni`` (glosa
validada), ``reading`` (``word`` o ``spell``) y ``replacement`` (forma canónica de la sigla tal
como se pronuncia). Sin entrada usable, la sigla queda en ``unresolved``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.pipeline.normalize.rewrite import Lexicon


@dataclass
class AcronymState:
    """Estado por documento: qué siglas ya se mencionaron."""

    seen: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class AcronymResult:
    text: str | None  # None si no hay entrada usable
    rule_id: str | None
    first_mention: bool
    reason: str = ""


class AcronymExpander:
    def __init__(self, lexicon: Lexicon, letter_names_es: dict[str, str]):
        self.lexicon = lexicon
        self.letter_names = letter_names_es

    def spell_es(self, sigla: str) -> str:
        """Deletreo con los nombres castellanos de las letras (luego pasa por 2d)."""
        return " ".join(
            self.letter_names.get(ch.upper(), ch.lower()) for ch in sigla if ch.isalnum()
        )

    def expand(self, raw: str, state: AcronymState) -> AcronymResult:
        key = raw.replace(".", "") if raw.replace(".", "") in self.lexicon else raw
        entry = self.lexicon.get(key)
        if entry is None:
            return AcronymResult(
                None, None, key not in state.seen, "sigla sin entrada usable en el glosario (P2b)"
            )
        replacement, rid, extra = entry
        first = key not in state.seen
        state.seen.add(key)
        reading = (replacement or "").strip()
        if not reading:
            reading = self.spell_es(key) if extra.get("reading") == "spell" else key.lower()
        gloss = (extra.get("gloss_cni") or "").strip()
        if first and gloss:
            return AcronymResult(f"{gloss} {reading}", rid, True)
        if first and not gloss:
            return AcronymResult(reading, rid, True, "sigla sin glosa cni (P2b)")
        return AcronymResult(reading, rid, False)
