"""Simulación sintética de participantes por la API REAL (sin atajos a la base de datos).

Cada participante sintético (``eval.fase5.modelo.generar``) hace lo mismo que la PWA: crea su
sesión con consentimiento, envía los eventos de cada bloque con su ``condition`` y ``news_id``,
responde los cuestionarios y cierra la sesión (o abandona). Cada lote se REENVÍA una vez para
comprobar la idempotencia. Al final se exporta con el mismo código que usa el servidor.

Los datos quedan marcados como **piloto** (modo ``NA_EXPERIMENT_PILOTO``) y NO son datos reales.

Uso: uv run python -m eval.fase5.simulate [--n 32] [--out eval/fase5/out/export]
"""

from __future__ import annotations

import argparse
import os
import random
import shutil
import tempfile
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.experiment import export
from fastapi.testclient import TestClient
from sqlmodel import Session

from eval.fase5.material import crear_noticias
from eval.fase5.modelo import PARAMETROS, SEMILLA, generar

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "eval" / "fase5" / "out"
T0 = datetime(2026, 10, 12, 9, 0, 0, tzinfo=UTC)


def _ev(dev: str, tipo: str, cond: str | None, news: int | None, t: datetime, **payload) -> dict:
    return {
        "event_id": str(uuid.uuid4()),
        "session_id": dev,
        "condition": cond,
        "news_id": news,
        "type": tipo,
        "t_client": t.isoformat(),
        "payload": payload,
    }


def eventos_bloque(
    dev: str, b: dict, news: int, t: datetime
) -> tuple[list[dict], datetime, int, int]:
    """Eventos de un bloque, su instante final y los tiempos REALES (escucha y pantalla, en ms)."""
    c, k = b["condicion"], b["posicion"]
    inicio = t
    ev = [_ev(dev, "block-start", c, news, t, posicion=k)]
    escucha_ms = 0
    if c == "C1":
        t += timedelta(seconds=b["t_total_s"])
        ev.append(_ev(dev, "read-done", c, news, t))
    else:
        trozos = b["pausas"] + 1
        dur = b["t_total_s"] / trozos
        t += timedelta(seconds=1)
        for j in range(trozos):
            ev.append(_ev(dev, "play", c, news, t))
            ev.append(_ev(dev, "segment-start", c, news, t, idx=j))
            t += timedelta(seconds=dur)
            escucha_ms += round(dur * 1000)
            if j < trozos - 1:
                ev.append(_ev(dev, "pause", c, news, t))
                t += timedelta(seconds=5)  # pausa del participante: no cuenta como escucha
            else:
                ev.append(_ev(dev, "segment-end", c, news, t, idx=j))
        for r in range(b["repeticiones"]):
            ev.append(_ev(dev, "repeat-paragraph", c, news, t, paragraph=r))
        for _ in range(b["cambios_velocidad"]):
            ev.append(_ev(dev, "rate", c, news, t, rate=1.25))
    if b["degradacion"]:
        ev.append(_ev(dev, "degradacion", c, news, t, reason="fps-bajos", fps=14.0))
    t += timedelta(seconds=1)
    ev.append(_ev(dev, "block-end", c, news, t, posicion=k, reason="completo"))
    return ev, t, escucha_ms, round((t - inicio).total_seconds() * 1000)


def _post(client: TestClient, url: str, cuerpo: dict, clave: str):
    """Envía el lote y lo reenvía: el segundo envío no debe crear nada (idempotencia)."""
    r1 = client.post(url, json=cuerpo)
    assert r1.status_code == 201, (url, r1.status_code, r1.text[:300])
    r2 = client.post(url, json=cuerpo)
    assert r2.status_code == 201, (url, r2.status_code, r2.text[:300])
    return r1.json(), r2.json(), len(cuerpo[clave])


_ENV = (
    "NA_DATABASE_URL",
    "NA_STATIC_DIR",
    "NA_TTS_ENGINE",
    "NA_EXPERIMENT_PILOTO",
    "NA_EXPORT_TOKEN",
)


def simular(
    n: int = 32, seed: int = SEMILLA, params: dict = PARAMETROS, out: Path | None = None
) -> dict:
    """Ejecuta la simulación completa y devuelve el resumen (conteos e idempotencia).

    Usa una base de datos temporal y deja el entorno del proceso como lo encontró.
    """
    previos = {k: os.environ.get(k) for k in _ENV}
    try:
        return _simular(n, seed, params, out)
    finally:
        for k, v in previos.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        from app.db.session import get_engine

        get_engine.cache_clear()


def _simular(n: int, seed: int, params: dict, out: Path | None) -> dict:
    out = out or OUT / "export"
    trabajo = Path(tempfile.mkdtemp(prefix="na-sim-"))
    os.environ["NA_DATABASE_URL"] = f"sqlite:///{(trabajo / 'sim.db').as_posix()}"
    os.environ["NA_STATIC_DIR"] = str(trabajo / "static")
    os.environ["NA_TTS_ENGINE"] = "fake"
    os.environ["NA_EXPERIMENT_PILOTO"] = "true"
    os.environ.pop("NA_EXPORT_TOKEN", None)

    from app.db.session import get_engine, init_db
    from app.main import app

    get_engine.cache_clear()
    engine = get_engine()
    init_db(engine)
    news_ids = crear_noticias(engine, 4)
    rng = random.Random(seed)
    participantes = generar(n, seed, params)
    resumen = {
        "n_participantes": n,
        "semilla": seed,
        "sesiones_creadas": 0,
        "sesiones_completas": 0,
        "sesiones_abandonadas": 0,
        "eventos_enviados": 0,
        "eventos_nuevos_en_reenvio": 0,
        "respuestas_enviadas": 0,
        "respuestas_nuevas_en_reenvio": 0,
        "sesion_repetida_idempotente": True,
        "tiempos_reales": {},  # "P001:0" -> [escucha_ms, pantalla_ms]: la verdad de la simulación
    }
    with TestClient(app) as client:
        for i, p in enumerate(participantes):
            dev = str(uuid.UUID(int=rng.getrandbits(128)))
            cuerpo = {
                "participant_code": p["codigo"],
                "session_id": dev,
                "consent": True,
                "consent_version": "PENDIENTE-COMITE-ETICA-v0",
            }
            r = client.post("/api/experiment/sessions", json=cuerpo)
            assert r.status_code == 201, r.text
            resumen["sesiones_creadas"] += 1
            bloques_srv = r.json()["bloques"]
            # crear la misma sesión otra vez devuelve la misma asignación y no duplica nada
            r2 = client.post("/api/experiment/sessions", json=cuerpo)
            resumen["sesion_repetida_idempotente"] &= (
                r2.status_code == 200 and r2.json() == r.json()
            )

            t = T0 + timedelta(hours=2 * i)
            eventos = [_ev(dev, "consent", None, None, t, participant=p["codigo"])]
            respuestas = []
            for b in p["bloques"]:
                srv = bloques_srv[b["posicion"]]
                assert srv["condicion"] == b["condicion"], (
                    "la asignación del servidor no es la esperada"
                )
                assert srv["news_id"] == news_ids[b["slot_noticia"]]
                ev, t, escucha, pantalla = eventos_bloque(
                    dev, b, srv["news_id"], t + timedelta(seconds=5)
                )
                eventos += ev
                resumen["tiempos_reales"][f"{p['codigo']}:{b['posicion']}"] = [escucha, pantalla]
                respuestas.append(
                    {
                        "response_id": str(uuid.uuid4()),
                        "session_id": dev,
                        "participant_code": p["codigo"],
                        "kind": "post_noticia",
                        "posicion": b["posicion"],
                        "condition": b["condicion"],
                        "news_id": srv["news_id"],
                        "t_client": t.isoformat(),
                        "answers": {
                            **{f"comp_{k + 1}": v for k, v in enumerate(b["comp"])},
                            "esfuerzo": b["esfuerzo"],
                            "acep_facilidad": b["acep"][0],
                            "acep_agrado": b["acep"][1],
                            "acep_confianza": b["acep"][2],
                        },
                    }
                )
            if p["final"]:
                respuestas.append(
                    {
                        "response_id": str(uuid.uuid4()),
                        "session_id": dev,
                        "participant_code": p["codigo"],
                        "kind": "final",
                        "posicion": None,
                        "t_client": (t + timedelta(seconds=30)).isoformat(),
                        "answers": p["final"],
                    }
                )
                eventos.append(
                    _ev(dev, "session-finish", None, None, t + timedelta(seconds=40), blocks=4)
                )
            else:
                eventos.append(
                    _ev(
                        dev,
                        "abandon",
                        None,
                        None,
                        t + timedelta(seconds=40),
                        posicion=len(p["bloques"]),
                    )
                )
            for lote in (eventos[i : i + 400] for i in range(0, len(eventos), 400)):
                a, b2, tam = _post(client, "/api/events", {"events": lote}, "events")
                resumen["eventos_enviados"] += tam
                resumen["eventos_nuevos_en_reenvio"] += b2["nuevos"]
                assert a["nuevos"] == tam
            for lote in (respuestas[j : j + 5] for j in range(0, len(respuestas), 5)):
                a, b2, tam = _post(
                    client, "/api/experiment/responses", {"responses": lote}, "responses"
                )
                resumen["respuestas_enviadas"] += tam
                resumen["respuestas_nuevas_en_reenvio"] += b2["nuevos"]
                assert a["nuevos"] == tam
            estado = "completa" if p["final"] else "abandonada"
            fin = client.post(
                f"/api/experiment/sessions/{p['codigo']}/finish", json={"estado": estado}
            )
            assert fin.status_code == 200, fin.text
            resumen["sesiones_completas" if estado == "completa" else "sesiones_abandonadas"] += 1

    with Session(engine) as s:
        resumen["filas"] = export.escribir(s, out, ("csv", "json", "parquet"), incluir_piloto=True)
    resumen["carpeta"] = str(out)
    engine.dispose()
    shutil.rmtree(trabajo, ignore_errors=True)
    return resumen


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=32)
    ap.add_argument("--seed", type=int, default=SEMILLA)
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()
    r = simular(a.n, a.seed, out=a.out)
    r.pop("tiempos_reales")
    print(r)


if __name__ == "__main__":
    main()
