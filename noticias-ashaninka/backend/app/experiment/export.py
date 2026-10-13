"""Exportación limpia del experimento (tarea 5.6): CSV / JSON / Parquet listos para el análisis.

Tablas (una fila por...):
- ``sesiones``: participante.
- ``bloques``: participante × posición (la tabla del análisis: variables de ``docs/metrics.md``).
- ``respuestas``: ítem respondido (formato largo).
- ``eventos``: evento del cliente, sin ``session_id`` ni ``user_agent`` (privacidad, 5.5).

``COLUMNAS`` es la fuente única del diccionario de datos (``data/DATA_DICTIONARY.md``, que se
genera con ``python -m app.cli experiment dictionary``): una prueba exige que cubra el 100 % de las
columnas exportadas. Implementación en Python puro (``csv`` y ``json``), sin pandas.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.db.models import ClientEvent, ExperimentSession, QuestionnaireResponse
from app.experiment import instrumentos
from app.experiment.privacy import verificar_sin_pii

Fila = dict[str, Any]
Tablas = dict[str, list[Fila]]

COVARIABLES = ("variante", "edad_rango", "alfabetizacion", "familiaridad_tec")
RANKS = tuple(f"rank_{c}" for c in ("C1", "C2", "C3", "C4"))
# Claves del payload que no salen en ``eventos`` (huella del dispositivo / texto libre del cliente)
PAYLOAD_EXCLUIDO = frozenset({"user_agent", "message"})

# (nombre, tipo, unidad, valores, descripción)
_P = (
    "participante",
    "texto",
    "—",
    "p. ej. P007",
    "Código anónimo del participante (sin datos personales)",
)
COLUMNAS: dict[str, list[tuple[str, str, str, str, str]]] = {
    "sesiones": [
        _P,
        (
            "indice",
            "entero",
            "—",
            "0, 1, 2…",
            "Índice del participante (código − 1): decide fila y rotación",
        ),
        ("fila_williams", "entero", "—", "0–3", "Fila del cuadrado de Williams 4×4 (índice mod 4)"),
        (
            "desplazamiento_noticias",
            "entero",
            "—",
            "0–3",
            "Rotación de noticias ((índice // 4) mod 4)",
        ),
        (
            "piloto",
            "booleano",
            "0/1",
            "0, 1",
            "1 = sesión de prueba con pseudo-noticias; no entra en el análisis confirmatorio",
        ),
        ("estado", "texto", "—", "activa, completa, abandonada", "Estado de la sesión"),
        (
            "consent_version",
            "texto",
            "—",
            "versión",
            "Versión del consentimiento informado aceptado",
        ),
        (
            "bloques_completados",
            "entero",
            "bloques",
            "0–4",
            "Bloques completados (fin de la noticia y cuestionario enviado)",
        ),
        (
            "variante",
            "texto",
            "—",
            "asháninka, ashéninka, alto_perene, otra, no_sabe",
            "Variante que habla (autodeclarada)",
        ),
        (
            "edad_rango",
            "texto",
            "años",
            "18-29, 30-44, 45-59, 60+",
            "Rango de edad (nunca la edad exacta)",
        ),
        (
            "alfabetizacion",
            "texto",
            "—",
            "no_lee, lee_con_dificultad, lee_bien",
            "Lectura en asháninka (autodeclarada)",
        ),
        (
            "familiaridad_tec",
            "texto",
            "—",
            "ninguna, poca, media, alta",
            "Familiaridad con el celular y las apps",
        ),
        (
            "rank_C1",
            "entero",
            "puesto",
            "1–4",
            "Puesto de preferencia de C1 (1 = la que más prefirió)",
        ),
        ("rank_C2", "entero", "puesto", "1–4", "Puesto de preferencia de C2"),
        ("rank_C3", "entero", "puesto", "1–4", "Puesto de preferencia de C3"),
        ("rank_C4", "entero", "puesto", "1–4", "Puesto de preferencia de C4"),
    ],
    "bloques": [
        _P,
        ("piloto", "booleano", "0/1", "0, 1", "1 = sesión de prueba (ver sesiones.piloto)"),
        ("posicion", "entero", "—", "0–3", "Posición del bloque en la sesión (0 = primero)"),
        (
            "condicion",
            "texto",
            "—",
            "C1, C2, C3, C4",
            "Condición: C1 texto, C2 voz, C3 voz + texto, C4 voz + texto + avatar",
        ),
        ("news_id", "entero", "—", "id de noticia", "Noticia presentada en el bloque"),
        (
            "slot_noticia",
            "entero",
            "—",
            "0–3",
            "Índice de la noticia dentro del conjunto fijo de 4",
        ),
        ("fila_williams", "entero", "—", "0–3", "Fila del cuadrado de Williams del participante"),
        (
            "bloqueados_prop",
            "decimal",
            "proporción",
            "0–1",
            "Covariable: segmentos bloqueados (sin P2d) / segmentos de la noticia",
        ),
        (
            "t_pantalla_ms",
            "entero",
            "ms",
            "≥ 0",
            "Tiempo en pantalla: de block-start a block-end (o al último evento si no hubo fin)",
        ),
        (
            "t_escucha_ms",
            "entero",
            "ms",
            "≥ 0",
            "Tiempo de audio en reproducción (sin pausas); 0 en C1",
        ),
        ("repeticiones", "entero", "conteo", "≥ 0", "Eventos repeat-paragraph del bloque"),
        ("pausas", "entero", "conteo", "≥ 0", "Eventos pause del bloque"),
        ("cambios_velocidad", "entero", "conteo", "≥ 0", "Eventos rate del bloque"),
        (
            "degradacion_avatar",
            "booleano",
            "0/1",
            "0, 1",
            "1 = el avatar se degradó (imagen fija) en un bloque C4",
        ),
        (
            "completado",
            "booleano",
            "0/1",
            "0, 1",
            "1 = terminó la noticia (block-end «completo») y envió el cuestionario",
        ),
        (
            "comprension",
            "decimal",
            "proporción",
            "0–1",
            "Aciertos de los 4 ítems de comprensión / 4",
        ),
        ("esfuerzo", "entero", "escala", "1–9", "Esfuerzo mental (Paas)"),
        ("aceptabilidad", "decimal", "escala", "1–5", "Media de facilidad, agrado y confianza"),
        ("variante", "texto", "—", "ver sesiones", "Covariable del cuestionario final"),
        ("edad_rango", "texto", "años", "ver sesiones", "Covariable del cuestionario final"),
        ("alfabetizacion", "texto", "—", "ver sesiones", "Covariable del cuestionario final"),
        ("familiaridad_tec", "texto", "—", "ver sesiones", "Covariable del cuestionario final"),
    ],
    "respuestas": [
        _P,
        (
            "cuestionario",
            "texto",
            "—",
            "post_noticia, final",
            "Cuestionario al que pertenece el ítem",
        ),
        (
            "posicion",
            "entero",
            "—",
            "0–3 o vacío",
            "Posición del bloque (vacío en el cuestionario final)",
        ),
        ("condicion", "texto", "—", "C1–C4 o vacío", "Condición del bloque (vacío en el final)"),
        ("news_id", "entero", "—", "id o vacío", "Noticia del bloque (vacío en el final)"),
        ("item", "texto", "—", "id del ítem", "Identificador del ítem (ver questionnaire.yaml)"),
        (
            "valor",
            "texto",
            "según ítem",
            "—",
            "Respuesta (número u opción; en el comentario, el texto libre)",
        ),
    ],
    "eventos": [
        _P,
        (
            "posicion",
            "entero",
            "—",
            "0–3 o vacío",
            "Bloque al que pertenece el evento (por condición y noticia)",
        ),
        ("condicion", "texto", "—", "C1–C4 o vacío", "Condición activa cuando ocurrió el evento"),
        ("news_id", "entero", "—", "id o vacío", "Noticia activa cuando ocurrió el evento"),
        ("tipo", "texto", "—", "tipos de /api/events", "Tipo de evento"),
        ("t_client", "fecha-hora", "ISO 8601", "UTC", "Instante en el dispositivo"),
        ("t_rel_ms", "entero", "ms", "≥ 0", "Milisegundos desde el primer evento del participante"),
        ("payload", "json", "—", "claves cerradas", "Datos del evento (sin user_agent ni message)"),
    ],
}


def _naive(d: datetime) -> datetime:
    return d.astimezone(UTC).replace(tzinfo=None) if d.tzinfo else d


def _ms(a: datetime, b: datetime) -> int:
    return max(0, int((_naive(b) - _naive(a)).total_seconds() * 1000))


def metricas_bloque(eventos: list[tuple[str, datetime, dict]]) -> dict[str, Any]:
    """Métricas de tiempo e interacción de un bloque a partir de sus eventos ``(tipo, t, payload)``.

    - ``t_pantalla_ms``: suma de los intervalos block-start → block-end (si falta el fin, hasta el
      último evento del bloque), así una recarga a mitad de bloque no duplica el tiempo.
    - ``t_escucha_ms``: tiempo con audio en reproducción: desde ``play`` hasta ``pause`` o hasta
      el último ``segment-end`` si el audio terminó o el bloque cerró.
    """
    ev = sorted(eventos, key=lambda e: _naive(e[1]))
    pantalla = escucha = 0
    abierto: datetime | None = None
    reproduciendo: datetime | None = None
    ultimo_fin: datetime | None = None
    ultimo_t = ev[-1][1] if ev else None

    def cerrar_audio(hasta: datetime) -> None:
        nonlocal escucha, reproduciendo
        if reproduciendo is not None:
            escucha += _ms(reproduciendo, hasta)
            reproduciendo = None

    for tipo, t, _ in ev:
        if tipo == "block-start" and abierto is None:
            abierto = t
        elif tipo == "block-end":
            if abierto is not None:
                pantalla += _ms(abierto, t)
                abierto = None
            cerrar_audio(ultimo_fin or t)
        elif tipo == "play":
            if reproduciendo is None:
                reproduciendo = t
            ultimo_fin = None
        elif tipo == "pause":
            cerrar_audio(t)
        elif tipo == "segment-end":
            ultimo_fin = t
        elif tipo == "segment-start":
            ultimo_fin = None
    if abierto is not None and ultimo_t is not None:
        pantalla += _ms(abierto, ultimo_t)
    if reproduciendo is not None:
        cerrar_audio(ultimo_fin or ultimo_t or reproduciendo)

    def n(tipo: str) -> int:
        return sum(1 for e in ev if e[0] == tipo)

    return {
        "t_pantalla_ms": pantalla,
        "t_escucha_ms": escucha,
        "repeticiones": n("repeat-paragraph"),
        "pausas": n("pause"),
        "cambios_velocidad": n("rate"),
        "degradacion_avatar": int(n("degradacion") > 0),
        "fin_completo": any(e[0] == "block-end" and e[2].get("reason") == "completo" for e in ev),
    }


def construir(session: Session, incluir_piloto: bool = False) -> Tablas:
    sesiones = session.exec(select(ExperimentSession).order_by(ExperimentSession.indice)).all()
    if not incluir_piloto:
        sesiones = [s for s in sesiones if not s.piloto]
    t_ses: list[Fila] = []
    t_blo: list[Fila] = []
    t_res: list[Fila] = []
    t_eve: list[Fila] = []
    for s in sesiones:
        resp = session.exec(
            select(QuestionnaireResponse).where(QuestionnaireResponse.session_id == s.session_id)
        ).all()
        post = {r.posicion: r for r in resp if r.kind == "post_noticia"}
        final = next((r.answers for r in resp if r.kind == "final"), {})
        cov = {c: final.get(c) for c in COVARIABLES}
        eventos = session.exec(
            select(ClientEvent)
            .where(ClientEvent.session_id == s.session_id)
            .order_by(ClientEvent.t_client)
        ).all()
        por_bloque: dict[int, list[ClientEvent]] = {b["posicion"]: [] for b in s.secuencia}
        clave = {(b["condicion"], b["news_id"]): b["posicion"] for b in s.secuencia}
        t0 = eventos[0].t_client if eventos else None
        completados = 0
        for e in eventos:
            pos = clave.get((e.condition, e.news_id))
            if pos is not None:
                por_bloque[pos].append(e)
            t_eve.append(
                {
                    "participante": s.participant_code,
                    "posicion": pos,
                    "condicion": e.condition,
                    "news_id": e.news_id,
                    "tipo": e.type,
                    "t_client": _naive(e.t_client).isoformat(timespec="milliseconds") + "Z",
                    "t_rel_ms": _ms(t0, e.t_client) if t0 else 0,
                    "payload": json.dumps(
                        {k: v for k, v in e.payload.items() if k not in PAYLOAD_EXCLUIDO},
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                }
            )
        for b in s.secuencia:
            pos = b["posicion"]
            m = metricas_bloque([(e.type, e.t_client, e.payload) for e in por_bloque[pos]])
            r = post.get(pos)
            comp = esf = acep = None
            if r:
                comp = instrumentos.comprension(r.answers)
                esf = r.answers["esfuerzo"]
                acep = round(instrumentos.aceptabilidad(r.answers), 4)
            completado = int(bool(r) and m["fin_completo"])
            completados += completado
            t_blo.append(
                {
                    "participante": s.participant_code,
                    "piloto": int(s.piloto),
                    "posicion": pos,
                    "condicion": b["condicion"],
                    "news_id": b["news_id"],
                    "slot_noticia": b["slot_noticia"],
                    "fila_williams": s.indice % 4,
                    "bloqueados_prop": b["bloqueados_prop"],
                    **{
                        k: m[k]
                        for k in (
                            "t_pantalla_ms",
                            "t_escucha_ms",
                            "repeticiones",
                            "pausas",
                            "cambios_velocidad",
                            "degradacion_avatar",
                        )
                    },
                    "completado": completado,
                    "comprension": comp,
                    "esfuerzo": esf,
                    "aceptabilidad": acep,
                    **cov,
                }
            )
        for r in sorted(resp, key=lambda x: (x.kind, x.posicion)):
            for item, valor in r.answers.items():
                t_res.append(
                    {
                        "participante": s.participant_code,
                        "cuestionario": r.kind,
                        "posicion": None if r.posicion < 0 else r.posicion,
                        "condicion": r.condition,
                        "news_id": r.news_id,
                        "item": item,
                        "valor": valor,
                    }
                )
        t_ses.append(
            {
                "participante": s.participant_code,
                "indice": s.indice,
                "fila_williams": s.indice % 4,
                "desplazamiento_noticias": (s.indice // 4) % 4,
                "piloto": int(s.piloto),
                "estado": s.estado,
                "consent_version": s.consent_version,
                "bloques_completados": completados,
                **cov,
                **{k: final.get(k) for k in RANKS},
            }
        )
    return {"sesiones": t_ses, "bloques": t_blo, "respuestas": t_res, "eventos": t_eve}


def columnas(tabla: str) -> list[str]:
    return [c[0] for c in COLUMNAS[tabla]]


def a_csv(tabla: str, filas: list[Fila]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=columnas(tabla), extrasaction="raise", lineterminator="\n")
    w.writeheader()
    for f in filas:
        w.writerow({k: ("" if v is None else v) for k, v in f.items()})
    return buf.getvalue()


def archivos(tablas: Tablas, formatos: tuple[str, ...] = ("csv", "json")) -> dict[str, bytes]:
    """Archivos de la exportación (nombre -> bytes), incluido ``manifest.json``.

    Verifica la privacidad antes de devolver nada: si encuentra un identificador, falla.
    """
    problemas = verificar_sin_pii(tablas)
    if problemas:
        raise ValueError("la exportación contiene datos personales: " + "; ".join(problemas[:5]))
    out: dict[str, bytes] = {}
    for tabla, filas in tablas.items():
        if "csv" in formatos:
            out[f"{tabla}.csv"] = a_csv(tabla, filas).encode("utf-8")
        if "json" in formatos:
            out[f"{tabla}.json"] = json.dumps(filas, ensure_ascii=False, indent=1).encode("utf-8")
        if "parquet" in formatos:
            datos = _parquet(filas, columnas(tabla))
            if datos is not None:
                out[f"{tabla}.parquet"] = datos
    manifest = {
        "generado": datetime.now(UTC).isoformat(timespec="seconds"),
        "filas": {t: len(f) for t, f in tablas.items()},
        "incluye_piloto": any(f.get("piloto") for f in tablas["sesiones"]),
        "columnas": {t: columnas(t) for t in tablas},
        "sha256": {n: hashlib.sha256(b).hexdigest() for n, b in sorted(out.items())},
    }
    out["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=1).encode("utf-8")
    return out


def _parquet(filas: list[Fila], cols: list[str]) -> bytes | None:
    """Parquet solo si ``pyarrow`` está instalado (grupo ``eval``); si no, se omite."""
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError:
        print("[export] pyarrow no está instalado: se omite el Parquet (uv sync --group eval)")
        return None
    tabla = pa.table(
        {
            c: [
                ("" if f.get(c) is None else str(f.get(c)))
                if c in {"valor", "payload"}
                else f.get(c)
                for f in filas
            ]
            for c in cols
        }
    )
    buf = io.BytesIO()
    pq.write_table(tabla, buf)
    return buf.getvalue()


def escribir(session: Session, out: Path, formatos: tuple[str, ...], incluir_piloto: bool) -> dict:
    tablas = construir(session, incluir_piloto=incluir_piloto)
    out.mkdir(parents=True, exist_ok=True)
    for nombre, datos in archivos(tablas, formatos).items():
        (out / nombre).write_bytes(datos)
    return {t: len(f) for t, f in tablas.items()}


def diccionario_md() -> str:
    """Texto de ``data/DATA_DICTIONARY.md`` (generado desde ``COLUMNAS`` y el cuestionario)."""
    L = [
        "# Diccionario de datos de la exportación del experimento (Fase 5)",
        "",
        "> **Archivo generado** por `uv run python -m app.cli experiment dictionary` a partir de",
        "> `backend/app/experiment/export.py` (`COLUMNAS`). No lo edite a mano.",
        "",
        "Todas las tablas se exportan en CSV (UTF-8, separador coma, vacío = sin dato) y JSON, y en",
        "Parquet si `pyarrow` está instalado. El único identificador es el **código anónimo** del",
        "participante (`participante`); no se exportan nombres, documentos, teléfonos, geolocalización,",
        "edad exacta ni el identificador del dispositivo.",
        "",
    ]
    desc = {
        "sesiones": "una fila por participante",
        "bloques": "una fila por participante × posición (tabla del análisis)",
        "respuestas": "una fila por ítem respondido (formato largo)",
        "eventos": "una fila por evento del cliente",
    }
    for tabla, cols in COLUMNAS.items():
        L += [
            f"## `{tabla}.csv`: {desc[tabla]}",
            "",
            "| Variable | Tipo | Unidad | Valores | Descripción |",
            "|---|---|---|---|---|",
        ]
        for nombre, tipo, unidad, valores, d in cols:
            L.append(f"| `{nombre}` | {tipo} | {unidad} | {valores} | {d} |")
        L.append("")
    L += [
        "## Ítems de los cuestionarios (`respuestas.item`)",
        "",
        "| Cuestionario | Ítem | Tipo | Rango u opciones | Estado |",
        "|---|---|---|---|---|",
    ]
    for kind in instrumentos.KINDS:
        for it in instrumentos.items(kind):
            rango = (
                f"{it['min']}–{it['max']}"
                if "min" in it
                else ", ".join(map(str, it["opciones"]))
                if "opciones" in it
                else "0/1"
                if it["tipo"] == "binario"
                else f"texto ≤ {it['max']}"
            )
            L.append(f"| {kind} | `{it['id']}` | {it['tipo']} | {rango} | {it['status']} |")
    L.append("")
    return "\n".join(L)
