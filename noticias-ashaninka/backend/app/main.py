"""Aplicación FastAPI. Ejecutar con: uv run uvicorn app.main:app --reload"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import __version__
from app.api.news import router as news_router
from app.db.session import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Noticias en asháninka",
    version=__version__,
    description="Fase 1: ingesta, normalización, adaptación ortográfica y G2P. "
    "La voz y el avatar son sintéticos (ver LICENSES.md).",
    lifespan=lifespan,
)
app.include_router(news_router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": __version__}
