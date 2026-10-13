"""Selección de las 4 noticias fijas del experimento (tarea 5.2, requiere P4).

Reglas (``docs/metrics.md``, «Fase 5»):
- Solo noticias aptas (``News.apta_experimento``: revisadas por un hablante, no pseudo-noticias del
  corpus). En modo piloto se admiten pseudo-noticias, y todo queda marcado como piloto.
- Se prefieren las noticias **sin segmentos bloqueados** (limitación 42). Si faltan, se completan con
  las de menor proporción de bloqueados y esa proporción se guarda como covariable.
- La noticia debe tener al menos un segmento con audio (``tts_ready``).
- La elección es determinista (menos bloqueados, luego menor id) y se **fija** en
  ``ExperimentMaterial``: todos los participantes comparten el mismo conjunto.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Integer, cast, func
from sqlmodel import Session, select

from app.db.models import ExperimentMaterial, News, Segment

N_NOTICIAS = 4


class SinNoticiasAptas(Exception):
    """No hay 4 noticias que cumplan las condiciones del experimento."""


@dataclass(frozen=True)
class Candidata:
    news_id: int
    bloqueados_prop: float


def candidatas(session: Session, piloto: bool) -> list[Candidata]:
    filas = session.exec(
        select(
            Segment.news_id,
            func.count(Segment.id),
            func.sum(cast(Segment.tts_ready, Integer)),
        ).group_by(Segment.news_id)
    ).all()
    out: list[Candidata] = []
    for news_id, total, listos in filas:
        listos = int(listos or 0)
        if listos < 1:
            continue
        news = session.get(News, news_id)
        if news is None or (not piloto and not news.apta_experimento):
            continue
        out.append(Candidata(news_id, round((total - listos) / total, 4)))
    return sorted(out, key=lambda c: (c.bloqueados_prop, c.news_id))


def material(session: Session, piloto: bool) -> list[ExperimentMaterial]:
    """Devuelve las 4 noticias del experimento, fijándolas la primera vez.

    Lanza ``SinNoticiasAptas`` si no hay 4 candidatas y el material no estaba fijado.
    """
    fijado = session.exec(
        select(ExperimentMaterial)
        .where(ExperimentMaterial.piloto == piloto)
        .order_by(ExperimentMaterial.slot)
    ).all()
    if len(fijado) == N_NOTICIAS:
        return list(fijado)
    cand = candidatas(session, piloto)
    if len(cand) < N_NOTICIAS:
        raise SinNoticiasAptas(
            f"se necesitan {N_NOTICIAS} noticias aptas con audio y hay {len(cand)}"
            + ("" if piloto else " (modo real: revisadas por un hablante, P4)")
        )
    for fila in fijado:  # conjunto incompleto de una carga previa: se rehace
        session.delete(fila)
    session.flush()
    nuevas = [
        ExperimentMaterial(
            piloto=piloto, slot=i, news_id=c.news_id, bloqueados_prop=c.bloqueados_prop
        )
        for i, c in enumerate(cand[:N_NOTICIAS])
    ]
    session.add_all(nuevas)
    session.commit()
    return nuevas
