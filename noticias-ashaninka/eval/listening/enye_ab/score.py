"""Puntúa la escucha A/B de la ñ.

Uso: uv run python -m eval.listening.enye_ab.score respuestas_escucha_enye.csv [--oyente ID]

Lee las respuestas (exportadas desde hoja_escucha.html, o la hoja CSV llenada a mano) y la clave
(out/clave.csv), y reporta:
* controles: % de pares idénticos marcados "igual" (atención/consistencia del oyente);
* por par de hipótesis: victorias, empates y prueba binomial exacta bilateral (sin empates);
* tasa de victoria de cada hipótesis, también separada por ñ inicial/interna.
Resultado en eval/results/escucha_enye_<oyente>.json
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from math import comb
from pathlib import Path

from app.config import RESULTS_DIR

HERE = Path(__file__).parent


def binom_two_sided(k: int, n: int) -> float:
    if n == 0:
        return 1.0
    tail = sum(comb(n, i) for i in range(0, min(k, n - k) + 1)) / 2**n
    return min(1.0, 2 * tail)


def read_answers(path: Path) -> dict[int, str]:
    out = {}
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            ans = (row.get("respuesta") or row.get("respuesta(A/B/igual)") or "").strip().lower()
            if ans in {"a", "b", "igual"}:
                out[int(row["par"])] = ans
    return out


def score(answers: dict[int, str], key_path: Path = HERE / "out" / "clave.csv") -> dict:
    with open(key_path, encoding="utf-8", newline="") as f:
        key = list(csv.DictReader(f))
    catch_total = catch_ok = 0
    pair_stats: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    wins: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    answered = 0
    for k in key:
        n = int(k["par"])
        if n not in answers:
            continue
        answered += 1
        ans = answers[n]
        if k["control"] == "True":
            catch_total += 1
            catch_ok += ans == "igual"
            continue
        a, b = k["A"], k["B"]
        label = "-".join(sorted((a, b)))
        if ans == "igual":
            pair_stats[label]["empates"] += 1
            continue
        winner = a if ans == "a" else b
        pair_stats[label][winner] += 1
        for scope in ("total", k["posicion"]):
            wins[scope][winner] += 1
            wins[scope]["_comparaciones"] += 1
    pairs_out = {}
    for label, st in pair_stats.items():
        h1, h2 = label.split("-")
        n_dec = st[h1] + st[h2]
        pairs_out[label] = {
            h1: st[h1],
            h2: st[h2],
            "empates": st["empates"],
            "p_binomial": round(binom_two_sided(st[h1], n_dec), 4),
        }
    rates = {
        scope: {h: round(c / w["_comparaciones"], 3) for h, c in w.items() if h != "_comparaciones"}
        for scope, w in wins.items()
    }
    return {
        "pares_respondidos": answered,
        "pares_totales": len(key),
        "controles": {
            "total": catch_total,
            "marcados_igual": catch_ok,
            "pct": round(100 * catch_ok / catch_total, 1) if catch_total else None,
        },
        "por_par": pairs_out,
        "tasa_victoria": rates,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("respuestas")
    ap.add_argument("--oyente", default="anonimo")
    args = ap.parse_args(argv)
    result = score(read_answers(Path(args.respuestas)))
    result["oyente"] = args.oyente
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / f"escucha_enye_{args.oyente}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
