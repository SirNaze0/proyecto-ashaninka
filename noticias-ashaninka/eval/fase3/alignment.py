"""Tarea 3.2 — Validación de la alineación de VITS contra un alineador forzado independiente.

Compara los tiempos por palabra que salen de las duraciones de VITS (``durations.char_times`` de
``seg_NNN.json``) con la alineación forzada CTC de ``mms-1b-all`` sobre el MISMO audio
(Opus ya codificado, tal como lo oye el usuario). Sobre las oraciones de **dev** elegidas en
``prepare.py``; el split test no se usa.

Métricas definidas antes de medir (docs/metrics.md, Fase 3): error con signo y absoluto de
inicio, fin y centro de palabra (ms), y fracción dentro de 50 y 80 ms. Limitación de CTC en
``eval/fase3/ctc.py``.

Uso: uv run python -m eval.fase3.alignment
"""

from __future__ import annotations

import json
import random

import numpy as np
import soundfile as sf

from eval.fase2.tokenization.run import load_asr
from eval.fase3.ctc import error_stats, forced_align, words_from_chars
from eval.fase3.prepare import OUT, ROOT, STATIC

STRIDE_S = 0.02  # wav2vec2: un fotograma cada 20 ms
RESULT = ROOT / "eval" / "results" / "fase_3_alineacion.json"
SEED = 20261012


def cargar_segmento(news_id: int, idx: int) -> tuple[dict, np.ndarray, int]:
    seg = json.loads((STATIC / "news" / str(news_id) / f"seg_{idx:03d}.json").read_text("utf-8"))
    manifest = json.loads((STATIC / "news" / str(news_id) / "manifest.json").read_text("utf-8"))
    opus = manifest["segments"][idx]["audio"]["opus"].removeprefix("/static/")
    wav, sr = sf.read(STATIC / opus, dtype="float32")
    return seg, wav, sr


def alinear_asr(torch, proc, asr, wav: np.ndarray, sr: int, texto: str):
    """Spans (s) por carácter de ``texto`` según CTC; None en los caracteres sin token."""
    if sr != 16000:
        raise ValueError("se esperaba audio de 16 kHz")
    inputs = proc(wav, sampling_rate=sr, return_tensors="pt")
    with torch.no_grad():
        logits = asr(**inputs).logits[0]
    lp = torch.log_softmax(logits, dim=-1).numpy()
    vocab = proc.tokenizer.get_vocab()
    ids, pos = [], []
    for i, ch in enumerate(texto):
        tok = vocab.get("|" if ch == " " else ch)
        if tok is not None:
            ids.append(tok)
            pos.append(i)
    spans = forced_align(lp, ids, blank=proc.tokenizer.pad_token_id)
    por_char: list[tuple[float, float] | None] = [None] * len(texto)
    for p, (a, b) in zip(pos, spans, strict=True):
        por_char[p] = (a * STRIDE_S, b * STRIDE_S)
    return por_char, len(texto) - len(ids)


def comparar(seg: dict, asr_spans: list) -> dict:
    texto = seg["durations"]["text"]
    vits = [tuple(x) for x in seg["durations"]["char_times"]]
    # Solo palabras cuyos caracteres tienen todos intervalo CTC
    ok = [s is not None for s in asr_spans]
    errores = {"inicio": [], "fin": [], "centro": []}
    chars = []
    for (_w, v0, v1), (_, a0, a1) in zip(
        words_from_chars(texto, vits),
        words_from_chars(texto, [s or (0.0, 0.0) for s in asr_spans]),
        strict=True,
    ):
        errores["inicio"].append((a0 - v0) * 1000)
        errores["fin"].append((a1 - v1) * 1000)
        errores["centro"].append(((a0 + a1) / 2 - (v0 + v1) / 2) * 1000)
    for (v0, v1), s in zip(vits, asr_spans, strict=True):
        if s is not None and texto:
            chars.append(((s[0] + s[1]) / 2 - (v0 + v1) / 2) * 1000)
    return {"palabras": errores, "centros_caracter": chars, "sin_token": ok.count(False)}


def bootstrap_mae(por_oracion: list[list[float]], rng: random.Random, n: int = 1000) -> list[float]:
    medias = []
    for _ in range(n):
        muestra = [x for o in rng.choices(por_oracion, k=len(por_oracion)) for x in o]
        medias.append(float(np.mean(np.abs(muestra))))
    return [
        round(float(np.percentile(medias, 2.5)), 1),
        round(float(np.percentile(medias, 97.5)), 1),
    ]


def main() -> None:
    sel = json.loads((OUT / "selection.json").read_text("utf-8"))
    torch, proc, asr = load_asr()
    acumulado = {"inicio": [], "fin": [], "centro": []}
    por_oracion = {"inicio": [], "fin": [], "centro": []}
    centros_char: list[float] = []
    filas, sin_token = [], 0
    spans_por_noticia: dict[int, list] = {}
    for item in sel:
        seg, wav, sr = cargar_segmento(item["news_id"], item["idx"])
        spans, faltan = alinear_asr(torch, proc, asr, wav, sr, seg["durations"]["text"])
        r = comparar(seg, spans)
        sin_token += faltan
        spans_por_noticia[item["news_id"]] = {
            "texto": seg["durations"]["text"],
            "spans": [None if x is None else [round(x[0], 4), round(x[1], 4)] for x in spans],
        }
        for k in acumulado:
            acumulado[k] += r["palabras"][k]
            por_oracion[k].append(r["palabras"][k])
        centros_char += r["centros_caracter"]
        filas.append(
            {
                "news_id": item["news_id"],
                "palabras": len(r["palabras"]["inicio"]),
                "mae_centro_ms": round(float(np.mean(np.abs(r["palabras"]["centro"]))), 1),
            }
        )
        print(f"[3.2] noticia {item['news_id']}: centro MAE {filas[-1]['mae_centro_ms']} ms")
    (OUT / "ctc_spans.json").write_text(json.dumps(spans_por_noticia, ensure_ascii=False), "utf-8")
    rng = random.Random(SEED)
    res = {
        "tarea": "3.2",
        "split": "dev",
        "oraciones": len(sel),
        "palabras": len(acumulado["centro"]),
        "referencia": "alineación forzada CTC de mms-1b-all (adaptador cni) sobre el audio Opus",
        "semilla_bootstrap": SEED,
        "palabras_error": {k: error_stats(v) for k, v in acumulado.items()},
        "mae_centro_palabra_ic95_ms": bootstrap_mae(por_oracion["centro"], rng),
        "centro_caracter": error_stats(centros_char),
        "caracteres_sin_token_asr": sin_token,
        "por_oracion": filas,
        "limitacion": (
            "CTC da intervalos interiores a cada sonido (picos de 20 ms): el inicio tiende a ser "
            "posterior y el fin anterior al de VITS. El centro de palabra es la medida robusta."
        ),
        "anotacion_manual_praat": "pendiente: requiere a una persona (ver eval/fase3/praat/)",
    }
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(json.dumps(res, indent=2, ensure_ascii=False), "utf-8")
    print(
        json.dumps({k: res[k] for k in ("palabras_error", "mae_centro_palabra_ic95_ms")}, indent=1)
    )


if __name__ == "__main__":
    main()
