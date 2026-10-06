"""Tarea 2.2b — ¿Cómo se tokeniza la entrada de mms-tts-cni? T1 (VitsTokenizer) vs T2 (manual).

Hallazgo: el blanco de MMS es la letra "a" (id 0) y VitsTokenizer la trata como token especial,
lo que rompe el intercalado de blancos con "aa" o "a" inicial/final. Se comparan:
  T1 = salida de VitsTokenizer tal cual (lo que se usó en la Fase 1);
  T2 = intercalado estándar de VITS [0, c1, 0, c2, …, 0].

Misma muestra (100 oraciones de dev), misma hipótesis de adaptador (activa), misma semilla
por oración. Métrica: CER de ida y vuelta TTS -> mms-1b-all (espacio canónico), IC 95 % por
bootstrap y diferencia pareada T2 - T1.

Regla de decisión (fijada ANTES de ejecutar, 2026-10-06): se adopta T2 si su CER es menor con
IC 95 % pareado que excluye 0. Si no hay diferencia significativa, también se adopta T2 porque
da una correspondencia exacta token<->carácter (necesaria para la alineación de la Fase 3). Solo
se mantiene T1 si T1 es significativamente mejor.

Uso: uv run python -m eval.fase2.tokenization.run [--n 100]
"""

from __future__ import annotations

import argparse
import json
import random
import time
from datetime import UTC, datetime

from app.config import DOCS_DIR, RESULTS_DIR, get_settings
from app.pipeline.normalize.engine import Normalizer
from app.pipeline.tts.adapters.mms_cni import MmsCniAdapter
from app.pipeline.tts.mms_vits import MmsVitsEngine

from eval.fase1.mms_orthography.run import (
    SEED,
    base_resource_hypotheses,
    bootstrap_ci,
    build_sample,
    corpus_cer,
    git_commit,
    make_inverse,
    paired_bootstrap,
    transcribe,
    typographic,
    word_accuracy,
)

MODES = {"T1": "hf", "T2": "manual"}


def load_asr():
    import torch
    from transformers import AutoProcessor, Wav2Vec2ForCTC

    asr_dir = get_settings().models_dir / "facebook__mms-1b-all"
    proc = AutoProcessor.from_pretrained(asr_dir)
    proc.tokenizer.set_target_lang("cni")
    asr = Wav2Vec2ForCTC.from_pretrained(
        asr_dir, target_lang="cni", ignore_mismatched_sizes=True
    ).eval()
    asr.load_adapter("cni")
    return torch, proc, asr


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100)
    args = ap.parse_args(argv)
    normalizer = Normalizer.from_files()
    adapter = MmsCniAdapter.from_files()
    sample, info = build_sample(args.n, normalizer, MmsCniAdapter.from_files("H1"))
    inv = make_inverse(base_resource_hypotheses()[adapter.hypothesis].get("inverse", []))
    torch, proc, asr = load_asr()
    rows: dict[str, list[dict]] = {}
    t_start = time.time()
    for cond, mode in MODES.items():
        engine = MmsVitsEngine(tokenization=mode)
        engine.warmup()
        rows[cond] = []
        for i, item in enumerate(sample):
            text = adapter.adapt_validated(item["canonical"]).text_tts
            res = engine.synthesize(text, SEED + i)
            hyp = transcribe(torch, proc, asr, res.wav, res.sample_rate)
            rows[cond].append(
                {
                    "ref": item["ref"],
                    "ref_canon": typographic(item["canonical"]),
                    "hyp_canon": typographic(inv(hyp)),
                    "duracion_s": round(res.duration_s, 3),
                    "transcripcion": hyp,
                }
            )
            if (i + 1) % 20 == 0:
                print(f"[2.2b] {cond}: {i + 1}/{len(sample)} ({time.time() - t_start:.0f} s)")
    results = {}
    for cond, r in rows.items():
        results[cond] = {
            "modo": MODES[cond],
            "cer_canonico": round(corpus_cer(r, "ref_canon", "hyp_canon"), 4),
            "ic95": bootstrap_ci(r, "ref_canon", "hyp_canon", random.Random(SEED)),
            "precision_palabra": word_accuracy(r),
            "duracion_media_s": round(sum(x["duracion_s"] for x in r) / len(r), 3),
        }
    diff = paired_bootstrap(rows["T1"], rows["T2"], random.Random(SEED))  # T2 - T1
    if diff["ic95"][1] < 0:
        decision, why = "T2", "T2 reduce el CER de forma significativa"
    elif diff["ic95"][0] > 0:
        decision, why = "T1", "T1 es significativamente mejor"
    else:
        decision, why = (
            "T2",
            "sin diferencia significativa; T2 da correspondencia exacta token-carácter",
        )
    affected = sum(
        1
        for it in sample
        if (t := adapter.adapt(it["canonical"]).text_tts).startswith("a")
        or t.endswith("a")
        or "aa" in t
    )
    payload = {
        "tarea": "2.2b",
        "fecha": datetime.now(UTC).isoformat(timespec="seconds"),
        "commit": git_commit(),
        "adapter": adapter.id,
        "muestra": info,
        "oraciones_afectadas_por_el_tokenizador": affected,
        "condiciones": results,
        "diferencia_T2_menos_T1": diff,
        "decision": decision,
        "motivo": why,
        "duracion_s": round(time.time() - t_start, 1),
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "fase_2_tokenizacion.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (DOCS_DIR / "tokenization.md").write_text(render(payload), encoding="utf-8", newline="\n")
    print(f"[2.2b] decisión: {decision} ({why})")
    return 0


def render(p: dict) -> str:
    d = p["diferencia_T2_menos_T1"]
    lines = [
        "# Tokenización de la entrada de mms-tts-cni (tarea 2.2b)",
        "",
        "> GENERADO por `uv run python -m eval.fase2.tokenization.run`. No editar a mano.",
        f"> Fecha: {p['fecha']} · commit `{p['commit'][:7]}` · adaptador `{p['adapter']}`.",
        "",
        "## Hallazgo",
        "",
        "El blanco de MMS es la letra `a` (id 0). `VitsTokenizer` (transformers 4.46 y 5.18) la "
        "trata como token especial y rompe el intercalado de blancos cuando hay `aa` o una `a` "
        "inicial o final: por ejemplo, `a` se tokeniza `[0]` en vez de `[0, 0, 0]`.",
        f"En la muestra, {p['oraciones_afectadas_por_el_tokenizador']} de "
        f"{p['muestra']['muestra']} oraciones están afectadas.",
        "",
        "## Resultados",
        "",
        "| Condición | Modo | CER canónico | IC 95 % | Precisión por palabra | Duración media (s) |",
        "|---|---|---|---|---|---|",
    ]
    for c, r in p["condiciones"].items():
        lines.append(
            f"| {c} | {r['modo']} | {r['cer_canonico']} | {r['ic95']} | "
            f"{r['precision_palabra']} | {r['duracion_media_s']} |"
        )
    lines += [
        "",
        f"Diferencia pareada T2 − T1: {d['diferencia_cer_media']} (IC 95 % {d['ic95']}, "
        f"p = {d['p_valor_bilateral']}).",
        "",
        "## Decisión",
        "",
        "Regla fijada antes de ejecutar: se adopta T2 salvo que T1 sea significativamente mejor.",
        "",
        f"**{p['decision']}**: {p['motivo']}.",
        "",
        "Limitación: el TTS y el ASR de MMS comparten datos de entrenamiento (consistencia, no "
        "inteligibilidad humana).",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
