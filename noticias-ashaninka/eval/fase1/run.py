"""Métricas de la Fase 1 -> eval/results/fase_1.json (nunca se escriben a mano).

Uso: uv run python -m eval.fase1.run [--reps 100]

Mide sobre el split dev del corpus (y sobre data/news/ si hay noticias de prueba):
categorías, % sin resolver, marcas editoriales, palabras fuera del vocabulario MMS antes y
después del adaptador, estado de las reglas y latencia por etapa (N repeticiones).
Incorpora los resultados del experimento 1.9 si existen (eval/results/mms_orthography.json)
y la cobertura de pruebas si existe coverage.json.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import subprocess
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from app.config import (
    AMERICASNLP_COMMIT,
    MMS_ASR_REVISION,
    MMS_TTS_REVISION,
    RESULTS_DIR,
    ROOT,
)
from app.corpus.report import build_report
from app.metrics.timing import Timer
from app.pipeline.resources import all_resource_paths, load_resource
from app.pipeline.tts.adapters.mms_cni import MmsCniAdapter
from app.pipeline.tts.adapters.validate import find_oov
from app.schemas import NewsIn
from app.services import Pipeline

WORD_RX = re.compile(r"\w+")


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:  # pragma: no cover
        return "sin-commit"


def hardware() -> dict:
    ram = None
    try:
        import psutil  # type: ignore

        ram = round(psutil.virtual_memory().total / 2**30, 1)
    except Exception:
        ram = "no_medido (psutil no instalado)"
    return {
        "cpu": platform.processor() or platform.machine(),
        "nucleos": os.cpu_count(),
        "ram_gb": ram,
        "os": platform.platform(),
        "python": platform.python_version(),
    }


def oov_word_pct(texts: list[str], vocab: set[str]) -> float:
    words = [w for t in texts for w in WORD_RX.findall(t.lower())]
    bad = sum(1 for w in words if any(ch not in vocab for ch in w))
    return round(100 * bad / len(words), 2) if words else 0.0


def analyze(docs: list[str], pipeline: Pipeline) -> dict:
    cats: Counter[str] = Counter()
    flags: Counter[str] = Counter()
    unresolved_tokens = tokens = 0
    seg_total = seg_ready = 0
    canon, tts_texts = [], []
    flags_per_doc = []
    for doc in docs:
        rows = pipeline.process_text(doc)
        n_flags = 0
        for r in rows:
            seg_total += 1
            seg_ready += r["tts_ready"]
            canon.append(r["text_canonical"])
            tts_texts.append(pipeline.adapter.adapt(r["text_canonical"]).text_tts)
            for s in r["alignment_map"]:
                if s["category"] != "identity":
                    cats[s["category"]] += 1
                    tokens += 1
            norm_unres = [
                u for u in r["unresolved"] if not u["reason"].startswith(("G2P:", "bloqueado"))
            ]
            unresolved_tokens += len(norm_unres)
            for f in r["editorial_flags"]:
                flags[f["kind"]] += 1
                n_flags += 1
        flags_per_doc.append(n_flags)
    vocab = pipeline.adapter.vocab()
    return {
        "documentos": len(docs),
        "segmentos": seg_total,
        "tokens_no_identidad": tokens,
        "categorias_pct": {k: round(100 * v / tokens, 2) for k, v in cats.most_common()},
        "unresolved_pct": round(100 * unresolved_tokens / tokens, 2) if tokens else 0.0,
        "segmentos_listos_tts_pct": round(100 * seg_ready / seg_total, 2) if seg_total else 0.0,
        "editorial_flags_por_documento": {
            "media": round(sum(flags_per_doc) / len(flags_per_doc), 3) if flags_per_doc else 0,
            "por_tipo": dict(flags),
        },
        "palabras_fuera_vocab_antes_del_adaptador_pct": oov_word_pct(canon, vocab),
        "palabras_fuera_vocab_despues_del_adaptador_pct": oov_word_pct(tts_texts, vocab),
        "caracteres_fuera_vocab_restantes": dict(
            Counter(o.char for t in tts_texts for o in find_oov(t, vocab)).most_common()
        ),
    }


def latency(docs: list[str], pipeline: Pipeline, reps: int) -> dict:
    timer = Timer()
    for _ in range(reps):
        for d in docs:
            pipeline.process_text(d, timer)
    return timer.summary()


def rules_status() -> dict:
    total: Counter[str] = Counter()
    for p in all_resource_paths():
        total.update(load_resource(p).counts())
    return {
        "total": sum(total.values()),
        "validadas": total.get("validado", 0),
        "candidato_corpus": total.get("candidato-corpus", 0),
        "supuesto_ling": total.get("SUPUESTO-LING", 0) + total.get("SUPUESTO", 0),
    }


def load_test_news() -> list[str]:
    docs = []
    for f in sorted((ROOT / "data" / "news").glob("*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        for item in data if isinstance(data, list) else [data]:
            docs.append(NewsIn.model_validate(item).cuerpo_cni)
    return docs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=100)
    args = ap.parse_args(argv)
    from app.corpus.loader import load_split

    pipeline = Pipeline.default()
    corpus = build_report()
    dev_docs = [p.cni for p in load_split("dev")]
    test_news = load_test_news()
    candidates_path = ROOT / "data" / "candidates"
    cand_counts = {}
    if candidates_path.exists():
        import yaml

        for name, key in [
            ("numerals", "numerales"),
            ("acronyms", "siglas"),
            ("loanwords", "prestamos"),
            ("proper_nouns", "nombres_propios"),
            ("orthography_variants", "pares_variantes"),
        ]:
            data = yaml.safe_load((candidates_path / f"{name}.yaml").read_text(encoding="utf-8"))
            cand_counts[key] = len(data or [])

    orth = RESULTS_DIR / "mms_orthography.json"
    orth_data = json.loads(orth.read_text(encoding="utf-8")) if orth.exists() else None
    cov_path = ROOT / "coverage.json"
    coverage = (
        round(json.loads(cov_path.read_text())["totals"]["percent_covered"], 2)
        if cov_path.exists()
        else "no_medido (ejecuta pytest --cov --cov-report=json)"
    )
    h0 = MmsCniAdapter.from_files("H0")

    lat_docs = dev_docs[:50]
    payload = {
        "fase": 1,
        "commit": git_commit(),
        "fecha": datetime.now(UTC).isoformat(timespec="seconds"),
        "hardware": hardware(),
        "versiones_fijadas": {
            "americasnlp2021": AMERICASNLP_COMMIT,
            "mms-tts-cni": MMS_TTS_REVISION,
            "mms-1b-all": MMS_ASR_REVISION,
        },
        "resources_hash": {Path(p).name: load_resource(p).sha256 for p in all_resource_paths()},
        "corpus": {
            **{
                s: {
                    k: v
                    for k, v in corpus["splits"][s].items()
                    if k not in {"top_fuera_vocab", "letras", "variantes"}
                }
                for s in ("train", "dev", "test")
            },
            "diferencias_con_plan": corpus["diferencias_con_plan"] or "ninguna",
        },
        "candidatos": cand_counts,
        "noticias_prueba": (
            analyze(test_news, pipeline)
            if test_news
            else "no_medido (no hay noticias de prueba en data/news/)"
        ),
        "dev": analyze(dev_docs, pipeline),
        "vocab_mms_texto_crudo_dev": {
            "palabras_fuera_vocab_pct": oov_word_pct(dev_docs, h0.vocab()),
        },
        "ortografia_mms": (
            {
                "hipotesis": {
                    h: {
                        "cer_canonico": r["cer_canonico"],
                        "ic95": r["ic95"],
                        "cer_mms": r["cer_mms"],
                        "precision_palabra": r["precision_palabra"],
                    }
                    for h, r in orth_data["hipotesis"].items()
                },
                "elegida": orth_data["elegida"],
                "comparacion_vs_H0": orth_data["comparacion_vs_H0"],
                "escucha_ab": orth_data["hoja_ab"],
                "muestra": orth_data["muestra"],
            }
            if orth_data
            else "no_medido (ejecuta eval.fase1.mms_orthography.run)"
        ),
        "reglas": rules_status(),
        "g2p_per": "no_medido (falta P5; lista de muestreo en eval/fase1/p5_sample.csv)",
        "reescritura_aceptada_pct": "pendiente_hablante",
        "latencia_ms": {
            "n_documentos": len(lat_docs),
            "repeticiones": args.reps,
            **latency(lat_docs, pipeline, args.reps),
        },
        "cobertura_tests_pct": coverage,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / "fase_1.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[fase1] métricas escritas en {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
