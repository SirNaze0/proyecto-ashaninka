"""Carga y validación de los recursos lingüísticos en YAML.

Todos los recursos comparten un esquema común (ver PROMPT_FASE1.md §1.5):

.. code-block:: yaml

    resource: es_to_cni_phonology
    description: "…"
    config: {}            # parámetros propios del recurso
    entries:
      - id: P2D-001
        description: "…"
        pattern: "…"      # regex (reglas) o "source" (entradas de léxico)
        replacement: "…"
        examples: [{input: "…", output: "…", ref: "train:782"}]
        frequency: 12
        source: "…"
        status: validado | candidato-corpus | SUPUESTO-LING
"""

from __future__ import annotations

import hashlib
from functools import cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.config import ADAPTERS_DIR, G2P_RULES, NORMALIZE_RESOURCES

Status = Literal["validado", "candidato-corpus", "SUPUESTO-LING", "SUPUESTO"]


class Example(BaseModel):
    model_config = ConfigDict(extra="forbid")
    input: str
    output: str
    ref: str | None = None


class Entry(BaseModel):
    """Entrada de un recurso. Se admiten campos extra propios de cada recurso."""

    model_config = ConfigDict(extra="allow")
    id: str
    description: str = ""
    pattern: str | None = None
    source_form: str | None = Field(default=None, alias="source_form")
    replacement: str | None = None
    examples: list[Example] = Field(default_factory=list)
    frequency: int | None = None
    source: str
    status: Status

    @model_validator(mode="after")
    def _no_test_refs(self) -> Entry:
        for ex in self.examples:
            if ex.ref and ex.ref.lower().startswith("test"):
                raise ValueError(
                    f"{self.id}: los ejemplos no pueden citar el split test ({ex.ref})"
                )
        return self

    @property
    def usable(self) -> bool:
        return self.status == "validado"


class Resource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resource: str
    description: str
    config: dict[str, Any] = Field(default_factory=dict)
    entries: list[Entry] = Field(default_factory=list)
    path: str | None = None
    sha256: str | None = None

    def usable_entries(self, allow_candidates: bool = False) -> list[Entry]:
        ok = {"validado", "candidato-corpus"} if allow_candidates else {"validado"}
        return [e for e in self.entries if e.status in ok]

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for e in self.entries:
            out[e.status] = out.get(e.status, 0) + 1
        return out


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_resource(path: Path) -> Resource:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    data["path"] = path.as_posix()
    data["sha256"] = file_sha256(path)
    res = Resource.model_validate(data)
    ids = [e.id for e in res.entries]
    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        raise ValueError(f"{path.name}: ids duplicados {sorted(dup)}")
    return res


NORMALIZE_FILES = [
    "orthography_variants.yaml",
    "numerals_cni.yaml",
    "acronyms.yaml",
    "loanwords.yaml",
    "es_to_cni_phonology.yaml",
    "neologisms.yaml",
    "proper_nouns.yaml",
    "relative_dates.yaml",
    "segmentation.yaml",
]


def all_resource_paths() -> list[Path]:
    paths = [NORMALIZE_RESOURCES / f for f in NORMALIZE_FILES]
    paths += [G2P_RULES / "inventory.yaml", G2P_RULES / "cni.yaml"]
    paths += [ADAPTERS_DIR / "mms_cni.yaml"]
    return paths


@cache
def _cached(path_str: str, mtime: float) -> Resource:
    return load_resource(Path(path_str))


def get_resource(path: Path) -> Resource:
    """Carga con caché (se invalida si el archivo cambia)."""
    return _cached(str(path), path.stat().st_mtime)


def bundle_hash(resources: list[Resource]) -> str:
    h = hashlib.sha256()
    for r in sorted(resources, key=lambda x: x.resource):
        h.update(f"{r.resource}:{r.sha256}\n".encode())
    return h.hexdigest()


def validate_all() -> dict[str, dict[str, int]]:
    """Valida todos los recursos y devuelve el recuento por estado. Lanza si alguno es inválido."""
    return {p.name: load_resource(p).counts() for p in all_resource_paths()}
