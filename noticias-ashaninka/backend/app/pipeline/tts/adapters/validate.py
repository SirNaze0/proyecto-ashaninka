"""2f — Validación estricta: el texto que llega al TTS debe estar 100 % en su vocabulario.

Nunca se depende de que ``VitsTokenizer`` elimine caracteres (lo hace en silencio, ver
PLAN_DESARROLLO.md §3.2). Si queda un carácter fuera del vocabulario, se lanza un error.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OOVChar:
    char: str
    position: int


class OutOfVocabularyError(ValueError):
    def __init__(self, text: str, oov: list[OOVChar]):
        self.text = text
        self.oov = oov
        shown = ", ".join(f"{o.char!r}@{o.position}" for o in oov[:10])
        more = f" (+{len(oov) - 10})" if len(oov) > 10 else ""
        super().__init__(f"{len(oov)} caracteres fuera del vocabulario del TTS: {shown}{more}")


def find_oov(text: str, vocab: set[str]) -> list[OOVChar]:
    return [OOVChar(ch, i) for i, ch in enumerate(text) if ch not in vocab]


def validate_tts_text(text: str, vocab: set[str]) -> None:
    oov = find_oov(text, vocab)
    if oov:
        raise OutOfVocabularyError(text, oov)
