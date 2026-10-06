"""Registro de motores TTS: el motor se elige con UN parámetro (``NA_TTS_ENGINE``).

Cada motor con estado (MMS carga un modelo y su hook guarda estado) se usa a través de un
``EnginePool`` de ``NA_TTS_WORKERS`` instancias: así se pueden atender varias síntesis a la vez
sin compartir una instancia entre hilos.
"""

from __future__ import annotations

import queue
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager

from app.config import get_settings
from app.pipeline.tts.base import TTSEngine

ENGINES: dict[str, Callable[[], TTSEngine]] = {}


def register(name: str):
    def deco(factory: Callable[[], TTSEngine]):
        ENGINES[name] = factory
        return factory

    return deco


@register("fake")
def _fake() -> TTSEngine:
    from app.pipeline.tts.fake import FakeEngine

    return FakeEngine()


@register("mms_vits")
def _mms() -> TTSEngine:
    from app.pipeline.tts.mms_vits import MmsVitsEngine

    return MmsVitsEngine()


@register("espeak_ng")
def _espeak() -> TTSEngine:
    from app.pipeline.tts.espeak import ESpeakEngine

    return ESpeakEngine()


def create_engine(name: str | None = None) -> TTSEngine:
    name = name or get_settings().tts_engine
    if name not in ENGINES:
        raise ValueError(f"Motor TTS desconocido: {name!r} (disponibles: {sorted(ENGINES)})")
    return ENGINES[name]()


class EnginePool:
    """Pool de instancias del mismo motor (una síntesis por instancia a la vez)."""

    def __init__(self, name: str, size: int):
        self.name = name
        self.size = max(1, size)
        self._free: queue.Queue[TTSEngine] = queue.Queue()
        self.engines = [create_engine(name) for _ in range(self.size)]
        for e in self.engines:
            self._free.put(e)
        self.cold_start_ms: list[float] = []

    def warmup(self) -> float:
        self.cold_start_ms = [e.warmup() for e in self.engines]
        return max(self.cold_start_ms) if self.cold_start_ms else 0.0

    @contextmanager
    def acquire(self) -> Iterator[TTSEngine]:
        engine = self._free.get()
        try:
            yield engine
        finally:
            self._free.put(engine)

    def info(self):
        return self.engines[0].info()


_pools: dict[tuple[str, int], EnginePool] = {}
_lock = threading.Lock()


def get_pool(name: str | None = None, size: int | None = None) -> EnginePool:
    s = get_settings()
    key = (name or s.tts_engine, size or s.tts_workers)
    with _lock:
        if key not in _pools:
            _pools[key] = EnginePool(*key)
        return _pools[key]


def reset_pools() -> None:
    with _lock:
        _pools.clear()
