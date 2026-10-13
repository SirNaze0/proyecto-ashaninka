"""API del experimento (Fase 5): sesiones, cuestionarios y exportación.

Privacidad (tarea 5.5): el participante es solo un código anónimo (``P007``) y el dispositivo un
UUID. No se piden ni guardan nombres, documentos, teléfonos ni geolocalización; la edad va por
rangos y el comentario libre se rechaza si parece traer datos personales.
"""

from __future__ import annotations

import io
import zipfile
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlmodel import Session, func, select

from app.config import get_settings
from app.db.models import ExperimentSession, QuestionnaireResponse
from app.db.session import get_session
from app.experiment import export, instrumentos, latin, pool
from app.security import comprobar_token, hay_token_configurado

router = APIRouter(prefix="/api/experiment", tags=["experiment"])

_UUID = r"^[0-9a-fA-F-]{16,64}$"
MAX_RESPONSES = 20


# ------------------------------------------------------------------ configuración
@router.get("/config")
def config() -> dict[str, Any]:
    s = get_settings()
    d = instrumentos.cargar()
    return {
        "version_instrumentos": d["version"],
        "consent_version": s.consent_version,
        "consent_status": d["consentimiento"]["status"],
        "piloto": s.experiment_piloto,
        "condiciones": list(latin.CONDICIONES),
        "post_noticia": d["post_noticia"],
        "final": d["final"],
    }


# ------------------------------------------------------------------ sesiones
class SessionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    participant_code: str
    session_id: str = Field(pattern=_UUID)
    consent: bool
    consent_version: str = Field(max_length=80)

    @field_validator("participant_code")
    @classmethod
    def _codigo(cls, v: str) -> str:
        return latin.normalizar_codigo(v)  # ValueError -> 422


class BloqueOut(BaseModel):
    posicion: int
    condicion: str
    slot_noticia: int
    news_id: int
    bloqueados_prop: float


class SessionOut(BaseModel):
    participant_code: str
    indice: int
    piloto: bool
    estado: str
    consent_version: str
    bloques: list[BloqueOut]


def _out(s: ExperimentSession) -> SessionOut:
    return SessionOut(
        participant_code=s.participant_code,
        indice=s.indice,
        piloto=s.piloto,
        estado=s.estado,
        consent_version=s.consent_version,
        bloques=[BloqueOut(**b) for b in s.secuencia],
    )


@router.post("/sessions", response_model=SessionOut)
def crear_sesion(
    body: SessionIn, response: Response, session: Session = Depends(get_session)
) -> SessionOut:
    """Crea la sesión (idempotente por código: el mismo código devuelve la misma asignación)."""
    if not body.consent:
        raise HTTPException(422, "se requiere el consentimiento informado")
    actual = session.exec(
        select(ExperimentSession).where(ExperimentSession.participant_code == body.participant_code)
    ).first()
    if actual:
        if actual.session_id != body.session_id:
            raise HTTPException(409, "el código ya está en uso en otro dispositivo")
        return _out(actual)
    piloto = get_settings().experiment_piloto
    try:
        mat = pool.material(session, piloto)
    except pool.SinNoticiasAptas as e:
        raise HTTPException(409, str(e)) from e
    indice = latin.indice_participante(body.participant_code)
    bloques = [
        {
            "posicion": b.posicion,
            "condicion": b.condicion,
            "slot_noticia": b.slot_noticia,
            "news_id": mat[b.slot_noticia].news_id,
            "bloqueados_prop": mat[b.slot_noticia].bloqueados_prop,
        }
        for b in latin.secuencia(indice)
    ]
    nueva = ExperimentSession(
        participant_code=body.participant_code,
        session_id=body.session_id,
        indice=indice,
        secuencia=bloques,
        piloto=piloto,
        consent_version=body.consent_version,
    )
    session.add(nueva)
    session.commit()
    session.refresh(nueva)
    response.status_code = 201
    return _out(nueva)


def _sesion(session: Session, code: str) -> ExperimentSession:
    try:
        code = latin.normalizar_codigo(code)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    s = session.exec(
        select(ExperimentSession).where(ExperimentSession.participant_code == code)
    ).first()
    if not s:
        raise HTTPException(404, "sesión no encontrada")
    return s


@router.get("/sessions/{code}")
def estado_sesion(code: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    s = _sesion(session, code)
    resp = session.exec(
        select(QuestionnaireResponse.kind, QuestionnaireResponse.posicion).where(
            QuestionnaireResponse.session_id == s.session_id
        )
    ).all()
    return {**_out(s).model_dump(), "respondidos": sorted([f"{k}:{p}" for k, p in resp])}


class FinishIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    estado: Literal["completa", "abandonada"] = "completa"


@router.post("/sessions/{code}/finish", response_model=SessionOut)
def terminar(
    code: str, body: FinishIn | None = None, session: Session = Depends(get_session)
) -> SessionOut:
    s = _sesion(session, code)
    estado = (body or FinishIn()).estado
    if s.estado != "activa":  # idempotente: no se reabre ni se cambia una sesión cerrada
        return _out(s)
    if estado == "completa":
        n_post = session.exec(
            select(func.count(QuestionnaireResponse.id)).where(
                QuestionnaireResponse.session_id == s.session_id,
                QuestionnaireResponse.kind == "post_noticia",
            )
        ).one()
        hay_final = session.exec(
            select(func.count(QuestionnaireResponse.id)).where(
                QuestionnaireResponse.session_id == s.session_id,
                QuestionnaireResponse.kind == "final",
            )
        ).one()
        if n_post < latin.N_BLOQUES or not hay_final:
            raise HTTPException(409, "faltan cuestionarios por enviar para completar la sesión")
    s.estado = estado
    s.finished_at = datetime.now(UTC)
    session.add(s)
    session.commit()
    return _out(s)


# ------------------------------------------------------------------ cuestionarios
class ResponseIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    response_id: str = Field(pattern=_UUID)
    session_id: str = Field(pattern=_UUID)
    participant_code: str
    kind: Literal["post_noticia", "final"]
    posicion: int | None = Field(default=None, ge=0, le=3)
    condition: Literal["C1", "C2", "C3", "C4"] | None = None
    news_id: int | None = None
    t_client: datetime
    answers: dict[str, str | int | float | bool | None]

    @field_validator("participant_code")
    @classmethod
    def _codigo(cls, v: str) -> str:
        return latin.normalizar_codigo(v)


class ResponsesBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    responses: list[ResponseIn] = Field(min_length=1, max_length=MAX_RESPONSES)


class ResponsesOut(BaseModel):
    recibidos: int
    nuevos: int
    duplicados: int


@router.post("/responses", response_model=ResponsesOut, status_code=201)
def enviar_respuestas(
    batch: ResponsesBatch, session: Session = Depends(get_session)
) -> ResponsesOut:
    """Lote idempotente: se valida TODO antes de guardar (un lote inválido no guarda nada)."""
    filas: list[dict[str, Any]] = []
    for r in batch.responses:
        s = session.exec(
            select(ExperimentSession).where(
                ExperimentSession.participant_code == r.participant_code
            )
        ).first()
        if not s or s.session_id != r.session_id:
            raise HTTPException(422, f"sesión desconocida para {r.participant_code}")
        cond = news = None
        if r.kind == "post_noticia":
            if r.posicion is None:
                raise HTTPException(422, "post_noticia requiere la posición del bloque")
            bloque = s.secuencia[r.posicion]
            cond, news = bloque["condicion"], bloque["news_id"]
            if (r.condition and r.condition != cond) or (r.news_id and r.news_id != news):
                raise HTTPException(
                    422,
                    f"condición o noticia no coinciden con la asignada en la posición {r.posicion}",
                )
        elif r.posicion is not None:
            raise HTTPException(422, "el cuestionario final no lleva posición")
        try:
            answers = instrumentos.validar(r.kind, dict(r.answers))
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
        filas.append(
            {
                "response_id": r.response_id,
                "session_id": r.session_id,
                "participant_code": r.participant_code,
                "kind": r.kind,
                "posicion": -1 if r.posicion is None else r.posicion,
                "condition": cond,
                "news_id": news,
                "answers": answers,
                "t_client": r.t_client,
                "received_at": datetime.now(UTC),
            }
        )
    antes = session.exec(select(func.count(QuestionnaireResponse.id))).one()
    # INSERT OR IGNORE: ignora un response_id repetido y también una segunda respuesta (otro id)
    # al mismo cuestionario de la misma sesión (restricción única session_id+kind+posicion)
    session.execute(sqlite_insert(QuestionnaireResponse).values(filas).prefix_with("OR IGNORE"))
    session.commit()
    nuevos = session.exec(select(func.count(QuestionnaireResponse.id))).one() - antes
    return ResponsesOut(recibidos=len(filas), nuevos=nuevos, duplicados=len(filas) - nuevos)


# ------------------------------------------------------------------ exportación
def _autorizar_export(token: str | None) -> None:
    """Seguro por defecto: solo con modo piloto activo o con un token de exportación configurado."""
    if hay_token_configurado():  # NA_ADMIN_TOKEN o el alias NA_EXPORT_TOKEN (16 caracteres o más)
        if not comprobar_token(token):
            raise HTTPException(403, "token de exportación inválido")
    elif not get_settings().experiment_piloto:
        raise HTTPException(
            403,
            "exportación deshabilitada: defina NA_EXPORT_TOKEN (o use la CLI: experiment export)",
        )


@router.get("/export")
def exportar(
    incluir_piloto: bool = False,
    x_export_token: str | None = Header(default=None),
    x_admin_token: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> Response:
    _autorizar_export(x_export_token or x_admin_token)
    tablas = export.construir(session, incluir_piloto=incluir_piloto)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for nombre, contenido in export.archivos(tablas).items():
            z.writestr(nombre, contenido)
    return Response(
        buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="experimento.zip"'},
    )
