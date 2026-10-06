"""Extracción de candidatos desde el corpus (tarea 1.0).

Todo lo que produce este módulo lleva ``status: candidato-corpus``: es evidencia para que una
persona experta decida, no un dato confirmado. Solo se usan los splits **train** y **dev**;
**test** queda reservado para la medición final (disciplina de splits).

Salidas en ``data/candidates/``: numerals, acronyms, loanwords, proper_nouns,
orthography_variants y graphemes (YAML deterministas: mismo corpus → mismo archivo).
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import yaml

from app.config import CANDIDATES_DIR
from app.corpus.loader import Pair, load_split

EXTRACT_SPLITS = ("train", "dev")
MAX_EXAMPLES = 3

WORD_RX = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)?")
NUMERAL_RX = re.compile(r"([^\W\d_]+)\s?\((\d+(?:[.,]\d+)?)\)")
ACRONYM_RX = re.compile(r"\b(?:[A-ZÁÉÍÓÚÑ]\.){2,}|\b[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ0-9]{1,5}\b")
ROMAN_RX = re.compile(r"^(?=[IVX]{2,}$)X{0,3}(IX|IV|V?I{0,3})$")
SENTENCE_START_RX = re.compile(r"(^|[.!?¿¡:;]\s+|^\W+)$")

# Claves de agrupación para detectar variantes de escritura de la MISMA palabra.
# Son las sustituciones que el informe muestra en conflicto; agrupar no decide la forma canónica.
VARIANT_KEY_RULES = [
    (re.compile(r"tz"), "ts"),
    (re.compile(r"qu(?=[eiéí])"), "k"),
    (re.compile(r"c(?!h)"), "k"),
    (re.compile(r"v"), "b"),
]


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def is_heading(line: str) -> bool:
    """Línea mayoritariamente en mayúsculas (títulos): sus palabras no son siglas."""
    words = WORD_RX.findall(line)
    if len(words) < 2:
        return False
    upper = sum(1 for w in words if w.isupper() and len(w) > 1)
    return upper / len(words) >= 0.6


def _pairs() -> list[Pair]:
    out: list[Pair] = []
    for split in EXTRACT_SPLITS:
        out.extend(load_split(split))
    return out


def _example(pair: Pair, start: int, end: int, width: int = 40) -> dict:
    a, b = max(0, start - width), min(len(pair.cni), end + width)
    return {"ref": pair.ref, "cni": pair.cni[a:b].strip()}


def extract_numerals(pairs: list[Pair]) -> list[dict]:
    found: dict[tuple[str, str], list] = defaultdict(list)
    for p in pairs:
        for m in NUMERAL_RX.finditer(p.cni):
            found[(m.group(1).lower(), m.group(2))].append((p, m.start(), m.end()))
    word_values: dict[str, set[str]] = defaultdict(set)
    for w, v in found:
        word_values[w].add(v)
    out = []
    for (w, v), occ in sorted(found.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        noise = []
        if not v.isdigit():
            noise.append("valor no entero")
        if len(word_values[w]) > 1:
            noise.append(f"la palabra aparece con varios valores: {sorted(word_values[w])}")
        out.append(
            {
                "source_form": w,
                "value": v,
                "frequency": len(occ),
                "noise": noise,
                "examples": [_example(*o) for o in occ[:MAX_EXAMPLES]],
                "status": "candidato-corpus",
            }
        )
    return out


def extract_acronyms(pairs: list[Pair]) -> list[dict]:
    found: dict[str, list] = defaultdict(list)
    for p in pairs:
        if is_heading(p.cni):
            continue
        for m in ACRONYM_RX.finditer(p.cni):
            found[m.group(0).rstrip(".") if m.group(0).count(".") < 2 else m.group(0)].append(
                (p, m.start(), m.end())
            )
    out = []
    for form, occ in sorted(found.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        bare = form.replace(".", "")
        out.append(
            {
                "source_form": form,
                "kind": "romano" if ROMAN_RX.match(bare) else "sigla",
                "frequency": len(occ),
                "in_spanish_line": sum(1 for o in occ if bare in o[0].es.replace(".", "")),
                "examples": [_example(*o) for o in occ[:MAX_EXAMPLES]],
                "status": "candidato-corpus",
            }
        )
    return out


def _sentence_initial(text: str, start: int) -> bool:
    return bool(SENTENCE_START_RX.search(text[:start]))


def extract_loans_and_names(pairs: list[Pair]) -> tuple[list[dict], list[dict]]:
    loans: dict[str, list] = defaultdict(list)
    names: dict[str, list] = defaultdict(list)
    for p in pairs:
        es_words = {strip_accents(w.lower()) for w in WORD_RX.findall(p.es)}
        es_raw = set(WORD_RX.findall(p.es))
        heading = is_heading(p.cni)
        for m in WORD_RX.finditer(p.cni):
            w = m.group(0)
            if len(w) < 4 or heading:
                continue
            if w[0].isupper() and not _sentence_initial(p.cni, m.start()):
                if w in es_raw:
                    names[w].append((p, m.start(), m.end()))
            elif w.islower() and strip_accents(w) in es_words:
                loans[w].append((p, m.start(), m.end()))

    def pack(d: dict[str, list]) -> list[dict]:
        return [
            {
                "source_form": w,
                "frequency": len(occ),
                "examples": [_example(*o) for o in occ[:MAX_EXAMPLES]],
                "status": "candidato-corpus",
            }
            for w, occ in sorted(d.items(), key=lambda kv: (-len(kv[1]), kv[0]))
        ]

    # Un nombre propio candidato no se reporta además como préstamo
    for n in names:
        loans.pop(n.lower(), None)
    return pack(loans), pack(names)


def variant_key(word: str) -> str:
    k = word
    for rx, rep in VARIANT_KEY_RULES:
        k = rx.sub(rep, k)
    return k


def extract_variants(pairs: list[Pair], loans: set[str], names: set[str]) -> list[dict]:
    counts: Counter[str] = Counter()
    first_ref: dict[str, str] = {}
    for p in pairs:
        for w in WORD_RX.findall(p.cni):
            lw = w.lower()
            if lw in loans or w in names:
                continue
            counts[lw] += 1
            first_ref.setdefault(lw, p.ref)
    groups: dict[str, list[str]] = defaultdict(list)
    for w in counts:
        groups[variant_key(w)].append(w)
    out = []
    for key, forms in groups.items():
        if len(forms) < 2:
            continue
        forms_sorted = sorted(forms, key=lambda f: (-counts[f], f))
        out.append(
            {
                "key": key,
                "forms": [
                    {"form": f, "count": counts[f], "ref": first_ref[f]} for f in forms_sorted
                ],
                "total": sum(counts[f] for f in forms),
                "status": "candidato-corpus",
            }
        )
    out.sort(key=lambda g: (-g["total"], g["key"]))
    return out


def extract_graphemes(pairs: list[Pair], loans: set[str], names: set[str]) -> dict:
    """Letras observadas en palabras que NO aparecen en la oración castellana paralela.

    Criterio documentado: una letra es candidata a grafema nativo si su frecuencia relativa en
    esas palabras es >= 0,5 %. Los dígrafos se cuentan como evidencia, pero que representen un
    único fonema es una decisión lingüística (P1) que este módulo NO toma.
    """
    letters: Counter[str] = Counter()
    bigrams: Counter[str] = Counter()
    for p in pairs:
        es_words = {strip_accents(w.lower()) for w in WORD_RX.findall(p.es)}
        for w in WORD_RX.findall(p.cni):
            lw = w.lower()
            if lw in loans or w in names or strip_accents(lw) in es_words:
                continue
            letters.update(lw)
            bigrams.update(lw[i : i + 2] for i in range(len(lw) - 1))
    total = sum(letters.values())
    rows = [
        {"grapheme": c, "count": n, "pct": round(100 * n / total, 3)}
        for c, n in sorted(letters.items(), key=lambda kv: (-kv[1], kv[0]))
    ]
    digraph_candidates = ["ch", "sh", "ts", "ty", "ny", "tz", "qu"]
    return {
        "criterio": "frecuencia relativa >= 0,5 % en palabras no compartidas con la línea castellana",
        "umbral_pct": 0.5,
        "letras": rows,
        "nativas_candidatas": [r["grapheme"] for r in rows if r["pct"] >= 0.5],
        "digrafos_observados": {d: bigrams[d] for d in digraph_candidates},
    }


def _dump(data, path: Path, header: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=100)
    path.write_text(header + body, encoding="utf-8", newline="\n")


HEADER = (
    "# GENERADO por `uv run python -m app.cli corpus extract` desde AmericasNLP2021@d3f519c\n"
    "# (splits train y dev). status: candidato-corpus = evidencia, NO dato validado.\n"
)


def extract_all(out_dir: Path = CANDIDATES_DIR) -> dict[str, int]:
    pairs = _pairs()
    numerals = extract_numerals(pairs)
    acronyms = extract_acronyms(pairs)
    loans, names = extract_loans_and_names(pairs)
    loan_set = {x["source_form"] for x in loans}
    name_set = {x["source_form"] for x in names}
    variants = extract_variants(pairs, loan_set, name_set)
    graphemes = extract_graphemes(pairs, loan_set, name_set)
    _dump(numerals, out_dir / "numerals.yaml", HEADER)
    _dump(acronyms, out_dir / "acronyms.yaml", HEADER)
    _dump(loans, out_dir / "loanwords.yaml", HEADER)
    _dump(names, out_dir / "proper_nouns.yaml", HEADER)
    _dump(variants, out_dir / "orthography_variants.yaml", HEADER)
    _dump(graphemes, out_dir / "graphemes.yaml", HEADER)
    return {
        "numerales": len(numerals),
        "siglas": len(acronyms),
        "prestamos": len(loans),
        "nombres_propios": len(names),
        "pares_variantes": len(variants),
    }
