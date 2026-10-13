"""Tarea 3.2 — Kit de anotación manual en Praat y comparación con la alineación del sistema.

El plan pide validar contra 20 oraciones anotadas A MANO. Eso lo tiene que hacer una persona:
este módulo prepara el material y calcula el error cuando las anotaciones existan.

* ``kit``: escribe, en ``eval/fase3/praat/``, el WAV de las primeras 20 oraciones de la
  selección (dev) y un TextGrid VACÍO (una sola unidad por nivel) con dos niveles: ``palabras``
  y ``fonemas``. NO se pre-rellena con los límites del sistema para no sesgar a quien anota.
  Se incluye ``lista_de_palabras.txt`` con el texto que se debe segmentar.
* ``comparar``: lee los TextGrid anotados (mismo nombre, carpeta ``anotado/``) y calcula el error
  medio de los límites de palabra y de fonema contra ``seg_NNN.json``.

Uso: uv run python -m eval.fase3.praat kit | comparar
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import soundfile as sf

from eval.fase3.ctc import error_stats
from eval.fase3.prepare import OUT, ROOT, STATIC

PRAAT = ROOT / "eval" / "fase3" / "praat"
N = 20


def textgrid_vacio(dur: float, niveles: list[str]) -> str:
    out = [
        'File type = "ooTextFile"',
        'Object class = "TextGrid"',
        "",
        "xmin = 0",
        f"xmax = {dur:.4f}",
        "tiers? <exists>",
        f"size = {len(niveles)}",
        "item []:",
    ]
    for i, nombre in enumerate(niveles, 1):
        out += [
            f"    item [{i}]:",
            '        class = "IntervalTier"',
            f'        name = "{nombre}"',
            "        xmin = 0",
            f"        xmax = {dur:.4f}",
            "        intervals: size = 1",
            "        intervals [1]:",
            "            xmin = 0",
            f"            xmax = {dur:.4f}",
            '            text = ""',
        ]
    return "\n".join(out) + "\n"


def leer_textgrid(path: Path) -> dict[str, list[tuple[float, float, str]]]:
    """Niveles de intervalos de un TextGrid en formato largo: nombre -> [(xmin, xmax, texto)]."""
    txt = path.read_text(encoding="utf-8")
    niveles: dict[str, list[tuple[float, float, str]]] = {}
    for bloque in re.split(r"\n\s*item \[\d+\]:", txt)[1:]:
        nombre = re.search(r'name = "(.*?)"', bloque)
        if not nombre or "IntervalTier" not in bloque:
            continue
        intervalos = re.findall(
            r"intervals \[\d+\]:\s*xmin = ([\d.eE+-]+)\s*xmax = ([\d.eE+-]+)\s*text = \"(.*?)\"",
            bloque,
            flags=re.S,
        )
        niveles[nombre.group(1)] = [(float(a), float(b), t.strip()) for a, b, t in intervalos]
    return niveles


def limites(nivel: list[tuple[float, float, str]]) -> list[tuple[float, float]]:
    """Intervalos con texto (se ignoran los vacíos: silencios)."""
    return [(a, b) for a, b, t in nivel if t]


def errores_limites(ref: list[tuple[float, float]], sis: list[tuple[float, float]]) -> list[float]:
    """Errores (ms, sistema - referencia) de inicio y fin, en orden. Exige el mismo número."""
    if len(ref) != len(sis):
        raise ValueError(f"número distinto de unidades: anotadas {len(ref)}, sistema {len(sis)}")
    out: list[float] = []
    for (a0, a1), (s0, s1) in zip(ref, sis, strict=True):
        out += [(s0 - a0) * 1000, (s1 - a1) * 1000]
    return out


def kit() -> None:
    sel = json.loads((OUT / "selection.json").read_text("utf-8"))[:N]
    PRAAT.mkdir(parents=True, exist_ok=True)
    lista = []
    for item in sel:
        nid = item["news_id"]
        manifest = json.loads((STATIC / "news" / str(nid) / "manifest.json").read_text("utf-8"))
        wav, sr = sf.read(
            STATIC / manifest["segments"][0]["audio"]["opus"].removeprefix("/static/")
        )
        nombre = f"noticia_{nid:04d}"
        sf.write(PRAAT / f"{nombre}.wav", wav, sr, subtype="PCM_16")
        (PRAAT / f"{nombre}.TextGrid").write_text(
            textgrid_vacio(len(wav) / sr, ["palabras", "fonemas"]), encoding="utf-8"
        )
        seg = json.loads((STATIC / "news" / str(nid) / "seg_000.json").read_text("utf-8"))
        lista.append(f"{nombre}: {seg['durations']['text']}")
    (PRAAT / "lista_de_palabras.txt").write_text("\n".join(lista) + "\n", encoding="utf-8")
    print(f"[praat] {len(sel)} oraciones en {PRAAT}; anotar y guardar en {PRAAT / 'anotado'}")


def comparar() -> None:
    carpeta = PRAAT / "anotado"
    archivos = sorted(carpeta.glob("*.TextGrid")) if carpeta.exists() else []
    if not archivos:
        print("[praat] no hay anotaciones en", carpeta, "- comparación pendiente")
        return
    pal: list[float] = []
    fon: list[float] = []
    for tg in archivos:
        nid = int(tg.stem.split("_")[1])
        seg = json.loads((STATIC / "news" / str(nid) / "seg_000.json").read_text("utf-8"))
        niveles = leer_textgrid(tg)
        sis_p = [(w["t0"], w["t1"]) for w in seg["alignment"]["words"]]
        sis_f = [(p["t0"], p["t1"]) for p in seg["alignment"]["phonemes"]]
        pal += errores_limites(limites(niveles.get("palabras", [])), sis_p)
        fon += errores_limites(limites(niveles.get("fonemas", [])), sis_f)
    res = {
        "oraciones": len(archivos),
        "limites_palabra": error_stats(pal),
        "limites_fonema": error_stats(fon),
    }
    (ROOT / "eval" / "results" / "fase_3_praat.json").write_text(
        json.dumps(res, indent=2, ensure_ascii=False), "utf-8"
    )
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    {"kit": kit, "comparar": comparar}.get(cmd, lambda: print(__doc__))()
