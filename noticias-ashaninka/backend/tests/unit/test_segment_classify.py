import pytest
from app.pipeline.normalize.classify import (
    Classifier,
    is_heading,
    roman_value,
    sentence_initial,
    tokenize,
)
from app.pipeline.segment import Segmenter


@pytest.mark.smoke
def test_segments_keep_offsets():
    text = "Primera oración. Segunda aquí!\n\nOtro párrafo? Sí."
    segs = Segmenter.from_files().segment(text)
    assert [s.text for s in segs] == ["Primera oración.", "Segunda aquí!", "Otro párrafo?", "Sí."]
    assert [s.paragraph_idx for s in segs] == [0, 0, 1, 1]
    for s in segs:
        assert text[s.start : s.end] == s.text


def test_abbreviations_and_enumerations_do_not_split():
    seg = Segmenter(abbreviations=["Sr", "art"])
    text = "1. Intakantero nija.\nLo dijo el Sr. Pérez. Ver art. 5 ahora."
    out = [s.text for s in seg.segment(text)]
    assert out == ["1. Intakantero nija.", "Lo dijo el Sr. Pérez.", "Ver art. 5 ahora."]


def test_empty_text_and_trailing_spaces():
    seg = Segmenter()
    assert seg.segment("") == []
    assert seg.segment("   \n  ") == []
    out = seg.segment("  hola mundo  ")
    assert out[0].text == "hola mundo" and out[0].start == 2


def test_tokenize_kinds():
    toks = tokenize("S/ 20 y 58 % el 05/10/2026, 5 de octubre de 2026, 5° Nº 3 U2 I.U. kipatsi")
    kinds = [(t.text, t.kind) for t in toks if t.kind not in {"espacio", "puntuacion"}]
    assert ("S/ 20", "dinero") in kinds
    assert ("58 %", "porcentaje") in kinds
    assert ("05/10/2026", "fecha") in kinds
    assert ("5 de octubre de 2026", "fecha") in kinds
    assert ("5°", "ordinal") in kinds
    assert ("Nº", "abreviatura") in kinds
    assert ("U2", "sigla") in kinds and ("I.U.", "sigla") in kinds
    assert ("kipatsi", "palabra") in kinds


def test_heading_roman_and_sentence_start():
    assert is_heading("SANKENARENTSI ASHI TARAPOTO")
    assert not is_heading("Ora nampitsi VIII FOSPA akantasanotiro")
    assert not is_heading("UNO")
    assert roman_value("VIII") == 8 and roman_value("IV") == 4 and roman_value("XIX") == 19
    assert sentence_initial("Hola. Mundo", 6)
    assert not sentence_initial("Hola Mundo", 5)


def test_classifier_categories():
    c = Classifier(set("aiotrnkesmpyhjbñv"), {"Lima"}, {"radio"}, {"FOSPA"})
    text = "Kipatsi ora Lima radio Pablo Naviriri FOSPA VIII CIA 2026 25 doctor PRESIDENTEX"
    cats = {t.text: t.category for t in c.classify(text, tokenize(text))}
    assert cats["Kipatsi"] == "cni"  # inicio de oración
    assert cats["Lima"] == "nombre_propio"
    assert cats["radio"] == "prestamo"
    assert cats["Pablo"] == "nombre_propio"  # 'l' ajena al inventario
    assert cats["Naviriri"] == "nombre_propio_nativo"
    assert cats["FOSPA"] == "sigla"
    assert cats["VIII"] == "romano"
    assert cats["CIA"] == "sigla"
    assert cats["2026"] == "anio" and cats["25"] == "numero"
    assert cats["doctor"] == "castellano"
    assert cats["PRESIDENTEX"] == "castellano"  # mayúsculas largas no son sigla


def test_accented_words_are_spanish_like():
    c = Classifier(set("aiotrnkesmpyhjbñvcz"), set(), set(), set())
    text = "ora amazónicos kipatsi"
    cats = {t.text: t.category for t in c.classify(text, tokenize(text))}
    assert cats["amazónicos"] == "castellano"  # todas sus letras son "nativas", pero lleva tilde
    assert cats["kipatsi"] == "cni"


def test_heading_words_are_not_acronyms():
    c = Classifier(set("aiotrnkesmpyhjbñ"), set(), set(), set())
    text = "SANKENARENTSI ASHI TARAPOTO"
    assert {t.category for t in c.classify(text, tokenize(text)) if t.kind != "espacio"} == {"cni"}
