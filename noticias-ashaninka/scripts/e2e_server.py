"""Servidor de pruebas E2E de la PWA (Fase 4): datos deterministas con el motor ``fake``.

Crea una base de datos y una carpeta ``static/`` temporales y sirve la API, ``/static`` y la PWA
compilada (``frontend/dist``) en el mismo origen. No usa modelos ni datos lingüísticos nuevos: los
textos son oraciones del corpus de prueba y los títulos dicen explícitamente que son de prueba.

  noticia 1: completa, 2 párrafos, todas las oraciones con audio (manifiesto por lotes)
  noticia 2: con un segmento bloqueado en medio (nombre propio sin reescritura, P2d)
  noticia 3: procesada pero sin sintetizar -> respaldo bajo demanda (NDJSON)

Con ``--experimento`` (Fase 5) crea en cambio el material del experimento: 4 noticias «revisadas»
(ficticias) sin segmentos bloqueados y una quinta con un bloqueado, que el selector debe descartar.
La exportación y ``/api/events/summary`` exigen el token administrativo de las pruebas.

Uso: uv run python scripts/e2e_server.py [--port 8765] [--dir RUTA] [--experimento]
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

ADMIN_TOKEN = "e2e-admin-token-0123456789"  # el mismo que frontend/e2e/helpers.ts

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


# Fase 5: noticias de prueba del experimento (textos del corpus de prueba, todas con audio)
EXPERIMENTO = [
    ("EXPERIMENTO-1 (ficticia)", "Tee otimimotena katsini.\nOkantzi kemetsa. Tzimatsi kitaiteri."),
    ("EXPERIMENTO-2 (ficticia)", "Okantzi kemetsa.\nTzimatsi kitaiteri. Tee otimimotena katsini."),
    ("EXPERIMENTO-3 (ficticia)", "Tzimatsi kitaiteri.\nTee otimimotena katsini. Okantzi kemetsa."),
    ("EXPERIMENTO-4 (ficticia)", "Tee otimimotena katsini. Okantzi kemetsa.\nTzimatsi kitaiteri."),
    (
        "EXPERIMENTO-5 (ficticia, con bloqueado)",
        "Tee otimimotena katsini. Irotake Pablo Lima ayer en Satipo.",
    ),
]


def build_experimento(workdir: Path) -> None:
    os.environ.pop("NA_EXPORT_TOKEN", None)
    os.environ.pop("NA_EXPERIMENT_PILOTO", None)
    from app.batch.service import run_batch
    from app.db.models import News, Provenance
    from app.db.session import get_engine, init_db
    from sqlmodel import Session

    init_db()
    with Session(get_engine()) as s:
        for titulo, cuerpo in EXPERIMENTO:
            n = News(titulo_cni=titulo, cuerpo_cni=cuerpo, variante_dialectal="desconocida")
            n.provenance = Provenance(tipo="traduccion_humana", revisado_por_hablante=True)
            s.add(n)
        s.commit()
    run_batch([1, 2, 3, 4, 5])


def build(workdir: Path, experimento: bool = False) -> None:
    os.environ["NA_DATABASE_URL"] = f"sqlite:///{(workdir / 'e2e.db').as_posix()}"
    os.environ["NA_STATIC_DIR"] = str(workdir / "static")
    os.environ["NA_TTS_ENGINE"] = "fake"
    os.environ["NA_ADMIN_TOKEN"] = ADMIN_TOKEN  # Fase 6: los endpoints administrativos exigen token
    os.environ.setdefault("NA_FRONTEND_DIST", str(ROOT / "frontend" / "dist"))

    from app.batch.service import run_batch
    from app.db.models import News, Provenance
    from app.db.session import get_engine, init_db
    from sqlmodel import Session

    if experimento:
        build_experimento(workdir)
        return
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
    ap.add_argument("--experimento", action="store_true", help="material de la Fase 5")
    a = ap.parse_args()
    workdir = a.dir or Path(tempfile.mkdtemp(prefix="na-e2e-"))
    if workdir.exists():
        shutil.rmtree(workdir, ignore_errors=True)
    workdir.mkdir(parents=True)
    build(workdir, a.experimento)
    import uvicorn
    from app.main import app

    uvicorn.run(app, host="127.0.0.1", port=a.port, log_level="warning")


if __name__ == "__main__":
    main()
