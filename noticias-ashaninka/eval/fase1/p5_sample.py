"""Lista de muestreo para P5: 200 palabras de train para transcripción fonémica por una persona experta.

Muestreo estratificado y reproducible (semilla fija):
* solo palabras clasificadas como asháninka por el normalizador (no castellano, siglas ni nombres);
* tres estratos de frecuencia (alta: top 10 %, media, baja: frecuencia 1-2), en proporción 40/40/20;
* se garantiza que cada grafema del inventario candidato aparezca al menos 5 veces en la muestra.

Uso: uv run python -m eval.fase1.p5_sample  ->  eval/fase1/p5_sample.csv
La columna "transcripcion_fonemica" queda vacía para la persona experta.
"""

from __future__ import annotations

import csv
import random
from collections import Counter
from pathlib import Path

from app.corpus.loader import load_split
from app.pipeline.g2p.engine import G2P
from app.pipeline.normalize.engine import DocumentState, Normalizer

SEED = 20261005
N = 200
OUT = Path(__file__).parent / "p5_sample.csv"


def main() -> int:
    normalizer = Normalizer.from_files()
    g2p = G2P.from_files()
    counts: Counter[str] = Counter()
    for p in load_split("train"):
        r = normalizer.normalize(p.cni, DocumentState())
        for s in r.spans:
            if s.category == "cni" and len(s.norm_text) >= 3:
                counts[s.norm_text] += 1
    ranked = [w for w, _ in counts.most_common()]
    top = ranked[: max(1, len(ranked) // 10)]
    low = [w for w in ranked if counts[w] <= 2]
    mid = [w for w in ranked if w not in set(top) | set(low)]
    rng = random.Random(SEED)
    sample: list[tuple[str, str]] = []
    for stratum, words, k in (("alta", top, 80), ("media", mid, 80), ("baja", low, 40)):
        pick = rng.sample(words, min(k, len(words)))
        sample += [(w, stratum) for w in pick]
    # cobertura mínima de grafemas
    units = set(g2p.units)
    have = Counter(u for w, _ in sample for u in g2p.word(w)[0].phonemes)
    for unit in sorted(units):
        label = f"<{unit}>"
        extra = [
            w
            for w in ranked
            if label in g2p.word(w)[0].phonemes and w not in {x for x, _ in sample}
        ]
        while have[label] < 5 and extra:
            w = extra.pop(0)
            sample.append((w, "cobertura"))
            have.update(g2p.word(w)[0].phonemes)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(
            [
                "palabra_canonica",
                "frecuencia_train",
                "estrato",
                "segmentacion_g2p",
                "transcripcion_fonemica",
            ]
        )
        for w, stratum in sample:
            wr.writerow([w, counts[w], stratum, " ".join(g2p.word(w)[0].phonemes), ""])
    print(f"[P5] {len(sample)} palabras escritas en {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
