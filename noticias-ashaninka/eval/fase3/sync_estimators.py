"""Estimadores del desfase audio-boca (tarea 3.8) y su calibración con desplazamientos conocidos.

Convención: lag positivo = la boca va DESPUÉS del audio.

* ``energia``: correlación cruzada por clip entre la envolvente RMS del audio y la apertura de la
  boca renderizada. Es el método definido ANTES de medir (``docs/metrics.md``).
* ``plantilla``: correlación cruzada por clip entre la apertura de la boca y una plantilla de
  campanas gaussianas en los centros de las vocales según el alineador CTC (independiente de
  VITS y de las duraciones del sistema). Se añadió tras ver que ``energia`` no discrimina.
* ``agrupado``: promedio de las curvas de correlación de todos los clips (``energia`` o
  ``plantilla``); estima el desfase SISTEMÁTICO con mucho menos ruido que el de cada clip.

``calibrar`` aplica a la señal de la boca desplazamientos CONOCIDOS y mide cuánto se equivoca
cada estimador. Es la única forma de saber qué precisión tiene realmente el método, y no depende
de cuál sea el desfase verdadero del sistema.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable

import numpy as np
import soundfile as sf

from eval.fase3.prepare import OUT

HZ = 50
MAX_LAG_S = 0.3
WIN_S = 0.04
SIGMA_S = 0.04
VOCALES = "aeio"


def envelope(wav: np.ndarray, sr: int, n: int, hz: int = HZ, win_s: float = WIN_S) -> np.ndarray:
    """RMS del audio en ``n`` instantes k/hz, con ventana centrada de ``win_s``."""
    half = int(win_s * sr / 2)
    out = np.zeros(n)
    for k in range(n):
        c = int(k / hz * sr)
        seg = wav[max(0, c - half) : c + half]
        out[k] = float(np.sqrt(np.mean(seg**2))) if len(seg) else 0.0
    return out


def curva_xcorr(
    audio: np.ndarray, mouth: np.ndarray, hz: int = HZ, max_lag_s: float = MAX_LAG_S
) -> tuple[np.ndarray, np.ndarray]:
    """Correlación normalizada para cada lag (en muestras) de -max a +max."""
    a = (audio - audio.mean()) / (audio.std() or 1.0)
    m = (mouth - mouth.mean()) / (mouth.std() or 1.0)
    n, max_lag = len(a), int(max_lag_s * hz)
    lags = np.arange(-max_lag, max_lag + 1)
    corr = np.zeros(len(lags))
    for i, lag in enumerate(lags):
        x, y = (a[: n - lag], m[lag:]) if lag >= 0 else (a[-lag:], m[: n + lag])
        corr[i] = float(np.mean(x * y)) if len(x) else 0.0
    return lags, corr


def pico(lags: np.ndarray, corr: np.ndarray, hz: int = HZ) -> tuple[float, float]:
    """(lag en ms, correlación) del máximo, refinado con una parábola."""
    j = int(np.argmax(corr))
    frac = 0.0
    if 0 < j < len(corr) - 1:
        c0, c1, c2 = corr[j - 1], corr[j], corr[j + 1]
        den = c0 - 2 * c1 + c2
        frac = 0.5 * (c0 - c2) / den if den else 0.0
    return float((lags[j] + frac) / hz * 1000), float(corr[j])


def lag_xcorr(
    audio: np.ndarray, mouth: np.ndarray, hz: int = HZ, max_lag_s: float = MAX_LAG_S
) -> tuple[float, float]:
    return pico(*curva_xcorr(audio, mouth, hz, max_lag_s), hz=hz)


def plantilla_vocales(texto: str, spans: list, n: int, hz: int = HZ, sigma_s: float = SIGMA_S):
    """Campanas gaussianas en el centro CTC de cada vocal; 0 si no hay vocales con intervalo."""
    t = np.arange(n) / hz
    y = np.zeros(n)
    for ch, sp in zip(texto, spans, strict=True):
        if ch in VOCALES and sp is not None:
            y += np.exp(-0.5 * ((t - (sp[0] + sp[1]) / 2) / sigma_s) ** 2)
    return y


def desplazar(x: np.ndarray, ms: float, hz: int = HZ) -> np.ndarray:
    """Retrasa la señal ``ms`` milisegundos (interpolación lineal; repite el primer valor)."""
    t = np.arange(len(x))
    return np.interp(t - ms / 1000 * hz, t, x)


Clip = tuple[np.ndarray, np.ndarray, np.ndarray]  # (referencia de audio, plantilla, boca)


def estimadores(clips: list[Clip]) -> dict[str, Callable[[list[np.ndarray]], list[float]]]:
    """Cada estimador recibe la lista de señales de boca y devuelve un lag (ms) por clip."""

    def por_clip(idx: int):
        return lambda bocas: [lag_xcorr(c[idx], m)[0] for c, m in zip(clips, bocas, strict=True)]

    def agrupado(idx: int):
        def f(bocas):
            curvas = [curva_xcorr(c[idx], m) for c, m in zip(clips, bocas, strict=True)]
            lag = pico(curvas[0][0], np.mean([c[1] for c in curvas], axis=0))[0]
            return [lag] * len(bocas)

        return f

    return {
        "energia": por_clip(0),
        "plantilla": por_clip(1),
        "energia_agrupado": agrupado(0),
        "plantilla_agrupado": agrupado(1),
    }


def calibrar(clips: list[Clip], desplazamientos_ms=(-80, -40, 40, 80)) -> dict:
    """Precisión de cada estimador con desplazamientos conocidos.

    El error es RELATIVO: ``(lag con desplazamiento d) - (lag sin desplazar) - d``. Así no depende
    de cuál sea el desfase verdadero del sistema (que es justo lo que se quiere medir), solo de
    si el estimador sigue un desplazamiento conocido.
    """
    res: dict[str, dict] = {}
    for nombre, est in estimadores(clips).items():
        base = np.asarray(est([c[2] for c in clips]))
        por_desp = {}
        for d in desplazamientos_ms:
            err = np.abs(np.asarray(est([desplazar(c[2], d) for c in clips])) - base - d)
            por_desp[str(d)] = {
                "mae_ms": round(float(err.mean()), 1),
                "max_ms": round(float(err.max()), 1),
            }
        res[nombre] = {
            "por_desplazamiento": por_desp,
            "mae_global_ms": round(float(np.mean([v["mae_ms"] for v in por_desp.values()])), 1),
            "max_global_ms": round(float(max(v["max_ms"] for v in por_desp.values())), 1),
        }
    return res


def cargar_clips(ids: list[int], audio_loader, spans_ctc: dict) -> list[Clip]:
    out = []
    for nid in ids:
        sig = json.loads((OUT / "capture" / "signals" / f"news_{nid}.json").read_text("utf-8"))
        mouth = np.asarray(sig["signal"])
        wav, sr = audio_loader(nid)
        env = envelope(wav, sr, len(mouth))
        sp = spans_ctc[str(nid)]
        out.append((env, plantilla_vocales(sp["texto"], sp["spans"], len(mouth)), mouth))
    return out


def _audio(nid: int):
    wav, sr = sf.read(OUT / "clips" / f"news_{nid}.wav")
    return (wav if wav.ndim == 1 else wav[:, 0]), sr


if __name__ == "__main__":
    if sys.argv[1:] != ["calibrar"]:
        raise SystemExit(__doc__)
    ids = [s["news_id"] for s in json.loads((OUT / "selection.json").read_text("utf-8"))]
    spans = json.loads((OUT / "ctc_spans.json").read_text("utf-8"))
    cal = calibrar(cargar_clips(ids, _audio, spans))
    (OUT / "calibracion.json").write_text(json.dumps(cal, indent=1, ensure_ascii=False), "utf-8")
    for k, v in cal.items():
        print(f"{k:20s} MAE {v['mae_global_ms']:6.1f} ms   máx {v['max_global_ms']:6.1f} ms")
