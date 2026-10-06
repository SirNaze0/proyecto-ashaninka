"""Caché, manifiesto, modo por lotes y streaming NDJSON con FakeEngine (sin modelos)."""

import json

import numpy as np
import pytest
from app.audio import atomic_write, encode, kbps, opus_level_for
from app.batch.manifest import Manifest, export_schema
from app.batch.timings import canonical_times, span_times
from app.db.models import AudioAsset, News, Provenance, SynthesisRun
from fastapi.testclient import TestClient
from sqlmodel import Session, select

NEWS_BODY = "Okantzi kemetsa. Tzimatsi kitaiteri ayer.\nIrotake Pablo Lima."


@pytest.fixture
def tts_env(temp_db, tmp_path, monkeypatch):
    from app.api import synthesize as api_synth
    from app.pipeline.tts import registry

    monkeypatch.setenv("NA_TTS_ENGINE", "fake")
    monkeypatch.setenv("NA_STATIC_DIR", str(tmp_path / "static"))
    registry.reset_pools()
    api_synth.reset_synthesizers()
    yield tmp_path / "static"
    registry.reset_pools()
    api_synth.reset_synthesizers()


def _add_news(engine, body=NEWS_BODY) -> int:
    with Session(engine) as s:
        n = News(titulo_cni="t", cuerpo_cni=body)
        n.provenance = Provenance(tipo="traduccion_automatica")
        s.add(n)
        s.commit()
        return n.id


def test_audio_encoding_and_levels(tmp_path):
    wav = (0.2 * np.sin(np.linspace(0, 2000, 16000))).astype(np.float32)
    for fmt in ("opus", "mp3", "wav"):
        assert len(encode(wav, 16000, fmt)) > 100
    with pytest.raises(ValueError):
        encode(wav, 16000, "flac")
    assert opus_level_for(24) == pytest.approx(0.9123, abs=1e-3)
    assert opus_level_for(500) == 0.7 and opus_level_for(1) == 1.0
    assert kbps(b"x" * 1000, 1.0) == 8.0 and kbps(b"x", 0) == 0.0
    atomic_write(tmp_path / "a" / "b.bin", b"hola")
    assert (tmp_path / "a" / "b.bin").read_bytes() == b"hola"


def test_timings_projection():
    tts_times = [(0.0, 1.0), (1.0, 2.0), (2.0, 3.0)]  # "cab"
    cmap = [  # canónico "kab" -> tts "cab"; un carácter canónico sin audio al final
        {"src_start": 0, "src_end": 1, "dst_start": 0, "dst_end": 1},
        {"src_start": 1, "src_end": 3, "dst_start": 1, "dst_end": 3},
        {"src_start": 3, "src_end": 4, "dst_start": 3, "dst_end": 3},
    ]
    canon = canonical_times(4, tts_times, cmap)
    assert canon == [(0.0, 1.0), (1.0, 2.0), (2.0, 3.0), (3.0, 3.0)]
    spans = span_times(
        [
            {
                "orig_start": 0,
                "orig_end": 3,
                "orig_text": "KAB",
                "norm_text": "kab",
                "category": "cni",
            },
            {
                "orig_start": 3,
                "orig_end": 4,
                "orig_text": ".",
                "norm_text": ".",
                "category": "identity",
            },
        ],
        canon,
    )
    assert (spans[0]["t0"], spans[0]["t1"]) == (0.0, 3.0)
    assert spans[1]["t0"] == spans[1]["t1"] == 3.0


def test_batch_build_is_idempotent_and_manifest_valid(tts_env, temp_db, tmp_path):
    from app.batch.service import run_batch

    nid = _add_news(temp_db)
    first = run_batch()
    assert first["errors"] == 0 and first["synthesized"] >= 2
    second = run_batch([nid])
    assert second["synthesized"] == 0 and second["reused"] == first["synthesized"]
    manifest = json.loads((tts_env / "news" / str(nid) / "manifest.json").read_text("utf-8"))
    m = Manifest.model_validate(manifest)
    assert m.notices.synthetic_voice and m.engine.engine == "fake"
    assert m.segments_with_audio + m.segments_blocked == len(m.segments)
    blocked = [s for s in m.segments if not s.tts_ready]
    assert blocked and all(s.audio is None and s.blocked_reason for s in blocked)
    ok = next(s for s in m.segments if s.tts_ready)
    assert (tts_env / ok.audio.opus.removeprefix("/static/")).exists()
    timings = json.loads((tts_env / ok.timings.removeprefix("/static/")).read_text("utf-8"))
    assert timings["spans"][0]["t1"] > 0
    with Session(temp_db) as s:
        assert s.exec(select(AudioAsset)).first() is not None
        assert len(s.exec(select(SynthesisRun)).all()) == 2
    assert export_schema(tmp_path / "schema.json").exists()


def test_cache_key_changes_with_adapter(tts_env):
    from app.batch.service import Synthesizer
    from app.pipeline.tts.registry import get_pool

    s = Synthesizer(get_pool("fake", 1))
    assert s.cache_key("abc", "mms_cni/H1") == s.cache_key("abc", "mms_cni/H1")
    assert s.cache_key("abc", "mms_cni/H1") != s.cache_key("abc", "mms_cni/H3")
    a = s.synthesize_text("abc", "mms_cni/H1")
    b = s.synthesize_text("abc", "mms_cni/H1")
    assert not a.reused and b.reused and a.cache_key == b.cache_key


def test_streaming_order_blocked_and_range(tts_env, temp_db):
    from app.main import app

    nid = _add_news(temp_db)
    with TestClient(app) as c:
        with c.stream("GET", f"/api/synthesize/{nid}") as r:
            assert r.headers["content-type"].startswith("application/x-ndjson")
            events = [json.loads(line) for line in r.iter_lines() if line]
        kinds = [e["event"] for e in events]
        assert kinds[0] == "meta" and kinds[-1] == "done"
        assert "segment" in kinds and "blocked" in kinds
        assert all(e["t_ms"] >= 0 for e in events)
        assert [e["t_ms"] for e in events] == sorted(e["t_ms"] for e in events)
        first = next(e for e in events if e["event"] == "segment")
        r = c.get(first["audio"]["opus"], headers={"Range": "bytes=0-9"})
        assert r.status_code == 206 and len(r.content) == 10
        assert c.get(events[-1]["manifest"]).status_code == 200
        assert c.get("/api/synthesize/999").status_code == 404


def test_first_segment_arrives_before_the_rest(tts_env, temp_db, monkeypatch):
    """Con un motor lento, el primer segmento llega antes de que termine la noticia."""
    from app.api import synthesize as api_synth
    from app.main import app
    from app.pipeline.tts import registry
    from app.pipeline.tts.fake import FakeEngine

    monkeypatch.setitem(registry.ENGINES, "fake", lambda: FakeEngine(delay_s=0.3))
    registry.reset_pools()
    api_synth.reset_synthesizers()
    nid = _add_news(temp_db, "Kemetsa ora. Kipatsi ora. Tsimatsi ora.")
    with TestClient(app) as c, c.stream("GET", f"/api/synthesize/{nid}") as r:
        events = [json.loads(line) for line in r.iter_lines() if line]
    segs = [e for e in events if e["event"] == "segment"]
    assert len(segs) == 3
    assert segs[0]["t_ms"] < events[-1]["t_ms"] - 500  # los otros dos tardan >= 0,6 s más


def test_limits_413_and_503(tts_env, temp_db, monkeypatch):
    from app.api import synthesize as api_synth
    from app.main import app

    nid = _add_news(temp_db)
    with TestClient(app) as c:
        monkeypatch.setenv("NA_MAX_NEWS_CHARS", "5")
        assert c.get(f"/api/synthesize/{nid}").status_code == 413
        monkeypatch.setenv("NA_MAX_NEWS_CHARS", "20000")
        monkeypatch.setenv("NA_MAX_CONCURRENT_SYNTH", "1")
        monkeypatch.setattr(api_synth, "_active", 1)
        r = c.get(f"/api/synthesize/{nid}")
        assert r.status_code == 503 and r.headers["retry-after"] == "2"
        monkeypatch.setattr(api_synth, "_active", 0)


def test_batch_cli(tts_env, temp_db, capsys):
    from app.batch.__main__ import main

    _add_news(temp_db)
    assert main(["build"]) == 2
    assert main(["build", "--all"]) == 0
    assert '"errors": 0' in capsys.readouterr().out
