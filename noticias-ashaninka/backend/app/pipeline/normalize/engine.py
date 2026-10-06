"""Normalizador (etapa 2): orquesta 2a–2d y produce el texto CANÓNICO + mapa de alineación.

Se procesa por documento (estado compartido para la regla de primera mención de siglas) y se
emite el resultado por segmento. Los offsets de cada resultado son relativos al texto del
segmento que se normaliza.

Orden por token: 2a clasifica → según la categoría, 2-0 unifica (solo palabras asháninka),
2b verbaliza, 2c expande siglas o 2d reescribe lo castellano. El detector editorial (1.5b)
marca sin modificar. Todo lo que no tiene regla va a ``unresolved``: nunca se descarta.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.config import G2P_RULES, NORMALIZE_RESOURCES
from app.pipeline.normalize.acronyms import AcronymExpander, AcronymState
from app.pipeline.normalize.classify import (
    Classifier,
    Token,
    roman_value,
    strip_accents,
    tokenize,
)
from app.pipeline.normalize.editorial import EditorialDetector
from app.pipeline.normalize.rewrite import Lexicon, engine_from_resource
from app.pipeline.normalize.verbalize import AmbiguousNumber, Verbalized, Verbalizer
from app.pipeline.resources import Resource, bundle_hash, get_resource
from app.pipeline.rules import RewriteEngine
from app.pipeline.types import EditorialFlag, NormalizationResult, NormalizedSpan, Unresolved


@dataclass
class DocumentState:
    acronyms: AcronymState = field(default_factory=AcronymState)


def _statuses(resource: Resource, allow_candidates: bool) -> set[str]:
    declared = resource.config.get("apply_statuses")
    base = set(declared) if declared else {"validado"}
    if allow_candidates:
        base.add("candidato-corpus")
    return base


class Normalizer:
    def __init__(
        self, resources: dict[str, Resource], inventory: Resource, allow_candidates: bool = False
    ):
        self.allow_candidates = allow_candidates
        self.resources = resources
        r = resources
        st = {k: _statuses(v, allow_candidates) for k, v in r.items()}

        self.unify: RewriteEngine = engine_from_resource(
            r["orthography_variants"], st["orthography_variants"]
        )
        self.es_rewrite: RewriteEngine = engine_from_resource(
            r["es_to_cni_phonology"], st["es_to_cni_phonology"]
        )
        self.p2d_active = bool(self.es_rewrite.rules)
        self.loanwords = Lexicon(r["loanwords"], st["loanwords"])
        self.proper_nouns = Lexicon(r["proper_nouns"], st["proper_nouns"])
        self.neologisms = Lexicon(r["neologisms"], st["neologisms"])
        acr_lex = Lexicon(r["acronyms"], st["acronyms"])
        self.acronyms = AcronymExpander(acr_lex, r["acronyms"].config.get("letter_names_es", {}))

        numerals: dict[int, tuple[str, str]] = {}
        for e in r["numerals_cni"].usable_entries(allow_candidates):
            value = (e.model_extra or {}).get("value")
            if e.replacement and value is not None and str(value).isdigit():
                numerals[int(value)] = (e.replacement, e.id)
        small_max = r["numerals_cni"].config.get("small_max")
        self.verbalizer = Verbalizer(int(small_max) if small_max is not None else None, numerals)

        # Letras "nativas": inventario candidato + las que la unificación 2-0 resuelve
        native: set[str] = set()
        for e in inventory.entries:
            native.update(getattr(e, "grapheme", "") or "")
        native.update(inventory.config.get("excluidas_por_unificacion", []))
        self.native_letters = native
        self.classifier = Classifier(
            native, self.proper_nouns.keys(), self.loanwords.keys(), acr_lex.keys()
        )

        rel = r["relative_dates"].config
        covered = (
            self.loanwords.keys()
            | self.neologisms.keys()
            | {k.lower() for k in self.proper_nouns.keys()}
        )
        self.editorial = EditorialDetector(rel.get("es", []), rel.get("cni", []), covered)
        self.resources_hash = bundle_hash([*r.values(), inventory])

    @classmethod
    def from_files(
        cls,
        allow_candidates: bool = False,
        resources_dir: Path = NORMALIZE_RESOURCES,
        g2p_dir: Path = G2P_RULES,
    ) -> Normalizer:
        names = [
            "orthography_variants",
            "numerals_cni",
            "acronyms",
            "loanwords",
            "es_to_cni_phonology",
            "neologisms",
            "proper_nouns",
            "relative_dates",
        ]
        res = {n: get_resource(resources_dir / f"{n}.yaml") for n in names}
        return cls(res, get_resource(g2p_dir / "inventory.yaml"), allow_candidates)

    # ------------------------------------------------------------------ utilidades
    def has_foreign(self, text: str) -> bool:
        return any(
            ch.isalpha() and ch not in self.native_letters for ch in strip_accents(text.lower())
        )

    def _rewrite_es(self, text: str) -> tuple[str, tuple[str, ...]]:
        out, cmap = self.es_rewrite.apply(text.lower())
        return out, tuple(dict.fromkeys(e.rule_id for e in cmap if e.rule_id))

    def _spanish(
        self,
        t: Token,
        text: str,
        category: str,
        extra_rules: tuple[str, ...],
        unresolved: list[Unresolved],
        reason: str,
    ) -> NormalizedSpan:
        """Texto castellano verbalizado/literal -> 2d.

        Queda en ``unresolved`` si ninguna regla P2d se aplicó (la política exige reescribirlo
        como lo diría un hablante bilingüe) o si conserva grafemas ajenos al inventario. Lo
        primero no bloquea el TTS; lo segundo sí lo bloqueará en la validación 2f.
        """
        out, rids = self._rewrite_es(text)
        if self.has_foreign(out):
            unresolved.append(Unresolved(t.start, t.end, t.text, reason))
        elif not rids and any(ch.isalpha() for ch in out):
            unresolved.append(
                Unresolved(
                    t.start,
                    t.end,
                    t.text,
                    "castellano sin reescribir (P2d); pronunciable pero "
                    "no normalizado según la política",
                )
            )
        return NormalizedSpan(t.start, t.end, t.text, out, category, (*extra_rules, *rids))

    # ------------------------------------------------------------------ API
    def normalize(self, text: str, state: DocumentState | None = None) -> NormalizationResult:
        state = state or DocumentState()
        tokens = self.classifier.classify(text, tokenize(text))
        spans: list[NormalizedSpan] = []
        flags: list[EditorialFlag] = list(self.editorial.relative_dates(text))
        unresolved: list[Unresolved] = []
        used_candidates = False
        no_p2d = "castellano sin reescritura fonética (P2d vacía o sin regla aplicable)"

        for t in tokens:
            c = t.category
            if c in {"espacio", "puntuacion"}:
                spans.append(NormalizedSpan(t.start, t.end, t.text, t.text, "identity"))
            elif c == "cni":
                out, cmap = self.unify.apply(t.text.lower())
                rids = tuple(dict.fromkeys(e.rule_id for e in cmap if e.rule_id))
                spans.append(NormalizedSpan(t.start, t.end, t.text, out, "cni", rids))
            elif c == "nombre_propio_nativo":
                spans.append(NormalizedSpan(t.start, t.end, t.text, t.text.lower(), c))
            elif c in {"nombre_propio", "prestamo"}:
                lex = self.proper_nouns if c == "nombre_propio" else self.loanwords
                key = t.text if c == "nombre_propio" else t.text.lower()
                entry = lex.get(key)
                if entry and entry[0]:
                    spans.append(NormalizedSpan(t.start, t.end, t.text, entry[0], c, (entry[1],)))
                else:
                    reason = (
                        "nombre propio sin reescritura (gazetteer/P2d)"
                        if c == "nombre_propio"
                        else "préstamo sin forma adaptada (P2c)"
                    )
                    spans.append(self._spanish(t, t.text, c, (), unresolved, reason))
            elif c == "castellano":
                flags += self.editorial.spanish_word(t.text, t.start, t.end)
                spans.append(self._spanish(t, t.text, c, (), unresolved, no_p2d))
            elif c == "sigla":
                res = self.acronyms.expand(t.text, state.acronyms)
                if res.text is None:
                    unresolved.append(Unresolved(t.start, t.end, t.text, res.reason))
                    spans.append(NormalizedSpan(t.start, t.end, t.text, t.text.lower(), c))
                else:
                    if res.reason:
                        unresolved.append(Unresolved(t.start, t.end, t.text, res.reason))
                    spans.append(
                        self._spanish(t, res.text, c, (res.rule_id or "",), unresolved, no_p2d)
                    )
            else:
                span, extra_flags, cand = self._numeric(t, unresolved, no_p2d)
                spans.append(span)
                flags += extra_flags
                used_candidates |= cand

        canonical = "".join(s.norm_text for s in spans)
        return NormalizationResult(
            canonical, spans, flags, unresolved, self.resources_hash, used_candidates
        )

    def _numeric(self, t: Token, unresolved: list[Unresolved], no_p2d: str):
        c = t.category
        flags: list[EditorialFlag] = []
        try:
            if c == "numero":
                v, c = self.verbalizer.number(t.text)
                flags += self.editorial.number(v.value, t.start, t.end, t.text)
            elif c == "anio":
                v = self.verbalizer.year(t.text)
            elif c == "porcentaje":
                v = self.verbalizer.percent(t.text)
            elif c == "dinero":
                v = self.verbalizer.money(t.text)
                flags += self.editorial.number(v.value, t.start, t.end, t.text)
            elif c == "fecha":
                v = self.verbalizer.date(t.text)
                flags += self.editorial.date(t.start, t.end, t.text)
            elif c == "ordinal":
                v = self.verbalizer.ordinal(t.text)
            elif c == "romano":
                v = self.verbalizer.roman(roman_value(t.text.replace(".", "")))
            elif c == "abreviatura":
                v = Verbalized("número", "es", "VERB-ABBR-NUM")
            else:  # pragma: no cover - categoría no prevista
                raise AmbiguousNumber(t.text)
        except AmbiguousNumber:
            unresolved.append(
                Unresolved(t.start, t.end, t.text, "formato numérico ambiguo (no se adivina)")
            )
            return NormalizedSpan(t.start, t.end, t.text, t.text, c), flags, False
        if v.lang == "cni":
            cand = self._is_candidate(v.rule_id)
            return NormalizedSpan(t.start, t.end, t.text, v.text, c, (v.rule_id,)), flags, cand
        span = self._spanish(t, v.text, c, (v.rule_id,), unresolved, no_p2d)
        return span, flags, False

    def _is_candidate(self, rule_id: str) -> bool:
        for e in self.resources["numerals_cni"].entries:
            if e.id == rule_id:
                return e.status != "validado"
        return False
