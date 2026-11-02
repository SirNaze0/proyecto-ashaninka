"""Sala de redacción: `POST /api/news/{id}/build` sintetiza por lotes (público desde QuitarAdmin)."""

import pytest
from fastapi.testclient import TestClient

NOTICIA = {
    "titulo_cni": "Titulo de prueba",
    "cuerpo_cni": "Primera oracion de prueba. Segunda oracion de prueba.",
    "procedencia": {"tipo": "traduccion_humana", "revisado_por_hablante": False},
}


@pytest.fixture
def cliente(temp_db, tmp_path, monkeypatch):
    monkeypatch.setenv("NA_TTS_ENGINE", "fake")
    monkeypatch.setenv("NA_STATIC_DIR", str(tmp_path / "static"))
    monkeypatch.delenv("NA_ENV", raising=False)
    from app.main import app

    with TestClient(app) as c:
        yield c


def test_build_no_exige_token(cliente):
    # sin roles (QuitarAdmin): sin cabecera llega a la ruta (404 porque no existe la noticia)
    assert cliente.post("/api/news/1/build").status_code == 404


def test_build_noticia_inexistente_da_404(cliente):
    assert cliente.post("/api/news/999/build").status_code == 404


def test_build_sintetiza_y_escribe_el_manifiesto(cliente, tmp_path):
    r = cliente.post("/api/news", json=NOTICIA)
    assert r.status_code == 201
    nid = r.json()["id"]
    assert cliente.post(f"/api/news/{nid}/process").status_code == 200
    b = cliente.post(f"/api/news/{nid}/build")
    assert b.status_code == 200
    assert b.json()["noticias"] == 1
    assert b.json()["errors"] == 0
    assert (tmp_path / "static" / "news" / str(nid) / "manifest.json").exists()
