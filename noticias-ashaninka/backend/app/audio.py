"""Codificación de audio (tarea 2.5): Opus en OGG (principal) y MP3 (respaldo) con soundfile.

libsndfile 1.2.2 no permite fijar la tasa de bits de Opus directamente: se controla con
``compression_level`` (0 = máxima calidad). La relación nivel -> kbps se midió el 2026-10-06
sobre voz de mms-tts-cni a 16 kHz mono (tabla ``OPUS_LEVELS``). La tasa REAL de cada archivo se
calcula y se guarda en sus metadatos: es la cifra que se reporta, no la objetivo.
"""

from __future__ import annotations

import io
import os
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

# (compression_level, kbps medidos) para OGG/Opus, 16 kHz mono, libsndfile 1.2.2
OPUS_LEVELS = [(0.7, 83.5), (0.8, 58.4), (0.9, 26.4), (1.0, 6.8)]
MP3_LEVEL = 0.5  # ~30 kbps medidos (MPEG-2 Layer III a 16 kHz)


def opus_level_for(kbps: float) -> float:
    """Interpola el nivel de compresión que da aproximadamente ``kbps``."""
    pts = sorted(OPUS_LEVELS, key=lambda p: -p[1])  # kbps descendente
    if kbps >= pts[0][1]:
        return pts[0][0]
    if kbps <= pts[-1][1]:
        return pts[-1][0]
    for (l1, k1), (l2, k2) in zip(pts, pts[1:], strict=False):
        if k2 <= kbps <= k1:
            return round(l1 + (l2 - l1) * (k1 - kbps) / (k1 - k2), 4)
    return 0.9  # pragma: no cover


def encode(wav: np.ndarray, sr: int, fmt: str, opus_kbps: float = 24) -> bytes:
    buf = io.BytesIO()
    if fmt == "opus":
        sf.write(
            buf, wav, sr, format="OGG", subtype="OPUS", compression_level=opus_level_for(opus_kbps)
        )
    elif fmt == "mp3":
        sf.write(buf, wav, sr, format="MP3", subtype="MPEG_LAYER_III", compression_level=MP3_LEVEL)
    elif fmt == "wav":
        sf.write(buf, wav, sr, format="WAV", subtype="PCM_16")
    else:
        raise ValueError(f"formato no admitido: {fmt}")
    return buf.getvalue()


def kbps(data: bytes, duration_s: float) -> float:
    return round(len(data) * 8 / duration_s / 1000, 2) if duration_s else 0.0


def atomic_write(path: Path, data: bytes) -> None:
    """Escribe en un temporal y lo renombra: nunca queda un archivo a medias en la caché."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
