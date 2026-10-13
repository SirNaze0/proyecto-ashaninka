"""Tareas 3.7 y 3.8 — clips MP4 del avatar y métricas de sincronía labial.

Entrada: ``frontend/scripts/capture.mjs`` deja en ``eval/fase3/out/capture/`` los fotogramas JPEG
(25 fps) y la señal de apertura de la boca renderizada (50 Hz) de cada oración seleccionada, y
``eval.fase3.alignment`` deja ``ctc_spans.json``. Aquí se arman los MP4 con el audio de la oración
y se calculan, según ``docs/metrics.md``:

* desfase directo audio-boca (criterio principal, ≤ 80 ms), con los estimadores de
  ``sync_estimators`` y su calibración con desplazamientos conocidos;
* LSE-D y LSE-C con SyncNet, más un control negativo con el audio de otro clip.

Uso: uv run python -m eval.fase3.lipsync
"""

from __future__ import annotations

import json
import random
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf
from app.pipeline.viseme.track import sample

from eval.fase3 import syncnet
from eval.fase3.prepare import OUT, ROOT, STATIC
from eval.fase3.sync_estimators import (  # noqa: F401  (se reexportan para las pruebas)
    HZ,
    calibrar,
    cargar_clips,
    curva_xcorr,
    envelope,
    lag_xcorr,
    pico,
)

CAPTURE = OUT / "capture"
CLIPS = OUT / "clips"
RESULT = ROOT / "eval" / "results" / "fase_3_lipsync.json"
SEED = 20261012
CRITERIO_MS = 80


def audio_wav(news_id: int) -> tuple[np.ndarray, int, Path]:
    m = json.loads((STATIC / "news" / str(news_id) / "manifest.json").read_text("utf-8"))
    wav, sr = sf.read(STATIC / m["segments"][0]["audio"]["opus"].removeprefix("/static/"))
    path = CLIPS / f"news_{news_id}.wav"
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, wav, sr, subtype="PCM_16")
    return wav, sr, path


def build_mp4(news_id: int, wav_path: Path) -> Path:
    out = CLIPS / f"news_{news_id}.mp4"
    frames = CAPTURE / "frames" / str(news_id) / "%05d.jpg"
    cmd = [
        syncnet.ffmpeg_exe(),
        "-y",
        "-loglevel",
        "error",
        "-framerate",
        "25",
        "-i",
        str(frames),
        "-i",
        str(wav_path),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-crf",
        "18",
        "-c:a",
        "aac",
        "-shortest",
        str(out),
    ]
    subprocess.run(cmd, check=True)
    return out


def resumen(v: list[float]) -> dict:
    a = np.asarray(v, dtype=float)
    return {
        "n": int(a.size),
        "media": round(float(a.mean()), 2),
        "mediana": round(float(np.median(a)), 2),
        "p95": round(float(np.percentile(a, 95)), 2),
        "min": round(float(a.min()), 2),
        "max": round(float(a.max()), 2),
    }


def agrupado_con_ic(curvas: list[tuple[np.ndarray, np.ndarray]], rng: random.Random) -> dict:
    """Desfase sistemático: pico de la curva media de todos los clips, con IC 95 % por bootstrap."""
    lags = curvas[0][0]
    medias = np.mean([c[1] for c in curvas], axis=0)
    lag, corr = pico(lags, medias)
    boot = []
    for _ in range(1000):
        idx = rng.choices(range(len(curvas)), k=len(curvas))
        boot.append(pico(lags, np.mean([curvas[i][1] for i in idx], axis=0))[0])
    return {
        "lag_ms": round(lag, 1),
        "correlacion_en_el_pico": round(corr, 3),
        "ic95_ms": [
            round(float(np.percentile(boot, 2.5)), 1),
            round(float(np.percentile(boot, 97.5)), 1),
        ],
        "clips": len(curvas),
    }


def main() -> None:
    sel = json.loads((OUT / "selection.json").read_text("utf-8"))
    ids = [s["news_id"] for s in sel]
    spans = json.loads((OUT / "ctc_spans.json").read_text("utf-8"))
    mp4s, wavs = {}, {}
    for nid in ids:
        _, _, wavs[nid] = audio_wav(nid)
        mp4s[nid] = build_mp4(nid, wavs[nid])
    clips = cargar_clips(ids, lambda n: sf.read(wavs[n])[:2], spans)
    cal = calibrar(clips)

    filas = []
    for nid, (env, plant, mouth) in zip(ids, clips, strict=True):
        seg = json.loads((STATIC / "news" / str(nid) / "seg_000.json").read_text("utf-8"))
        kf = seg["visemes"]["keyframes"]
        pista = np.array([sum(sample(kf, k / HZ)[:5]) for k in range(len(mouth))])
        l_e, r_e = lag_xcorr(env, mouth)
        l_p, r_p = lag_xcorr(plant, mouth)
        filas.append(
            {
                "news_id": nid,
                "duracion_s": round(len(mouth) / HZ, 2),
                "energia_ms": round(l_e, 1),
                "energia_corr": round(r_e, 3),
                "plantilla_ms": round(l_p, 1),
                "plantilla_corr": round(r_p, 3),
                "pista_plantilla_ms": round(lag_xcorr(plant, pista)[0], 1),
            }
        )
        print(f"[3.8] noticia {nid}: energía {l_e:+.0f} ms · plantilla {l_p:+.0f} ms (r={r_p:.2f})")
    rng = random.Random(SEED)
    agrup = {
        "energia": agrupado_con_ic([curva_xcorr(c[0], c[2]) for c in clips], rng),
        "plantilla": agrupado_con_ic([curva_xcorr(c[1], c[2]) for c in clips], rng),
    }

    model, mod = syncnet.load_model()
    _, weights_sha = syncnet.ensure_syncnet()
    for i, nid in enumerate(ids):
        filas[i]["sync"] = syncnet.evaluate(model, mod, mp4s[nid], wavs[nid])
        otro = ids[(i + 1) % len(ids)]  # control negativo: audio de otro clip
        filas[i]["sync_control"] = syncnet.evaluate(model, mod, mp4s[nid], wavs[otro])
        s, c = filas[i]["sync"], filas[i]["sync_control"]
        print(
            f"[3.8] noticia {nid}: LSE-D {s['lse_d']:.2f} LSE-C {s['lse_c']:.2f} "
            f"(control {c['lse_d']:.2f}/{c['lse_c']:.2f})"
        )
    por_clip = {k: [abs(f[k]) for f in filas] for k in ("energia_ms", "plantilla_ms")}
    res = {
        "tarea": "3.7-3.8",
        "clips": len(filas),
        "split": "dev",
        "desfase_directo": {
            "definicion": "docs/metrics.md (estimadores y calibración)",
            "criterio_ms": CRITERIO_MS,
            "calibracion_con_desplazamientos_conocidos": cal,
            "por_clip_abs_ms": {k: resumen(v) for k, v in por_clip.items()},
            "por_clip_sobre_80ms": {
                k: sum(x > CRITERIO_MS for x in v) for k, v in por_clip.items()
            },
            "sistematico_agrupado": agrup,
            "pista_sin_render_plantilla_abs_ms": resumen(
                [abs(f["pista_plantilla_ms"]) for f in filas]
            ),
        },
        "syncnet": {
            "pesos_sha256": weights_sha,
            "commit_codigo": syncnet.COMMIT,
            "lse_d": resumen([f["sync"]["lse_d"] for f in filas]),
            "lse_c": resumen([f["sync"]["lse_c"] for f in filas]),
            "control_negativo_lse_d": resumen([f["sync_control"]["lse_d"] for f in filas]),
            "control_negativo_lse_c": resumen([f["sync_control"]["lse_c"] for f in filas]),
            "offset_fotogramas": resumen([f["sync"]["offset_fotogramas"] for f in filas]),
        },
        "por_clip": filas,
    }
    RESULT.write_text(json.dumps(res, indent=2, ensure_ascii=False), "utf-8")
    top = {k: res[k] for k in ("desfase_directo", "syncnet")}
    print(json.dumps(top, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
