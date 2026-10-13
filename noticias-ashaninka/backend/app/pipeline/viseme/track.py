"""Pista de visemas con coarticulación (tareas 3.3 y 3.4).

Del alineamiento por fonema (``align.py``) y del mapa grafema -> visema (``map.yaml``) se
construye una pista de ``eventos`` contiguos (cada uno con un vector de pesos por canal) y, de
ella, ``keyframes`` lineales por tramos que el cliente solo tiene que interpolar:

* cada evento mantiene su vector de pesos y entre dos eventos contiguos hay una transición de
  ancho ``s = min(smooth_ms, duración de ambos)``, ubicada alrededor del límite según ``lead``
  (``lead`` = fracción de la transición que ocurre ANTES del límite);
* coarticulación anticipatoria: una consonante sin forma labial propia adopta una fracción
  (``coarticulation``) de la forma de la vocal siguiente si es contigua (misma palabra);
* los huecos (espacios, puntuación, grafemas desconocidos) y el silencio final son eventos
  neutros (todos los pesos en 0).

SUPUESTO-LING: el mapa entero. Cada pista lleva ``status`` y el hash del mapa para trazabilidad.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.config import VISEME_RESOURCES, get_settings
from app.pipeline.resources import Resource, get_resource
from app.pipeline.viseme.align import PhonemeTime, WordTime

MAP_PATH = VISEME_RESOURCES / "map.yaml"
VOWELS = ("A", "I", "U", "E", "O")
EPS = 1e-6

Event = tuple[float, float, list[float], str]


@dataclass(frozen=True)
class VisemeEntry:
    id: str
    weights: dict[str, float]
    coarticulation: float


class VisemeMap:
    def __init__(self, resource: Resource):
        cfg = resource.config
        self.channels: list[str] = list(cfg["channels"])
        self.default_smooth_ms: float = float(cfg.get("smooth_ms", 50))
        self.default_lead: float = float(cfg.get("lead", 0.5))
        self.sha256: str = resource.sha256 or ""
        self.status = "SUPUESTO-LING"
        self.entries: dict[str, VisemeEntry] = {}
        for e in resource.entries:  # el mapa completo es SUPUESTO-LING: se usan todas sus entradas
            extra = e.model_extra or {}
            bad = set(extra.get("weights", {})) - set(self.channels)
            if bad:
                raise ValueError(f"{e.id}: canales desconocidos {sorted(bad)}")
            self.entries[extra["grapheme"]] = VisemeEntry(
                e.id, dict(extra.get("weights", {})), float(extra.get("coarticulation", 0.0))
            )

    @classmethod
    def from_file(cls, path: Path = MAP_PATH) -> VisemeMap:
        return cls(get_resource(path))

    def vector(self, weights: dict[str, float]) -> list[float]:
        return [round(float(weights.get(c, 0.0)), 4) for c in self.channels]


def _params(vm: VisemeMap, smooth_ms: float | None, lead: float | None) -> tuple[float, float]:
    cfg = get_settings()
    s = smooth_ms if smooth_ms is not None else cfg.viseme_smooth_ms
    s = vm.default_smooth_ms if s is None else s
    ld = lead if lead is not None else cfg.viseme_lead
    ld = vm.default_lead if ld is None else ld
    if not 0.0 <= ld <= 1.0 or s < 0:
        raise ValueError("smooth_ms debe ser >= 0 y lead debe estar entre 0 y 1")
    return float(s), float(ld)


def build_events(phonemes: list[PhonemeTime], total_s: float, vm: VisemeMap) -> list[Event]:
    """Eventos contiguos (t0, t1, vector, grafema) que cubren [0, total_s]."""
    # (t0, t1, pesos, coarticulación, índice de palabra, grafema); palabra -1 = hueco neutro
    raw: list[tuple[float, float, dict[str, float], float, int, str]] = []
    cursor = 0.0
    for p in sorted(phonemes, key=lambda x: (x.t0, x.t1)):
        entry = vm.entries.get(p.g)
        t0, t1 = max(p.t0, cursor), min(max(p.t1, cursor), total_s)
        if t1 - t0 <= EPS:
            continue  # sin duración audible: no genera evento
        if t0 - cursor > EPS:
            raw.append((cursor, t0, {}, 0.0, -1, ""))
        raw.append(
            (
                t0,
                t1,
                dict(entry.weights) if entry else {},
                entry.coarticulation if entry else 0.0,
                p.word,
                p.g,
            )
        )
        cursor = t1
    if total_s - cursor > EPS:
        raw.append((cursor, total_s, {}, 0.0, -1, ""))
    events: list[Event] = []
    for i, (t0, t1, w, coart, word, g) in enumerate(raw):
        vec = vm.vector(w)
        if coart > 0 and i + 1 < len(raw):
            n_t0, _, n_w, _, n_word, _ = raw[i + 1]
            if (
                n_word == word
                and abs(n_t0 - t1) <= EPS
                and any(n_w.get(v, 0.0) > 0 for v in VOWELS)
            ):
                add = vm.vector({v: coart * n_w.get(v, 0.0) for v in VOWELS})
                vec = [min(1.0, a + b) for a, b in zip(vec, add, strict=True)]
        events.append((t0, t1, vec, g))
    return events


def build_keyframes(events: list[Event], smooth_ms: float, lead: float) -> list[list]:
    """Puntos [t, [pesos…]] de una curva lineal por tramos con transiciones suavizadas."""
    # Eventos contiguos con el mismo vector son una sola forma: se funden (la curva no cambia)
    merged: list[Event] = []
    for ev in events:
        if merged and merged[-1][2] == ev[2]:
            merged[-1] = (merged[-1][0], ev[1], ev[2], merged[-1][3])
        else:
            merged.append(ev)
    events = merged
    n = len(events)
    if n == 0:
        return []
    s = [0.0] * (n + 1)  # s[i] = ancho de la transición ANTES del evento i (s[0] = s[n] = 0)
    for i in range(1, n):
        d_prev = events[i - 1][1] - events[i - 1][0]
        d_next = events[i][1] - events[i][0]
        s[i] = max(0.0, min(smooth_ms / 1000.0, d_prev, d_next))
    knots: list[tuple[float, list[float]]] = []
    for i, (t0, t1, vec, _g) in enumerate(events):
        a = t0 + (1.0 - lead) * s[i]
        b = t1 - lead * s[i + 1]
        knots.append((a, vec))
        if b - a > EPS:
            knots.append((b, vec))
    out: list[list] = []
    for t, vec in knots:
        if out and abs(out[-1][0] - t) <= EPS and out[-1][1] == vec:
            continue
        out.append([round(t, 4), vec])
    return out


def build_track(
    words: list[WordTime],
    phonemes: list[PhonemeTime],
    total_s: float,
    vm: VisemeMap | None = None,
    smooth_ms: float | None = None,
    lead: float | None = None,
) -> dict:
    """Bloques ``alignment`` y ``visemes`` que se escriben en ``seg_NNN.json``."""
    vm = vm or VisemeMap.from_file()
    smooth, ld = _params(vm, smooth_ms, lead)
    events = build_events(phonemes, total_s, vm)
    return {
        "alignment": {
            "words": [w.to_dict() for w in words],
            "phonemes": [p.to_dict() for p in phonemes],
            "nota": "SUPUESTO-LING: el fonema es el grafema segmentado por el G2P (P1 abierto)",
        },
        "visemes": {
            "status": vm.status,
            "map_sha256": vm.sha256,
            "channels": vm.channels,
            "smooth_ms": smooth,
            "lead": ld,
            "duration_s": round(total_s, 4),
            "events": [
                {"t0": round(a, 4), "t1": round(b, 4), "w": v, "g": g} for a, b, v, g in events
            ],
            "keyframes": build_keyframes(events, smooth, ld),
        },
    }


def sample(keyframes: list[list], t: float) -> list[float]:
    """Evalúa la curva en el instante ``t`` (misma regla que el cliente TypeScript)."""
    if not keyframes:
        return []
    if t <= keyframes[0][0]:
        return list(keyframes[0][1])
    if t >= keyframes[-1][0]:
        return list(keyframes[-1][1])
    lo, hi = 0, len(keyframes) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if keyframes[mid][0] <= t:
            lo = mid
        else:
            hi = mid
    (t0, v0), (t1, v1) = keyframes[lo], keyframes[hi]
    u = (t - t0) / (t1 - t0) if t1 > t0 else 1.0
    return [a + (b - a) * u for a, b in zip(v0, v1, strict=True)]
