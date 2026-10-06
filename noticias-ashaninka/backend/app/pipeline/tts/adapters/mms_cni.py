"""2e — Adaptador ortográfico canónica -> ortografía de entrenamiento de facebook/mms-tts-cni.

Las hipótesis (H0, H1, …) se definen en ``mms_cni.yaml`` y son condiciones experimentales
(tarea 1.9). H0 reproduce el defecto: el texto pasa sin adaptar (solo en minúsculas) y es el
tokenizador quien elimina lo que no conoce; por eso H0 nunca supera la validación 2f.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.config import ADAPTERS_DIR, MMS_VOCAB
from app.pipeline.resources import Resource, get_resource
from app.pipeline.rules import RewriteEngine, RewriteRule
from app.pipeline.tts.adapters.base import OrthographyAdapter
from app.pipeline.tts.adapters.validate import find_oov, validate_tts_text
from app.pipeline.types import AdaptedText, CharMapEntry


def load_mms_vocab(path: Path = MMS_VOCAB) -> set[str]:
    return set(json.loads(path.read_text(encoding="utf-8")))


class MmsCniAdapter(OrthographyAdapter):
    def __init__(
        self, resource: Resource, hypothesis: str | None = None, vocab: set[str] | None = None
    ):
        cfg = resource.config
        self.hypothesis = hypothesis or cfg.get("active", "H1")
        hyps = cfg.get("hypotheses", {})
        if self.hypothesis not in hyps:
            raise ValueError(f"Hipótesis desconocida: {self.hypothesis} (hay {sorted(hyps)})")
        spec = hyps[self.hypothesis]
        self.description = spec.get("description", "")
        self.raw = bool(spec.get("raw", False))
        by_id = {e.id: e for e in resource.entries}
        rule_ids = [] if self.raw else [*cfg.get("typographic", []), *spec.get("rules", [])]
        missing = [r for r in rule_ids if r not in by_id]
        if missing:
            raise ValueError(f"{self.hypothesis}: reglas inexistentes {missing}")
        self.rule_ids = rule_ids
        self.engine = RewriteEngine(
            [
                RewriteRule(
                    r, by_id[r].pattern or "", by_id[r].replacement or "", by_id[r].description
                )
                for r in rule_ids
            ]
        )
        self.id = f"mms_cni/{self.hypothesis}"
        self._vocab = vocab

    @classmethod
    def from_files(
        cls, hypothesis: str | None = None, path: Path = ADAPTERS_DIR / "mms_cni.yaml"
    ) -> MmsCniAdapter:
        return cls(get_resource(path), hypothesis)

    def vocab(self) -> set[str]:
        if self._vocab is None:
            self._vocab = load_mms_vocab()
        return self._vocab

    def adapt(self, text_canonical: str) -> AdaptedText:
        text = text_canonical.lower()
        if self.raw:
            return AdaptedText(text, [CharMapEntry(0, len(text), 0, len(text), None)], self.id)
        out, cmap = self.engine.apply(text)
        # Recorta espacios en los bordes manteniendo el mapa coherente
        lead = len(out) - len(out.lstrip(" "))
        trail = len(out) - len(out.rstrip(" "))
        if lead or trail:
            out, cmap = _trim(out, cmap, lead, trail)
        return AdaptedText(out, cmap, self.id)

    def adapt_validated(self, text_canonical: str) -> AdaptedText:
        """Adapta y valida (2f). Lanza ``OutOfVocabularyError`` si algo queda fuera."""
        adapted = self.adapt(text_canonical)
        validate_tts_text(adapted.text_tts, self.vocab())
        return adapted

    def oov_after(self, text_canonical: str) -> list[str]:
        return [o.char for o in find_oov(self.adapt(text_canonical).text_tts, self.vocab())]


def _trim(out: str, cmap: list[CharMapEntry], lead: int, trail: int):
    """Elimina ``lead`` espacios iniciales y ``trail`` finales ajustando los offsets de destino."""
    new_len = len(out) - lead - trail
    fixed: list[CharMapEntry] = []
    for e in cmap:
        ds = min(max(e.dst_start - lead, 0), new_len)
        de = min(max(e.dst_end - lead, 0), new_len)
        fixed.append(CharMapEntry(e.src_start, e.src_end, ds, de, e.rule_id))
    return out[lead : len(out) - trail if trail else None], fixed
