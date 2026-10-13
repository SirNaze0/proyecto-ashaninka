"""Registro de eventos del experimento (Fase 4, tarea 4.4 / base de la Fase 5).

El cliente guarda los eventos en IndexedDB (cola) y los envía por lotes cuando hay red. Cada
evento trae un ``event_id`` UUID generado en el dispositivo: reenviar un lote es idempotente.

Privacidad (tarea 5.5): el ``session_id`` es un UUID anónimo y el ``payload`` solo admite claves
de una lista cerrada con valores escalares cortos. Nada de nombres, documentos ni geolocalización.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlmodel import Session, select

from app.db.models import ClientEvent
from app.db.session import get_session

router = APIRouter(prefix="/api/events", tags=["events"])

MAX_BATCH = 500
EventType = Literal[
    "view-start",
    "view-end",
    "play",
    "pause",
    "seek",
    "rate",
    "repeat-paragraph",
    "segment-start",
    "segment-end",
    "blocked-shown",
    "degradacion",
    "avatar-ok",
    "text-size",
    "lang",
    "save-offline",
    "offline-sync",
    "error",
    # Fase 5: flujo del experimento
    "consent",
    "block-start",
    "block-end",
    "read-done",
    "questionnaire-submit",
    "session-finish",
    "abandon",
]
PAYLOAD_KEYS = frozenset(
    {
        "idx",
        "paragraph",
        "rate",
        "reason",
        "fps",
        "mode",
        "modo",
        "size",
        "lang",
        "duration_ms",
        "ttfa_ms",
        "delay_ms",
        "user_agent",
        "message",
        "position_s",
        "count",
        "posicion",
        "participant",
        "blocks",
    }
)
_UUID = re.compile(r"^[0-9a-fA-F-]{16,64}$")
Scalar = str | int | float | bool | None


class EventIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str
    session_id: str
    condition: Literal["C1", "C2", "C3", "C4"] | None = None
    news_id: int | None = None
    type: EventType
    t_client: datetime
    payload: dict[str, Scalar] = Field(default_factory=dict)

    @field_validator("event_id", "session_id")
    @classmethod
    def _uuid(cls, v: str) -> str:
        if not _UUID.match(v):
            raise ValueError("debe ser un UUID anónimo generado en el dispositivo")
        return v

    @field_validator("payload")
    @classmethod
    def _payload(cls, v: dict[str, Scalar]) -> dict[str, Scalar]:
        extra = set(v) - PAYLOAD_KEYS
        if extra:
            raise ValueError(f"claves de payload no permitidas: {sorted(extra)}")
        for k, x in v.items():
            if isinstance(x, str) and len(x) > 300:
                raise ValueError(f"valor demasiado largo en {k}")
        return v


class BatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    events: list[EventIn] = Field(min_length=1, max_length=MAX_BATCH)


class BatchOut(BaseModel):
    recibidos: int
    nuevos: int
    duplicados: int


@router.post("", response_model=BatchOut, status_code=201)
def post_events(batch: BatchIn, session: Session = Depends(get_session)) -> BatchOut:
    rows: list[dict[str, Any]] = [
        {
            "event_id": e.event_id,
            "session_id": e.session_id,
            "condition": e.condition,
            "news_id": e.news_id,
            "type": e.type,
            "t_client": e.t_client,
            "payload": e.payload,
        }
        for e in batch.events
    ]
    before = session.exec(select(func.count(ClientEvent.id))).one()
    # INSERT OR IGNORE sobre la clave única event_id: idempotente y sin carreras entre lotes
    session.execute(sqlite_insert(ClientEvent).values(rows).prefix_with("OR IGNORE"))
    session.commit()
    after = session.exec(select(func.count(ClientEvent.id))).one()
    nuevos = after - before
    return BatchOut(recibidos=len(rows), nuevos=nuevos, duplicados=len(rows) - nuevos)


@router.get("/summary")
def summary(session: Session = Depends(get_session)) -> dict:
    by_type = session.exec(select(ClientEvent.type, func.count()).group_by(ClientEvent.type)).all()
    by_cond = session.exec(
        select(ClientEvent.condition, func.count()).group_by(ClientEvent.condition)
    ).all()
    return {
        "total": sum(c for _, c in by_type),
        "por_tipo": {t: c for t, c in by_type},
        "por_condicion": {str(k): c for k, c in by_cond},
        "sesiones": session.exec(select(func.count(func.distinct(ClientEvent.session_id)))).one(),
    }
