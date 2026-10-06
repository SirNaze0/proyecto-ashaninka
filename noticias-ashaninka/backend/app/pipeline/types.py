"""Tipos compartidos por las etapas del pipeline de texto.

Los offsets son índices de caracteres (Python, semiabiertos [start, end)).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class NormalizedSpan:
    """Correspondencia entre un fragmento del texto original y su forma canónica."""

    orig_start: int
    orig_end: int
    orig_text: str
    norm_text: str
    category: str
    rule_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class CharMapEntry:
    """Correspondencia canónico ↔ ortografía del motor TTS (adaptador 2e)."""

    src_start: int
    src_end: int
    dst_start: int
    dst_end: int
    rule_id: str | None = None


@dataclass
class EditorialFlag:
    kind: str  # big_number | full_date | missing_neologism | relative_date
    orig_start: int
    orig_end: int
    note: str


@dataclass
class Unresolved:
    orig_start: int
    orig_end: int
    text: str
    reason: str


@dataclass
class NormalizationResult:
    text_canonical: str
    spans: list[NormalizedSpan]
    editorial_flags: list[EditorialFlag] = field(default_factory=list)
    unresolved: list[Unresolved] = field(default_factory=list)
    resources_hash: str = ""
    used_candidates: bool = False


@dataclass
class AdaptedText:
    text_tts: str
    char_map: list[CharMapEntry]
    adapter_id: str


@dataclass
class PhonemizedWord:
    word: str
    phonemes: list[str]
    char_spans: list[tuple[int, int]]
    rule_ids: list[str]


@dataclass
class G2PResult:
    words: list[PhonemizedWord]
    unknown: list[Unresolved]


def to_jsonable(obj):
    """Convierte dataclasses (y listas de ellas) a estructuras serializables en JSON."""
    if isinstance(obj, list):
        return [to_jsonable(o) for o in obj]
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    return obj
