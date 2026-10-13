"""Esquema del manifiesto por noticia (tarea 2.5). El JSON Schema se exporta a docs/."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = (
    "1.1"  # 1.1 (Fase 3): agrega ``visemes``; los manifiestos 1.0 siguen siendo válidos
)


class AudioFiles(BaseModel):
    model_config = ConfigDict(extra="forbid")
    opus: str
    mp3: str
    opus_kbps: float
    mp3_kbps: float


class ManifestSegment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idx: int
    paragraph_idx: int
    text_orig: str
    tts_ready: bool
    audio: AudioFiles | None = Field(description="null si el segmento está bloqueado")
    duration_s: float | None
    timings: str | None = Field(description="URL del JSON con duraciones y tiempos por fragmento")
    blocked_reason: str | None


class Notices(BaseModel):
    model_config = ConfigDict(extra="forbid")
    synthetic_voice: str
    license: str
    commercial_use: bool
    non_commercial_warning: str | None
    dialect: str


class EngineRef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    engine: str
    model: str
    revision: str
    adapter_id: str
    params: dict


class VisemeInfo(BaseModel):
    """Trazabilidad de la pista de visemas incluida en cada ``seg_NNN.json`` (Fase 3)."""

    model_config = ConfigDict(extra="forbid")
    status: str = Field(description="SUPUESTO-LING mientras no se valide P1")
    map_sha256: str
    channels: list[str]


class Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = SCHEMA_VERSION
    news_id: int
    titulo_cni: str
    fecha_publicacion: str | None
    generated_at: str
    engine: EngineRef
    notices: Notices
    segments: list[ManifestSegment]
    visemes: VisemeInfo | None = None
    total_duration_s: float
    segments_with_audio: int
    segments_blocked: int


def export_schema(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(Manifest.model_json_schema(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return path
