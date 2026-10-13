"""Tareas 3.1 y 4.7 (parte) — peso del paquete del avatar medido con ``vite build``.

Lee ``frontend/dist/.vite/manifest.json`` y calcula, en gzip, el peso de lo que se descarga al
abrir el visor (``inicial``) y de lo que se carga de forma diferida (three, three-vrm), más el del
modelo VRM. También mide las dos opciones de la comparativa (``frontend/bench``).

Uso: (cd frontend && npm run build && npm run bench:size) && uv run python -m eval.fase3.bundle
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIST = ROOT / "frontend" / "dist"
BENCH = ROOT / "frontend" / "bench" / "dist"
VRM = ROOT / "frontend" / "public" / "models" / "presentadora_provisional.vrm"
PRESUPUESTO_INICIAL_BYTES = 3 * 1024 * 1024


def gz(path: Path) -> int:
    return len(gzip.compress(path.read_bytes(), compresslevel=9))


def estatico(manifest: dict, key: str, visto: set[str]) -> set[str]:
    """Archivos que se descargan SIEMPRE al cargar el punto de entrada ``key``."""
    if key in visto:
        return set()
    visto.add(key)
    chunk = manifest[key]
    out = {chunk["file"], *chunk.get("css", [])}
    for imp in chunk.get("imports", []):
        out |= estatico(manifest, imp, visto)
    return out


def medir() -> dict:
    manifest = json.loads((DIST / ".vite" / "manifest.json").read_text("utf-8"))
    entrada = next(k for k, v in manifest.items() if v.get("isEntry") and k == "visor.html")
    inicial = estatico(manifest, entrada, set()) | {"visor.html"}
    diferidos = {v["file"] for v in manifest.values() if not v.get("isEntry")} - inicial
    tam = lambda files: sum(gz(DIST / f) for f in files)  # noqa: E731
    res = {
        "inicial_gzip_bytes": tam(inicial),
        "inicial_archivos": sorted(inicial),
        "diferido_gzip_bytes": tam(diferidos),
        "diferido_archivos": sorted(diferidos),
        "presupuesto_inicial_bytes": PRESUPUESTO_INICIAL_BYTES,
        "cumple_presupuesto_inicial": tam(inicial) < PRESUPUESTO_INICIAL_BYTES,
        "nota": "el avatar va FUERA del presupuesto inicial (carga diferida, PLAN §4.7)",
    }
    if VRM.exists():
        res["vrm_provisional_bytes"] = VRM.stat().st_size
        res["vrm_meta_final_bytes"] = 2 * 1024 * 1024
        res["vrm_cumple_meta_2mb"] = VRM.stat().st_size <= 2 * 1024 * 1024
    if BENCH.exists():
        res["comparativa_3_1"] = {
            d.name: {
                "min_bytes": (d / f"{d.name}.js").stat().st_size,
                "gzip_bytes": gz(d / f"{d.name}.js"),
            }
            for d in sorted(BENCH.iterdir())
            if (d / f"{d.name}.js").exists()
        }
    return res


if __name__ == "__main__":
    print(json.dumps(medir(), indent=1, ensure_ascii=False))
