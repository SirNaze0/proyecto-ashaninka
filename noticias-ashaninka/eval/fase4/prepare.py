"""Prepara el material de la evaluación de la Fase 4 (tarea 4.7).

Usa una base de datos y una carpeta ``static`` PROPIAS (``eval/fase4/out/``). Regla de selección,
fijada ANTES de medir (``docs/metrics.md``, «Revisión del material»): el corpus tiene una oración
por línea, así que cada pseudo-noticia agrupa 3 líneas CONSECUTIVAS del split **dev** (las líneas
1-2 en el párrafo 1 y la 3 en el párrafo 2), desde la línea 1 y en orden, hasta ``--news``
noticias. No se descarta ninguna: los segmentos bloqueados (sin P2d) entran tal como vienen. Se
sintetiza con ``mms_vits`` (adaptador y semilla por defecto). Nunca se usa el split test.

Uso: uv run python -m eval.fase4.prepare [--news 30] [--lines 3]
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "eval" / "fase4" / "out"
STATIC = OUT / "static"
DB = OUT / "bench.db"


def entorno() -> None:
    os.environ["NA_DATABASE_URL"] = f"sqlite:///{DB.relative_to(ROOT).as_posix()}"
    os.environ["NA_STATIC_DIR"] = STATIC.relative_to(ROOT).as_posix()
    os.environ["NA_TTS_ENGINE"] = "mms_vits"
    # Fase 6: /api/events/summary exige token; fase4_bench.mjs usa este mismo valor por defecto
    os.environ.setdefault("NA_ADMIN_TOKEN", "bench-fase4-token-0123456789")


def importar(n_news: int, lines: int) -> list[int]:
    from app.corpus.loader import load_split
    from app.db.models import News, Provenance
    from app.db.session import get_engine, init_db
    from sqlmodel import Session, select

    init_db()
    pairs = load_split("dev")[: n_news * lines]
    if len(pairs) < n_news * lines:
        raise SystemExit("el split dev no alcanza para la selección pedida")
    ids = []
    with Session(get_engine()) as s:
        for k in range(n_news):
            grp = pairs[k * lines : (k + 1) * lines]
            cuerpo = " ".join(p.cni for p in grp[:-1]) + "\n" + grp[-1].cni
            n = News(
                titulo_cni=f"dev:{grp[0].line}-{grp[-1].line}",
                cuerpo_cni=cuerpo,
                titulo_es=f"dev:{grp[0].line}-{grp[-1].line}",
                cuerpo_es=" ".join(p.es for p in grp),
                variante_dialectal="mixta (corpus AmericasNLP)",
                fuente_original=f"AmericasNLP2021@d3f519c dev:{grp[0].line}-{grp[-1].line}",
            )
            n.provenance = Provenance(
                tipo="corpus_americasnlp",
                sistema="AmericasNLP2021",
                version="d3f519c",
                revisado_por_hablante=False,
            )
            s.add(n)
        s.commit()
        ids = [n.id for n in s.exec(select(News)).all()]
    return ids


def seleccion() -> list[dict]:
    out = []
    for d in sorted((STATIC / "news").iterdir(), key=lambda p: int(p.name)):
        m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
        out.append(
            {
                "news_id": m["news_id"],
                "titulo": m["titulo_cni"],
                "segmentos": len(m["segments"]),
                "con_audio": m["segments_with_audio"],
                "bloqueados": m["segments_blocked"],
                "duracion_s": m["total_duration_s"],
                "parrafos": len({s["paragraph_idx"] for s in m["segments"]}),
            }
        )
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--news", type=int, default=30)
    ap.add_argument("--lines", type=int, default=3)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    entorno()
    if DB.exists():
        raise SystemExit(f"{DB} ya existe: bórralo para repetir la preparación")
    ids = importar(a.news, a.lines)
    print(f"[fase4] {len(ids)} pseudo-noticias importadas")
    from app.batch.service import run_batch

    print("[fase4] síntesis:", run_batch())
    sel = seleccion()
    (OUT / "selection.json").write_text(json.dumps(sel, indent=1, ensure_ascii=False), "utf-8")
    print(f"[fase4] {len(sel)} noticias -> {OUT / 'selection.json'}")


if __name__ == "__main__":
    main()
