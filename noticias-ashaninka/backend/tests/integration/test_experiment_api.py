"""API del experimento (Fase 5): sesiones, cuestionarios idempotentes, privacidad y exportación."""

import csv
import io
import json
import uuid
import zipfile
from datetime import UTC, datetime, timedelta

import pytest
from app.experiment import export, latin
from fastapi.testclient import TestClient

from eval.fase5.material import crear_noticias

COMPLETA = dict(
    comp_1=1,
    comp_2=0,
    comp_3=1,
    comp_4=1,
    esfuerzo=5,
    acep_facilidad=4,
    acep_agrado=3,
    acep_confianza=5,
)
FINAL = dict(
    variante="otra",
    edad_rango="30-44",
    alfabetizacion="lee_bien",
    familiaridad_tec="media",
    rank_C1=4,
    rank_C2=3,
    rank_C3=1,
    rank_C4=2,
)


@pytest.fixture
def env(temp_db, monkeypatch):
    monkeypatch.setenv("NA_TTS_ENGINE", "fake")
    monkeypatch.delenv("NA_EXPERIMENT_PILOTO", raising=False)
    monkeypatch.delenv("NA_EXPORT_TOKEN", raising=False)
    monkeypatch.delenv("NA_ADMIN_TOKEN", raising=False)  # el modo piloto abre la exportación
    from app.main import app

    with TestClient(app) as client:
        yield client, temp_db


def _sesion(client, code="P001", dev=None, consent=True):
    dev = dev or str(uuid.uuid4())
    r = client.post(
        "/api/experiment/sessions",
        json={
            "participant_code": code,
            "session_id": dev,
            "consent": consent,
            "consent_version": "PENDIENTE-COMITE-ETICA-v0",
        },
    )
    return r, dev


def _resp(dev, code, kind, posicion=None, answers=None, **kw):
    return {
        "response_id": str(uuid.uuid4()),
        "session_id": dev,
        "participant_code": code,
        "kind": kind,
        "posicion": posicion,
        "t_client": datetime.now(UTC).isoformat(),
        "answers": answers
        if answers is not None
        else (COMPLETA if kind == "post_noticia" else FINAL),
        **kw,
    }


def _evento(dev, tipo, cond, news, t, **payload):
    return {
        "event_id": str(uuid.uuid4()),
        "session_id": dev,
        "condition": cond,
        "news_id": news,
        "type": tipo,
        "t_client": t.isoformat(),
        "payload": payload,
    }


def test_config_expone_instrumentos_sin_castellano_de_noticias(env):
    client, _ = env
    c = client.get("/api/experiment/config").json()
    assert c["piloto"] is False and c["condiciones"] == ["C1", "C2", "C3", "C4"]
    assert len(c["post_noticia"]) == 8 and len(c["final"]) == 9
    assert c["consent_status"] == "PENDIENTE-COMITE-ETICA"


def test_sin_noticias_aptas_no_se_puede_iniciar(env):
    client, engine = env
    crear_noticias(engine, 4, revisada=False)  # sin revisión de un hablante
    r, _ = _sesion(client)
    assert r.status_code == 409 and "aptas" in r.json()["detail"]


def test_pseudo_noticias_del_corpus_solo_en_modo_piloto(env, monkeypatch):
    client, engine = env
    crear_noticias(engine, 4, revisada=True, tipo="corpus_americasnlp")
    assert _sesion(client)[0].status_code == 409
    monkeypatch.setenv("NA_EXPERIMENT_PILOTO", "true")
    r, _ = _sesion(client)
    assert r.status_code == 201 and r.json()["piloto"] is True


def test_consentimiento_y_codigo_obligatorios(env):
    client, engine = env
    crear_noticias(engine)
    assert _sesion(client, consent=False)[0].status_code == 422
    for malo in ["Juan Perez", "123", "juan@x.com"]:
        assert _sesion(client, code=malo)[0].status_code == 422


def test_sesion_asigna_williams_y_es_idempotente(env):
    client, engine = env
    ids = crear_noticias(engine)
    r, dev = _sesion(client, "P007")
    assert r.status_code == 201
    j = r.json()
    esperado = latin.secuencia(6)
    assert [b["condicion"] for b in j["bloques"]] == [b.condicion for b in esperado]
    assert [b["news_id"] for b in j["bloques"]] == [ids[b.slot_noticia] for b in esperado]
    r2, _ = _sesion(client, "p-007", dev=dev)  # mismo código y dispositivo: misma asignación
    assert r2.status_code == 200 and r2.json() == j
    assert _sesion(client, "P007")[0].status_code == 409  # otro dispositivo, mismo código


def test_prefiere_noticias_sin_bloqueados_y_marca_la_covariable(env):
    client, engine = env
    crear_noticias(engine, 5, bloqueadas=(0,))  # la primera tiene un segmento bloqueado
    j = _sesion(client)[0].json()
    assert all(b["bloqueados_prop"] == 0 for b in j["bloques"])
    assert 1 not in {b["news_id"] for b in j["bloques"]}


def test_completa_con_noticias_con_bloqueados_y_las_marca(env):
    client, engine = env
    crear_noticias(engine, 4, bloqueadas=(0, 1))
    props = sorted(b["bloqueados_prop"] for b in _sesion(client)[0].json()["bloques"])
    assert props == [0, 0, pytest.approx(1 / 3, abs=1e-3), pytest.approx(1 / 3, abs=1e-3)]


def test_respuestas_idempotentes_y_validadas(env):
    client, engine = env
    crear_noticias(engine)
    _, dev = _sesion(client, "P001")
    r0 = _resp(dev, "P001", "post_noticia", 0)
    ok = client.post("/api/experiment/responses", json={"responses": [r0]})
    assert ok.status_code == 201 and ok.json()["nuevos"] == 1
    again = client.post("/api/experiment/responses", json={"responses": [r0]}).json()
    assert (again["nuevos"], again["duplicados"]) == (0, 1)
    # otra respuesta (otro id) al mismo cuestionario: no se duplica
    otra = client.post(
        "/api/experiment/responses", json={"responses": [_resp(dev, "P001", "post_noticia", 0)]}
    ).json()
    assert otra["nuevos"] == 0

    def malo(**kw):
        return client.post(
            "/api/experiment/responses", json={"responses": [_resp(dev, "P001", **kw)]}
        ).status_code

    assert malo(kind="post_noticia", posicion=1, answers={**COMPLETA, "esfuerzo": 11}) == 422
    assert malo(kind="post_noticia", posicion=None) == 422
    assert malo(kind="final", posicion=2) == 422
    assert malo(kind="post_noticia", posicion=1, condition="C4") in (201, 422)
    assert malo(kind="final", answers={**FINAL, "comentario": "llama a 987654321"}) == 422
    assert malo(kind="post_noticia", posicion=2, news_id=9999) == 422
    # sesión desconocida o dispositivo distinto
    assert (
        client.post(
            "/api/experiment/responses",
            json={"responses": [_resp(str(uuid.uuid4()), "P001", "final")]},
        ).status_code
        == 422
    )


def test_un_lote_invalido_no_guarda_nada(env):
    client, engine = env
    crear_noticias(engine)
    _, dev = _sesion(client)
    lote = [
        _resp(dev, "P001", "post_noticia", 0),
        _resp(dev, "P001", "post_noticia", 1, answers={**COMPLETA, "esfuerzo": 0}),
    ]
    assert client.post("/api/experiment/responses", json={"responses": lote}).status_code == 422
    assert client.get("/api/experiment/sessions/P001").json()["respondidos"] == []


def test_condicion_incoherente_con_la_asignada_se_rechaza(env):
    client, engine = env
    crear_noticias(engine)
    r, dev = _sesion(client)
    b0 = r.json()["bloques"][0]
    mala = next(c for c in latin.CONDICIONES if c != b0["condicion"])
    code = client.post(
        "/api/experiment/responses",
        json={"responses": [_resp(dev, "P001", "post_noticia", 0, condition=mala)]},
    ).status_code
    assert code == 422
    assert (
        client.post(
            "/api/experiment/responses",
            json={
                "responses": [
                    _resp(
                        dev,
                        "P001",
                        "post_noticia",
                        0,
                        condition=b0["condicion"],
                        news_id=b0["news_id"],
                    )
                ]
            },
        ).status_code
        == 201
    )


def test_finalizar_exige_los_5_cuestionarios_y_es_idempotente(env):
    client, engine = env
    crear_noticias(engine)
    _, dev = _sesion(client)
    assert client.post("/api/experiment/sessions/P001/finish").status_code == 409
    lote = [_resp(dev, "P001", "post_noticia", k) for k in range(4)] + [_resp(dev, "P001", "final")]
    assert client.post("/api/experiment/responses", json={"responses": lote}).json()["nuevos"] == 5
    assert client.post("/api/experiment/sessions/P001/finish").json()["estado"] == "completa"
    assert client.post("/api/experiment/sessions/P001/finish").json()["estado"] == "completa"
    assert client.post("/api/experiment/sessions/P404/finish").status_code == 404


def test_abandonar_no_exige_cuestionarios(env):
    client, engine = env
    crear_noticias(engine)
    _sesion(client)
    r = client.post("/api/experiment/sessions/P001/finish", json={"estado": "abandonada"})
    assert r.json()["estado"] == "abandonada"


def test_eventos_nuevos_se_aceptan_y_los_desconocidos_no(env):
    client, _ = env
    t = datetime.now(UTC)
    dev = str(uuid.uuid4())
    ok = [_evento(dev, "block-start", "C2", 1, t, posicion=0, participant="P001")]
    assert client.post("/api/events", json={"events": ok}).status_code == 201
    mal = [_evento(dev, "block-start", "C2", 1, t, nombre="Juan")]
    assert client.post("/api/events", json={"events": mal}).status_code == 422


def _sesion_completa(client, dev, code, ids):
    """Reproduce lo que haría la PWA: eventos reales del bloque + cuestionarios."""
    j = client.get(f"/api/experiment/sessions/{code}").json()
    t = datetime.now(UTC)
    eventos = [_evento(dev, "consent", None, None, t, participant=code)]
    for b in j["bloques"]:
        c, n, k = b["condicion"], b["news_id"], b["posicion"]
        eventos += [_evento(dev, "block-start", c, n, t, posicion=k)]
        if c != "C1":
            eventos += [
                _evento(dev, "play", c, n, t + timedelta(seconds=1)),
                _evento(dev, "segment-start", c, n, t + timedelta(seconds=1), idx=0),
                _evento(dev, "segment-end", c, n, t + timedelta(seconds=11), idx=0),
                _evento(dev, "pause", c, n, t + timedelta(seconds=12)),
            ]
        eventos += [
            _evento(
                dev, "block-end", c, n, t + timedelta(seconds=20), posicion=k, reason="completo"
            )
        ]
        t += timedelta(seconds=60)
    assert client.post("/api/events", json={"events": eventos}).status_code == 201
    lote = [_resp(dev, code, "post_noticia", k) for k in range(4)] + [_resp(dev, code, "final")]
    assert client.post("/api/experiment/responses", json={"responses": lote}).status_code == 201


def test_exportacion_completa_y_privada(env, monkeypatch):
    client, engine = env
    ids = crear_noticias(engine)
    monkeypatch.setenv("NA_EXPERIMENT_PILOTO", "true")
    for i in range(1, 5):
        code = f"P00{i}"
        _, dev = _sesion(client, code)
        _sesion_completa(client, dev, code, ids)
    r = client.get("/api/experiment/export?incluir_piloto=true")
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    z = zipfile.ZipFile(io.BytesIO(r.content))
    assert {
        "sesiones.csv",
        "bloques.csv",
        "respuestas.csv",
        "eventos.csv",
        "manifest.json",
        "bloques.json",
    } <= set(z.namelist())
    bloques = list(csv.DictReader(io.StringIO(z.read("bloques.csv").decode())))
    assert len(bloques) == 16 and list(bloques[0]) == export.columnas("bloques")
    # las 4 condiciones aparecen 4 veces y en cada posición una sola vez por fila de Williams
    assert {c: sum(b["condicion"] == c for b in bloques) for c in latin.CONDICIONES} == {
        c: 4 for c in latin.CONDICIONES
    }
    assert all(b["completado"] == "1" and b["comprension"] == "0.75" for b in bloques)
    c1 = [b for b in bloques if b["condicion"] == "C1"]
    assert all(b["t_escucha_ms"] == "0" for b in c1)
    c2 = [b for b in bloques if b["condicion"] == "C2"]
    assert all(b["t_escucha_ms"] == "11000" and b["t_pantalla_ms"] == "20000" for b in c2)
    ses = list(csv.DictReader(io.StringIO(z.read("sesiones.csv").decode())))
    assert [s["bloques_completados"] for s in ses] == ["4"] * 4 and ses[0]["variante"] == "otra"
    ev = z.read("eventos.csv").decode()
    assert "session_id" not in ev.splitlines()[0] and "user_agent" not in ev
    man = json.loads(z.read("manifest.json"))
    assert man["incluye_piloto"] is True and man["filas"]["bloques"] == 16


def test_exportacion_excluye_el_piloto_por_defecto(env, monkeypatch):
    client, engine = env
    crear_noticias(engine)
    monkeypatch.setenv("NA_EXPERIMENT_PILOTO", "true")
    _sesion(client)
    z = zipfile.ZipFile(io.BytesIO(client.get("/api/experiment/export").content))
    assert json.loads(z.read("manifest.json"))["filas"]["sesiones"] == 0


def test_exportacion_cerrada_por_defecto_y_con_token(env, monkeypatch):
    client, _ = env
    assert client.get("/api/experiment/export").status_code == 403  # modo real sin token
    monkeypatch.setenv("NA_EXPORT_TOKEN", "secreto-de-exportacion-0123")
    assert client.get("/api/experiment/export").status_code == 403
    assert (
        client.get(
            "/api/experiment/export", headers={"x-export-token": "secreto-de-exportacion-0123"}
        ).status_code
        == 200
    )


def test_exportacion_rechaza_datos_personales(env, monkeypatch):
    client, engine = env
    crear_noticias(engine)
    monkeypatch.setenv("NA_EXPERIMENT_PILOTO", "true")
    _, dev = _sesion(client)
    from app.db.models import QuestionnaireResponse
    from sqlmodel import Session, select

    ok = _resp(dev, "P001", "final")
    client.post("/api/experiment/responses", json={"responses": [ok]})
    with Session(engine) as s:  # un dato personal que se colara por otra vía
        r = s.exec(select(QuestionnaireResponse)).one()
        r.answers = {**r.answers, "comentario": "mi correo es ana@correo.com"}
        s.add(r)
        s.commit()
        with pytest.raises(ValueError, match="datos personales"):
            export.archivos(export.construir(s, incluir_piloto=True))


def test_cli_exporta_y_genera_diccionario(env, monkeypatch, tmp_path):
    client, engine = env
    crear_noticias(engine)
    monkeypatch.setenv("NA_EXPERIMENT_PILOTO", "true")
    _sesion(client)
    from app.cli import main

    assert main(["experiment", "export", "--out", str(tmp_path / "x"), "--incluir-piloto"]) == 0
    assert (tmp_path / "x" / "sesiones.csv").exists()
    assert main(["experiment", "dictionary", "--out", str(tmp_path / "d.md")]) == 0
    assert "bloqueados_prop" in (tmp_path / "d.md").read_text(encoding="utf-8")
