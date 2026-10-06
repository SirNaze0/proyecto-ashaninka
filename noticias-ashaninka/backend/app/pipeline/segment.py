"""Segmentación en párrafos y oraciones (tarea 1.4).

Los offsets se conservan respecto al texto original: ``text[seg.start:seg.end] == seg.text``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from app.config import NORMALIZE_RESOURCES
from app.pipeline.resources import get_resource

PARAGRAPH_SPLIT = re.compile(r"\n+")


@dataclass(frozen=True)
class SegmentSpan:
    idx: int
    paragraph_idx: int
    start: int
    end: int
    text: str


class Segmenter:
    def __init__(
        self,
        terminators: str = ".!?…",
        abbreviations: list[str] | None = None,
        enumeration_max_digits: int = 3,
    ):
        self.terminators = terminators
        self.abbreviations = {a.lower().rstrip(".") for a in (abbreviations or [])}
        self.enum_rx = re.compile(rf"^\s*\d{{1,{enumeration_max_digits}}}$")
        t = re.escape(terminators)
        # fin de oración: uno o más terminadores (+ comillas/paréntesis de cierre) y espacio
        self.boundary = re.compile(rf"[{t}]+[\"'”’)\]]*(?=\s+)")

    @classmethod
    def from_files(cls, path: Path = NORMALIZE_RESOURCES / "segmentation.yaml") -> Segmenter:
        cfg = get_resource(path).config
        return cls(
            cfg.get("terminators", ".!?…"),
            cfg.get("abbreviations", []),
            int(cfg.get("enumeration_max_digits", 3)),
        )

    def _is_false_boundary(self, para: str, para_start: int, end_of_mark: int) -> bool:
        before = para[para_start:end_of_mark].rstrip(self.terminators + "\"'”’)]")
        last = re.split(r"\s+", before.strip())[-1] if before.strip() else ""
        if last.lower().rstrip(".") in self.abbreviations:
            return True
        # "1." al inicio de un párrafo: enumeración, no fin de oración
        return bool(self.enum_rx.match(before))

    def segment(self, text: str) -> list[SegmentSpan]:
        out: list[SegmentSpan] = []
        para_idx = -1
        pos = 0
        for m in [*PARAGRAPH_SPLIT.finditer(text), None]:
            p_end = m.start() if m else len(text)
            para = text[pos:p_end]
            if para.strip():
                para_idx += 1
                sent_start = 0
                for b in self.boundary.finditer(para):
                    if self._is_false_boundary(para, sent_start, b.end()):
                        continue
                    self._emit(out, text, pos + sent_start, pos + b.end(), para_idx)
                    sent_start = b.end()
                self._emit(out, text, pos + sent_start, p_end, para_idx)
            if m:
                pos = m.end()
        return out

    @staticmethod
    def _emit(out: list[SegmentSpan], text: str, start: int, end: int, para_idx: int) -> None:
        chunk = text[start:end]
        lead = len(chunk) - len(chunk.lstrip())
        trail = len(chunk) - len(chunk.rstrip())
        s, e = start + lead, end - trail
        if e > s:
            out.append(SegmentSpan(len(out), para_idx, s, e, text[s:e]))
