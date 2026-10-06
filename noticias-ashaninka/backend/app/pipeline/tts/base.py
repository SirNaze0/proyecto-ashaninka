"""Interfaz abstracta de los motores TTS (tarea 2.1).

Todo motor intercambiable implementa ``TTSEngine``: ``info()``, ``warmup()`` y
``synthesize(text, seed)``. El motor se elige con un único parámetro (``NA_TTS_ENGINE``),
ver ``app.pipeline.tts.registry``.
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field

import numpy as np

SYNTHETIC_NOTICE = "Voz sintética generada por computadora; no es la voz de una persona."


@dataclass(frozen=True)
class EngineInfo:
    engine: str  # "mms_vits" | "espeak_ng" | "fake"
    model: str
    revision: str
    license: str
    commercial_use: bool
    dialect: str
    input_kind: str  # "text_tts" | "phonemes" | "text_es"
    sample_rate: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TokenDurations:
    """Duraciones que el motor usó realmente (solo motores que las exponen, p. ej. VITS).

    ``tokens``: secuencia de entrada del modelo (incluye los blancos intercalados).
    ``frames``: frames por token. ``hop_samples``: muestras por frame.
    ``char_times``: (inicio_s, fin_s) por carácter de ``text`` (el texto que recibió el motor).
    """

    text: str
    tokens: list[str]
    frames: list[int]
    hop_samples: int
    sample_rate: int
    char_times: list[tuple[float, float]]
    blank_rule: str = "mitad-y-mitad"

    @property
    def total_samples(self) -> int:
        return int(sum(self.frames)) * self.hop_samples

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AudioResult:
    wav: np.ndarray  # float32 mono
    sample_rate: int
    seed: int
    synth_ms: float
    durations: TokenDurations | None = None
    meta: dict = field(default_factory=dict)

    @property
    def duration_s(self) -> float:
        return len(self.wav) / self.sample_rate

    @property
    def rtf(self) -> float:
        return (self.synth_ms / 1000) / self.duration_s if self.duration_s else float("inf")


class TTSEngine(ABC):
    """Contrato de un motor TTS."""

    @abstractmethod
    def info(self) -> EngineInfo: ...

    @abstractmethod
    def warmup(self) -> float:
        """Carga el modelo (si hace falta) y devuelve el tiempo de carga en frío en ms."""

    @abstractmethod
    def synthesize(self, text: str, seed: int) -> AudioResult: ...

    def params(self) -> dict:
        """Parámetros que afectan al audio (entran en la clave de caché y en los metadatos)."""
        return {}


def derive_seed(text: str, engine: str, revision: str, adapter_id: str) -> int:
    """Semilla determinista por segmento: mismo texto + motor + revisión + adaptador = mismo audio."""
    h = hashlib.sha256(f"{text}\x1f{engine}\x1f{revision}\x1f{adapter_id}".encode()).digest()
    return int.from_bytes(h[:4], "big")


def chars_from_tokens(
    text: str, frames: list[int], layout: list[int | None] | bool
) -> list[tuple[float, float]]:
    """Reparte los frames de los tokens entre los caracteres de ``text``.

    ``layout``: por token, el índice del carácter que representa o ``None`` si es un blanco.
    Atajos: ``False`` = un token por carácter; ``True`` = intercalado estándar
    (blanco, c0, blanco, c1, …, blanco). Cada blanco se reparte mitad y mitad entre el carácter
    anterior y el siguiente (entero al único vecino si está en un extremo). Devuelve
    (frame_inicio, frame_fin) por carácter, contiguos y sin huecos.
    """
    n = len(text)
    if n == 0:
        return []
    if layout is False:
        layout = list(range(n))
    elif layout is True:
        layout = [None] * (2 * n + 1)
        layout[1::2] = list(range(n))
    if len(layout) != len(frames):
        raise ValueError(f"{len(frames)} tokens para un layout de {len(layout)}")
    if sorted(i for i in layout if i is not None) != list(range(n)):
        raise ValueError("el layout no cubre cada carácter exactamente una vez")
    char_frames = [0.0] * n
    for k, (idx, f) in enumerate(zip(layout, frames, strict=True)):
        if idx is not None:
            char_frames[idx] += f
            continue
        prev = next((layout[j] for j in range(k - 1, -1, -1) if layout[j] is not None), None)
        nxt = next((layout[j] for j in range(k + 1, len(layout)) if layout[j] is not None), None)
        if prev is not None and nxt is not None:
            char_frames[prev] += f / 2
            char_frames[nxt] += f / 2
        else:
            char_frames[prev if prev is not None else nxt] += f
    out, pos = [], 0.0
    for f in char_frames:
        out.append((pos, pos + f))
        pos += f
    return out
