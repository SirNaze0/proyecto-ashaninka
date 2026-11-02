"""Velocidad de la traducción del ciclo de TV Perú: trozos de 4 frente a la noticia entera (Fase 5).

Definido ANTES de ejecutar en ``docs/metrics.md`` (sección «Traducción en trozos dentro del ciclo de TV
Perú»). Una sola ejecución; no guarda texto de TV Perú ni de BiTAM (URL, SHA-256, recuentos y tiempos).

    # con el servicio BiTAM encendido y sin otra carga en el equipo:
    uv run python -m eval.tvperu.lotes [--traductor http://127.0.0.1:8100]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path

from app.config import RESULTS_DIR
from app.feed import tvperu
from app.pipeline.segment import Segmenter
from app.translation import EnTrozos, HttpTranslator

SALIDA = RESULTS_DIR / "tvperu_lotes.json"
ORDEN = [(4, 0), (0, 4), (4, 0)]  # alternado por noticia (fijado en docs/metrics.md)


def _h(textos: list[str]) -> list[str]:
    return [hashlib.sha256(t.encode("utf-8")).hexdigest()[:12] for t in textos]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--traductor", default=os.getenv("NA_TRANSLATOR_URL") or "http://127.0.0.1:8100"
    )
    ap.add_argument("--salida", type=Path, default=SALIDA)
    args = ap.parse_args(argv)

    url_feed = os.getenv("NA_FEED_URL") or "https://www.tvperu.gob.pe/rss.xml"
    rss = tvperu.descargar_rss(url_feed, 30)
    items = [i for i in tvperu.parsear_rss(rss) if tvperu.recortar(i.parrafos)][:3]
    seg = Segmenter.from_files()
    http = HttpTranslator(args.traductor, timeout=1800)
    salud = http.salud()
    http.translate_batch(["Calentamiento del servicio."])  # se descarta

    noticias = []
    for item, orden in zip(items, ORDEN, strict=False):
        cuerpo = "\n".join(tvperu.recortar(item.parrafos))
        textos = [tvperu.titulo_recortado(item.titulo)] + [s.text for s in seg.segment(cuerpo)]
        medidas: dict[int, dict] = {}
        for lote in orden:
            t0 = time.perf_counter()
            r = EnTrozos(http, lote).translate_batch(textos)
            s = time.perf_counter() - t0
            medidas[lote] = {
                "s": round(s, 1),
                "s_por_texto": round(s / len(textos), 2),
                "hash": _h(r.translations),
            }
            print(f"{item.url[-50:]} lote={lote}: {s:.1f} s", flush=True)
        distintas = sum(a != b for a, b in zip(medidas[4]["hash"], medidas[0]["hash"], strict=True))
        noticias.append(
            {
                "url": item.url,
                "textos": len(textos),
                "orden": list(orden),
                "lote_4": {k: v for k, v in medidas[4].items() if k != "hash"},
                "todo_junto": {k: v for k, v in medidas[0].items() if k != "hash"},
                "ahorro": round(1 - medidas[4]["s"] / medidas[0]["s"], 3),
                "salidas_distintas": distintas,
            }
        )

    t4 = sum(n["lote_4"]["s"] for n in noticias)
    t0 = sum(n["todo_junto"]["s"] for n in noticias)
    salida = {
        "fecha": datetime.now(UTC).isoformat(timespec="seconds"),
        "definicion": "docs/metrics.md (Traducción en trozos dentro del ciclo de TV Perú)",
        "rss_sha256": hashlib.sha256(rss).hexdigest(),
        "traductor": {k: salud.get(k) for k in ("modelo", "version", "dispositivo", "dtype")},
        "noticias": noticias,
        "total": {
            "lote_4_s": round(t4, 1),
            "todo_junto_s": round(t0, 1),
            "ahorro": round(1 - t4 / t0, 3) if t0 else None,
            "salidas_distintas": sum(n["salidas_distintas"] for n in noticias),
            "textos": sum(n["textos"] for n in noticias),
        },
    }
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(
        json.dumps(salida, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(salida["total"], ensure_ascii=False))
    print(f"[lotes] {args.salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
