"""Motor y sesiones de base de datos.

En esta fase el esquema se aplica con ``SQLModel.metadata.create_all`` (idempotente).
Las migraciones versionadas (Alembic) se incorporan cuando el esquema se estabilice;
queda registrado en docs/limitations.md.
"""

from __future__ import annotations

from collections.abc import Iterator
from functools import cache
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from app.config import get_settings
from app.db import models  # noqa: F401  (registra las tablas)


@cache
def get_engine(url: str | None = None) -> Engine:
    url = url or get_settings().database_url
    if url.startswith("sqlite:///"):
        Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30})
    if url.startswith("sqlite"):
        # WAL: lecturas concurrentes mientras otro proceso/hilo escribe (streaming simultáneo)
        @event.listens_for(engine, "connect")
        def _wal(dbapi_conn, _record):  # pragma: no cover - trivial
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA busy_timeout=30000")
            cur.close()

    return engine


def init_db(engine: Engine | None = None) -> None:
    SQLModel.metadata.create_all(engine or get_engine())


def get_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session
