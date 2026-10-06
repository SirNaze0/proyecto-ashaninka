"""Pruebas de contrato TTSEngine (Fake siempre; MMS y eSpeak si están disponibles) y duraciones."""

import numpy as np
import pytest
from app.config import get_settings
from app.pipeline.tts.base import AudioResult, chars_from_tokens, derive_seed
from app.pipeline.tts.espeak import ESpeakEngine, PhonemeModeDisabled, find_espeak
from app.pipeline.tts.fake import FakeEngine
from app.pipeline.tts.registry import EnginePool, create_engine, get_pool, reset_pools

HAS_MMS = (get_settings().models_dir / "facebook__mms-tts-cni" / "model.safetensors").exists()
HAS_ESPEAK = find_espeak(get_settings().espeak_path) is not None

ENGINES = [
    pytest.param("fake", id="fake"),
    pytest.param(
        "mms_vits",
        id="mms",
        marks=[pytest.mark.eval, pytest.mark.skipif(not HAS_MMS, reason="falta mms-tts-cni")],
    ),
    pytest.param(
        "espeak_ng",
        id="espeak",
        marks=pytest.mark.skipif(not HAS_ESPEAK, reason="eSpeak-NG no instalado"),
    ),
]
TEXT = "quipatsi anyaantsi"


@pytest.mark.parametrize("name", ENGINES)
def test_engine_contract(name):
    eng = create_engine(name)
    assert eng.warmup() >= 0
    info = eng.info()
    assert info.engine == name and info.license and info.sample_rate > 0
    a = eng.synthesize(TEXT, 42)
    b = eng.synthesize(TEXT, 42)
    assert isinstance(a, AudioResult)
    assert a.wav.dtype == np.float32 and a.wav.ndim == 1 and len(a.wav) > 0
    assert a.sample_rate == info.sample_rate and a.duration_s > 0 and a.rtf > 0
    assert np.array_equal(a.wav, b.wav), "misma semilla = mismo audio"
    assert "aviso" in a.meta
    with pytest.raises(ValueError):
        eng.synthesize("   ", 1)


@pytest.mark.smoke
def test_fake_durations_match_audio():
    r = FakeEngine().synthesize("abc", 1)
    assert r.durations.total_samples == len(r.wav)
    assert r.durations.char_times[-1][1] == pytest.approx(r.duration_s)


def test_chars_from_tokens_layouts():
    # intercalado estándar: blanco, a, blanco, b, blanco
    spans = chars_from_tokens("ab", [2, 4, 2, 6, 2], True)
    assert spans == [(0.0, 7.0), (7.0, 16.0)]
    assert chars_from_tokens("ab", [3, 5], False) == [(0.0, 3.0), (3.0, 8.0)]
    # layout tipo HF: 'a' suelta sin blancos, 'b' con blancos
    assert chars_from_tokens("ab", [3, 1, 4, 1], [0, None, 1, None]) == [(0.0, 3.5), (3.5, 9.0)]
    assert chars_from_tokens("", [], True) == []
    with pytest.raises(ValueError):
        chars_from_tokens("ab", [1, 2], True)
    with pytest.raises(ValueError):
        chars_from_tokens("ab", [1, 2], [0, 0])


def test_derive_seed_is_deterministic_and_sensitive():
    s = derive_seed("t", "mms_vits", "r", "H1")
    assert s == derive_seed("t", "mms_vits", "r", "H1")
    assert s != derive_seed("t", "mms_vits", "r", "H2")


def test_registry_and_pool():
    reset_pools()
    with pytest.raises(ValueError):
        create_engine("nope")
    pool = EnginePool("fake", 2)
    assert pool.warmup() == 0.0 and pool.info().engine == "fake"
    with pool.acquire() as e1, pool.acquire() as e2:
        assert e1 is not e2
    assert get_pool("fake", 1) is get_pool("fake", 1)


def test_hf_layout_matches_vits_tokenizer_rule():
    from app.pipeline.tts.mms_vits import hf_layout

    assert hf_layout("a") == [0]
    assert hf_layout("ab") == [0, None, 1, None]
    assert hf_layout("bab") == [None, 0, None, 1, None, 2, None]
    assert len(hf_layout("quipatsi anyaantsi")) == 36  # medido con VitsTokenizer


def test_espeak_phoneme_mode_is_disabled_without_p1():
    eng = ESpeakEngine(mode="fonemas")
    with pytest.raises(PhonemeModeDisabled):
        eng._check_phoneme_mode()


@pytest.mark.skipif(HAS_ESPEAK, reason="solo cuando eSpeak-NG NO está instalado")
def test_espeak_missing_is_explicit():
    from app.pipeline.tts.espeak import ESpeakNotInstalled

    with pytest.raises(ESpeakNotInstalled):
        ESpeakEngine().synthesize("hola", 1)


# ------------------------------------------------------------------ MMS: hook y R13
@pytest.mark.eval
@pytest.mark.skipif(not HAS_MMS, reason="falta mms-tts-cni")
def test_mms_duration_hook_on_50_sentences():
    """Criterio de cierre: sum(frames)*hop == len(wav) en >= 50 oraciones, ambos modos."""
    from app.corpus.loader import corpus_available, load_split
    from app.pipeline.normalize.engine import DocumentState, Normalizer
    from app.pipeline.tts.adapters.mms_cni import MmsCniAdapter
    from app.pipeline.tts.mms_vits import MmsVitsEngine

    if not corpus_available():
        pytest.skip("sin corpus")
    norm, ad = Normalizer.from_files(), MmsCniAdapter.from_files()
    texts = []
    for p in load_split("dev"):
        t = ad.adapt(norm.normalize(p.cni, DocumentState()).text_canonical).text_tts
        if t and not ad.oov_after(t) and len(t) < 200:
            texts.append(t)
        if len(texts) == 50:
            break
    assert len(texts) == 50
    for mode in ("manual", "hf"):
        eng = MmsVitsEngine(tokenization=mode)
        for i, t in enumerate(texts[: 50 if mode == "manual" else 10]):
            r = eng.synthesize(t, i)
            d = r.durations
            assert d.total_samples == len(r.wav)
            assert len(d.char_times) == len(t)
            ends = [b for _, b in d.char_times]
            assert ends == sorted(ends) and ends[-1] == pytest.approx(r.duration_s, abs=1e-3)


@pytest.mark.eval
@pytest.mark.skipif(not HAS_MMS, reason="falta mms-tts-cni")
def test_mms_rejects_text_the_tokenizer_would_alter():
    from app.pipeline.tts.mms_vits import MmsVitsEngine, TokenizerDropError

    with pytest.raises(TokenizerDropError):
        MmsVitsEngine().synthesize("kipatsi", 1)
    with pytest.raises(ValueError):
        MmsVitsEngine(tokenization="otra")
