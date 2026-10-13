"""Servidor de pruebas E2E de la PWA (Fase 4): datos deterministas con el motor ``fake``.

Crea una base de datos y una carpeta ``static/`` temporales y sirve la API, ``/static`` y la PWA
compilada (``frontend/dist``) en el mismo origen. No usa modelos ni datos lingüísticos nuevos: los
textos son oraciones del corpus de prueba y los títulos dicen explícitamente que son de prueba.

  noticia 1: completa, 2 párrafos, todas las oraciones con audio (manifiesto por lotes)
  noticia 2: con un segmento bloqueado en medio (nombre propio sin reescritura, P2d)
  noticia 3: procesada pero sin sintetizar -> respaldo bajo demanda (NDJSON)

Uso: uv run python scripts/e2e_server.py [--port 8765] [--dir RUTA]
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

NEWS = [
    (
        "PRUEBA-1 (ficticia)",
        "Tee otimimotena katsini.\nOkantzi kemetsa. Tzimatsi kitaiteri.",
    ),
    (
        "PRUEBA-2 (ficticia, con bloqueado)",
        "Tee otimimotena katsini. Irotake Pablo Lima ayer en Satipo. Okantzi kemetsa.",
    ),
    ("PRUEBA-3 (ficticia, sin sintetizar)", "Tee otimimotena katsini. Okantzi kemetsa."),
]


def build(workdir: Path) -> None:
    os.environ["NA_DATABASE_URL"] = f"sqlite:///{(workdir / 'e2e.db').as_posix()}"
    os.environ["NA_STATIC_DIR"] = str(workdir / "static")
    os.environ["NA_TTS_ENGINE"] = "fake"
    os.environ.setdefault("NA_FRONTEND_DIST", str(ROOT / "frontend" / "dist"))

    from app.batch.service import run_batch
    from app.db.models import News, Provenance
    from app.db.session import get_engine, init_db
    from sqlmodel import Session

    init_db()
    with Session(get_engine()) as s:
        for titulo, cuerpo in NEWS:
            n = News(titulo_cni=titulo, cuerpo_cni=cuerpo, variante_dialectal="desconocida")
            n.provenance = Provenance(tipo="corpus_americasnlp")
            s.add(n)
        s.commit()
    run_batch([1, 2])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--dir", type=Path, default=None)
    a = ap.parse_args()
    workdir = a.dir or Path(tempfile.mkdtemp(prefix="na-e2e-"))
    if workdir.exists():
        shutil.rmtree(workdir, ignore_errors=True)
    workdir.mkdir(parents=True)
    build(workdir)
    import uvicorn
    from app.main import app

    uvicorn.run(app, host="127.0.0.1", port=a.port, log_level="warning")


if __name__ == "__main__":
    main()
