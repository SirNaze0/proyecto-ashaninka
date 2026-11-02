"""Un ciclo real del lector de TV Perú con BiTAM y la voz MMS (NoticiasTVPeru, Fase 3).

Métricas, material y reglas definidos ANTES de ejecutar en ``docs/metrics.md`` (sección «Noticias
automáticas de TV Perú»). NO evalúa la calidad de la traducción (contrato §2).

    # con el servicio BiTAM encendido (traductor/run.ps1) y sin otra carga en el equipo:
    uv run python -m eval.tvperu.run [--traductor http://127.0.0.1:8100] [--con-carga]

Usa una base de datos y un directorio estático TEMPORALES (no toca ``data/noticias.db``). El resultado
no guarda texto de TV Perú ni de BiTAM: URL, recuentos, tiempos y hashes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from app.config import RESULTS_DIR

SALIDA = RESULTS_DIR / "tvperu.json"


def _sha(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:16]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--traductor", default=os.getenv("NA_TRANSLATOR_URL") or "http://127.0.0.1:8100"
    )
    ap.add_argument(
        "--con-carga", action="store_true", help="declara que el equipo tenía otra carga"
    )
    ap.add_argument("--salida", type=Path, default=SALIDA)
    args = ap.parse_args(argv)

    trabajo = Path(tempfile.mkdtemp(prefix="na-tvperu-"))
    os.environ["NA_DATABASE_URL"] = f"sqlite:///{(trabajo / 'tvperu.db').as_posix()}"
    os.environ["NA_STATIC_DIR"] = str(trabajo / "static")
    os.environ["NA_TRANSLATOR_ENGINE"] = "http"
    os.environ["NA_TRANSLATOR_URL"] = args.traductor
    os.environ.setdefault("NA_TTS_ENGINE", "mms_vits")

    from app.db.models import FeedItem, News
    from app.db.session import get_engine
    from app.feed import servicio
    from app.pipeline.segment import Segmenter
    from app.translation import estado_traductor
    from sqlmodel import Session, select

    salud = estado_traductor()
    sintesis_s: dict[int, float] = {}
    original = servicio._sintetizar

    def cronometrado(news_id: int) -> dict:
        t0 = time.perf_counter()
        r = original(news_id)
        sintesis_s[news_id] = round(time.perf_counter() - t0, 2)
        return r

    servicio._sintetizar = cronometrado
    res = servicio.ejecutar_ciclo(esperar=True)

    seg = Segmenter.from_files()
    noticias = []
    with Session(get_engine()) as s:
        for pub in res["publicadas"]:
            n = s.get(News, pub["news_id"])
            item = s.exec(select(FeedItem).where(FeedItem.news_id == n.id)).one()
            oraciones = len(seg.segment(item.cuerpo_es))
            motivos = Counter()
            for x in n.segments:
                if not x.tts_ready:
                    for u in x.unresolved:
                        if str(u.get("reason", "")).startswith("bloqueado"):
                            motivos[str(u["reason"]).split(":")[0]] += 1
            manifiesto = Path(os.environ["NA_STATIC_DIR"]) / "news" / str(n.id) / "manifest.json"
            audio_s = (
                json.loads(manifiesto.read_text("utf-8")).get("total_duration_s")
                if manifiesto.is_file()
                else None
            )
            con_audio = sum(1 for x in n.segments if x.tts_ready)
            noticias.append(
                {
                    "url": item.url,
                    "categoria": item.categoria,
                    "titulo_es_sha256": _sha(item.titulo_es),
                    "parrafos_enviados": len(item.cuerpo_es.splitlines()),
                    "oraciones_enviadas": oraciones,
                    "caracteres_enviados": len(item.cuerpo_es),
                    "traduccion_s": pub["traduccion_s"],
                    "traduccion_s_por_oracion": round(
                        pub["traduccion_s"] / max(1, oraciones + 1), 2
                    ),
                    "sintesis_s": sintesis_s.get(n.id),
                    "segmentos": len(n.segments),
                    "segmentos_con_audio": con_audio,
                    "segmentos_bloqueados": len(n.segments) - con_audio,
                    "motivo_bloqueo_mas_frecuente": motivos.most_common(1)[0] if motivos else None,
                    "audio_s": audio_s,
                }
            )
        conteo = Counter(x.estado for x in s.exec(select(FeedItem)).all())

    salida = {
        "fecha": datetime.now(UTC).isoformat(timespec="seconds"),
        "definicion": "docs/metrics.md#noticias-automáticas-de-tv-perú-noticiastvperu-fase-3",
        "fuente": os.getenv("NA_FEED_URL") or "https://www.tvperu.gob.pe/rss.xml",
        "traductor": {
            k: salud.get(k) for k in ("disponible", "motivo", "modelo", "version", "dispositivo")
        },
        "tts_engine": os.environ["NA_TTS_ENGINE"],
        "sin_otra_carga": not args.con_carga,
        "estado": "medido" if res["publicadas"] else "pendiente",
        "motivo": res["motivo"],
        "ciclo": {
            "nuevas": res["nuevas"],
            "publicadas": len(res["publicadas"]),
            "errores": res["errores"],
            "pendientes": res["pendientes"],
            "items_por_estado": dict(conteo),
            "duracion_s": res["duracion_s"],
            "audio": res["audio"],
        },
        "noticias": noticias,
    }
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(
        json.dumps(salida, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(salida, ensure_ascii=False, indent=2))
    print(f"[tvperu] {args.salida}")
    return 0 if res["publicadas"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
