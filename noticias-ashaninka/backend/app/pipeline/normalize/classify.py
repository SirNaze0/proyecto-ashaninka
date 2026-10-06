"""2a — Tokenización y clasificación de tokens.

Categorías: numero_pequeno | numero_grande | numero | porcentaje | dinero | anio | fecha |
ordinal | abreviatura | sigla | romano | nombre_propio | nombre_propio_nativo | prestamo |
castellano | cni | espacio | puntuacion.

La heurística de nombre propio y la detección de "castellano" por grafemas ajenos al
inventario son SUPUESTO-LING (dependen de P1); se documentan en docs/limitations.md.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

MONTHS_ES = (
    "enero febrero marzo abril mayo junio julio agosto septiembre setiembre "
    "octubre noviembre diciembre"
).split()
_MONTHS = "|".join(MONTHS_ES)

TOKEN_PATTERNS: list[tuple[str, str]] = [
    (
        "dinero",
        r"(?:S/\.?|US\$|\$)\s?\d{1,3}(?:[ .,]\d{3})*(?:[.,]\d{1,2})?(?!\d)"
        r"|\d+(?:[.,]\d+)?\s?\$",
    ),
    ("porcentaje", r"\d+(?:[.,]\d+)?\s?%"),
    ("fecha", r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"),
    ("fecha", rf"\b\d{{1,2}} de (?i:{_MONTHS})(?: del? \d{{4}})?\b"),
    ("ordinal", r"\d+\s?[°º]"),
    ("abreviatura", r"\b[Nn][°º.](?=\s?\d)"),
    ("sigla", r"(?:[A-ZÁÉÍÓÚÑ]\.){2,}"),
    ("sigla", r"\b[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ0-9]*[A-ZÁÉÍÓÚÑ0-9]\b(?![a-záéíóúñ])"),
    ("numero", r"\d+(?:[.,]\d+)*"),
    ("palabra", r"[^\W\d_]+(?:['’][^\W\d_]+)*"),
    ("espacio", r"\s+"),
    ("puntuacion", r"."),
]
TOKEN_RX = re.compile("|".join(f"(?P<t{i}>{p})" for i, (_, p) in enumerate(TOKEN_PATTERNS)))
_KINDS = [k for k, _ in TOKEN_PATTERNS]

ROMAN_RX = re.compile(r"^(?=[IVX]{2,}$)X{0,3}(IX|IV|V?I{0,3})$")
YEAR_RX = re.compile(r"^(1[89]\d\d|20\d\d|2100)$")
SENTENCE_START_RX = re.compile(r"(^|[.!?¿¡:;]\s+|^[\W]+)$")
WORD_RX = re.compile(r"[^\W\d_]+")
ACCENTED_RX = re.compile(r"[áéíóúü]")


@dataclass
class Token:
    start: int
    end: int
    text: str
    kind: str  # tipo léxico inicial (patrón que coincidió)
    category: str = ""


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def tokenize(text: str) -> list[Token]:
    tokens = []
    for m in TOKEN_RX.finditer(text):
        kind = _KINDS[int(m.lastgroup[1:])]  # type: ignore[index]
        tokens.append(Token(m.start(), m.end(), m.group(0), kind))
    return tokens


def is_heading(text: str) -> bool:
    """Segmento mayoritariamente en mayúsculas: sus palabras son títulos, no siglas."""
    words = WORD_RX.findall(text)
    if len(words) < 2:
        return False
    return sum(1 for w in words if w.isupper() and len(w) > 1) / len(words) >= 0.6


def roman_value(s: str) -> int:
    vals = {"I": 1, "V": 5, "X": 10}
    total = 0
    for i, ch in enumerate(s):
        v = vals[ch]
        total += -v if i + 1 < len(s) and vals[s[i + 1]] > v else v
    return total


def sentence_initial(text: str, start: int) -> bool:
    return bool(SENTENCE_START_RX.search(text[:start]))


class Classifier:
    """Asigna categoría a cada token usando los recursos (gazetteer, préstamos, siglas)."""

    def __init__(
        self,
        native_letters: set[str],
        proper_nouns: set[str],
        loanwords: set[str],
        acronyms: set[str],
    ):
        self.native = native_letters
        self.proper_nouns = proper_nouns
        self.loanwords = loanwords
        self.acronyms = acronyms

    def has_foreign(self, word: str) -> bool:
        """SUPUESTO-LING: castellano probable si tiene una letra fuera del inventario canónico
        candidato (P1) o una vocal con tilde (en el corpus las tildes son casi exclusivas de
        palabras castellanas: á 0,007 % en palabras asháninka; ver docs/corpus_report.md)."""
        low = word.lower()
        if ACCENTED_RX.search(low):
            return True
        return any(ch not in self.native for ch in strip_accents(low) if ch.isalpha())

    def classify(self, text: str, tokens: list[Token]) -> list[Token]:
        heading = is_heading(text)
        for t in tokens:
            t.category = self._category(text, t, heading)
        return tokens

    def _category(self, text: str, t: Token, heading: bool) -> str:
        k = t.kind
        if k in {
            "espacio",
            "puntuacion",
            "dinero",
            "porcentaje",
            "fecha",
            "ordinal",
            "abreviatura",
        }:
            return k
        if k == "numero":
            return "anio" if YEAR_RX.match(t.text) else "numero"
        w = t.text
        if k == "sigla":
            bare = w.replace(".", "")
            # Títulos en mayúsculas y palabras largas en mayúsculas no son siglas
            if bare.isalpha() and w.count(".") == 0 and (heading or len(bare) > 6):
                return "cni" if not self.has_foreign(w) else "castellano"
            if bare in self.acronyms or w in self.acronyms:
                return "sigla"
            return "romano" if ROMAN_RX.match(bare) else "sigla"
        # palabra
        if w in self.proper_nouns:
            return "nombre_propio"
        if w.lower() in self.loanwords:
            return "prestamo"
        # SUPUESTO-LING: mayúscula inicial fuera de inicio de oración = nombre propio
        if not heading and w[:1].isupper() and not sentence_initial(text, t.start):
            return "nombre_propio" if self.has_foreign(w) else "nombre_propio_nativo"
        if self.has_foreign(w):
            return "castellano"
        return "cni"
