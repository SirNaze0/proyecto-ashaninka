"""Verifica (o genera) los SHA-256 de los pesos de los modelos contra ``models.lock.json`` (tarea 6.4).

``init.sh`` fija la *revisión* de cada modelo de Hugging Face; este script añade la huella de cada
archivo descargado, de modo que una descarga corrupta, truncada o cambiada se detecta antes de
sintetizar. El archivo de bloqueo se generó con los modelos descargados de la revisión fijada.

Uso:
  uv run python scripts/verify_models.py                  # servicio (obligatorio) + evaluación si existe
  uv run python scripts/verify_models.py --solo-servicio  # solo mms-tts-cni (lo que necesita Docker)
  uv run python scripts/verify_models.py --descargar      # baja (revisión fijada) lo que falte o esté mal y verifica
  uv run python scripts/verify_models.py --generar        # reescribe models.lock.json (solo si cambia la revisión)

Códigos de salida: 0 todo bien · 3 un hash no coincide · 4 falta un archivo obligatorio.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "models.lock.json"
MODELS = ROOT / "models"
BLOQUE = 8 * 1024 * 1024
OK, DISTINTO, FALTA = 0, 3, 4

# Qué modelo necesita cada parte del sistema (las revisiones salen de app.config)
USO = {
    "facebook/mms-tts-cni": ("servicio", "mms-tts-cni (VITS, CC-BY-NC 4.0): voz del servicio"),
    "facebook/mms-1b-all": (
        "evaluacion",
        "mms-1b-all + adaptador cni (CC-BY-NC 4.0): solo para medir inteligibilidad",
    ),
}


def sha256_archivo(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while bloque := f.read(BLOQUE):
            h.update(bloque)
    return h.hexdigest()


def carpeta_modelo(models_dir: Path, repo: str) -> Path:
    return models_dir / repo.replace("/", "__")


def archivos_del_modelo(carpeta: Path) -> list[Path]:
    """Los archivos del modelo (no la caché de Hugging Face ni subcarpetas)."""
    return sorted(p for p in carpeta.iterdir() if p.is_file() and not p.name.startswith("."))


def verificar(lock: dict, models_dir: Path, solo_servicio: bool = False) -> list[dict]:
    """Un resultado por archivo: ``estado`` en ok | distinto | falta | omitido."""
    out: list[dict] = []
    for repo, m in lock["modelos"].items():
        obligatorio = m["necesario_para"] == "servicio"
        if solo_servicio and not obligatorio:
            continue
        carpeta = carpeta_modelo(models_dir, repo)
        if not carpeta.is_dir():
            out.append(
                {"modelo": repo, "archivo": "*", "estado": "falta" if obligatorio else "omitido"}
            )
            continue
        for nombre, esperado in m["archivos"].items():
            p = carpeta / nombre
            if not p.is_file():
                out.append({"modelo": repo, "archivo": nombre, "estado": "falta"})
            elif p.stat().st_size != esperado["bytes"]:
                out.append(
                    {"modelo": repo, "archivo": nombre, "estado": "distinto", "motivo": "tamaño"}
                )
            else:
                ok = sha256_archivo(p) == esperado["sha256"]
                out.append(
                    {"modelo": repo, "archivo": nombre, "estado": "ok" if ok else "distinto"}
                )
    return out


def codigo_de_salida(resultados: list[dict]) -> int:
    estados = {r["estado"] for r in resultados}
    if "distinto" in estados:
        return DISTINTO
    if "falta" in estados:
        return FALTA
    return OK


def descargar_servicio(lock: dict, models_dir: Path) -> None:
    """Descarga (revisión fijada) los modelos del servicio que no estén o no coincidan."""
    sys.path.insert(
        0, str(ROOT)
    )  # permite `python scripts/verify_models.py` sin instalar el paquete
    for repo, m in lock["modelos"].items():
        if m["necesario_para"] != "servicio":
            continue
        malos = [r for r in verificar({"modelos": {repo: m}}, models_dir) if r["estado"] != "ok"]
        if not malos:
            print(f"[modelos] {repo}: ya está completo")
            continue
        from eval.fase1.download_models import main as descargar

        # forzar: ``snapshot_download`` rehace los archivos cuyo hash no coincide con el del repositorio
        descargar([repo, m["revision"]])


def generar(models_dir: Path) -> dict:
    """Huellas de los modelos descargados (revisión fijada en ``app.config``)."""
    from app.config import MMS_ASR_REVISION, MMS_TTS_REVISION

    revisiones = {"facebook/mms-tts-cni": MMS_TTS_REVISION, "facebook/mms-1b-all": MMS_ASR_REVISION}
    modelos: dict = {}
    for repo, (uso, descripcion) in USO.items():
        carpeta = carpeta_modelo(models_dir, repo)
        if not carpeta.is_dir():
            print(f"[modelos] {repo}: no está descargado; no se incluye", file=sys.stderr)
            continue
        modelos[repo] = {
            "revision": revisiones[repo],
            "necesario_para": uso,
            "descripcion": descripcion,
            "archivos": {
                p.name: {"sha256": sha256_archivo(p), "bytes": p.stat().st_size}
                for p in archivos_del_modelo(carpeta)
            },
        }
    return {
        "version": 1,
        "nota": "Huellas SHA-256 de los archivos de cada modelo en la revisión fijada, generadas con "
        "scripts/verify_models.py --generar a partir de la descarga de init.sh. Los pesos (.safetensors) "
        "se contrastaron con el SHA-256 LFS que publica Hugging Face (coincide); los JSON pequeños no "
        "tienen SHA-256 publicado y son de primer uso. Regenerar solo si cambia la revisión en app/config.py.",
        "modelos": modelos,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--lock", type=Path, default=LOCK)
    ap.add_argument("--models-dir", type=Path, default=MODELS)
    ap.add_argument("--solo-servicio", action="store_true")
    ap.add_argument("--generar", action="store_true")
    ap.add_argument(
        "--descargar",
        action="store_true",
        help="descarga los modelos del servicio que falten o no coincidan y vuelve a verificar",
    )
    a = ap.parse_args(argv)
    if a.generar:
        lock = generar(a.models_dir)
        a.lock.write_text(json.dumps(lock, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        n = sum(len(m["archivos"]) for m in lock["modelos"].values())
        print(f"[modelos] {a.lock.name}: {len(lock['modelos'])} modelos, {n} archivos")
        return OK
    lock = json.loads(a.lock.read_text(encoding="utf-8"))
    if a.descargar:
        descargar_servicio(lock, a.models_dir)
        a.solo_servicio = True
    resultados = verificar(lock, a.models_dir, a.solo_servicio)
    for r in resultados:
        print(f"[modelos] {r['estado']:<8} {r['modelo']}/{r['archivo']}")
    codigo = codigo_de_salida(resultados)
    estado = "OK" if codigo == OK else f"FALLO (código {codigo})"
    print(f"[modelos] {estado}")
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
