"""API de la PWA (Fase 4): catálogo, detalle sin castellano, eventos idempotentes y privacidad."""

import uuid
from datetime import UTC, datetime

import pytest
from app.db.models import News, Provenance
from conftest import ADMIN
from fastapi.testclient import TestClient
from sqlmodel import Session

BODY = "Okantzi kemetsa. Tzimatsi kitaiteri.\nIrotake Pablo Lima."


@pytest.fixture
def env(temp_db, tmp_path, monkeypatch):
    from app.api import synthesize as api_synth
    from app.pipeline.tts import registry

    monkeypatch.setenv("NA_TTS_ENGINE", "fake")
    monkeypatch.setenv("NA_STATIC_DIR", str(tmp_path / "static"))
    registry.reset_pools()
    api_synth.reset_synthesizers()
    from app.main import app

    with TestClient(app, headers=ADMIN) as client:
        yield client, temp_db, tmp_path / "static"
    registry.reset_pools()
    api_synth.reset_synthesizers()


def _news(engine, titulo="t", es="SECRETO EN CASTELLANO") -> int:
    with Session(engine) as s:
        n = News(titulo_cni=titulo, cuerpo_cni=BODY, titulo_es=es, cuerpo_es=es)
        n.provenance = Provenance(tipo="traduccion_automatica")
        s.add(n)
        s.commit()
        return n.id


def _ev(**kw) -> dict:
    base = {
        "event_id": str(uuid.uuid4()),
        "session_id": str(uuid.uuid4()),
        "condition": "C3",
        "news_id": 1,
        "type": "play",
        "t_client": datetime.now(UTC).isoformat(),
        "payload": {},
    }
    base.update(kw)
    return base


def test_catalog_list_and_detail_never_expose_spanish(env):
    client, engine, _ = env
    nid = _news(engine)
    lst = client.get("/api/catalog").json()
    assert [i["id"] for i in lst] == [nid]
    assert lst[0]["manifest_url"] is None and lst[0]["apta_experimento"] is False
    assert "SECRETO" not in client.get("/api/catalog").text
    client.post(f"/api/news/{nid}/process")
    det = client.get(f"/api/catalog/{nid}")
    assert det.status_code == 200 and "SECRETO" not in det.text
    pars = det.json()["parrafos"]
    assert len(pars) == 2 and pars[0][0]["text_orig"].startswith("Okantzi")
    assert det.json()["avisos"]["synthetic_voice"]


def test_catalog_detail_without_processing_falls_back_to_body(env):
    client, engine, _ = env
    nid = _news(engine)
    pars = client.get(f"/api/catalog/{nid}").json()["parrafos"]
    assert [p[0]["text_orig"] for p in pars] == [
        "Okantzi kemetsa. Tzimatsi kitaiteri.",
        "Irotake Pablo Lima.",
    ]
    assert all(not p[0]["tts_ready"] for p in pars)


def test_catalog_404_and_manifest_url_after_batch(env):
    client, engine, _ = env
    assert client.get("/api/catalog/999").status_code == 404
    nid = _news(engine)
    from app.batch.service import run_batch

    run_batch()
    item = client.get("/api/catalog").json()[0]
    assert item["manifest_url"] == f"/static/news/{nid}/manifest.json"
    manifest = client.get(item["manifest_url"]).json()
    assert manifest["segments_with_audio"] >= 2  # la suma no debe saturar en 1 (columna booleana)
    assert item["segmentos_con_audio"] == manifest["segments_with_audio"]
    assert item["segmentos_bloqueados"] == manifest["segments_blocked"]
    assert item["duracion_s"] == manifest["total_duration_s"]
    assert client.get("/api/catalog?solo_con_audio=true").json()
    assert client.get(item["manifest_url"]).status_code == 200


def test_static_audio_supports_range(env):
    client, engine, _ = env
    _news(engine)
    from app.batch.service import run_batch

    run_batch()
    man = client.get("/static/news/1/manifest.json").json()
    url = next(s["audio"]["opus"] for s in man["segments"] if s["audio"])
    r = client.get(url, headers={"Range": "bytes=0-9"})
    assert r.status_code == 206 and len(r.content) == 10


def test_events_idempotent_and_summary(env):
    client, _, _ = env
    batch = {"events": [_ev(), _ev(type="pause", payload={"position_s": 1.5})]}
    r = client.post("/api/events", json=batch)
    assert r.status_code == 201 and r.json() == {"recibidos": 2, "nuevos": 2, "duplicados": 0}
    again = client.post("/api/events", json=batch).json()
    assert again == {"recibidos": 2, "nuevos": 0, "duplicados": 2}
    s = client.get("/api/events/summary").json()
    assert s["total"] == 2 and s["por_condicion"] == {"C3": 2} and s["sesiones"] == 2


def test_events_validation_and_privacy(env):
    client, _, _ = env
    post = lambda ev: client.post("/api/events", json={"events": [ev]}).status_code  # noqa: E731
    assert post(_ev(type="inventado")) == 422
    assert post(_ev(condition="C9")) == 422
    assert post(_ev(event_id="no es uuid")) == 422
    assert post(_ev(payload={"nombre": "Ana"})) == 422  # clave fuera de la lista
    assert post(_ev(payload={"message": "x" * 301})) == 422
    assert post(_ev(payload={"geo": [1, 2]})) == 422
    assert post(_ev(correo="a@b.c")) == 422  # campo extra
    assert client.post("/api/events", json={"events": []}).status_code == 422
    big = {"events": [_ev() for _ in range(501)]}
    assert client.post("/api/events", json=big).status_code == 422
    assert client.get("/api/events/summary").json()["total"] == 0


def test_catalog_meta_has_no_body_text(env):
    client, engine, _ = env
    nid = _news(engine)
    r = client.get(f"/api/catalog/{nid}/meta")
    assert r.status_code == 200 and r.json()["id"] == nid
    assert "Okantzi" not in r.text and "SECRETO" not in r.text
    assert client.get("/api/catalog/999/meta").status_code == 404


def test_static_gzip_only_for_text_and_never_for_audio_or_range(env):
    client, engine, _ = env
    _news(engine)
    from app.batch.service import run_batch

    run_batch()
    m = client.get("/static/news/1/manifest.json", headers={"Accept-Encoding": "gzip"})
    assert m.headers.get("content-encoding") == "gzip" and m.json()["news_id"] == 1
    plain = client.get("/static/news/1/manifest.json", headers={"Accept-Encoding": "identity"})
    assert "content-encoding" not in plain.headers
    url = next(s["audio"]["opus"] for s in m.json()["segments"] if s["audio"])
    a = client.get(url, headers={"Accept-Encoding": "gzip"})
    assert "content-encoding" not in a.headers  # el audio ya está comprimido
    r = client.get(
        "/static/news/1/manifest.json", headers={"Range": "bytes=0-9", "Accept-Encoding": "gzip"}
    )
    assert r.status_code == 206 and "content-encoding" not in r.headers
