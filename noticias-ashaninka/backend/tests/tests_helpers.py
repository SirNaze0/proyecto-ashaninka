"""Aserciones compartidas por las pruebas."""

from app.pipeline.types import NormalizationResult


def assert_alignment(text: str, r: NormalizationResult) -> None:
    """Propiedades del mapa original↔canónico (PROMPT_FASE1 §1.5c)."""
    pos = 0
    for s in r.spans:
        assert s.orig_start == pos, f"hueco/solape en {pos}"
        assert text[s.orig_start : s.orig_end] == s.orig_text
        pos = s.orig_end
    assert pos == len(text), "el texto original no se cubre completo"
    assert "".join(s.norm_text for s in r.spans) == r.text_canonical
    for s in r.spans:
        if s.category == "identity":
            assert s.norm_text == s.orig_text
