"""API REST de noticias (tarea 1.3). Nunca expone el texto en castellano."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db.models import News, Provenance
from app.db.session import get_session
from app.metrics.timing import Timer
from app.schemas import NewsIn, NewsOut
from app.security import require_admin
from app.services import Pipeline, editorial_report, import_payloads, process_news

# Administrativo (Fase 6): la PWA no lo usa; la vía normal es la CLI (app.cli import|process)
router = APIRouter(prefix="/api/news", tags=["news"], dependencies=[Depends(require_admin)])


def to_out(n: News) -> NewsOut:
    p = n.provenance
    return NewsOut(
        id=n.id or 0,
        titulo_cni=n.titulo_cni,
        cuerpo_cni=n.cuerpo_cni,
        variante_dialectal=n.variante_dialectal,
        fecha_publicacion=n.fecha_publicacion,
        fuente_original=n.fuente_original,
        estado=n.estado,
        procedencia_tipo=p.tipo if p else "desconocida",
        revisado_por_hablante=bool(p and p.revisado_por_hablante),
        apta_experimento=n.apta_experimento,
    )


def _get(session: Session, news_id: int) -> News:
    n = session.get(News, news_id)
    if n is None:
        raise HTTPException(404, f"No existe la noticia {news_id}")
    return n


@router.post("", response_model=NewsOut, status_code=201)
def create_news(payload: NewsIn, session: Session = Depends(get_session)) -> NewsOut:
    news_id = import_payloads([payload], session)[0]
    return to_out(_get(session, news_id))


@router.post("/import", response_model=list[int], status_code=201)
def import_news(payloads: list[NewsIn], session: Session = Depends(get_session)) -> list[int]:
    return import_payloads(payloads, session)


@router.get("", response_model=list[NewsOut])
def list_news(session: Session = Depends(get_session)) -> list[NewsOut]:
    return [to_out(n) for n in session.exec(select(News)).all()]


@router.get("/{news_id}", response_model=NewsOut)
def get_news(news_id: int, session: Session = Depends(get_session)) -> NewsOut:
    return to_out(_get(session, news_id))


@router.put("/{news_id}", response_model=NewsOut)
def update_news(news_id: int, payload: NewsIn, session: Session = Depends(get_session)) -> NewsOut:
    n = _get(session, news_id)
    for k, v in payload.model_dump(exclude={"procedencia"}).items():
        setattr(n, k, v)
    if n.provenance is None:  # pragma: no cover - la restricción de inserción lo impide
        n.provenance = Provenance(**payload.procedencia.model_dump())
    else:
        for k, v in payload.procedencia.model_dump().items():
            setattr(n.provenance, k, v)
    n.estado = "ingested"  # el texto pudo cambiar: hay que volver a procesar
    for s in list(n.segments):
        session.delete(s)
    session.add(n)
    session.commit()
    session.refresh(n)
    return to_out(n)


@router.delete("/{news_id}", status_code=204)
def delete_news(news_id: int, session: Session = Depends(get_session)) -> None:
    session.delete(_get(session, news_id))
    session.commit()


@router.post("/{news_id}/process")
def process(news_id: int, session: Session = Depends(get_session)) -> dict:
    n = _get(session, news_id)
    timer = Timer()
    count = process_news(session, n, Pipeline.default(), timer)
    session.commit()
    return {
        "news_id": news_id,
        "estado": n.estado,
        "segmentos": count,
        "latencia_ms": timer.summary(),
    }


@router.get("/{news_id}/segments")
def segments(news_id: int, session: Session = Depends(get_session)) -> list[dict]:
    n = _get(session, news_id)
    return [s.model_dump(exclude={"news_id"}) for s in n.segments]


@router.get("/{news_id}/editorial-report")
def report(news_id: int, session: Session = Depends(get_session)) -> dict:
    _get(session, news_id)
    return editorial_report(news_id)
