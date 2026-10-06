"""Informe del corpus: reproduce las mediciones del §3.2 de PLAN_DESARROLLO.md.

Método (idéntico al análisis exploratorio del 2026-10-05):

* caracteres: todos los caracteres no blancos del texto en minúsculas;
* tokens: coincidencias de la expresión ``\\w+`` (Unicode) sobre el texto original;
* tipos: tokens distintos en minúsculas;
* "fuera del vocabulario": carácter que no está en ``vocab.json`` de mms-tts-cni.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from app.config import DOCS_DIR, MMS_VOCAB
from app.corpus.loader import SPLITS, Pair, load_split

TOKEN_RX = re.compile(r"\w+")

# Valores publicados en PLAN_DESARROLLO.md v1.2 §3.2, para comparar
PLAN_VALUES = {
    "train": {
        "oraciones": 3883,
        "tokens": 26145,
        "tipos": 10231,
        "chars_fuera_vocab_pct": 13.46,
        "palabras_fuera_vocab_pct": 60.3,
        "lineas_con_digitos": 338,
    },
    "dev": {
        "oraciones": 883,
        "tokens": 6086,
        "tipos": 2686,
        "chars_fuera_vocab_pct": 10.87,
        "palabras_fuera_vocab_pct": 53.0,
        "lineas_con_digitos": 94,
    },
    "test": {
        "oraciones": 1003,
        "tokens": 6453,
        "tipos": 2899,
        "chars_fuera_vocab_pct": 11.2,
        "palabras_fuera_vocab_pct": 53.7,
        "lineas_con_digitos": 71,
    },
}

VARIANT_PAIRS = [("b", "v"), ("ts", "tz"), ("k", "c(?!h)"), ("k", "qu"), ("ñ", "ny")]


def load_vocab(path: Path = MMS_VOCAB) -> set[str]:
    return set(json.loads(path.read_text(encoding="utf-8")))


def split_stats(pairs: list[Pair], vocab: set[str]) -> dict:
    text = "\n".join(p.cni for p in pairs)
    low = text.lower()
    chars = Counter(ch for ch in low if not ch.isspace())
    total = sum(chars.values())
    oov = {c: n for c, n in chars.items() if c not in vocab}
    tokens = TOKEN_RX.findall(text)
    words = [t.lower() for t in tokens]
    oov_words = sum(1 for w in words if any(ch not in vocab for ch in w))
    letters = {c: n for c, n in chars.items() if c.isalpha()}
    return {
        "oraciones": len(pairs),
        "caracteres": total,
        "tokens": len(tokens),
        "tipos": len(set(words)),
        "chars_fuera_vocab_pct": round(100 * sum(oov.values()) / total, 2) if total else 0.0,
        "palabras_fuera_vocab_pct": round(100 * oov_words / len(words), 1) if words else 0.0,
        "lineas_con_digitos": sum(1 for p in pairs if re.search(r"\d", p.cni)),
        "top_fuera_vocab": sorted(oov.items(), key=lambda kv: -kv[1])[:20],
        "letras": sorted(letters.items(), key=lambda kv: -kv[1]),
        "variantes": {
            f"{a}/{b}": [len(re.findall(a, low)), len(re.findall(b, low))] for a, b in VARIANT_PAIRS
        },
    }


def digit_preservation(pairs: list[Pair]) -> dict:
    es_digits = [p for p in pairs if re.search(r"\d", p.es)]
    both = [p for p in es_digits if re.search(r"\d", p.cni)]
    return {"lineas_es_con_digitos": len(es_digits), "tambien_en_cni": len(both)}


def compare_with_plan(stats: dict[str, dict]) -> list[str]:
    diffs = []
    for split, expected in PLAN_VALUES.items():
        for key, val in expected.items():
            got = stats[split][key]
            if (isinstance(val, float) and abs(got - val) > 0.05) or (
                isinstance(val, int) and got != val
            ):
                diffs.append(f"{split}.{key}: plan={val}, medido={got}")
    return diffs


def build_report() -> dict:
    vocab = load_vocab()
    data = {s: load_split(s) for s in SPLITS}
    stats = {s: split_stats(p, vocab) for s, p in data.items()}
    return {
        "vocab_mms": sorted(vocab),
        "splits": stats,
        "digitos_train": digit_preservation(data["train"]),
        "diferencias_con_plan": compare_with_plan(stats),
    }


def render_markdown(rep: dict) -> str:
    s = rep["splits"]
    lines = [
        "# Informe del corpus AmericasNLP 2021 asháninka–castellano",
        "",
        "> GENERADO por `uv run python -m app.cli corpus report`. No editar a mano.",
        "> Corpus: commit `d3f519c` (hashes verificados). Vocabulario: `facebook/mms-tts-cni@a744890`.",
        "",
        "## Medidas por split",
        "",
        "| Medida | train | dev | test |",
        "|---|---|---|---|",
    ]
    rows = [
        ("Oraciones", "oraciones"),
        ("Caracteres (sin espacios)", "caracteres"),
        ("Tokens (`\\w+`)", "tokens"),
        ("Tipos (minúsculas)", "tipos"),
        ("% caracteres fuera del vocabulario MMS", "chars_fuera_vocab_pct"),
        ("% palabras con ≥1 carácter fuera del vocabulario MMS", "palabras_fuera_vocab_pct"),
        ("Líneas con dígitos", "lineas_con_digitos"),
    ]
    for label, key in rows:
        lines.append(f"| {label} | {s['train'][key]} | {s['dev'][key]} | {s['test'][key]} |")
    lines += [
        "",
        "## Vocabulario de mms-tts-cni",
        "",
        "`" + " ".join(c if c != " " else "␠" for c in rep["vocab_mms"]) + "`",
        "",
        "## Caracteres fuera del vocabulario más frecuentes (train)",
        "",
        "| Carácter | Apariciones |",
        "|---|---|",
    ]
    lines += [f"| `{c}` | {n} |" for c, n in s["train"]["top_fuera_vocab"]]
    lines += [
        "",
        "## Variación ortográfica (recuentos en el texto en minúsculas)",
        "",
        "| Par | train | dev | test |",
        "|---|---|---|---|",
    ]
    for pair in s["train"]["variantes"]:
        cells = [" / ".join(map(str, s[x]["variantes"][pair])) for x in ("train", "dev", "test")]
        lines.append(f"| `{pair}` | " + " | ".join(cells) + " |")
    d = rep["digitos_train"]
    lines += [
        "",
        "## Conservación de dígitos al traducir (train)",
        "",
        f"{d['tambien_en_cni']} de {d['lineas_es_con_digitos']} líneas castellanas con dígitos "
        "también tienen dígitos en asháninka.",
        "",
        "## Frecuencia de letras (train)",
        "",
        ", ".join(f"`{c}` {n}" for c, n in s["train"]["letras"]),
        "",
        "## Comparación con PLAN_DESARROLLO.md v1.2 §3.2",
        "",
    ]
    if rep["diferencias_con_plan"]:
        lines += [f"- {x}" for x in rep["diferencias_con_plan"]]
    else:
        lines.append("Ninguna diferencia: las mediciones coinciden con las publicadas en el plan.")
    lines.append("")
    return "\n".join(lines)


def write_report(out: Path = DOCS_DIR / "corpus_report.md") -> dict:
    rep = build_report()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_markdown(rep), encoding="utf-8", newline="\n")
    return rep
