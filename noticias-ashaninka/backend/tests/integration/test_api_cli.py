import json

import pytest
from app.cli import main as cli
from app.db.models import MissingProvenanceError, News
from conftest import ADMIN, requires_corpus
from fastapi.testclient import TestClient
from sqlmodel import Session

NEWS = {
    "titulo_cni": "Kipatsi",
    "cuerpo_cni": "Okantzi Pablo 2026. Tzimatsi kitaiteri 05/10/2026, ayer.",
    "titulo_es": "Tierra",
    "cuerpo_es": "texto en castellano que nunca debe salir",
    "variante_dialectal": "desconocida",
    "fecha_publicacion": "2026-10-05",
    "fuente_original": "prueba",
    "procedencia": {"tipo": "traduccion_automatica", "sistema": "x", "version": "1"},
}


@pytest.fixture
def client(temp_db):
    from app.main import app

    with TestClient(app, headers=ADMIN) as c:
        yield c


def test_news_without_provenance_is_rejected(temp_db):
    with Session(temp_db) as s:
        s.add(News(titulo_cni="a", cuerpo_cni="b"))
        with pytest.raises(MissingProvenanceError):
            s.commit()


def test_api_crud_and_processing(client):
    bad = {k: v for k, v in NEWS.items() if k != "procedencia"}
    assert client.post("/api/news", json=bad).status_code == 422
    r = client.post("/api/news", json=NEWS)
    assert r.status_code == 201
    body = r.json()
    assert "cuerpo_es" not in body and "titulo_es" not in body
    assert body["apta_experimento"] is False
    nid = body["id"]
    assert client.get("/api/news").json()[0]["id"] == nid
    assert client.get("/api/health").json()["status"] == "ok"

    proc = client.post(f"/api/news/{nid}/process").json()
    assert proc["estado"] == "processed" and proc["segmentos"] == 2
    assert {"segmentacion", "normalizacion", "adaptador_mms", "g2p"} <= set(proc["latencia_ms"])

    segs = client.get(f"/api/news/{nid}/segments").json()
    assert segs[0]["text_canonical"].startswith("okantsi")
    assert segs[0]["adapter_id"] == "mms_cni/H1"
    rep = client.get(f"/api/news/{nid}/editorial-report").json()
    kinds = {f["kind"] for s in rep["segmentos"] for f in s["marcas_editoriales"]}
    assert {"full_date", "relative_date"} <= kinds

    upd = dict(
        NEWS,
        cuerpo_cni="Kemetsa.",
        procedencia=dict(NEWS["procedencia"], revisado_por_hablante=True),
    )
    r = client.put(f"/api/news/{nid}", json=upd)
    assert r.json()["estado"] == "ingested" and r.json()["apta_experimento"] is True
    assert client.get(f"/api/news/{nid}/segments").json() == []

    assert client.post("/api/news/import", json=[NEWS, NEWS]).status_code == 201
    assert client.delete(f"/api/news/{nid}").status_code == 204
    assert client.get(f"/api/news/{nid}").status_code == 404


def test_cli_roundtrip(temp_db, tmp_path, capsys):
    d = tmp_path / "news"
    d.mkdir()
    (d / "n.json").write_text(json.dumps([NEWS]), encoding="utf-8")
    assert cli(["db-init"]) == 0
    assert cli(["validate-resources"]) == 0
    assert cli(["import", str(d)]) == 0
    assert cli(["import", str(d)]) == 0  # idempotente: no duplica
    assert "0 noticias importadas" in capsys.readouterr().out
    assert cli(["process", "--all"]) == 0
    assert cli(["process", "--news", "1"]) == 0
    assert cli(["report", "--news", "1"]) == 0
    out = capsys.readouterr().out
    assert "Noticia 1" in out and "editorial/full_date" in out
    assert cli(["import"]) == 2 and cli(["process"]) == 2


@requires_corpus
@pytest.mark.corpus
def test_import_from_corpus_is_idempotent(temp_db):
    from app.services import import_from_corpus

    assert len(import_from_corpus("dev", limit=3)) == 3
    assert import_from_corpus("dev", limit=3) == []


@requires_corpus
@pytest.mark.corpus
def test_all_dev_sentences_process_without_exceptions(temp_db):
    """Criterio de cierre: el 100 % de dev se procesa; lo listo para TTS está 100 % en vocabulario."""
    from app.corpus.loader import load_split
    from app.pipeline.tts.adapters.validate import find_oov
    from app.services import Pipeline

    p = Pipeline.default()
    vocab = p.adapter.vocab()
    ready = 0
    for pair in load_split("dev"):
        for row in p.process_text(pair.cni):
            if row["tts_ready"]:
                ready += 1
                assert find_oov(row["text_tts"], vocab) == []
            else:
                assert row["text_tts"] is None
                assert any("bloqueado para TTS" in u["reason"] for u in row["unresolved"])
    assert ready > 0
