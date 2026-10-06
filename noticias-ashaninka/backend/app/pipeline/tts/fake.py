"""FakeEngine: tono determinista para pruebas sin modelos (tarea 2.1).

Duración proporcional al texto (80 ms por carácter), frecuencia derivada de la
semilla. Expone duraciones por carácter como lo haría VITS (sin blancos), para probar la
cadena completa. ``delay_s`` simula el tiempo de síntesis en las pruebas de streaming.
"""

from __future__ import annotations

import time

import numpy as np

from app.pipeline.tts.base import (
    SYNTHETIC_NOTICE,
    AudioResult,
    EngineInfo,
    TokenDurations,
    TTSEngine,
    chars_from_tokens,
)

SR = 16000
HOP = 160  # 10 ms por frame
FRAMES_PER_CHAR = 8


class FakeEngine(TTSEngine):
    def __init__(self, delay_s: float = 0.0):
        self.delay_s = delay_s

    def info(self) -> EngineInfo:
        return EngineInfo(
            engine="fake",
            model="tono-sintetico",
            revision="1",
            license="MIT (código del proyecto)",
            commercial_use=True,
            dialect="no aplica (motor de pruebas)",
            input_kind="text_tts",
            sample_rate=SR,
        )

    def warmup(self) -> float:
        return 0.0

    def params(self) -> dict:
        return {"frames_per_char": FRAMES_PER_CHAR, "hop": HOP}

    def synthesize(self, text: str, seed: int) -> AudioResult:
        if not text.strip():
            raise ValueError("FakeEngine: texto vacío")
        t0 = time.perf_counter()
        if self.delay_s:
            time.sleep(self.delay_s)
        frames = [FRAMES_PER_CHAR] * len(text)
        n_samples = sum(frames) * HOP
        freq = 180 + seed % 200
        t = np.arange(n_samples, dtype=np.float32) / SR
        wav = (0.2 * np.sin(2 * np.pi * freq * t)).astype(np.float32)
        spans = chars_from_tokens(text, frames, False)
        durations = TokenDurations(
            text=text,
            tokens=list(text),
            frames=frames,
            hop_samples=HOP,
            sample_rate=SR,
            char_times=[(a * HOP / SR, b * HOP / SR) for a, b in spans],
            blank_rule="sin blancos",
        )
        synth_ms = (time.perf_counter() - t0) * 1000
        return AudioResult(
            wav=wav,
            sample_rate=SR,
            seed=seed,
            synth_ms=synth_ms,
            durations=durations,
            meta={"aviso": SYNTHETIC_NOTICE},
        )
