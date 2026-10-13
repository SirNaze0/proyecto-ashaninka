"""Catálogo de noticias para la PWA (Fase 4, tarea 4.1).

Vista pública y ligera: lista y detalle por párrafos. NUNCA expone el texto en castellano
(no contamina el experimento) ni el JSON interno de cada segmento. El audio, el manifiesto y los
tiempos los sirve ``/static``; aquí solo se dice si ya existen (``manifest_url``).
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlmodel import Session, select

from app.config import get_settings
from app.db.models import News, Segment
from app.db.session import get_session

router = APIRouter(prefix="/api/catalog", tags=["catalog"])

SYNTHETIC_NOTICE = "Voz sintética generada por computadora; no es la voz de una persona."


class CatalogItem(BaseModel):
    id: int
    titulo_cni: str
    variante_dialectal: str
    fecha_publicacion: str | None
    procedencia_tipo: str
    revisado_por_hablante: bool
    apta_experimento: bool
    segmentos: int
    segmentos_con_audio: int
    segmentos_bloqueados: int
    duracion_s: float | None
    manifest_url: str | None


class CatalogSegment(BaseModel):
    idx: int
    paragraph_idx: int
    text_orig: str
    tts_ready: bool
    blocked_reason: str | None


class CatalogDetail(BaseModel):
    id: int
    titulo_cni: str
    variante_dialectal: str
    fecha_publicacion: str | None
    procedencia_tipo: str
    apta_experimento: bool
    manifest_url: str | None
    parrafos: list[list[CatalogSegment]]
    avisos: dict[str, str]


def _manifest(news_id: int) -> tuple[str | None, dict | None]:
    """URL y contenido del manifiesto si ya se generó (modo por lotes)."""
    path: Path = get_settings().static_dir / "news" / str(news_id) / "manifest.json"
    if not path.is_file():
        return None, None
    try:
        return f"/static/news/{news_id}/manifest.json", json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):  # manifiesto a medio escribir o dañado: se trata como ausente
        return None, None


def _blocked_reason(seg: Segment) -> str | None:
    if seg.tts_ready:
        return None
    return next(
        (u["reason"] for u in seg.unresolved if str(u.get("reason", "")).startswith("bloqueado")),
        "bloqueado para TTS",
    )


def _item(n: News, counts: tuple[int, int, int]) -> CatalogItem:
    total, ready, blocked = counts
    url, manifest = _manifest(n.id or 0)
    p = n.provenance
    return CatalogItem(
        id=n.id or 0,
        titulo_cni=n.titulo_cni,
        variante_dialectal=n.variante_dialectal,
        fecha_publicacion=n.fecha_publicacion.isoformat() if n.fecha_publicacion else None,
        procedencia_tipo=p.tipo if p else "desconocida",
        revisado_por_hablante=bool(p and p.revisado_por_hablante),
        apta_experimento=n.apta_experimento,
        segmentos=total,
        segmentos_con_audio=ready,
        segmentos_bloqueados=blocked,
        duracion_s=manifest.get("total_duration_s") if manifest else None,
        manifest_url=url,
    )


@router.get("", response_model=list[CatalogItem])
def list_catalog(
    solo_con_audio: bool = False,
    limit: int = 200,
    offset: int = 0,
    session: Session = Depends(get_session),
) -> list[CatalogItem]:
    limit = max(1, min(limit, 500))
    rows = session.exec(
        select(Segment.news_id, func.count(Segment.id), func.sum(Segment.tts_ready)).group_by(
            Segment.news_id
        )
    ).all()
    counts = {nid: (int(t), int(r or 0), int(t) - int(r or 0)) for nid, t, r in rows}
    items = []
    for n in session.exec(select(News).order_by(News.id)).all():
        item = _item(n, counts.get(n.id, (0, 0, 0)))
        if solo_con_audio and not item.manifest_url:
            continue
        items.append(item)
    return items[offset : offset + limit]


@router.get("/{news_id}", response_model=CatalogDetail)
def catalog_detail(news_id: int, session: Session = Depends(get_session)) -> CatalogDetail:
    n = session.get(News, news_id)
    if n is None:
        raise HTTPException(404, f"No existe la noticia {news_id}")
    url, manifest = _manifest(news_id)
    paragraphs: dict[int, list[CatalogSegment]] = {}
    for s in n.segments:
        paragraphs.setdefault(s.paragraph_idx, []).append(
            CatalogSegment(
                idx=s.idx,
                paragraph_idx=s.paragraph_idx,
                text_orig=s.text_orig,
                tts_ready=s.tts_ready,
                blocked_reason=_blocked_reason(s),
            )
        )
    if not paragraphs:  # noticia aún sin procesar: solo el texto (C1), sin audio posible
        for i, par in enumerate(p.strip() for p in n.cuerpo_cni.splitlines() if p.strip()):
            paragraphs[i] = [
                CatalogSegment(
                    idx=i, paragraph_idx=i, text_orig=par, tts_ready=False, blocked_reason=None
                )
            ]
    notices = {"synthetic_voice": SYNTHETIC_NOTICE}
    if manifest:
        notices = {
            "synthetic_voice": manifest["notices"]["synthetic_voice"],
            "license": manifest["notices"]["license"],
            "non_commercial_warning": manifest["notices"].get("non_commercial_warning") or "",
        }
    p = n.provenance
    return CatalogDetail(
        id=n.id or 0,
        titulo_cni=n.titulo_cni,
        variante_dialectal=n.variante_dialectal,
        fecha_publicacion=n.fecha_publicacion.isoformat() if n.fecha_publicacion else None,
        procedencia_tipo=p.tipo if p else "desconocida",
        apta_experimento=n.apta_experimento,
        manifest_url=url,
        parrafos=[paragraphs[k] for k in sorted(paragraphs)],
        avisos=notices,
    )
