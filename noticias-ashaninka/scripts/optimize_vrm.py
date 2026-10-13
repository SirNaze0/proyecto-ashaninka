"""Reduce el peso de un modelo VRM/GLB (tarea 3.5).

1. Texturas: se reescriben a un máximo de ``--max-px`` (JPEG si no tienen transparencia real,
   PNG si la tienen).
2. Opcional, ``--keep-expressions aa,ih,ou,ee,oh,blink``: se eliminan las expresiones VRM que no
   se piden y los morph targets que solo ellas usaban (el rostro de VRoid trae 57; el visor usa 6).
   Es la mayor parte del peso del modelo.

Los nodos, huesos y extensiones VRMC_* no se tocan: los índices de nodos se conservan; solo se
reindexan accessors, bufferViews y los morph targets que se eliminan.

Uso: uv run python scripts/optimize_vrm.py entrada.vrm salida.vrm [--max-px 1024]
     [--quality 86] [--keep-expressions aa,ih,ou,ee,oh,blink]
"""

from __future__ import annotations

import argparse
import io
import json
import struct
from pathlib import Path

from PIL import Image

GLB_MAGIC = 0x46546C67
CHUNK_JSON = 0x4E4F534A
CHUNK_BIN = 0x004E4942


def leer_glb(data: bytes) -> tuple[dict, bytes]:
    magic, version, _ = struct.unpack("<III", data[:12])
    if magic != GLB_MAGIC or version != 2:
        raise ValueError("no es un GLB 2.0")
    pos, doc, binario = 12, None, b""
    while pos < len(data):
        n, tipo = struct.unpack("<II", data[pos : pos + 8])
        trozo = data[pos + 8 : pos + 8 + n]
        if tipo == CHUNK_JSON:
            doc = json.loads(trozo)
        elif tipo == CHUNK_BIN:
            binario = trozo
        pos += 8 + n
    if doc is None:
        raise ValueError("el GLB no tiene bloque JSON")
    return doc, binario


def escribir_glb(doc: dict, binario: bytes) -> bytes:
    js = json.dumps(doc, separators=(",", ":"), ensure_ascii=False).encode()
    js += b" " * (-len(js) % 4)
    binario += b"\0" * (-len(binario) % 4)
    total = 12 + 8 + len(js) + 8 + len(binario)
    return (
        struct.pack("<III", GLB_MAGIC, 2, total)
        + struct.pack("<II", len(js), CHUNK_JSON)
        + js
        + struct.pack("<II", len(binario), CHUNK_BIN)
        + binario
    )


def recomprimir(raw: bytes, max_px: int, calidad: int) -> tuple[bytes, str]:
    img = Image.open(io.BytesIO(raw))
    img.load()
    if max(img.size) > max_px:
        img.thumbnail((max_px, max_px), Image.Resampling.LANCZOS)
    tiene_alfa = img.mode in ("RGBA", "LA") and img.getchannel("A").getextrema()[0] < 255
    buf = io.BytesIO()
    if tiene_alfa:
        img.convert("RGBA").save(buf, "PNG", optimize=True)
        return buf.getvalue(), "image/png"
    img.convert("RGB").save(buf, "JPEG", quality=calidad, optimize=True)
    return buf.getvalue(), "image/jpeg"


def _accessor_refs(doc: dict):
    """Cada sitio del documento que apunta a un accessor, como (contenedor, clave)."""
    for m in doc.get("meshes", []):
        for p in m["primitives"]:
            for k in p["attributes"]:
                yield p["attributes"], k
            if "indices" in p:
                yield p, "indices"
            for t in p.get("targets", []):
                for k in t:
                    yield t, k
    for sk in doc.get("skins", []):
        if "inverseBindMatrices" in sk:
            yield sk, "inverseBindMatrices"
    for an in doc.get("animations", []):
        for smp in an["samplers"]:
            yield smp, "input"
            yield smp, "output"


def recortar_expresiones(doc: dict, mantener: set[str]) -> dict:
    """Elimina las expresiones no pedidas y los morph targets que ya nadie usa."""
    vrm = doc["extensions"]["VRMC_vrm"]
    exp = vrm["expressions"]
    for grupo in ("preset", "custom"):
        for nombre in [n for n in exp.get(grupo, {}) if n not in mantener]:
            del exp[grupo][nombre]
    usados: dict[int, set[int]] = {}  # malla -> morph targets conservados
    todas = [e for g in ("preset", "custom") for e in exp.get(g, {}).values()]
    for e in todas:
        for b in e.get("morphTargetBinds", []):
            usados.setdefault(doc["nodes"][b["node"]]["mesh"], set()).add(b["index"])
    nuevo: dict[int, dict[int, int]] = {
        m: {o: i for i, o in enumerate(sorted(v))} for m, v in usados.items()
    }
    for e in todas:
        for b in e.get("morphTargetBinds", []):
            b["index"] = nuevo[doc["nodes"][b["node"]]["mesh"]][b["index"]]
    for mi, mesh in enumerate(doc["meshes"]):
        mantener_idx = sorted(usados.get(mi, set()))
        for p in mesh["primitives"]:
            if "targets" in p:
                p["targets"] = [p["targets"][i] for i in mantener_idx]
        nombres = (mesh.get("extras") or {}).get("targetNames")
        if nombres is not None:
            mesh["extras"]["targetNames"] = [nombres[i] for i in mantener_idx]
        if "weights" in mesh:
            mesh["weights"] = [mesh["weights"][i] for i in mantener_idx]
    return {"expresiones": sorted(n for g in exp.values() for n in g)}


def compactar(doc: dict, binario: bytes) -> bytes:
    """Quita accessors y bufferViews sin referencias y reconstruye el buffer binario."""
    refs = list(_accessor_refs(doc))
    usados = sorted({c[k] for c, k in refs})
    nuevo_acc = {v: i for i, v in enumerate(usados)}
    for c, k in refs:
        c[k] = nuevo_acc[c[k]]
    accs = [doc["accessors"][i] for i in usados]
    doc["accessors"] = accs
    vistas_usadas: set[int] = {i["bufferView"] for i in doc.get("images", [])}
    for a in accs:
        if "bufferView" in a:
            vistas_usadas.add(a["bufferView"])
        for sp in ("indices", "values"):
            if "sparse" in a:
                vistas_usadas.add(a["sparse"][sp]["bufferView"])
    orden = sorted(vistas_usadas)
    nuevo_bv = {v: i for i, v in enumerate(orden)}
    for a in accs:
        if "bufferView" in a:
            a["bufferView"] = nuevo_bv[a["bufferView"]]
        if "sparse" in a:
            for sp in ("indices", "values"):
                a["sparse"][sp]["bufferView"] = nuevo_bv[a["sparse"][sp]["bufferView"]]
    for i in doc.get("images", []):
        i["bufferView"] = nuevo_bv[i["bufferView"]]
    vistas = [doc["bufferViews"][i] for i in orden]
    out = bytearray()
    for v in vistas:
        trozo = binario[v.get("byteOffset", 0) :][: v["byteLength"]]
        out += bytes(-len(out) % 4)
        v["byteOffset"] = len(out)
        out += trozo
    doc["bufferViews"] = vistas
    doc["buffers"][0]["byteLength"] = len(out)
    return bytes(out)


def optimizar(
    entrada: Path,
    salida: Path,
    max_px: int = 1024,
    calidad: int = 86,
    mantener_expresiones: set[str] | None = None,
) -> dict:
    data = entrada.read_bytes()
    doc, binario = leer_glb(data)
    extra: dict = {}
    if mantener_expresiones:
        extra = recortar_expresiones(doc, mantener_expresiones)
        binario = compactar(doc, binario)
    vistas = doc["bufferViews"]
    nuevas: dict[int, bytes] = {}
    for img in doc.get("images", []):
        v = img["bufferView"]
        raw = binario[vistas[v].get("byteOffset", 0) :][: vistas[v]["byteLength"]]
        nuevas[v], img["mimeType"] = recomprimir(raw, max_px, calidad)
    out, offset = bytearray(), 0
    for i, v in enumerate(vistas):
        trozo = nuevas.get(i)
        if trozo is None:
            trozo = binario[v.get("byteOffset", 0) :][: v["byteLength"]]
        out += b"\0" * (-len(out) % 4)
        v["byteOffset"], v["byteLength"] = len(out), len(trozo)
        out += trozo
        offset += len(trozo)
    doc["buffers"][0]["byteLength"] = len(out)
    resultado = escribir_glb(doc, bytes(out))
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_bytes(resultado)
    return {"bytes_antes": len(data), "bytes_despues": len(resultado), **extra}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("entrada", type=Path)
    p.add_argument("salida", type=Path)
    p.add_argument("--max-px", type=int, default=1024)
    p.add_argument("--quality", type=int, default=86)
    p.add_argument("--keep-expressions", default="", help="lista separada por comas")
    a = p.parse_args()
    mantener = {x for x in a.keep_expressions.split(",") if x} or None
    r = optimizar(a.entrada, a.salida, a.max_px, a.quality, mantener)
    print(f"{r['bytes_antes'] / 1e6:.2f} MB -> {r['bytes_despues'] / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
