"""Modo bajo demanda (tarea 2.7): streaming NDJSON por oración.

``GET /api/synthesize/{news_id}?engine=…`` emite, en orden:
  {"event": "meta", …}                      avisos, motor y número de segmentos
  {"event": "segment", …} | {"event": "blocked", …}   uno por oración, en cuanto su audio
                                            está escrito en la caché (o reutilizado)
  {"event": "done", …}
Cada evento lleva ``t_ms`` (ms desde que llegó la solicitud): el ``t_ms`` del primer evento
``segment`` es el TTFA del servidor (definición en docs/metrics.md).

La síntesis (CPU) corre en hilos con ``asyncio.to_thread``; el pool limita las síntesis
simultáneas a ``NA_TTS_WORKERS`` y las solicitudes activas se limitan a
``NA_MAX_CONCURRENT_SYNTH`` (503 + Retry-After al superarlo; nada de colas infinitas).
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from app.batch.service import Synthesizer, ensure_processed
from app.config import get_settings
from app.db.models import News
from app.db.session import get_engine
from app.pipeline.tts.registry import get_pool

router = APIRouter(prefix="/api/synthesize", tags=["synthesize"])

_active = 0
_active_lock = threading.Lock()
_synths: dict[str, Synthesizer] = {}
_synth_lock = threading.Lock()


def get_synthesizer(engine: str | None) -> Synthesizer:
    name = engine or get_settings().tts_engine
    with _synth_lock:
        if name not in _synths:
            _synths[name] = Synthesizer(get_pool(name))
        return _synths[name]


def reset_synthesizers() -> None:
    with _synth_lock:
        _synths.clear()


def _line(obj: dict) -> bytes:
    return (json.dumps(obj, ensure_ascii=False) + "\n").encode()


async def _stream(news_id: int, synth: Synthesizer, t0: float) -> AsyncIterator[bytes]:
    global _active
    try:
        with Session(get_engine()) as session:
            news = session.get(News, news_id)
            await asyncio.to_thread(ensure_processed, session, news)
            segments = list(news.segments)
            adapter_id = next((s.adapter_id for s in segments if s.adapter_id), "")
            ms = lambda: round((time.perf_counter() - t0) * 1000, 2)  # noqa: E731
            yield _line(
                {
                    "event": "meta",
                    "t_ms": ms(),
                    "news_id": news_id,
                    "segments": len(segments),
                    "engine": synth.engine_ref(adapter_id).model_dump(),
                    "notices": synth.notices().model_dump(),
                }
            )
            manifest_segs = []
            for seg in segments:
                if not seg.tts_ready:
                    ms_seg = synth.manifest_segment(seg, None, None)
                    manifest_segs.append(ms_seg)
                    yield _line({"event": "blocked", "t_ms": ms(), **ms_seg.model_dump()})
                    continue
                audio = await asyncio.to_thread(
                    synth.synthesize_text, synth.text_for(seg), seg.adapter_id
                )
                timings = synth.write_segment(session, news, seg, audio)
                ms_seg = synth.manifest_segment(seg, audio, timings)
                manifest_segs.append(ms_seg)
                yield _line(
                    {
                        "event": "segment",
                        "t_ms": ms(),
                        "reused": audio.reused,
                        **ms_seg.model_dump(),
                    }
                )
            synth.write_manifest(news, manifest_segs, adapter_id)
            session.commit()
            yield _line(
                {"event": "done", "t_ms": ms(), "manifest": f"/static/news/{news_id}/manifest.json"}
            )
    finally:
        with _active_lock:
            _active -= 1


@router.get("/{news_id}")
async def synthesize(news_id: int, engine: str | None = None) -> StreamingResponse:
    global _active
    t0 = time.perf_counter()
    s = get_settings()
    with Session(get_engine()) as session:
        news = session.get(News, news_id)
        if news is None:
            raise HTTPException(404, f"No existe la noticia {news_id}")
        if len(news.cuerpo_cni) > s.max_news_chars:
            raise HTTPException(413, f"La noticia supera {s.max_news_chars} caracteres")
    with _active_lock:
        if _active >= s.max_concurrent_synth:
            raise HTTPException(
                503, "Demasiadas síntesis simultáneas", headers={"Retry-After": "2"}
            )
        _active += 1
    try:
        synth = await asyncio.to_thread(get_synthesizer, engine)
    except Exception:
        with _active_lock:
            _active -= 1
        raise
    return StreamingResponse(_stream(news_id, synth, t0), media_type="application/x-ndjson")
