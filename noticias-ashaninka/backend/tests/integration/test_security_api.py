"""Fase 6 + QuitarAdmin: todo es público (sin token), cabeceras, límite y salud."""

import json
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[3]

# (método, ruta, cuerpo): lo que ANTES era administrativo; ahora responde sin token (nunca 403)
ANTES_ADMINISTRATIVOS = [
    ("GET", "/api/events/summary", None),
    ("GET", "/api/news", None),
    ("GET", "/api/news/1", None),
    ("GET", "/api/news/1/segments", None),
    ("GET", "/api/news/1/editorial-report", None),
    ("POST", "/api/news", {}),
    ("POST", "/api/news/import", []),
    ("POST", "/api/news/translate", {}),
    ("GET", "/api/news/translate/status", None),
    ("PUT", "/api/news/1", {}),
    ("DELETE", "/api/news/1", None),
    ("POST", "/api/news/1/process", None),
    ("GET", "/api/experiment/export", None),
]


@pytest.fixture
def cliente(temp_db, monkeypatch):
    monkeypatch.setenv("NA_TTS_ENGINE", "fake")
    monkeypatch.delenv("NA_EXPERIMENT_PILOTO", raising=False)
    monkeypatch.delenv("NA_ENV", raising=False)
    from app.main import app

    with TestClient(app) as c:
        yield c


def _llamar(c, metodo, ruta, cuerpo=None, **kw):
    return c.request(metodo, ruta, json=cuerpo, **kw)


@pytest.mark.parametrize(("metodo", "ruta", "cuerpo"), ANTES_ADMINISTRATIVOS)
def test_sin_token_nada_da_403(cliente, metodo, ruta, cuerpo):
    assert _llamar(cliente, metodo, ruta, cuerpo).status_code != 403  # 200, 404 o 422 según el caso
    r = _llamar(cliente, metodo, ruta, cuerpo, headers={"x-admin-token": "cualquiera"})
    assert r.status_code != 403  # una cabecera antigua se ignora


def test_cualquiera_puede_crear_y_borrar_una_noticia(cliente):
    noticia = {
        "titulo_cni": "PRUEBA (ficticia)",
        "cuerpo_cni": "Tee otimimotena katsini.",
        "procedencia": {"tipo": "traduccion_humana", "revisado_por_hablante": False},
    }
    r = cliente.post("/api/news", json=noticia)
    assert r.status_code == 201, r.text
    nid = r.json()["id"]
    assert cliente.delete(f"/api/news/{nid}").status_code == 204
    assert cliente.get(f"/api/news/{nid}").status_code == 404


def test_exportacion_y_resumen_abiertos(cliente):
    assert cliente.get("/api/experiment/export").status_code == 200
    assert cliente.get("/api/events/summary").status_code == 200


def test_lo_que_usa_la_pwa_sigue_abierto(cliente):
    assert cliente.get("/api/health").status_code == 200
    assert cliente.get("/api/catalog").status_code == 200
    assert cliente.get("/api/experiment/config").status_code == 200
    ev = {
        "event_id": str(uuid.uuid4()),
        "session_id": str(uuid.uuid4()),
        "type": "view-start",
        "t_client": datetime.now(UTC).isoformat(),
        "payload": {},
    }
    assert cliente.post("/api/events", json={"events": [ev]}).status_code == 201


def test_el_motor_se_elige_sin_token(cliente):
    # QuitarAdmin: cualquier motor registrado se puede pedir sin token
    assert cliente.get("/api/synthesize/999?engine=fake").status_code == 404  # no existe la noticia
    assert cliente.get("/api/synthesize/999").status_code == 404
    assert cliente.get("/api/synthesize/999?engine=espeak_ng").status_code == 404


# ------------------------------------------------------------------ cabeceras
@pytest.mark.parametrize("ruta", ["/api/health", "/api/catalog", "/no-existe", "/static/x.json"])
def test_cabeceras_de_seguridad_en_toda_respuesta(cliente, ruta):
    r = cliente.get(ruta)
    h = r.headers
    assert h["x-content-type-options"] == "nosniff"
    assert h["x-frame-options"] == "DENY"
    assert h["referrer-policy"] == "no-referrer"
    assert "geolocation=()" in h["permissions-policy"]
    assert "default-src 'self'" in h["content-security-policy"]
    assert "strict-transport-security" not in h  # HTTP local: sin HSTS


def test_hsts_solo_con_https(cliente, monkeypatch):
    enc = {"x-forwarded-proto": "https"}
    assert "strict-transport-security" not in cliente.get("/api/health", headers=enc).headers
    monkeypatch.setenv("NA_TRUST_PROXY", "true")  # solo se cree al proxy si se configura
    h = cliente.get("/api/health", headers=enc).headers
    assert "max-age=31536000" in h["strict-transport-security"]
    assert "strict-transport-security" not in cliente.get("/api/health").headers


def test_la_documentacion_interactiva_no_lleva_csp_en_desarrollo(cliente):
    r = cliente.get("/docs")
    assert r.status_code == 200 and "content-security-policy" not in r.headers
    assert r.headers["x-content-type-options"] == "nosniff"


def test_el_streaming_y_el_range_siguen_funcionando_con_los_middlewares(cliente, tmp_path):
    from app.config import get_settings

    f = get_settings().static_dir / "prueba_rango.bin"
    f.write_bytes(bytes(range(256)))
    try:
        r = cliente.get("/static/prueba_rango.bin", headers={"range": "bytes=10-19"})
        assert r.status_code == 206 and r.content == bytes(range(10, 20))
        assert r.headers["content-range"] == "bytes 10-19/256"
        assert "content-security-policy" in r.headers
    finally:
        f.unlink()


# ------------------------------------------------------------------ límite de tasa
def test_el_limite_de_tasa_responde_429_con_cabeceras(cliente, monkeypatch):
    monkeypatch.setenv("NA_RATE_LIMIT_PER_MIN", "3")
    codigos = [cliente.post("/api/experiment/responses", json={}).status_code for _ in range(5)]
    assert codigos[:3] == [422, 422, 422] and codigos[3:] == [429, 429]
    r = cliente.post("/api/experiment/responses", json={})
    assert r.status_code == 429 and int(r.headers["retry-after"]) >= 1
    assert "content-security-policy" in r.headers  # la respuesta 429 también lleva cabeceras
    for _ in range(30):  # salud y lecturas quedan exentas
        assert cliente.get("/api/health").status_code == 200
        assert cliente.get("/api/catalog").status_code == 200


def test_sin_limite_si_se_desactiva(cliente, monkeypatch):
    monkeypatch.setenv("NA_RATE_LIMIT_PER_MIN", "0")
    assert {cliente.post("/api/experiment/responses", json={}).status_code for _ in range(20)} == {
        422
    }


# ------------------------------------------------------------------ salud
def test_health_ready_con_motor_fake(cliente):
    r = cliente.get("/api/health/ready")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "db": True, "static": True, "tts": True}


def test_health_ready_degradado_sin_modelo_y_sin_revelar_rutas(cliente, monkeypatch, tmp_path):
    monkeypatch.setenv("NA_TTS_ENGINE", "mms_vits")
    monkeypatch.setenv("NA_MODELS_DIR", str(tmp_path / "vacio"))
    r = cliente.get("/api/health/ready")
    assert r.status_code == 503 and r.json()["tts"] is False and r.json()["status"] == "degradado"
    assert set(r.json()) == {"status", "db", "static", "tts"}
    assert str(tmp_path) not in r.text


# ------------------------------------------------------------------ producción (proceso aparte)
def _en_produccion(env_extra: dict) -> dict:
    """La documentación se decide al importar la app: se comprueba en un proceso nuevo."""
    codigo = (
        "import json\n"
        "from fastapi.testclient import TestClient\n"
        "from app.main import app\n"
        "with TestClient(app) as c:\n"
        "    r = c.get('/api/health')\n"
        "    print(json.dumps({'docs': c.get('/docs').status_code,\n"
        "        'redoc': c.get('/redoc').status_code,\n"
        "        'openapi': c.get('/openapi.json').status_code,\n"
        "        'health': r.status_code,\n"
        "        'hsts': r.headers.get('strict-transport-security'),\n"
        "        'resumen': c.get('/api/events/summary').status_code}))\n"
    )
    import os

    env = {**os.environ, "NA_TTS_ENGINE": "fake", "NA_ENV": "production", **env_extra}
    out = subprocess.run(
        [sys.executable, "-c", codigo],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_produccion_sin_docs_con_hsts_y_sin_token(tmp_path):
    r = _en_produccion(
        {
            "NA_DATABASE_URL": f"sqlite:///{(tmp_path / 'p.db').as_posix()}",
            "NA_STATIC_DIR": str(tmp_path / "static"),
        }
    )
    assert (r["docs"], r["redoc"], r["openapi"]) == (404, 404, 404)
    assert r["health"] == 200 and "max-age" in r["hsts"]
    assert r["resumen"] == 200  # QuitarAdmin: también en producción es público
