"""2-0 (unificación ortográfica) y 2d (reescritura fonética castellano -> ortografía canónica cni).

Ambas usan el motor genérico de reglas ordenadas (``app.pipeline.rules``). Las reglas se leen
de ``orthography_variants.yaml`` y ``es_to_cni_phonology.yaml``; solo se aplican las usables
(``validado``, o también ``candidato-corpus``/``SUPUESTO-LING`` cuando el recurso lo declara
como decisión explícita del tesista, ver ``usable_statuses``).
"""

from __future__ import annotations

from app.pipeline.resources import Resource
from app.pipeline.rules import RewriteEngine, RewriteRule


def engine_from_resource(resource: Resource, statuses: set[str]) -> RewriteEngine:
    rules = [
        RewriteRule(e.id, e.pattern or "", e.replacement or "", e.description)
        for e in resource.entries
        if e.status in statuses and e.pattern
    ]
    return RewriteEngine(rules)


class Lexicon:
    """Léxico forma de origen -> forma canónica (préstamos, gazetteer, siglas)."""

    def __init__(self, resource: Resource, statuses: set[str]):
        self.items: dict[str, tuple[str | None, str, dict]] = {}
        for e in resource.entries:
            if e.status in statuses and e.source_form:
                extra = e.model_extra or {}
                self.items[e.source_form] = (e.replacement, e.id, extra)

    def __contains__(self, key: str) -> bool:
        return key in self.items

    def get(self, key: str):
        return self.items.get(key)

    def keys(self) -> set[str]:
        return set(self.items)
