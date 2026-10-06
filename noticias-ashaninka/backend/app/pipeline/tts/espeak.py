"""ESpeakEngine: línea base con eSpeak-NG (tarea 2.3). GPL-3.0, sin restricción comercial (R3).

Modo ``texto-es`` (el único habilitado ahora): eSpeak-NG lee el texto CANÓNICO del segmento con
la voz castellana. Es una línea base INGENUA ("un sintetizador genérico leyendo la ortografía
asháninka"), no un TTS asháninka.

Modo ``fonemas``: convierte la segmentación del G2P a la notación ``[[…]]`` de eSpeak, pero queda
DESHABILITADO mientras el inventario (P1) tenga entradas sin validar: no se usan fonemas
inventados.
"""

from __future__ import annotations

import io
import shutil
import subprocess
import time
from pathlib import Path

import numpy as np
import soundfile as sf

from app.config import G2P_RULES, get_settings
from app.pipeline.resources import get_resource
from app.pipeline.tts.base import SYNTHETIC_NOTICE, AudioResult, EngineInfo, TTSEngine

WINDOWS_DEFAULT = Path("C:/Program Files/eSpeak NG/espeak-ng.exe")


class ESpeakNotInstalled(FileNotFoundError):
    pass


class PhonemeModeDisabled(RuntimeError):
    pass


def find_espeak(configured: str | None = None) -> str | None:
    for candidate in (configured, shutil.which("espeak-ng")):
        if candidate and Path(candidate).exists():
            return str(candidate)
    if WINDOWS_DEFAULT.exists():
        return str(WINDOWS_DEFAULT)
    return None


class ESpeakEngine(TTSEngine):
    def __init__(
        self, mode: str = "texto-es", voice: str | None = None, rate: int = 150, pitch: int = 50
    ):
        s = get_settings()
        self.binary = find_espeak(s.espeak_path)
        self.mode = mode
        self.voice = voice or s.espeak_voice
        self.rate = rate
        self.pitch = pitch
        self._version: str | None = None

    def _require(self) -> str:
        if not self.binary:
            raise ESpeakNotInstalled(
                "eSpeak-NG no está instalado: instálalo (MSI oficial en Windows) o define "
                "NA_ESPEAK_PATH. Ver ./init.sh --with-tts"
            )
        return self.binary

    def version(self) -> str:
        if self._version is None:
            out = subprocess.run(
                [self._require(), "--version"], capture_output=True, text=True, check=True
            ).stdout
            # "eSpeak NG text-to-speech: 1.52.0  Data at: …"
            parts = out.split(":")
            self._version = parts[1].split()[0] if len(parts) > 1 else out.strip()
        return self._version

    def info(self) -> EngineInfo:
        return EngineInfo(
            engine="espeak_ng",
            model=f"eSpeak NG (voz {self.voice})",
            revision=self.version() if self.binary else "no instalado",
            license="GPL-3.0",
            commercial_use=True,
            dialect=f"ninguna: voz castellana '{self.voice}' leyendo ortografía asháninka "
            "(línea base ingenua)",
            input_kind="text_es" if self.mode == "texto-es" else "phonemes",
            sample_rate=22050,
        )

    def warmup(self) -> float:
        t0 = time.perf_counter()
        self.version()
        if self.mode == "fonemas":
            self._check_phoneme_mode()
        return (time.perf_counter() - t0) * 1000

    def params(self) -> dict:
        return {"mode": self.mode, "voice": self.voice, "rate": self.rate, "pitch": self.pitch}

    def _check_phoneme_mode(self) -> None:
        inv = get_resource(G2P_RULES / "inventory.yaml")
        pending = [e.id for e in inv.entries if e.status != "validado"]
        if pending or not inv.entries:
            raise PhonemeModeDisabled(
                f"Modo fonemas deshabilitado: {len(pending)} entradas del inventario sin validar "
                "(P1). No se usan fonemas inventados."
            )

    def synthesize(self, text: str, seed: int) -> AudioResult:
        if not text.strip():
            raise ValueError("ESpeakEngine: texto vacío")
        if self.mode == "fonemas":
            self._check_phoneme_mode()
        binary = self._require()
        t0 = time.perf_counter()
        proc = subprocess.run(
            [
                binary,
                "-v",
                self.voice,
                "-s",
                str(self.rate),
                "-p",
                str(self.pitch),
                "-b",
                "1",
                "--stdout",
            ],
            input=text.encode("utf-8"),
            capture_output=True,
            check=True,
        )
        wav, sr = sf.read(io.BytesIO(proc.stdout), dtype="float32")
        if wav.ndim > 1:
            wav = wav.mean(axis=1)
        synth_ms = (time.perf_counter() - t0) * 1000
        return AudioResult(
            wav=np.ascontiguousarray(wav, dtype=np.float32),
            sample_rate=sr,
            seed=seed,
            synth_ms=synth_ms,
            durations=None,
            meta={"aviso": SYNTHETIC_NOTICE, **self.params()},
        )
