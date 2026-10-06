"""Tarea 1.9 — Experimento de ortografía MMS (P6): prueba de ida y vuelta TTS -> ASR.

Para cada hipótesis del adaptador (H0 sin adaptar, H1, …):
  texto canónico -> adaptador -> mms-tts-cni (semilla fija) -> WAV 16 kHz
  -> mms-1b-all con adaptador cni -> transcripción (ortografía MMS)
  -> inversa documentada MMS->canónica -> CER contra el texto canónico de entrada.

Métrica principal: CER en el espacio canónico (corpus-level: ediciones / caracteres de referencia).
Secundarias: CER en el espacio MMS, precisión por palabra y recuperación por carácter conflictivo.
IC 95 % por bootstrap (1000 remuestreos de oraciones) y diferencia pareada H1 - H0.

LIMITACIÓN: el TTS y el ASR de MMS comparten datos de entrenamiento; la prueba mide
consistencia del par de modelos, no inteligibilidad humana.

Uso: uv run --group eval python -m eval.fase1.mms_orthography.run [--n 100] [--hyps H0,H1]
Requiere: ./init.sh --with-asr-eval
"""

from __future__ import annotations

import argparse
import csv
import json
import platform
import random
import re
import subprocess
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from app.config import (
    AMERICASNLP_COMMIT,
    DOCS_DIR,
    MMS_ASR_REVISION,
    MMS_TTS_REVISION,
    RESULTS_DIR,
    ROOT,
    get_settings,
)
from app.corpus.loader import load_split
from app.pipeline.normalize.engine import DocumentState, Normalizer
from app.pipeline.tts.adapters.mms_cni import MmsCniAdapter
from app.pipeline.tts.adapters.validate import find_oov

OUT = Path(__file__).parent / "out"
SEED = 20261005
CONFLICT = ["k", "b", "ñ", "ts"]
BOOTSTRAP = 1000


# ------------------------------------------------------------------ texto
def typographic(s: str) -> str:
    """Espacio de comparación: minúsculas, sin tildes ni puntuación, espacios simples."""
    s = s.lower()
    for a, b in (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"), ("ü", "u")):
        s = s.replace(a, b)
    s = re.sub(r"[^\w\s'-]|_", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def make_inverse(pairs: list[list[str]]):
    compiled = [(re.compile(p), r) for p, r in pairs]

    def inv(s: str) -> str:
        out, i = [], 0
        while i < len(s):
            for rx, rep in compiled:
                m = rx.match(s, i)
                if m and m.end() > i:
                    out.append(rep)
                    i = m.end()
                    break
            else:
                out.append(s[i])
                i += 1
        return "".join(out)

    return inv


def edit_distance(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


# ------------------------------------------------------------------ muestra
def build_sample(n: int, normalizer: Normalizer, h1: MmsCniAdapter) -> tuple[list[dict], dict]:
    """Muestra fija y estratificada de dev, solo con oraciones cuyo texto canónico queda 100 %
    en el vocabulario MMS bajo H1 (las bloqueadas por falta de P2d se excluyen y se cuentan)."""
    pairs = load_split("dev")
    eligible, blocked, too_short = [], 0, 0
    for p in pairs:
        canon = normalizer.normalize(p.cni, DocumentState()).text_canonical
        if find_oov(h1.adapt(canon).text_tts, h1.vocab()):
            blocked += 1
            continue
        if not (20 <= len(canon) <= 300):
            too_short += 1
            continue
        eligible.append({"ref": p.ref, "orig": p.cni, "canonical": canon})
    rng = random.Random(SEED)
    rng.shuffle(eligible)
    chosen: list[dict] = []
    for ch, quota in (("ñ", 25), ("b", 25)):
        for item in eligible:
            if len([c for c in chosen if ch in c["canonical"]]) >= quota:
                break
            if ch in item["canonical"] and item not in chosen:
                chosen.append(item)
    for item in eligible:
        if len(chosen) >= n:
            break
        if item not in chosen and "k" in item["canonical"]:
            chosen.append(item)
    for item in eligible:
        if len(chosen) >= n:
            break
        if item not in chosen:
            chosen.append(item)
    info = {
        "dev_total": len(pairs),
        "bloqueadas_sin_p2d": blocked,
        "fuera_de_rango_longitud": too_short,
        "elegibles": len(eligible),
        "muestra": min(n, len(chosen)),
    }
    return chosen[:n], info


# ------------------------------------------------------------------ modelos
def load_models():
    import torch
    from transformers import AutoProcessor, VitsModel, VitsTokenizer, Wav2Vec2ForCTC

    mdir = get_settings().models_dir
    tts_dir, asr_dir = mdir / "facebook__mms-tts-cni", mdir / "facebook__mms-1b-all"
    if not (tts_dir / "model.safetensors").exists() or not (asr_dir / "model.safetensors").exists():
        raise SystemExit("Faltan modelos: ejecuta ./init.sh --with-asr-eval")
    tts_tok = VitsTokenizer.from_pretrained(tts_dir)
    tts = VitsModel.from_pretrained(tts_dir).eval()
    proc = AutoProcessor.from_pretrained(asr_dir)
    proc.tokenizer.set_target_lang("cni")
    asr = Wav2Vec2ForCTC.from_pretrained(
        asr_dir, target_lang="cni", ignore_mismatched_sizes=True
    ).eval()
    asr.load_adapter("cni")
    return torch, tts_tok, tts, proc, asr


def synthesize(torch, tok, tts, text: str, seed: int):
    inputs = tok(text, return_tensors="pt")
    if inputs["input_ids"].shape[-1] == 0:
        return None
    torch.manual_seed(seed)
    with torch.no_grad():
        wav = tts(**inputs).waveform[0]
    # Texto que realmente llega al modelo (tras la limpieza de VitsTokenizer, sin blancos)
    model_input = tok.prepare_for_tokenization(text, normalize=True)[0]
    return wav.numpy(), tts.config.sampling_rate, model_input


def transcribe(torch, proc, asr, wav, sr: int) -> str:
    inputs = proc(wav, sampling_rate=sr, return_tensors="pt")
    with torch.no_grad():
        logits = asr(**inputs).logits
    ids = torch.argmax(logits, dim=-1)[0]
    return proc.decode(ids)


# ------------------------------------------------------------------ estadística
def corpus_cer(rows: list[dict], key_ref: str, key_hyp: str) -> float:
    edits = sum(edit_distance(r[key_ref], r[key_hyp]) for r in rows)
    chars = sum(len(r[key_ref]) for r in rows)
    return edits / chars if chars else float("nan")


def bootstrap_ci(rows, key_ref, key_hyp, rng):
    n = len(rows)
    edits = [edit_distance(r[key_ref], r[key_hyp]) for r in rows]
    chars = [len(r[key_ref]) for r in rows]
    vals = []
    for _ in range(BOOTSTRAP):
        idx = [rng.randrange(n) for _ in range(n)]
        vals.append(sum(edits[i] for i in idx) / max(1, sum(chars[i] for i in idx)))
    vals.sort()
    return [round(vals[int(0.025 * BOOTSTRAP)], 4), round(vals[int(0.975 * BOOTSTRAP) - 1], 4)]


def paired_bootstrap(rows_a, rows_b, rng):
    n = len(rows_a)
    ea = [edit_distance(r["ref_canon"], r["hyp_canon"]) for r in rows_a]
    eb = [edit_distance(r["ref_canon"], r["hyp_canon"]) for r in rows_b]
    ch = [len(r["ref_canon"]) for r in rows_a]
    diffs = []
    for _ in range(BOOTSTRAP):
        idx = [rng.randrange(n) for _ in range(n)]
        c = max(1, sum(ch[i] for i in idx))
        diffs.append(sum(eb[i] for i in idx) / c - sum(ea[i] for i in idx) / c)
    diffs.sort()
    le = sum(1 for d in diffs if d <= 0) / BOOTSTRAP
    ge = sum(1 for d in diffs if d >= 0) / BOOTSTRAP
    return {
        "diferencia_cer_media": round(sum(diffs) / BOOTSTRAP, 4),
        "ic95": [
            round(diffs[int(0.025 * BOOTSTRAP)], 4),
            round(diffs[int(0.975 * BOOTSTRAP) - 1], 4),
        ],
        "p_valor_bilateral": round(min(1.0, 2 * min(le, ge)), 4),
    }


def char_recovery(rows: list[dict]) -> dict:
    out = {}
    for ch in CONFLICT:
        ref = sum(r["ref_canon"].count(ch) for r in rows)
        hit = sum(min(r["ref_canon"].count(ch), r["hyp_canon"].count(ch)) for r in rows)
        out[ch] = {"apariciones_ref": ref, "recuperacion": round(hit / ref, 4) if ref else None}
    return out


def word_accuracy(rows: list[dict]) -> float:
    hits = total = 0
    for r in rows:
        ref, hyp = r["ref_canon"].split(), Counter(r["hyp_canon"].split())
        total += len(ref)
        for w in ref:
            if hyp[w] > 0:
                hits += 1
                hyp[w] -= 1
    return round(hits / total, 4) if total else float("nan")


# ------------------------------------------------------------------ principal
def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:  # pragma: no cover
        return "sin-commit"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--hyps", default=None, help="lista separada por comas; por defecto todas")
    ap.add_argument("--ab", type=int, default=20, help="oraciones para la hoja de escucha A/B")
    args = ap.parse_args(argv)

    normalizer = Normalizer.from_files(allow_candidates=False)
    base = MmsCniAdapter.from_files()
    hyps_cfg = base_resource_hypotheses()
    hyps = args.hyps.split(",") if args.hyps else list(hyps_cfg)
    active = hyps_cfg.get(base.hypothesis, {})
    adapters = {h: MmsCniAdapter.from_files(h) for h in hyps}
    sample, sample_info = build_sample(args.n, normalizer, MmsCniAdapter.from_files("H1"))
    print(f"[1.9] muestra: {json.dumps(sample_info, ensure_ascii=False)}")

    torch, tok, tts, proc, asr = load_models()
    OUT.mkdir(parents=True, exist_ok=True)
    import soundfile as sf

    results: dict[str, dict] = {}
    per_hyp_rows: dict[str, list[dict]] = {}
    t_start = time.time()
    for h in hyps:
        ad = adapters[h]
        inverse_pairs = hyps_cfg[h].get("inverse") or active.get("inverse") or []
        inv = make_inverse(inverse_pairs)
        rows = []
        for i, item in enumerate(sample):
            text_in = ad.adapt(item["canonical"]).text_tts
            syn = synthesize(torch, tok, tts, text_in, SEED + i)
            if syn is None:
                transcript, model_input = "", ""
            else:
                wav, sr, model_input = syn
                if i < args.ab:
                    sf.write(OUT / f"{h}_{i:03d}.wav", wav, sr)
                transcript = transcribe(torch, proc, asr, wav, sr)
            ref_canon = typographic(item["canonical"])
            rows.append(
                {
                    "ref": item["ref"],
                    "ref_canon": ref_canon,
                    "hyp_canon": typographic(inv(transcript)),
                    "ref_mms": typographic(
                        adapters.get("H1", ad).adapt(item["canonical"]).text_tts
                    ),
                    "hyp_mms": typographic(transcript),
                    "entrada_modelo": model_input,
                    "transcripcion": transcript,
                }
            )
            if (i + 1) % 10 == 0:
                print(f"[1.9] {h}: {i + 1}/{len(sample)} ({time.time() - t_start:.0f} s)")
        per_hyp_rows[h] = rows
        rng = random.Random(SEED)
        results[h] = {
            "descripcion": hyps_cfg[h].get("description", ""),
            "cer_canonico": round(corpus_cer(rows, "ref_canon", "hyp_canon"), 4),
            "ic95": bootstrap_ci(rows, "ref_canon", "hyp_canon", rng),
            "cer_mms": round(corpus_cer(rows, "ref_mms", "hyp_mms"), 4),
            "precision_palabra": word_accuracy(rows),
            "recuperacion_por_caracter": char_recovery(rows),
            "inversa_usada": inverse_pairs,
        }
        with open(OUT / f"transcripciones_{h}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)

    candidates = [h for h in hyps if not hyps_cfg[h].get("raw")]
    best = min(candidates, key=lambda h: results[h]["cer_canonico"]) if candidates else None
    comparison = None
    if best and "H0" in per_hyp_rows:
        comparison = paired_bootstrap(per_hyp_rows["H0"], per_hyp_rows[best], random.Random(SEED))

    ab_sheet = None
    if best and "H0" in per_hyp_rows:
        ab_sheet = write_ab_sheet(best, min(args.ab, len(sample)), sample)

    payload = {
        "tarea": "1.9",
        "fecha": datetime.now(UTC).isoformat(timespec="seconds"),
        "commit": git_commit(),
        "hardware": {"cpu": platform.processor(), "os": platform.platform()},
        "versiones": {
            "americasnlp2021": AMERICASNLP_COMMIT,
            "mms-tts-cni": MMS_TTS_REVISION,
            "mms-1b-all": MMS_ASR_REVISION,
        },
        "semilla": SEED,
        "bootstrap": BOOTSTRAP,
        "muestra": sample_info,
        "hipotesis": results,
        "elegida": best,
        "comparacion_vs_H0": comparison,
        "hoja_ab": ab_sheet,
        "duracion_s": round(time.time() - t_start, 1),
        "limitacion": "TTS y ASR de MMS comparten datos de entrenamiento: la prueba mide "
        "consistencia, no inteligibilidad humana.",
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "mms_orthography.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (DOCS_DIR / "mms_orthography.md").write_text(render_md(payload), encoding="utf-8", newline="\n")
    print(f"[1.9] elegida: {best}; resultados en eval/results/mms_orthography.json")
    return 0


def base_resource_hypotheses() -> dict:
    from app.config import ADAPTERS_DIR
    from app.pipeline.resources import get_resource

    return get_resource(ADAPTERS_DIR / "mms_cni.yaml").config["hypotheses"]


def write_ab_sheet(best: str, n: int, sample: list[dict]) -> str:
    """Hoja de escucha A/B a ciegas (H0 frente a la mejor), orden aleatorizado con semilla."""
    rng = random.Random(SEED + 1)
    path = OUT / "escucha_ab.csv"
    key_path = OUT / "escucha_ab_clave.csv"
    with (
        open(path, "w", newline="", encoding="utf-8") as f,
        open(key_path, "w", newline="", encoding="utf-8") as k,
    ):
        w, wk = csv.writer(f), csv.writer(k)
        w.writerow(
            ["item", "texto_original", "audio_A", "audio_B", "preferido(A/B/igual)", "comentario"]
        )
        wk.writerow(["item", "A", "B"])
        for i in range(n):
            pair = ["H0", best]
            rng.shuffle(pair)
            w.writerow(
                [i, sample[i]["orig"], f"{pair[0]}_{i:03d}.wav", f"{pair[1]}_{i:03d}.wav", "", ""]
            )
            wk.writerow([i, pair[0], pair[1]])
    return "pendiente_hablante"


def render_md(p: dict) -> str:
    lines = [
        "# Experimento de ortografía MMS (tarea 1.9, P6)",
        "",
        "> GENERADO por `uv run python -m eval.fase1.mms_orthography.run`. No editar a mano.",
        f"> Fecha: {p['fecha']} · commit `{p['commit'][:7]}` · semilla {p['semilla']} · "
        f"bootstrap {p['bootstrap']}.",
        "",
        "## Método",
        "",
        "Texto canónico (normalizador, sin candidatos) → adaptador de la hipótesis → "
        "`mms-tts-cni` → `mms-1b-all` (adaptador `cni`) → inversa MMS→canónica → CER contra la "
        "entrada. H0 no adapta: `VitsTokenizer` elimina en silencio los caracteres desconocidos.",
        "",
        "## Muestra",
        "",
        "| Medida | Valor |",
        "|---|---|",
    ]
    lines += [f"| {k} | {v} |" for k, v in p["muestra"].items()]
    lines += [
        "",
        "## Resultados",
        "",
        "| Hipótesis | CER canónico | IC 95 % | CER espacio MMS | Precisión por palabra |",
        "|---|---|---|---|---|",
    ]
    for h, r in p["hipotesis"].items():
        lines.append(
            f"| {h} | {r['cer_canonico']} | {r['ic95']} | {r['cer_mms']} | "
            f"{r['precision_palabra']} |"
        )
    lines += [
        "",
        "### Recuperación por carácter conflictivo (proxy por recuento)",
        "",
        "| Hipótesis | " + " | ".join(CONFLICT) + " |",
        "|---|" + "---|" * len(CONFLICT),
    ]
    for h, r in p["hipotesis"].items():
        cells = [str(r["recuperacion_por_caracter"][c]["recuperacion"]) for c in CONFLICT]
        lines.append(f"| {h} | " + " | ".join(cells) + " |")
    lines += ["", "## Decisión", "", f"Hipótesis elegida: **{p['elegida']}**."]
    if p["comparacion_vs_H0"]:
        c = p["comparacion_vs_H0"]
        pv = c["p_valor_bilateral"]
        ptxt = f"p < {1 / p['bootstrap']:g} (ningún remuestreo cruza 0)" if pv == 0 else f"p = {pv}"
        lines.append(
            f"Diferencia pareada de CER ({p['elegida']} − H0): {c['diferencia_cer_media']} "
            f"(IC 95 % {c['ic95']}, {ptxt})."
        )
    lines += [
        "",
        f"Escucha A/B con hablante: {p['hoja_ab']}.",
        "",
        "## Limitación",
        "",
        p["limitacion"],
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
