import importlib.util

import pytest
from app.config import get_settings
from app.pipeline.g2p.engine import G2P
from app.pipeline.rules import check_map
from app.pipeline.tts.adapters.mms_cni import MmsCniAdapter, load_mms_vocab
from app.pipeline.tts.adapters.validate import OutOfVocabularyError, find_oov, validate_tts_text
from conftest import e, res


@pytest.mark.smoke
def test_vocab_matches_published_letters():
    letters = {c for c in load_mms_vocab() if c.isalpha()}
    assert letters == set("acehijmnopqrstuvy")
    assert not {"k", "b", "ñ", "z", "g", "l", "d", "f"} & letters


@pytest.mark.smoke
def test_h1_maps_conflicting_chars_and_keeps_valid_map():
    a = MmsCniAdapter.from_files("H1")
    src = "kipatsi, añaantsi kemetsa ¡bakotsi! otzitzi ashéninka 5º"
    out = a.adapt(src)
    assert out.text_tts == "quipatsi anyaantsi quemetsa vacotsi otsitsi asheninca 5"
    assert check_map(out.char_map, src, out.text_tts) == []
    validate_tts_text(out.text_tts, a.vocab())  # no lanza
    assert a.adapt_validated(src).text_tts == out.text_tts
    assert a.oov_after(src) == []


def test_h0_is_raw_and_fails_validation():
    a = MmsCniAdapter.from_files("H0")
    out = a.adapt("Kipatsi")
    assert out.text_tts == "kipatsi" and a.raw
    with pytest.raises(OutOfVocabularyError) as err:
        a.adapt_validated("kipatsi")
    assert err.value.oov[0].char == "k"
    assert "k" in a.oov_after("kipatsi")


def test_validation_helpers():
    assert [o.char for o in find_oov("ab", {"a"})] == ["b"]
    with pytest.raises(OutOfVocabularyError, match="1 caracteres"):
        validate_tts_text("ab", {"a"})
    long_text = "b" * 12
    with pytest.raises(OutOfVocabularyError, match=r"\(\+2\)"):
        validate_tts_text(long_text, {"a"})


def test_adapter_config_errors():
    good = {"hypotheses": {"HX": {"rules": ["NOPE"]}}}
    with pytest.raises(ValueError, match="inexistentes"):
        MmsCniAdapter(res("mms", [], good), "HX", vocab=set())
    with pytest.raises(ValueError, match="desconocida"):
        MmsCniAdapter(res("mms", [], good), "HZ", vocab=set())


def test_adapter_trims_edges():
    r = res(
        "mms",
        [e("P", pattern=r"[.!]", replacement=" ")],
        {"typographic": ["P"], "hypotheses": {"H": {"rules": []}}},
    )
    a = MmsCniAdapter(r, "H", vocab=set("abc "))
    out = a.adapt("!abc.")
    assert out.text_tts == "abc"
    assert all(0 <= m.dst_start <= m.dst_end <= len(out.text_tts) for m in out.char_map)


@pytest.mark.eval
@pytest.mark.skipif(
    importlib.util.find_spec("transformers") is None
    or not (get_settings().models_dir / "facebook__mms-tts-cni" / "vocab.json").exists(),
    reason="requiere el grupo eval y ./init.sh --with-audio-eval",
)
def test_tokenizer_does_not_drop_anything_after_adapter():
    """Regresión clave (R13): tras el adaptador, VitsTokenizer no elimina ningún carácter."""
    from transformers import VitsTokenizer

    tok = VitsTokenizer.from_pretrained(get_settings().models_dir / "facebook__mms-tts-cni")
    a = MmsCniAdapter.from_files("H1")
    for src in ["kipatsi añaantsi bakotsi", "tzimatsi ashéninka kemetsa", "ora irt akakotiro"]:
        text_tts = a.adapt_validated(src).text_tts
        prepared = tok.prepare_for_tokenization(text_tts, normalize=True)[0]
        assert prepared == text_tts
    # y demuestra el defecto con H0
    assert tok.prepare_for_tokenization("kipatsi", normalize=True)[0] == "ipatsi"


# ------------------------------------------------------------------ G2P
def test_g2p_with_fictitious_inventory(fake_inventory):
    rules = res("g2p_rules", [e("CTX-1", pattern="n(?=t)", replacement="N")])
    g = G2P(fake_inventory, rules)
    w, unknown = g.word("xyanti")
    assert w.phonemes == ["X", "A", "N", "T", "I"]
    assert w.char_spans == [(0, 2), (2, 3), (3, 4), (4, 5), (5, 6)]
    assert w.rule_ids[0] == "INV-XY" and "CTX-1" in w.rule_ids
    assert unknown == []
    assert g.validated


def test_g2p_unknown_graphemes_do_not_raise(fake_inventory):
    g = G2P(fake_inventory, res("g2p_rules"))
    r = g.text("max kulo")
    assert [u.text for u in r.unknown] == ["k", "u", "l"]
    assert r.unknown[0].orig_start == 4


@pytest.mark.smoke
def test_real_inventory_is_candidate_and_marks_placeholders():
    g = G2P.from_files()
    w, _ = g.word("tsimatsi")
    assert w.phonemes == ["<ts>", "<i>", "<m>", "<a>", "<ts>", "<i>"]
    assert not g.validated  # nada validado todavía (P1)
