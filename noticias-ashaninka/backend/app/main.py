"""Aplicación FastAPI. Ejecutar con: uv run uvicorn app.main:app --reload"""

from __future__ import annotations

import gzip
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.datastructures import Headers
from starlette.responses import FileResponse, Response

from app import __version__
from app.api.catalog import router as catalog_router
from app.api.events import router as events_router
from app.api.news import router as news_router
from app.api.synthesize import router as synthesize_router
from app.config import ROOT, get_settings
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


_TEXTUAL = {".js", ".css", ".html", ".json", ".svg", ".webmanifest"}
_gzip_cache: dict[tuple[str, int, int], bytes] = {}


class _Files(StaticFiles):
    """StaticFiles con gzip SOLO para archivos de texto (JS, CSS, JSON, SVG). El audio (Opus/MP3) ya
    está comprimido y las peticiones con ``Range`` se sirven tal cual. En producción lo hace el
    proxy (Caddy); esto mantiene realistas los bytes transferidos en local y en las mediciones."""

    async def get_response(self, path, scope):
        resp = await super().get_response(path, scope)
        h = Headers(scope=scope)
        if (
            isinstance(resp, FileResponse)
            and resp.status_code == 200
            and "gzip" in h.get("accept-encoding", "")
            and "range" not in h
            and Path(resp.path).suffix in _TEXTUAL
        ):
            full = Path(resp.path)
            st = full.stat()
            key = (str(full), st.st_mtime_ns, st.st_size)
            if key not in _gzip_cache:
                _gzip_cache[key] = gzip.compress(full.read_bytes(), 6)
            keep = {k: v for k, v in resp.headers.items() if k in {"etag", "last-modified"}}
            return Response(
                _gzip_cache[key],
                media_type=resp.media_type,
                headers={**keep, "Content-Encoding": "gzip", "Vary": "Accept-Encoding"},
            )
        return resp


app = FastAPI(
    title="Noticias en asháninka",
    version=__version__,
    description="Fases 1-4: ingesta, normalización, G2P, síntesis, visemas y API de la PWA. "
    "La voz y el avatar son sintéticos (ver LICENSES.md).",
    lifespan=lifespan,
)
app.include_router(news_router)
app.include_router(synthesize_router)
app.include_router(catalog_router)
app.include_router(events_router)

# Caché de audio y manifiestos. StaticFiles (Starlette) responde a Range: base de la descarga
# reanudable de la Fase 4.
_static = get_settings().static_dir
_static.mkdir(parents=True, exist_ok=True)
app.mount("/static", _Files(directory=_static), name="static")


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


class _PwaFiles(_Files):
    """Sirve la PWA compilada. ``index.html``, el Service Worker y el manifiesto nunca se cachean
    (así una versión nueva se instala); lo de ``assets/`` lleva hash en el nombre: inmutable."""

    async def get_response(self, path, scope):
        resp = await super().get_response(path, scope)
        if path.startswith("assets/"):
            resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        elif path in {"", ".", "index.html", "sw.js", "manifest.webmanifest"}:
            resp.headers["Cache-Control"] = "no-cache"
        return resp


# La PWA (frontend/dist) se sirve en el mismo origen que /static y /api: el Service Worker
# necesita ese origen y las pruebas E2E y mediciones también. Va al final: no tapa las rutas.
_dist = Path(os.getenv("NA_FRONTEND_DIST", str(ROOT / "frontend" / "dist")))
if (_dist / "index.html").is_file():
    app.mount("/", _PwaFiles(directory=_dist, html=True), name="pwa")
