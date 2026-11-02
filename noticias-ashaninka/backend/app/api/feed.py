"""API del lector de TV Perú (NoticiasTVPeru). Pública, como todo desde QuitarAdmin.

- ``GET  /api/feed/status``: configuración, si hay un ciclo en curso, último resultado y conteos.
- ``PUT  /api/feed/config``: intervalo (0, 15, 30, 60, 180 o 360 min) y noticias por ciclo (1 a 5).
- ``POST /api/feed/run``: lanza un ciclo en segundo plano (202). 409 si ya hay uno; 503 si la función
  está apagada (``NA_FEED_ENABLED=false``): así nada dispara peticiones a TV Perú sin quererlo.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.config import get_settings
from app.feed import servicio

router = APIRouter(prefix="/api/feed", tags=["feed"])


class FeedConfigIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intervalo_min: Literal[0, 15, 30, 60, 180, 360] | None = None
    max_por_ciclo: int | None = Field(default=None, ge=1, le=5)


@router.get("/status")
def status() -> dict:
    return servicio.estado()


@router.put("/config")
def config(cfg: FeedConfigIn) -> dict:
    return servicio.actualizar_config(cfg.intervalo_min, cfg.max_por_ciclo)


@router.post("/run", status_code=202)
def run() -> JSONResponse:
    if not get_settings().feed_enabled:
        raise HTTPException(503, "la actualización automática está apagada (NA_FEED_ENABLED=false)")
    if not servicio.lanzar_en_segundo_plano():
        raise HTTPException(409, "ya hay una actualización en curso")
    return JSONResponse({"iniciado": True}, status_code=202)
