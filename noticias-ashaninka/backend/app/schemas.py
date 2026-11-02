"""Esquemas Pydantic del contrato de ingesta (PLAN_DESARROLLO.md §2)."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ProvenanceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tipo: Literal["traduccion_humana", "traduccion_automatica", "automatica_revisada"]
    sistema: str | None = None
    version: str | None = None
    revisado_por_hablante: bool = False
    revisor_id: str | None = None


class NewsIn(BaseModel):
    """Contrato con la tesis de traducción. ``procedencia`` es obligatoria."""

    model_config = ConfigDict(extra="forbid")
    titulo_cni: str = Field(min_length=1)
    cuerpo_cni: str = Field(min_length=1)
    titulo_es: str | None = None
    cuerpo_es: str | None = None
    variante_dialectal: str = "desconocida"
    fecha_publicacion: date | None = None
    fuente_original: str = "desconocido"
    procedencia: ProvenanceIn


class NewsOut(BaseModel):
    """Vista pública: NUNCA incluye el texto en castellano (no contamina el experimento)."""

    id: int
    titulo_cni: str
    cuerpo_cni: str
    variante_dialectal: str
    fecha_publicacion: date | None
    fuente_original: str
    estado: str
    procedencia_tipo: str
    revisado_por_hablante: bool
    apta_experimento: bool


# ------------------------------------------------------------------ traducción BiTAM
class TranslateIn(BaseModel):
    """Noticia en castellano para obtener un borrador en asháninka (``POST /api/news/translate``).

    Los límites coinciden con ``app.translation.service`` (MAX_CARACTERES_TITULO/CUERPO)."""

    model_config = ConfigDict(extra="forbid")
    titulo_es: str = Field(min_length=1, max_length=300)
    cuerpo_es: str = Field(min_length=1, max_length=8000)


class OracionTraducidaOut(BaseModel):
    parrafo: int  # -1 = título
    es: str
    cni_modelo: str  # salida cruda de BiTAM (minúsculas, MINEDU 2024)
    cni: str  # tras restaurar mayúsculas desde la fuente


class TranslateOut(BaseModel):
    """Borrador SIN guardar: quien redacta lo revisa y lo publica con ``POST /api/news``."""

    titulo_cni: str
    paragraphs: list[str]
    oraciones: list[OracionTraducidaOut]
    procedencia: ProvenanceIn
    modelo: str
    segundos: float
    avisos: list[str]
