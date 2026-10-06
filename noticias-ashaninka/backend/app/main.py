"""Aplicación FastAPI. Ejecutar con: uv run uvicorn app.main:app --reload"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api.news import router as news_router
from app.api.synthesize import router as synthesize_router
from app.config import get_settings
from app.db.session import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    if os.getenv("NA_TTS_PRELOAD", "false").lower() in {"1", "true", "yes", "si", "sí"}:
        # Carga el modelo al arrancar: la primera solicitud no paga la carga en frío
        from app.api.synthesize import get_synthesizer

        get_synthesizer(None)
    _point_static_to(get_settings().static_dir)
    yield


app = FastAPI(
    title="Noticias en asháninka",
    version=__version__,
    description="Fases 1-2: ingesta, normalización, adaptación ortográfica, G2P y síntesis de voz. "
    "La voz y el avatar son sintéticos (ver LICENSES.md).",
    lifespan=lifespan,
)
app.include_router(news_router)
app.include_router(synthesize_router)

# Caché de audio y manifiestos. StaticFiles (Starlette) responde a Range: base de la descarga
# reanudable de la Fase 4.
_static = get_settings().static_dir
_static.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=_static), name="static")


def _point_static_to(directory) -> None:
    """La carpeta estática se fija al arrancar (permite cambiarla con NA_STATIC_DIR)."""
    directory.mkdir(parents=True, exist_ok=True)
    for route in app.routes:
        if getattr(route, "name", None) == "static":
            route.app.directory = directory
            route.app.all_directories = route.app.get_directories(directory, None)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": __version__}
