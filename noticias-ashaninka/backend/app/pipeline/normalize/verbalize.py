"""2b — Verbalización de números, porcentajes, dinero, años, fechas y ordinales.

Política (§3.1 del plan): números pequeños en asháninka (solo con numerales de P2a usables);
lo demás en palabras castellanas con ``num2words`` (lang ``es``), que después pasan por la
reescritura fonética 2d. Los separadores ambiguos NO se adivinan: devuelven ``None`` y el
token queda en ``unresolved``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from num2words import num2words

from app.pipeline.normalize.classify import MONTHS_ES

MONTH_NAMES = {
    i + 1: m
    for i, m in enumerate(
        [
            "enero",
            "febrero",
            "marzo",
            "abril",
            "mayo",
            "junio",
            "julio",
            "agosto",
            "septiembre",
            "octubre",
            "noviembre",
            "diciembre",
        ]
    )
}


class AmbiguousNumber(ValueError):
    pass


@dataclass(frozen=True)
class Verbalized:
    text: str
    lang: str  # "cni" | "es"
    rule_id: str
    value: Decimal | None = None


def parse_number(raw: str) -> Decimal:
    """Interpreta un número con separadores. Lanza ``AmbiguousNumber`` si no se puede decidir.

    * Solo dígitos -> entero.
    * Dos tipos de separador ("1,500.50" / "1.500,50"): el último es el decimal.
    * Un mismo separador repetido ("1.500.000"): miles.
    * Un único separador seguido de 1 o 2 dígitos ("0,5", "2.75"): decimal.
    * Un único separador seguido de exactamente 3 dígitos ("10,000", "2.500"): AMBIGUO
      (puede ser miles o decimal); no se adivina.
    """
    s = raw.replace(" ", "")
    if s.isdigit():
        return Decimal(s)
    seps = [c for c in s if c in ".,"]
    if len(set(seps)) == 2:
        dec = s[max(s.rfind("."), s.rfind(","))]
        thou = "," if dec == "." else "."
        return Decimal(s.replace(thou, "").replace(dec, "."))
    sep = seps[0]
    parts = s.split(sep)
    if len(parts) > 2:
        if all(len(p) == 3 for p in parts[1:]):
            return Decimal("".join(parts))
        raise AmbiguousNumber(raw)
    if len(parts[1]) == 3:
        raise AmbiguousNumber(raw)
    return Decimal(f"{parts[0]}.{parts[1]}")


def number_es(value: Decimal) -> str:
    if value == value.to_integral_value():
        return num2words(int(value), lang="es")
    int_part, dec_part = f"{value:f}".split(".")
    dec_words = (
        " ".join(num2words(int(d), lang="es") for d in dec_part)
        if dec_part.startswith("0")
        else num2words(int(dec_part), lang="es")
    )
    return f"{num2words(int(int_part), lang='es')} coma {dec_words}"


class Verbalizer:
    def __init__(self, small_max: int | None, cni_numerals: dict[int, tuple[str, str]]):
        """``cni_numerals``: valor -> (palabra cni, id de la entrada) solo con entradas usables."""
        self.small_max = small_max
        self.cni_numerals = cni_numerals

    def number_category(self, value: Decimal) -> str:
        if value != value.to_integral_value():
            return "numero_grande"
        if self.small_max is not None:
            return "numero_pequeno" if int(value) <= self.small_max else "numero_grande"
        # Sin límite validado: solo se considera pequeño lo que tiene numeral usable
        return "numero_pequeno" if int(value) in self.cni_numerals else "numero"

    def number(self, raw: str) -> tuple[Verbalized, str]:
        value = parse_number(raw)
        cat = self.number_category(value)
        if cat == "numero_pequeno" and int(value) in self.cni_numerals:
            word, rid = self.cni_numerals[int(value)]
            return Verbalized(word, "cni", rid, value), cat
        return Verbalized(number_es(value), "es", "VERB-NUM-ES", value), cat

    @staticmethod
    def percent(raw: str) -> Verbalized:
        value = parse_number(raw.replace("%", "").strip())
        return Verbalized(f"{number_es(value)} por ciento", "es", "VERB-PCT", value)

    @staticmethod
    def money(raw: str) -> Verbalized:
        s = raw.strip()
        if s.startswith(("S/", "S/.")):
            unit_one, unit_many = "sol", "soles"
            num = re.sub(r"^S/\.?", "", s).strip()
        else:
            unit_one, unit_many = "dólar", "dólares"
            num = s.replace("US$", "").replace("$", "").strip()
        value = parse_number(num.replace(" ", ""))
        whole = int(value)
        cents = int((value - whole) * 100)
        unit = unit_one if whole == 1 else unit_many
        whole_words = "un" if whole == 1 else num2words(whole, lang="es")
        text = f"{whole_words} {unit}"
        if cents:
            text += f" con {num2words(cents, lang='es')} céntimos"
        return Verbalized(text, "es", "VERB-MONEY", value)

    @staticmethod
    def year(raw: str) -> Verbalized:
        return Verbalized(num2words(int(raw), lang="es"), "es", "VERB-YEAR", Decimal(raw))

    @staticmethod
    def ordinal(raw: str) -> Verbalized:
        n = int(re.sub(r"\D", "", raw))
        return Verbalized(num2words(n, lang="es", to="ordinal"), "es", "VERB-ORD", Decimal(n))

    @staticmethod
    def roman(value: int) -> Verbalized:
        return Verbalized(
            num2words(value, lang="es", to="ordinal"), "es", "VERB-ROMAN", Decimal(value)
        )

    @staticmethod
    def date(raw: str) -> Verbalized:
        """dd/mm/aaaa (convención peruana) o "5 de octubre de 2026"."""
        m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", raw)
        if m:
            d, mo, y = int(m.group(1)), int(m.group(2)), m.group(3)
            if len(y) != 4 or not (1 <= d <= 31 and 1 <= mo <= 12):
                raise AmbiguousNumber(raw)
            return Verbalized(
                f"{num2words(d, lang='es')} de {MONTH_NAMES[mo]} de {num2words(int(y), lang='es')}",
                "es",
                "VERB-DATE-NUM",
            )
        m = re.fullmatch(r"(\d{1,2}) de (\w+)(?: del? (\d{4}))?", raw, flags=re.IGNORECASE)
        if not m or m.group(2).lower() not in MONTHS_ES:
            raise AmbiguousNumber(raw)
        text = f"{num2words(int(m.group(1)), lang='es')} de {m.group(2).lower()}"
        if m.group(3):
            text += f" de {num2words(int(m.group(3)), lang='es')}"
        return Verbalized(text, "es", "VERB-DATE-TXT")
