"""MmsVitsEngine: facebook/mms-tts-cni con captura de duraciones (tarea 2.2).

Duraciones (§4 del plan). En ``transformers`` 5.18, ``VitsModel.forward`` calcula::

    log_duration = duration_predictor(..., reverse=True, noise_scale=noise_scale_duration)
    duration = ceil(exp(log_duration) * input_padding_mask * (1 / speaking_rate))
    len(waveform) = sum(duration) * prod(upsample_rates)

Un *forward hook* sobre ``model.duration_predictor`` captura ``log_duration`` ya con el ruido
aplicado (el valor que el modelo usa). Se repite la fórmula con la misma máscara y velocidad, y
se VERIFICA que ``sum(frames) * hop == len(waveform)``; si no coincide se lanza un error (no se
devuelven tiempos sin verificar).

Tokenización (hallazgo de la Fase 2). El token de relleno/blanco de MMS es la letra ``"a"``
(id 0). ``VitsTokenizer`` (igual en transformers 4.46 y 5.18) la trata como token especial: cada
``a`` del texto se toma suelta, sin blancos alrededor, y el intercalado se rompe cuando hay
``aa`` o una ``a`` al inicio/final (``"a"`` -> ``[0]`` en vez de ``[0, 0, 0]``). Hay dos modos:

* ``manual``: intercalado estándar de VITS ``[0, c1, 0, c2, …, 0]`` (lo que describe el propio
  ``VitsTokenizer._tokenize``);
* ``hf``: la salida de ``VitsTokenizer`` tal cual.

El modo se elige con ``NA_MMS_TOKENIZATION`` y queda en los metadatos; el experimento de la
tarea 2.2b decide cuál se usa por defecto.

Entrada: solo ``text_tts`` ya validado (2f). Antes de sintetizar se comprueba que la salida
normalizada de ``VitsTokenizer`` sea idéntica al texto (regresión R13): el tokenizador nunca
debe eliminar caracteres en silencio.
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path

import numpy as np

from app.config import MMS_TTS_REVISION, get_settings
from app.pipeline.tts.base import (
    SYNTHETIC_NOTICE,
    AudioResult,
    EngineInfo,
    TokenDurations,
    TTSEngine,
    chars_from_tokens,
)


class TokenizerDropError(ValueError):
    """El tokenizador eliminaría caracteres del texto (R13)."""


class DurationMismatchError(RuntimeError):
    """Las duraciones capturadas no reproducen la longitud del audio."""


class MmsVitsEngine(TTSEngine):
    REPO = "facebook/mms-tts-cni"

    def __init__(
        self,
        model_dir: Path | None = None,
        torch_threads: int | None = None,
        tokenization: str | None = None,
    ):
        s = get_settings()
        self.tokenization = tokenization or os.getenv("NA_MMS_TOKENIZATION", "manual")
        if self.tokenization not in {"manual", "hf"}:
            raise ValueError(f"NA_MMS_TOKENIZATION desconocida: {self.tokenization}")
        self.model_dir = model_dir or s.models_dir / "facebook__mms-tts-cni"
        self.torch_threads = s.torch_threads if torch_threads is None else torch_threads
        self._model = None
        self._tok = None
        self._lock = threading.Lock()  # el hook guarda estado: una síntesis a la vez por instancia
        self._captured = None

    # ------------------------------------------------------------------ carga
    def info(self) -> EngineInfo:
        return EngineInfo(
            engine="mms_vits",
            model=self.REPO,
            revision=MMS_TTS_REVISION,
            license="CC-BY-NC-4.0",
            commercial_use=False,
            dialect="no documentada (la de los datos de entrenamiento de MMS)",
            input_kind="text_tts",
            sample_rate=16000,
        )

    def warmup(self) -> float:
        if self._model is not None:
            return 0.0
        if not (self.model_dir / "model.safetensors").exists():
            raise FileNotFoundError(
                f"Falta el modelo en {self.model_dir}: ejecuta ./init.sh --with-tts"
            )
        t0 = time.perf_counter()
        import torch
        from transformers import VitsModel, VitsTokenizer

        if self.torch_threads:
            torch.set_num_threads(self.torch_threads)
        self._torch = torch
        self._tok = VitsTokenizer.from_pretrained(self.model_dir)
        self._model = VitsModel.from_pretrained(self.model_dir).eval()
        self._model.duration_predictor.register_forward_hook(self._hook)
        cfg = self._model.config
        self.hop = int(np.prod(cfg.upsample_rates))
        self.sample_rate = int(cfg.sampling_rate)
        return (time.perf_counter() - t0) * 1000

    def _hook(self, _module, _inputs, output):
        self._captured = output.detach().clone()

    def params(self) -> dict:
        if self._model is None:
            return {"speaking_rate": None}
        c = self._model.config
        return {
            "speaking_rate": c.speaking_rate,
            "noise_scale": c.noise_scale,
            "noise_scale_duration": c.noise_scale_duration,
            "torch_threads": self.torch_threads or "defecto",
            "tokenization": self.tokenization,
        }

    # ------------------------------------------------------------------ síntesis
    def check_tokenizer(self, text: str) -> None:
        prepared = self._tok.prepare_for_tokenization(text, normalize=True)[0]
        if prepared != text:
            raise TokenizerDropError(
                f"VitsTokenizer alteraría el texto: {text!r} -> {prepared!r} (R13)"
            )

    def encode(self, text: str):
        """Devuelve (inputs del modelo, layout token->carácter) según el modo de tokenización."""
        torch = self._torch
        vocab = self._tok.get_vocab()
        if self.tokenization == "manual":
            ids, layout = [0], [None]
            for i, ch in enumerate(text):
                ids += [vocab[ch], 0]
                layout += [i, None]
        else:
            ids = self._tok(text)["input_ids"]
            layout = hf_layout(text)
            if len(layout) != len(ids):
                raise RuntimeError(
                    f"layout HF inesperado para {text!r}: {len(layout)} != {len(ids)}"
                )
        inputs = {
            "input_ids": torch.tensor([ids], dtype=torch.long),
            "attention_mask": torch.ones((1, len(ids)), dtype=torch.long),
        }
        return inputs, layout

    def synthesize(self, text: str, seed: int) -> AudioResult:
        self.warmup()
        if not text.strip():
            raise ValueError("MmsVitsEngine: texto vacío")
        self.check_tokenizer(text)
        torch = self._torch
        with self._lock:
            t0 = time.perf_counter()
            inputs, layout = self.encode(text)
            torch.manual_seed(seed)
            self._captured = None
            with torch.no_grad():
                out = self._model(**inputs)
            wav = out.waveform[0].numpy().astype(np.float32)
            synth_ms = (time.perf_counter() - t0) * 1000
            log_duration = self._captured
        durations = self._durations(text, inputs, layout, log_duration, len(wav))
        return AudioResult(
            wav=wav,
            sample_rate=self.sample_rate,
            seed=seed,
            synth_ms=synth_ms,
            durations=durations,
            meta={"aviso": SYNTHETIC_NOTICE, **self.params()},
        )

    def _durations(self, text, inputs, layout, log_duration, n_samples: int) -> TokenDurations:
        if log_duration is None:
            raise DurationMismatchError("El hook no capturó log_duration")
        torch = self._torch
        mask = inputs["attention_mask"].unsqueeze(1).to(log_duration.dtype)  # (1, 1, T)
        length_scale = 1.0 / self._model.config.speaking_rate
        frames = torch.ceil(torch.exp(log_duration) * mask * length_scale)[0, 0].long().tolist()
        total = max(sum(frames), 1) * self.hop
        if total != n_samples:
            raise DurationMismatchError(
                f"sum(frames)*hop={total} != len(waveform)={n_samples} para {text!r}"
            )
        ids = inputs["input_ids"][0].tolist()
        tokens = [self._tok.convert_ids_to_tokens(i) for i in ids]
        spans = chars_from_tokens(text, frames, layout)
        sec = self.hop / self.sample_rate
        return TokenDurations(
            text=text,
            tokens=tokens,
            frames=frames,
            hop_samples=self.hop,
            sample_rate=self.sample_rate,
            char_times=[(round(a * sec, 5), round(b * sec, 5)) for a, b in spans],
            blank_rule=f"mitad-y-mitad; tokenización {self.tokenization}",
        )


def hf_layout(text: str) -> list[int | None]:
    """Reproduce la disposición que produce ``VitsTokenizer``: el texto se parte en cada ``a``
    (token especial, va suelto) y cada tramo sin ``a`` se intercala con blancos."""
    layout: list[int | None] = []
    i = 0
    while i < len(text):
        if text[i] == "a":
            layout.append(i)
            i += 1
            continue
        j = i
        while j < len(text) and text[j] != "a":
            j += 1
        layout.append(None)
        for k in range(i, j):
            layout += [k, None]
        i = j
    return layout
