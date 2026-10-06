"""Medición de latencia por etapa (ms). Cada etapa del pipeline mide su propio tiempo."""

from __future__ import annotations

import statistics
import time
from collections import defaultdict
from collections.abc import Iterator
from contextlib import contextmanager


def percentile(values: list[float], p: float) -> float:
    """Percentil con interpolación lineal (equivalente a numpy 'linear')."""
    if not values:
        return float("nan")
    s = sorted(values)
    k = (len(s) - 1) * p / 100
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


class Timer:
    def __init__(self) -> None:
        self.samples: dict[str, list[float]] = defaultdict(list)

    @contextmanager
    def measure(self, stage: str) -> Iterator[None]:
        t0 = time.perf_counter()
        try:
            yield
        finally:
            self.samples[stage].append((time.perf_counter() - t0) * 1000)

    def summary(self) -> dict[str, dict[str, float]]:
        return {
            stage: {
                "n": len(v),
                "p50": round(percentile(v, 50), 4),
                "p95": round(percentile(v, 95), 4),
                "media": round(statistics.fmean(v), 4),
            }
            for stage, v in self.samples.items()
        }
