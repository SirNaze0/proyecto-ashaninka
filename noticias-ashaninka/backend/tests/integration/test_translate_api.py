"""``POST /api/news/translate`` (MejoraEIntegracion, Fase 2): administrativo y sin escritura."""

from __future__ import annotations

import os
import socket

import pytest
from conftest import ADMIN
from fastapi.testclient import TestClient
from sqlmodel import Session, select

NOTICIA = {
    "titulo_es": "Lluvias en Satipo",
    "cuerpo_es": "Llovió mucho en Satipo. El río creció.\n\nNo hay heridos.",
}


@pytest.fixture
def cliente(temp_db, monkeypatch):
    monkeypatch.setenv("NA_TTS_ENGINE", "fake")
    monkeypatch.setenv("NA_TRANSLATOR_ENGINE", "fake")
    monkeypatch.setenv("NA_RATE_LIMIT_PER_MIN", "0")
    monkeypatch.delenv("NA_ENV", raising=False)
    from app.main import app

    with TestClient(app) as c:
        yield c


def test_sin_token_403(cliente) -> None:
    assert cliente.post("/api/news/translate", json=NOTICIA).status_code == 403
    r = cliente.post("/api/news/translate", json=NOTICIA, headers={"x-admin-token": "malo"})
    assert r.status_code == 403


def test_con_token_devuelve_borrador_y_no_guarda(cliente, temp_db) -> None:
    from app.db.models import News

    r = cliente.post("/api/news/translate", json=NOTICIA, headers=ADMIN)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["titulo_cni"] == "Lluvias en Satipo [fake-bitam]"
    assert len(d["paragraphs"]) == 2
    assert d["procedencia"]["tipo"] == "traduccion_automatica"
    assert d["procedencia"]["revisado_por_hablante"] is False
    assert d["procedencia"]["sistema"] == "BiTAM es2cni"
    assert len(d["oraciones"]) == 4 and d["oraciones"][0]["parrafo"] == -1
    with Session(temp_db) as s:
        assert s.exec(select(News)).all() == []  # NO escribe en la base de datos


def test_el_borrador_se_publica_con_el_flujo_normal(cliente) -> None:
    d = cliente.post("/api/news/translate", json=NOTICIA, headers=ADMIN).json()
    noticia = {
        "titulo_cni": d["titulo_cni"],
        "cuerpo_cni": "\n\n".join(d["paragraphs"]),
        **NOTICIA,
        "procedencia": d["procedencia"],
    }
    r = cliente.post("/api/news", json=noticia, headers=ADMIN)
    assert r.status_code == 201, r.text
    assert r.json()["procedencia_tipo"] == "traduccion_automatica"
    assert r.json()["revisado_por_hablante"] is False
    assert r.json()["apta_experimento"] is False


@pytest.mark.parametrize(
    "cuerpo",
    [
        {"titulo_es": "T", "cuerpo_es": "a" * 8001},
        {"titulo_es": "T" * 301, "cuerpo_es": "Hola."},
        {"titulo_es": "T", "cuerpo_es": " ".join(["Hola."] * 81)},
        {"titulo_es": "T", "cuerpo_es": "a" * 1001 + "."},
        {"titulo_es": "", "cuerpo_es": "Hola."},
        {"titulo_es": "T"},
        {"titulo_es": "T", "cuerpo_es": "Hola.", "extra": 1},
    ],
)
def test_limites_422(cliente, cuerpo) -> None:
    assert cliente.post("/api/news/translate", json=cuerpo, headers=ADMIN).status_code == 422


def test_sin_url_configurada_503(cliente, monkeypatch) -> None:
    monkeypatch.setenv("NA_TRANSLATOR_ENGINE", "http")
    monkeypatch.setenv("NA_TRANSLATOR_URL", "")
    r = cliente.post("/api/news/translate", json=NOTICIA, headers=ADMIN)
    assert r.status_code == 503
    assert "NA_TRANSLATOR_URL" in r.json()["detail"]


def test_servicio_caido_503(cliente, monkeypatch) -> None:
    with socket.socket() as sk:
        sk.bind(("127.0.0.1", 0))
        puerto = sk.getsockname()[1]
    monkeypatch.setenv("NA_TRANSLATOR_ENGINE", "http")
    monkeypatch.setenv("NA_TRANSLATOR_URL", f"http://127.0.0.1:{puerto}")
    monkeypatch.setenv("NA_TRANSLATOR_TIMEOUT", "2")
    r = cliente.post("/api/news/translate", json=NOTICIA, headers=ADMIN)
    assert r.status_code == 503


# ------------------------------------------------------------------ servicio real (opcional)
@pytest.mark.traductor
def test_servicio_bitam_real(cliente, monkeypatch) -> None:
    """Con el servicio BiTAM encendido: ``NA_TRANSLATOR_URL=http://127.0.0.1:8100 pytest -m traductor``."""
    url = os.environ.get("NA_TRANSLATOR_URL") or "http://127.0.0.1:8100"
    monkeypatch.setenv("NA_TRANSLATOR_ENGINE", "http")
    monkeypatch.setenv("NA_TRANSLATOR_URL", url)
    r = cliente.post("/api/news/translate", json=NOTICIA, headers=ADMIN)
    if r.status_code == 503:
        pytest.skip(f"servicio BiTAM no disponible en {url}")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["procedencia"]["version"].startswith("bitam_v5")
    assert all(o["cni_modelo"] == o["cni_modelo"].lower() for o in d["oraciones"])
    assert all(o["cni"].strip() for o in d["oraciones"])
    assert "Satipo" in " ".join(d["paragraphs"])  # nombre propio restaurado desde la fuente
