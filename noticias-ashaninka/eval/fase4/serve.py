"""Sirve la PWA compilada con la base de datos y la caché de audio de la evaluación de la Fase 4.

Mismo origen para ``/``, ``/api`` y ``/static`` (como en producción). Corre con ``mms_vits`` como
motor, pero en modo por lotes no sintetiza nada: solo entrega los archivos ya generados.

Uso: uv run python -m eval.fase4.serve [--port 8766]
"""

from __future__ import annotations

import argparse
import sys

from eval.fase4.prepare import ROOT, entorno


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=8766)
    a = ap.parse_args()
    entorno()
    sys.path.insert(0, str(ROOT / "backend"))
    import uvicorn
    from app.main import app

    uvicorn.run(app, host="127.0.0.1", port=a.port, log_level="warning")


if __name__ == "__main__":
    main()
