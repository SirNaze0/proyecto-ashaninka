"""Tarea 2.10 — Inteligibilidad objetiva: CER de ida y vuelta TTS -> mms-1b-all sobre el split TEST.

Es la primera vez que se usa el split test (disciplina de splits de la Fase 1). Muestra fija de
200 oraciones de test listas para el TTS (semilla fija). Por motor:
  * mms_vits: text_tts (adaptador activo, tokenización por defecto);
  * espeak_ng (modo texto-es): texto canónico con la voz castellana (línea base ingenua).
El audio de eSpeak (22 050 Hz) se remuestrea a 16 kHz por interpolación lineal para el ASR.

Métrica: CER en el espacio canónico (transcripción -> inversa del adaptador -> comparación con el
texto canónico), IC 95 % por bootstrap y diferencia pareada mms_vits - espeak_ng.

SESGO DECLARADO: el ASR de MMS comparte datos de entrenamiento con el TTS de MMS, por lo que la
comparación favorece a mms_vits. Mide consistencia, no inteligibilidad humana.

Uso: uv run python -m eval.fase2.intelligibility.run [--n 200]
"""

from __future__ import annotations

import argparse
import json
import random
import time
from datetime import UTC, datetime

import numpy as np
from app.config import DOCS_DIR, RESULTS_DIR, get_settings
from app.corpus.loader import load_split
from app.pipeline.normalize.engine import DocumentState, Normalizer
from app.pipeline.tts.adapters.mms_cni import MmsCniAdapter
from app.pipeline.tts.base import derive_seed
from app.pipeline.tts.espeak import find_espeak
from app.pipeline.tts.registry import create_engine

from eval.fase1.mms_orthography.run import (
    base_resource_hypotheses,
    bootstrap_ci,
    corpus_cer,
    git_commit,
    make_inverse,
    paired_bootstrap,
    transcribe,
    typographic,
    word_accuracy,
)
from eval.fase2.tokenization.run import load_asr

SEED = 20261007
ASR_SR = 16000


def resample(wav: np.ndarray, sr: int, target: int = ASR_SR) -> np.ndarray:
    if sr == target:
        return wav
    n = int(round(len(wav) * target / sr))
    x_old = np.linspace(0, 1, len(wav), endpoint=False)
    x_new = np.linspace(0, 1, n, endpoint=False)
    return np.interp(x_new, x_old, wav).astype(np.float32)


def build_test_sample(n: int, normalizer: Normalizer, adapter: MmsCniAdapter) -> tuple[list, dict]:
    pairs = load_split("test")
    eligible = []
    for p in pairs:
        canon = normalizer.normalize(p.cni, DocumentState()).text_canonical
        tts = adapter.adapt(canon).text_tts
        if tts and not adapter.oov_after(canon) and 20 <= len(canon) <= 300:
            eligible.append({"ref": p.ref, "canonical": canon, "text_tts": tts})
    rng = random.Random(SEED)
    rng.shuffle(eligible)
    return eligible[:n], {
        "test_total": len(pairs),
        "elegibles": len(eligible),
        "muestra": min(n, len(eligible)),
        "semilla": SEED,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    args = ap.parse_args(argv)
    normalizer, adapter = Normalizer.from_files(), MmsCniAdapter.from_files()
    sample, info = build_test_sample(args.n, normalizer, adapter)
    inv = make_inverse(base_resource_hypotheses()[adapter.hypothesis].get("inverse", []))
    engines = ["mms_vits"] + (["espeak_ng"] if find_espeak(get_settings().espeak_path) else [])
    torch, proc, asr = load_asr()
    rows: dict[str, list[dict]] = {}
    t_start = time.time()
    for name in engines:
        eng = create_engine(name)
        eng.warmup()
        info_e = eng.info()
        rows[name] = []
        for i, item in enumerate(sample):
            text = item["text_tts"] if info_e.input_kind == "text_tts" else item["canonical"]
            res = eng.synthesize(text, derive_seed(text, name, info_e.revision, adapter.id))
            hyp = transcribe(torch, proc, asr, resample(res.wav, res.sample_rate), ASR_SR)
            rows[name].append(
                {
                    "ref": item["ref"],
                    "ref_canon": typographic(item["canonical"]),
                    "hyp_canon": typographic(inv(hyp)),
                    "transcripcion": hyp,
                }
            )
            if (i + 1) % 25 == 0:
                print(f"[2.10] {name}: {i + 1}/{len(sample)} ({time.time() - t_start:.0f} s)")
    results = {
        name: {
            "cer": round(corpus_cer(r, "ref_canon", "hyp_canon"), 4),
            "ic95": bootstrap_ci(r, "ref_canon", "hyp_canon", random.Random(SEED)),
            "precision_palabra": word_accuracy(r),
        }
        for name, r in rows.items()
    }
    if "espeak_ng" not in results:
        results["espeak_ng"] = "no_medido (eSpeak-NG no instalado)"
    diff = None
    if "espeak_ng" in rows:
        diff = paired_bootstrap(rows["espeak_ng"], rows["mms_vits"], random.Random(SEED))
    payload = {
        "tarea": "2.10",
        "fecha": datetime.now(UTC).isoformat(timespec="seconds"),
        "commit": git_commit(),
        "adapter": adapter.id,
        "tokenizacion_mms": create_engine("mms_vits").tokenization,
        "muestra": info,
        "motores": results,
        "diferencia_mms_menos_espeak": diff,
        "sesgo": "El ASR de MMS comparte datos con el TTS de MMS: la comparación favorece a mms_vits.",
        "duracion_s": round(time.time() - t_start, 1),
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "fase_2_inteligibilidad.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (DOCS_DIR / "intelligibility.md").write_text(render(payload), encoding="utf-8", newline="\n")
    print(f"[2.10] {json.dumps(results, ensure_ascii=False)}")
    return 0


def render(p: dict) -> str:
    lines = [
        "# Inteligibilidad objetiva por motor (tarea 2.10)",
        "",
        "> GENERADO por `uv run python -m eval.fase2.intelligibility.run`. No editar a mano.",
        f"> Fecha: {p['fecha']} · commit `{p['commit'][:7]}` · adaptador `{p['adapter']}` · "
        f"tokenización MMS `{p['tokenizacion_mms']}`.",
        "",
        "Método: TTS → `mms-1b-all` (adaptador `cni`) → CER en el espacio canónico. Muestra fija "
        "del split **test** (primera vez que se usa).",
        "",
        "| Medida | Valor |",
        "|---|---|",
    ]
    lines += [f"| {k} | {v} |" for k, v in p["muestra"].items()]
    lines += ["", "| Motor | CER | IC 95 % | Precisión por palabra |", "|---|---|---|---|"]
    for name, r in p["motores"].items():
        if isinstance(r, dict):
            lines.append(f"| {name} | {r['cer']} | {r['ic95']} | {r['precision_palabra']} |")
        else:
            lines.append(f"| {name} | {r} | | |")
    if p["diferencia_mms_menos_espeak"]:
        d = p["diferencia_mms_menos_espeak"]
        lines.append(
            f"\nDiferencia pareada mms_vits − espeak_ng: {d['diferencia_cer_media']} "
            f"(IC 95 % {d['ic95']}, p = {d['p_valor_bilateral']})."
        )
    lines += [
        "",
        "## Sesgo y limitaciones",
        "",
        p["sesgo"],
        "La línea base eSpeak lee la ortografía asháninka con la voz castellana: es una "
        "referencia ingenua, no un TTS asháninka. Su audio se remuestrea a 16 kHz por "
        "interpolación lineal.",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
