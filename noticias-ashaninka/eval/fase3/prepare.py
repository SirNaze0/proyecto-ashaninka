"""Prepara el material de la evaluación de la Fase 3 (tareas 3.2, 3.7 y 3.8).

Usa una base de datos y una carpeta ``static`` PROPIAS (``eval/fase3/out/``) para no mezclar la
evaluación con las noticias de trabajo. Importa las primeras ``--import`` oraciones del split
**dev** del corpus (nunca test, y no se ajusta nada con ellas más allá de los parámetros ya
fijados) y las sintetiza con ``mms_vits``.

Regla de selección, fijada ANTES de mirar resultados: las primeras 40 noticias de dev, en orden,
cuya única oración tiene audio y dura entre 2 y 12 s. Queda en ``selection.json``.

Uso: uv run python -m eval.fase3.prepare [--import 150] [--select 40]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "eval" / "fase3" / "out"
STATIC = OUT / "static"
DB = OUT / "eval.db"
DUR_MIN, DUR_MAX = 2.0, 12.0


def entorno() -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        NA_DATABASE_URL=f"sqlite:///{DB.relative_to(ROOT).as_posix()}",
        NA_STATIC_DIR=STATIC.relative_to(ROOT).as_posix(),
        NA_TTS_ENGINE="mms_vits",
    )
    return env


def correr(*args: str) -> None:
    subprocess.run([sys.executable, "-m", *args], cwd=ROOT, env=entorno(), check=True)


def seleccionar(n: int) -> list[dict]:
    """Primeras ``n`` noticias (orden de id) con una oración con audio de 2 a 12 s."""
    elegidas: list[dict] = []
    for d in sorted((STATIC / "news").iterdir(), key=lambda p: int(p.name)):
        m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
        segs = [s for s in m["segments"] if s["tts_ready"]]
        if len(m["segments"]) != 1 or not segs:
            continue
        dur = segs[0]["duration_s"]
        if DUR_MIN <= dur <= DUR_MAX:
            elegidas.append(
                {"news_id": m["news_id"], "idx": 0, "duration_s": dur, "titulo": m["titulo_cni"]}
            )
        if len(elegidas) == n:
            break
    return elegidas


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--import", dest="n_import", type=int, default=150)
    p.add_argument("--select", type=int, default=40)
    a = p.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    correr("app.cli", "import", "--from-corpus", "dev", "--limit", str(a.n_import))
    correr("app.batch", "build", "--all")
    sel = seleccionar(a.select)
    (OUT / "selection.json").write_text(json.dumps(sel, indent=1, ensure_ascii=False), "utf-8")
    print(f"[fase3] {len(sel)} oraciones seleccionadas -> {OUT / 'selection.json'}")
    if len(sel) < a.select:
        raise SystemExit(f"se necesitan {a.select} y solo hay {len(sel)}: aumentar --import")


if __name__ == "__main__":
    main()
