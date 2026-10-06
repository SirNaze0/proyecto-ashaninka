"""Normalizador con recursos FICTICIOS (ver conftest): prueba el motor, no datos del asháninka."""

import pytest
from app.pipeline.normalize.engine import DocumentState, Normalizer
from app.pipeline.normalize.rewrite import Lexicon
from tests_helpers import assert_alignment


@pytest.mark.smoke
def test_alignment_properties(fake_normalizer):
    text = "Tasi qoxi Lima, 25 ayer XYZ y XYZ. ¿Doctor? 10,000"
    r = fake_normalizer.normalize(text)
    assert_alignment(text, r)


def test_unification_only_on_native_words(fake_normalizer):
    r = fake_normalizer.normalize("qoxi Qima")
    cats = {s.orig_text: (s.category, s.norm_text) for s in r.spans}
    assert cats["qoxi"] == ("cni", "xoxi")  # regla ficticia q -> x
    assert cats["Qima"][0] == "nombre_propio_nativo"  # los nombres no se unifican
    assert "F-ORT-1" in next(s for s in r.spans if s.orig_text == "qoxi").rule_ids


def test_acronym_first_mention_then_only_acronym(fake_normalizer):
    state = DocumentState()
    r1 = fake_normalizer.normalize("Ese XYZ y XYZ.", state)
    r2 = fake_normalizer.normalize("Otra vez XYZ.", state)  # misma noticia
    outs = [s.norm_text for s in r1.spans if s.orig_text == "XYZ"]
    assert outs == ["mano tasi ixiz", "ixiz"]
    assert [s.norm_text for s in r2.spans if s.orig_text == "XYZ"] == ["ixiz"]


def test_acronym_spelled_without_gloss_and_unknown(fake_normalizer):
    r = fake_normalizer.normalize("La ONU y la CIA")
    onu = next(s for s in r.spans if s.orig_text == "ONU")
    assert onu.norm_text == "o ene u"
    reasons = [u.reason for u in r.unresolved]
    assert any("sin glosa" in x for x in reasons)
    assert any("sin entrada usable" in x for x in reasons)  # CIA


def test_numbers_and_candidates(fake_resources, fake_inventory):
    strict = Normalizer(fake_resources, fake_inventory, allow_candidates=False)
    r = strict.normalize("1 2 3")
    assert [s.norm_text for s in r.spans if s.category.startswith("numero")][:2] == ["mon", "tos"]
    assert not r.used_candidates
    loose = Normalizer(fake_resources, fake_inventory, allow_candidates=True)
    r = loose.normalize("3")
    assert r.text_canonical == "tix" and r.used_candidates


def test_spanish_rewrite_and_unresolved(fake_normalizer):
    r = fake_normalizer.normalize("Ese doctor llegó")
    doc = next(s for s in r.spans if s.orig_text == "doctor")
    assert doc.norm_text == "toctor".replace("r", "n")  # reglas ficticias d->t, r->n
    assert "F-P2D-1" in doc.rule_ids
    # 'c' es ajena al inventario ficticio: queda sin resolver, nunca se descarta
    assert any(u.text == "doctor" for u in r.unresolved)
    assert any(f.kind == "missing_neologism" for f in r.editorial_flags)


def test_spanish_without_p2d_is_flagged(fake_resources, fake_inventory):
    fake_resources = dict(fake_resources)
    from conftest import res

    fake_resources["es_to_cni_phonology"] = res("es_to_cni_phonology")
    n = Normalizer(fake_resources, fake_inventory)
    r = n.normalize("Tasi 7")  # 'siete' solo tiene letras del inventario ficticio... salvo e/i
    assert any("P2d" in u.reason for u in r.unresolved)


def test_lexicon_entries(fake_normalizer):
    r = fake_normalizer.normalize("Ese radio de Lima")
    norms = {s.orig_text: s.norm_text for s in r.spans}
    assert norms["radio"] == "ratio" and norms["Lima"] == "nima"


def test_editorial_flags(fake_normalizer):
    r = fake_normalizer.normalize("Hoy 05/10/2026 vino 2500 gente con S/ 3000 y vacuna")
    kinds = sorted(f.kind for f in r.editorial_flags)
    assert kinds.count("relative_date") == 1
    assert "full_date" in kinds
    assert kinds.count("big_number") == 2
    # 'vacuna' está cubierta por el glosario de neologismos ficticio
    assert not any("vacuna" in f.note for f in r.editorial_flags)


def test_ambiguous_number_kept_and_reported(fake_normalizer):
    r = fake_normalizer.normalize("Son 10,000")
    span = next(s for s in r.spans if s.orig_text == "10,000")
    assert span.norm_text == "10,000"
    assert any("ambiguo" in u.reason for u in r.unresolved)


def test_other_numeric_categories(fake_normalizer):
    r = fake_normalizer.normalize("Nº 5 el 5° y VIII con 58 % en 2026, 3 de mayo")
    cats = {s.category for s in r.spans}
    assert {"abreviatura", "ordinal", "romano", "porcentaje", "anio", "fecha"} <= cats


def test_lexicon_helper(fake_resources):
    lex = Lexicon(fake_resources["loanwords"], {"validado"})
    assert "radio" in lex and lex.get("radio")[0] == "ratio" and lex.keys() == {"radio"}


@pytest.mark.smoke
def test_real_normalizer_builds_and_is_deterministic():
    n = Normalizer.from_files()
    text = "Okantzi Pablo 2026 tzimatsi kitaiteri, I.U. 10,000."
    a, b = n.normalize(text), n.normalize(text)
    assert a.text_canonical == b.text_canonical
    assert "okantsi" in a.text_canonical and "tsimatsi" in a.text_canonical
    assert_alignment(text, a)
