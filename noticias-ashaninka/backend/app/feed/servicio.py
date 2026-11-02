"""Ciclo de ingesta automática: TV Perú → BiTAM → pipeline → síntesis por lotes → tablón.

Un ciclo:

1. Descarga el RSS y registra como ``pendiente`` cada ``guid`` nuevo (con el texto ya recortado).
2. Elige hasta ``max_por_ciclo`` pendientes, las más recientes, y las procesa de la más antigua a la más
   nueva: así los ``id`` crecen con la fecha y el tablón «recientes» queda en orden.
3. Por cada una: traduce con BiTAM (``traducir_noticia``), crea la noticia con procedencia
   ``traduccion_automatica`` **no revisada** (``import_payloads``), la procesa (``process_news``) y
   sintetiza el audio (``run_batch``).

Errores:
- Traductor apagado o sin configurar → la noticia sigue ``pendiente`` y el ciclo se corta (se reintenta en
  el siguiente). No se publica nada sin traducir: el tablón nunca muestra castellano como si fuera asháninka.
- Error de traducción o del pipeline → ``error`` y ``intentos += 1``; al tercer intento, ``descartada``.

Nunca se inventa texto en asháninka: todo el texto ``cni`` sale de BiTAM (o del motor ``fake`` en pruebas,
que lo marca con ``[fake-bitam]``). Solo puede correr un ciclo a la vez (``_CANDADO``).
"""

from __future__ import annotations

import dataclasses
import threading
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlmodel import Session, func, select

from app.config import Settings, get_settings
from app.db.models import FeedConfig, FeedItem, News
from app.db.session import get_engine, init_db
from app.feed import tvperu
from app.metrics.timing import Timer
from app.schemas import NewsIn
from app.services import Pipeline, import_payloads, process_news
from app.translation import (
    EnTrozos,
    TextoDemasiadoLargo,
    TraductorError,
    TraductorNoDisponible,
    get_translator,
    traducir_noticia,
)

MAX_INTENTOS = 3
INTERVALOS_PERMITIDOS = (0, 15, 30, 60, 180, 360)  # minutos; 0 = apagado
_CANDADO = threading.Lock()


class CicloEnCurso(RuntimeError):
    """Ya hay un ciclo ejecutándose."""


def _ahora() -> datetime:
    return datetime.now(UTC)


def _utc(d: datetime | None) -> datetime | None:
    """SQLite devuelve fechas sin zona: se interpretan como UTC (así se guardan)."""
    if d is None:
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def ejecutando() -> bool:
    return _CANDADO.locked()


# ------------------------------------------------------------------ configuración
def obtener_config(session: Session, settings: Settings | None = None) -> FeedConfig:
    cfg = session.get(FeedConfig, 1)
    if cfg is None:
        s = settings or get_settings()
        inicial = s.feed_intervalo_min if s.feed_intervalo_min in INTERVALOS_PERMITIDOS else 0
        cfg = FeedConfig(id=1, intervalo_min=inicial)
        session.add(cfg)
        session.commit()
        session.refresh(cfg)
    return cfg


def actualizar_config(intervalo_min: int | None = None, max_por_ciclo: int | None = None) -> dict:
    init_db()
    with Session(get_engine()) as session:
        cfg = obtener_config(session)
        if intervalo_min is not None:
            cfg.intervalo_min = intervalo_min
        if max_por_ciclo is not None:
            cfg.max_por_ciclo = max_por_ciclo
        session.add(cfg)
        session.commit()
    return estado()


def proxima_ejecucion(cfg: FeedConfig) -> datetime | None:
    if cfg.intervalo_min <= 0:
        return None
    ultima = _utc(cfg.ultima_ejecucion)
    if ultima is None:
        return _ahora()
    return ultima + timedelta(minutes=cfg.intervalo_min)


def toca_ejecutar(cfg: FeedConfig, ahora: datetime | None = None) -> bool:
    prox = proxima_ejecucion(cfg)
    return prox is not None and (ahora or _ahora()) >= prox


def estado(settings: Settings | None = None) -> dict[str, Any]:
    s = settings or get_settings()
    init_db()
    with Session(get_engine()) as session:
        cfg = obtener_config(session, s)
        conteo = dict(
            session.exec(select(FeedItem.estado, func.count()).group_by(FeedItem.estado)).all()
        )
        ultima = _utc(cfg.ultima_ejecucion)
        prox = proxima_ejecucion(cfg)
        return {
            "habilitado": s.feed_enabled,
            "fuente": "TV Perú",
            "fuente_url": s.feed_url,
            "intervalo_min": cfg.intervalo_min,
            "intervalos_permitidos": list(INTERVALOS_PERMITIDOS),
            "max_por_ciclo": cfg.max_por_ciclo,
            "ejecutando": ejecutando(),
            "ultima_ejecucion": ultima.isoformat() if ultima else None,
            "proxima_ejecucion": prox.isoformat() if (prox and s.feed_enabled) else None,
            "ultimo_resultado": cfg.ultimo_resultado or None,
            "items": {
                k: int(conteo.get(k, 0)) for k in ("pendiente", "publicada", "error", "descartada")
            },
        }


# ------------------------------------------------------------------ ciclo
def _registrar_nuevos(session: Session, items: list[tvperu.ItemFuente]) -> int:
    conocidos = set(session.exec(select(FeedItem.guid)).all())
    nuevos = 0
    for it in items:
        if it.guid in conocidos:
            continue
        cuerpo = tvperu.recortar(it.parrafos)
        fi = FeedItem(
            guid=it.guid,
            url=it.url,
            categoria=it.categoria,
            titulo_es=tvperu.titulo_recortado(it.titulo),
            cuerpo_es="\n".join(cuerpo),
            publicado_en=it.publicado_en,
        )
        if not cuerpo:  # sin texto aprovechable (solo vídeo o galería): no hay nada que traducir
            fi.estado, fi.error = "descartada", "sin párrafos de texto en el feed"
        session.add(fi)
        conocidos.add(it.guid)
        nuevos += 1
    session.commit()
    return nuevos


def _fallo(item: FeedItem, mensaje: str) -> None:
    item.intentos += 1
    item.error = mensaje[:500]
    item.estado = "descartada" if item.intentos >= MAX_INTENTOS else "error"
    item.updated_at = _ahora()


def _publicar(session: Session, item: FeedItem, borrador, pipeline: Pipeline) -> int:
    payload = NewsIn(
        titulo_cni=borrador.titulo_cni,
        cuerpo_cni="\n".join(borrador.paragraphs),
        titulo_es=item.titulo_es,
        cuerpo_es=item.cuerpo_es,
        fecha_publicacion=item.publicado_en.date() if item.publicado_en else None,
        fuente_original=item.url,
        procedencia=borrador.procedencia,
    )
    news_id = import_payloads([payload], session)[0]
    news = session.get(News, news_id)
    process_news(session, news, pipeline, Timer())
    session.commit()
    if news.estado == "error":
        error = news.error or "error del pipeline"
        session.delete(news)  # no se deja en el tablón una noticia que no se pudo procesar
        session.commit()
        raise RuntimeError(f"pipeline: {error}")
    return news_id


def _sintetizar(news_id: int) -> dict:
    from app.batch.service import run_batch  # importación diferida: carga torch solo si hace falta

    return run_batch([news_id])


def ejecutar_ciclo(settings: Settings | None = None, *, esperar: bool = False) -> dict[str, Any]:
    """Un ciclo completo. Lanza ``CicloEnCurso`` si ya hay otro (salvo ``esperar=True``)."""
    if not _CANDADO.acquire(blocking=esperar):
        raise CicloEnCurso("ya hay una actualización en curso")
    try:
        return _ciclo(settings or get_settings())
    finally:
        _CANDADO.release()


def _ciclo(s: Settings) -> dict[str, Any]:
    t0 = time.perf_counter()
    inicio = _ahora()
    res: dict[str, Any] = {
        "inicio": inicio.isoformat(),
        "nuevas": 0,
        "publicadas": [],
        "errores": 0,
        "pendientes": 0,
        "motivo": None,
        "audio": {"segmentos": 0, "bloqueados": 0, "errores": 0},
    }
    init_db()
    with Session(get_engine()) as session:
        cfg = obtener_config(session, s)
        try:
            res["nuevas"] = _registrar_nuevos(
                session,
                tvperu.parsear_rss(
                    tvperu.descargar_rss(s.feed_url, s.feed_timeout, s.feed_user_agent)
                ),
            )
        except (tvperu.FuenteNoDisponible, tvperu.FuenteError) as e:
            res["motivo"] = f"TV Perú: {e}"

        candidatos = session.exec(
            select(FeedItem)
            .where(FeedItem.estado.in_(("pendiente", "error")))
            .order_by(FeedItem.publicado_en.desc(), FeedItem.id.desc())
            .limit(max(1, cfg.max_por_ciclo))
        ).all()
        candidatos = sorted(candidatos, key=lambda x: (_utc(x.publicado_en) or inicio, x.id or 0))

        translator = None
        pipeline = None
        for item in candidatos:
            try:
                # el ciclo no es interactivo: espera más que la Redacción (NA_FEED_TRANSLATOR_TIMEOUT)
                translator = translator or EnTrozos(
                    get_translator(
                        dataclasses.replace(s, translator_timeout=s.feed_translator_timeout)
                    ),
                    s.feed_translator_lote,  # trozos pequeños: más rápido en GPU de 6 GB (Fase 5)
                )
                borrador = traducir_noticia(item.titulo_es, item.cuerpo_es, translator)
            except TraductorNoDisponible as e:
                res["motivo"] = f"traductor no disponible: {e}"
                break  # sigue pendiente; se reintenta en el próximo ciclo
            except (TextoDemasiadoLargo, TraductorError) as e:
                _fallo(item, f"traducción: {e}")
                session.add(item)
                session.commit()
                res["errores"] += 1
                continue
            try:
                pipeline = pipeline or Pipeline.default()
                news_id = _publicar(session, item, borrador, pipeline)
            except Exception as e:  # el pipeline nunca debe tumbar el ciclo
                session.rollback()
                _fallo(item, str(e))
                session.add(item)
                session.commit()
                res["errores"] += 1
                continue
            item.estado, item.news_id, item.error = "publicada", news_id, None
            item.updated_at = _ahora()
            session.add(item)
            session.commit()
            audio = _sintetizar(news_id)
            res["audio"]["segmentos"] += int(audio.get("synthesized", 0)) + int(
                audio.get("reused", 0)
            )
            res["audio"]["bloqueados"] += int(audio.get("blocked", 0))
            res["audio"]["errores"] += int(audio.get("errors", 0))
            res["publicadas"].append(
                {
                    "news_id": news_id,
                    "titulo_es": item.titulo_es,
                    "url": item.url,
                    "traduccion_s": borrador.segundos,
                }
            )

        res["pendientes"] = int(
            session.exec(
                select(func.count()).select_from(FeedItem).where(FeedItem.estado == "pendiente")
            ).one()
        )
        res["duracion_s"] = round(time.perf_counter() - t0, 2)
        cfg = obtener_config(session, s)
        cfg.ultima_ejecucion = _ahora()
        cfg.ultimo_resultado = res
        session.add(cfg)
        session.commit()
    return res


def lanzar_en_segundo_plano(settings: Settings | None = None) -> bool:
    """Ejecuta un ciclo en un hilo. ``False`` si ya había uno en curso."""
    if not _CANDADO.acquire(blocking=False):
        return False

    def _correr() -> None:
        try:
            _ciclo(settings or get_settings())
        except Exception:  # el estado del ciclo queda en el log; el hilo no debe propagar
            import logging

            logging.getLogger("uvicorn.error").exception("feed: el ciclo falló")
        finally:
            _CANDADO.release()

    threading.Thread(target=_correr, name="feed-ciclo", daemon=True).start()
    return True
