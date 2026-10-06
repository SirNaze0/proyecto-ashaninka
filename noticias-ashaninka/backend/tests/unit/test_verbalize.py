from decimal import Decimal

import pytest
from app.pipeline.normalize.verbalize import AmbiguousNumber, Verbalizer, number_es, parse_number


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("25", Decimal("25")),
        ("0,5", Decimal("0.5")),
        ("2.75", Decimal("2.75")),
        ("1.500.000", Decimal("1500000")),
        ("1,500.50", Decimal("1500.50")),
        ("1.500,50", Decimal("1500.50")),
        ("1 500", Decimal("1500")),
    ],
)
def test_parse_number(raw, expected):
    assert parse_number(raw) == expected


@pytest.mark.parametrize("raw", ["10,000", "2.500", "1.50.0"])
def test_ambiguous_numbers_are_not_guessed(raw):
    with pytest.raises(AmbiguousNumber):
        parse_number(raw)


def test_number_es():
    assert number_es(Decimal("21")) == "veintiuno"
    assert number_es(Decimal("0.5")) == "cero coma cinco"
    assert number_es(Decimal("2.05")) == "dos coma cero cinco"
    assert number_es(Decimal("3.25")) == "tres coma veinticinco"


def test_number_categories_without_limit_use_only_usable_numerals():
    v = Verbalizer(None, {1: ("mon", "F-NUM-1")})
    out, cat = v.number("1")
    assert (out.text, out.lang, cat) == ("mon", "cni", "numero_pequeno")
    out, cat = v.number("7")
    assert (out.lang, cat) == ("es", "numero")
    out, cat = v.number("0,5")
    assert cat == "numero_grande"


def test_number_categories_with_limit():
    v = Verbalizer(3, {1: ("mon", "F-NUM-1")})
    assert v.number("2")[1] == "numero_pequeno"  # pequeño pero sin numeral -> castellano
    assert v.number("2")[0].lang == "es"
    assert v.number("40")[1] == "numero_grande"


def test_percent_money_year_ordinal_roman():
    assert Verbalizer.percent("58 %").text == "cincuenta y ocho por ciento"
    assert Verbalizer.money("S/ 1").text == "un sol"
    assert Verbalizer.money("S/. 20,50").text == "veinte soles con cincuenta céntimos"
    assert Verbalizer.money("$ 3").text == "tres dólares"
    assert Verbalizer.money("1 $").text == "un dólar"
    assert Verbalizer.year("2026").text == "dos mil veintiséis"
    assert Verbalizer.ordinal("1°").text == "primero"
    assert Verbalizer.roman(8).text == "octavo"


def test_dates():
    assert Verbalizer.date("05/10/2026").text == "cinco de octubre de dos mil veintiséis"
    assert Verbalizer.date("5 de Octubre de 2026").text == "cinco de octubre de dos mil veintiséis"
    assert Verbalizer.date("12 de mayo").text == "doce de mayo"
    for bad in ["32/01/2026", "05/13/2026", "05/10/26", "5 de brumario"]:
        with pytest.raises(AmbiguousNumber):
            Verbalizer.date(bad)
