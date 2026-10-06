"""Modelo de datos (SQLModel + SQLite). Ver PLAN_DESARROLLO.md §2 y PROMPT_FASE1.md §1.2."""

from datetime import UTC, date, datetime
from typing import Any, Optional

from sqlalchemy import JSON, Column, event
from sqlmodel import Field, Relationship, SQLModel


def _now() -> datetime:
    return datetime.now(UTC)


PROVENANCE_TYPES = {
    "traduccion_humana",
    "traduccion_automatica",
    "automatica_revisada",
    "corpus_americasnlp",  # pseudo-noticias para pruebas; nunca aptas para el experimento
}


class News(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    titulo_cni: str
    cuerpo_cni: str
    # El texto en castellano es solo referencia: nunca se expone en endpoints del experimento
    titulo_es: str | None = None
    cuerpo_es: str | None = None
    variante_dialectal: str = "desconocida"
    fecha_publicacion: date | None = None
    fuente_original: str = "desconocido"
    estado: str = "ingested"  # ingested | processed | error
    error: str | None = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)

    provenance: Optional["Provenance"] = Relationship(
        back_populates="news",
        sa_relationship_kwargs={"uselist": False, "cascade": "all, delete-orphan"},
    )
    segments: list["Segment"] = Relationship(
        back_populates="news",
        sa_relationship_kwargs={"cascade": "all, delete-orphan", "order_by": "Segment.idx"},
    )

    @property
    def apta_experimento(self) -> bool:
        p = self.provenance
        return bool(p and p.revisado_por_hablante and p.tipo != "corpus_americasnlp")


class Provenance(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    news_id: int = Field(foreign_key="news.id", unique=True)
    tipo: str
    sistema: str | None = None
    version: str | None = None
    revisado_por_hablante: bool = False
    revisor_id: str | None = None

    news: Optional["News"] = Relationship(back_populates="provenance")


class Segment(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    news_id: int = Field(foreign_key="news.id", index=True)
    idx: int
    paragraph_idx: int
    orig_start: int
    orig_end: int
    text_orig: str
    text_canonical: str
    text_tts: str | None = None  # ortografía del motor TTS; None si quedó bloqueado
    tts_ready: bool = False
    alignment_map: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    tts_char_map: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    phonemes: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    editorial_flags: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    unresolved: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    resources_hash: str = ""
    adapter_id: str = ""
    used_candidates: bool = False

    news: Optional["News"] = Relationship(back_populates="segments")


class ResourceVersion(SQLModel, table=True):
    """Hash de cada YAML usado al procesar: cada segmento sabe con qué reglas se generó."""

    id: int | None = Field(default=None, primary_key=True)
    bundle_hash: str = Field(index=True)
    resource: str
    sha256: str
    created_at: datetime = Field(default_factory=_now)


class MissingProvenanceError(ValueError):
    pass


@event.listens_for(News, "before_insert")
def _require_provenance(mapper, connection, target: News) -> None:  # noqa: ARG001
    if target.provenance is None:
        raise MissingProvenanceError("Una noticia sin procedencia no se puede guardar (§2)")
    if target.provenance.tipo not in PROVENANCE_TYPES:
        raise ValueError(f"Tipo de procedencia desconocido: {target.provenance.tipo}")


# ------------------------------------------------------------------ Fase 2: síntesis
class AudioAsset(SQLModel, table=True):
    """Un archivo de audio en la caché por contenido, asociado a un segmento."""

    id: int | None = Field(default=None, primary_key=True)
    segment_id: int = Field(foreign_key="segment.id", index=True)
    engine: str
    cache_key: str = Field(index=True)
    format: str  # opus | mp3
    path: str  # relativo a la carpeta static/
    sha256: str
    duration_s: float
    kbps: float
    meta: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=_now)


class SynthesisRun(SQLModel, table=True):
    """Registro de cada ejecución de síntesis (por lotes o bajo demanda)."""

    id: int | None = Field(default=None, primary_key=True)
    engine: str
    mode: str  # batch | on_demand
    started_at: datetime = Field(default_factory=_now)
    finished_at: datetime | None = None
    news_count: int = 0
    synthesized: int = 0
    reused: int = 0
    blocked: int = 0
    errors: int = 0
    detail: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
