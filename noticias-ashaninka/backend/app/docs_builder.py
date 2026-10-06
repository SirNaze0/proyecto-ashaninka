"""Genera docs/normalization_rules.md a partir de los YAML (contribución citable, §3.1 del plan)."""

from __future__ import annotations

from pathlib import Path

from app.config import DOCS_DIR
from app.pipeline.resources import all_resource_paths, load_resource


def _cell(v) -> str:
    return str(v if v is not None else "").replace("|", "\\|").replace("\n", " ")


def build_normalization_docs(out: Path = DOCS_DIR / "normalization_rules.md") -> Path:
    resources = [load_resource(p) for p in all_resource_paths()]
    total: dict[str, int] = {}
    for r in resources:
        for k, v in r.counts().items():
            total[k] = total.get(k, 0) + v
    lines = [
        "# Reglas de normalización y recursos lingüísticos",
        "",
        "> GENERADO por `uv run python -m app.cli build-docs`. No editar a mano: editar los YAML.",
        "",
        "Estados: **validado** (aprobado por persona experta) · **candidato-corpus** (evidencia del",
        "corpus AmericasNLP, sin validar) · **SUPUESTO-LING** / **SUPUESTO** (decisión provisional",
        "o condición experimental, pendiente de validación).",
        "",
        "## Resumen",
        "",
        "| Estado | Entradas |",
        "|---|---|",
    ]
    lines += [f"| {k} | {v} |" for k, v in sorted(total.items())] or ["| (ninguna) | 0 |"]
    lines += ["", "| Recurso | Archivo | SHA-256 | Entradas por estado |", "|---|---|---|---|"]
    for r in resources:
        counts = ", ".join(f"{k}={v}" for k, v in sorted(r.counts().items())) or "vacío"
        lines.append(
            f"| {r.resource} | `{Path(r.path or '').name}` | `{(r.sha256 or '')[:12]}` | {counts} |"
        )
    for r in resources:
        lines += ["", f"## {r.resource}", "", r.description, ""]
        if not r.entries:
            lines.append("_Sin entradas._ Ver los comentarios `SUPUESTO-LING` del archivo.")
            continue
        lines += [
            "| id | Descripción | Patrón / forma | Reemplazo | Ejemplo | Fuente | Estado |",
            "|---|---|---|---|---|---|---|",
        ]
        for e in r.entries:
            extra = e.model_extra or {}
            form = e.pattern or e.source_form or extra.get("grapheme") or ""
            rep = e.replacement if e.replacement is not None else extra.get("phoneme", "")
            ex = e.examples[0] if e.examples else None
            ex_txt = f"{ex.input} → {ex.output}" if ex else ""
            lines.append(
                f"| {_cell(e.id)} | {_cell(e.description)} | `{_cell(form)}` | `{_cell(rep)}` | "
                f"{_cell(ex_txt)} | {_cell(e.source)} | {e.status} |"
            )
    lines.append("")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return out
