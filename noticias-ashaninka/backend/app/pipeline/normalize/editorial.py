"""1.5b — Detector editorial: MARCA, nunca modifica (§3.1 del plan).

Tipos de marca:
* ``big_number``: número >= ``big_number_min`` (candidato a redondeo editorial);
* ``full_date``: fecha completa (candidata a fecha relativa, con la salvaguarda de R10);
* ``missing_neologism``: palabra castellana sin entrada en préstamos, gazetteer ni neologismos;
* ``relative_date``: fecha relativa ya presente (riesgo R10: caduca si el audio es estático).
"""

from __future__ import annotations

import re
from decimal import Decimal

from app.pipeline.types import EditorialFlag


class EditorialDetector:
    def __init__(
        self,
        relative_es: list[str],
        relative_cni: list[str],
        covered_terms: set[str],
        big_number_min: int = 1000,
    ):
        phrases = sorted({*relative_es, *relative_cni}, key=len, reverse=True)
        self.relative_rx = (
            re.compile(r"\b(?:" + "|".join(re.escape(p) for p in phrases) + r")\b", re.IGNORECASE)
            if phrases
            else None
        )
        self.covered = {t.lower() for t in covered_terms}
        self.big_number_min = big_number_min

    def number(self, value: Decimal | None, start: int, end: int, raw: str) -> list[EditorialFlag]:
        if value is not None and value >= self.big_number_min:
            return [
                EditorialFlag(
                    "big_number",
                    start,
                    end,
                    f"'{raw}': número grande, candidato a redondeo editorial",
                )
            ]
        return []

    @staticmethod
    def date(start: int, end: int, raw: str) -> list[EditorialFlag]:
        return [
            EditorialFlag(
                "full_date",
                start,
                end,
                f"'{raw}': fecha completa; ¿pasar a relativa respecto a la fecha "
                "de publicación? (ver R10)",
            )
        ]

    def spanish_word(self, word: str, start: int, end: int) -> list[EditorialFlag]:
        if word.lower() in self.covered:
            return []
        return [
            EditorialFlag(
                "missing_neologism",
                start,
                end,
                f"'{word}': término castellano sin entrada en P2c/P2e/gazetteer",
            )
        ]

    def relative_dates(self, text: str) -> list[EditorialFlag]:
        if not self.relative_rx:
            return []
        return [
            EditorialFlag(
                "relative_date",
                m.start(),
                m.end(),
                f"'{m.group(0)}': fecha relativa; caduca si el audio se sirve estático (R10)",
            )
            for m in self.relative_rx.finditer(text)
        ]
