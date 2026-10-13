"""Tarea 4.7 (parte) — peso del *shell* de la PWA medido con ``vite build``.

Lee ``frontend/dist/.vite/manifest.json`` y calcula, en gzip, lo que se descarga SIEMPRE al abrir la
PWA (HTML, JS y CSS iniciales, manifiesto web, íconos precargados por el Service Worker) y lo que
queda de carga diferida (three, three-vrm, visor del avatar), más el modelo VRM. La medición real de
bytes transferidos en Chromium está en ``frontend/scripts/fase4_bench.mjs`` (``carga.json``).

Uso: (cd frontend && npm run build) && uv run python -m eval.fase4.bundle
"""

from __future__ import annotations

import gzip
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIST = ROOT / "frontend" / "dist"
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


def precache_del_sw() -> list[str]:
    """Lista de precarga que el plugin de Vite inyectó en ``sw.js``."""
    codigo = (DIST / "sw.js").read_text("utf-8")
    m = re.search(r"\[(?:\"/[^\"]*\",?)+\]", codigo)
    return json.loads(m.group(0)) if m else []


def medir() -> dict:
    manifest = json.loads((DIST / ".vite" / "manifest.json").read_text("utf-8"))
    entrada = next(k for k, v in manifest.items() if v.get("isEntry") and k == "index.html")
    inicial = estatico(manifest, entrada, set()) | {"index.html"}
    diferidos = {v["file"] for v in manifest.values() if not v.get("isEntry")} - inicial
    tam = lambda files: sum(gz(DIST / f) for f in files)  # noqa: E731
    precache = precache_del_sw()
    pre_bytes = sum(gz(DIST / p.lstrip("/")) for p in precache if (DIST / p.lstrip("/")).is_file())
    res = {
        "inicial_gzip_bytes": tam(inicial),
        "inicial_archivos": sorted(inicial),
        "diferido_gzip_bytes": tam(diferidos),
        "diferido_archivos": sorted(diferidos),
        "sw_js_gzip_bytes": gz(DIST / "sw.js"),
        "precache_sw_archivos": precache,
        "precache_sw_gzip_bytes": pre_bytes,
        "precache_sw_incluye_avatar": any(
            re.search(r"three|GLTFLoader|viewer|\.vrm", p) for p in precache
        ),
        "presupuesto_inicial_bytes": PRESUPUESTO_INICIAL_BYTES,
        "cumple_presupuesto_inicial": tam(inicial) < PRESUPUESTO_INICIAL_BYTES,
        "nota": "el avatar va FUERA del presupuesto inicial (carga diferida, PLAN §4.7)",
    }
    if VRM.exists():
        res["vrm_provisional_bytes"] = VRM.stat().st_size
        res["vrm_meta_final_bytes"] = 2 * 1024 * 1024
        res["vrm_cumple_meta_2mb"] = VRM.stat().st_size <= 2 * 1024 * 1024
        res["inicial_mas_avatar_mas_vrm_gzip_bytes"] = (
            tam(inicial) + tam(diferidos) + VRM.stat().st_size
        )
    return res


if __name__ == "__main__":
    print(json.dumps(medir(), indent=1, ensure_ascii=False))
