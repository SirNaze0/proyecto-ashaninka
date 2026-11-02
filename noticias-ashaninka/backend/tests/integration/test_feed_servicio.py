"""Ciclo TV Perú → BiTAM (falso) → pipeline → audio (fake) → tablón, y la API /api/feed (NoticiasTVPeru)."""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

MUESTRA = Path(__file__).resolve().parents[1] / "fixtures" / "tvperu_rss_muestra.xml"


class _Feed:
    """Servidor local que sirve el RSS de muestra (nunca se contacta a TV Perú en las pruebas)."""

    def __init__(self):
        feed = self
        self.peticiones = 0

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                feed.peticiones += 1
                cuerpo = MUESTRA.read_bytes()
                self.send_response(200)
                self.send_header("Content-Length", str(len(cuerpo)))
                self.end_headers()
                self.wfile.write(cuerpo)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}/rss.xml"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def cerrar(self):
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture
def feed():
    f = _Feed()
    yield f
    f.cerrar()


@pytest.fixture
def entorno(temp_db, tmp_path, monkeypatch, feed):
    monkeypatch.setenv("NA_TTS_ENGINE", "fake")
    monkeypatch.setenv("NA_STATIC_DIR", str(tmp_path / "static"))
    monkeypatch.setenv("NA_TRANSLATOR_ENGINE", "fake")
    monkeypatch.setenv("NA_FEED_URL", feed.url)
    monkeypatch.delenv("NA_FEED_INTERVALO_MIN", raising=False)
    monkeypatch.delenv("NA_ENV", raising=False)
    return feed


def _noticias():
    from app.db.models import News
    from app.db.session import get_engine
    from sqlmodel import Session, select

    with Session(get_engine()) as s:
        return [
            (
                n.id,
                n.titulo_cni,
                n.fuente_original,
                n.provenance.tipo,
                n.provenance.revisado_por_hablante,
                n.apta_experimento,
                n.estado,
                n.titulo_es,
            )
            for n in s.exec(select(News).order_by(News.id)).all()
        ]


def test_ciclo_publica_tres_con_procedencia_automatica_y_audio(entorno, tmp_path):
    from app.feed import servicio

    res = servicio.ejecutar_ciclo()
    assert res["motivo"] is None and res["errores"] == 0
    assert res["nuevas"] == 5  # 4 con texto + 1 solo vídeo (descartada al registrar)
    assert len(res["publicadas"]) == 3

    filas = _noticias()
    assert len(filas) == 3
    # se procesan de la más antigua a la más nueva entre las 3 más recientes: el id crece con la fecha
    assert [f[7] for f in filas] == [
        "Noticia ficticia tres de prueba",
        "Noticia ficticia dos de prueba",
        "Noticia ficticia uno de prueba",
    ]
    for _id, titulo_cni, fuente, tipo, revisado, apta, estado, _ in filas:
        assert titulo_cni.endswith(
            "[fake-bitam]"
        )  # el texto cni sale del traductor, nunca inventado
        assert fuente.startswith("https://www.tvperu.gob.pe/noticias/")
        assert (tipo, revisado, apta, estado) == (
            "traduccion_automatica",
            False,
            False,
            "processed",
        )
        assert (tmp_path / "static" / "news" / str(_id) / "manifest.json").is_file()
    # el traductor falso devuelve castellano en minúsculas: la validación estricta del adaptador MMS lo
    # bloquea (como haría con cualquier texto fuera del vocabulario); con BiTAM la salida es cni
    audio = res["audio"]
    assert audio["segmentos"] + audio["bloqueados"] > 0 and audio["errores"] == 0

    st = servicio.estado()
    assert st["items"] == {"pendiente": 1, "publicada": 3, "error": 0, "descartada": 1}
    assert st["ultimo_resultado"]["publicadas"][0]["url"].startswith("https://www.tvperu.gob.pe/")


def test_un_segundo_ciclo_no_duplica_y_vacia_la_cola(entorno):
    from app.feed import servicio

    servicio.ejecutar_ciclo()
    res = servicio.ejecutar_ciclo()
    assert res["nuevas"] == 0 and len(res["publicadas"]) == 1  # la cuarta que quedaba pendiente
    tercero = servicio.ejecutar_ciclo()
    assert tercero["publicadas"] == [] and tercero["pendientes"] == 0
    assert len(_noticias()) == 4
    assert entorno.peticiones == 3  # una petición al feed por ciclo


def test_traductor_caido_deja_todo_pendiente(entorno, monkeypatch):
    from app.feed import servicio

    monkeypatch.setenv("NA_TRANSLATOR_ENGINE", "http")
    monkeypatch.setenv("NA_TRANSLATOR_URL", "")  # sin configurar
    res = servicio.ejecutar_ciclo()
    assert res["publicadas"] == [] and "traductor no disponible" in res["motivo"]
    assert _noticias() == []  # nunca se publica castellano como si fuera asháninka
    assert servicio.estado()["items"]["pendiente"] == 4


def test_errores_de_traduccion_se_reintentan_y_luego_se_descartan(entorno, monkeypatch):
    from app.feed import servicio
    from app.translation import TraductorError

    def falla(*a, **k):
        raise TraductorError("el traductor respondió 500", status=500)

    monkeypatch.setattr(servicio, "traducir_noticia", falla)
    for _ in range(servicio.MAX_INTENTOS):
        servicio.ejecutar_ciclo()
    st = servicio.estado()
    assert st["items"]["publicada"] == 0 and st["items"]["descartada"] >= 3


def test_fuente_caida_se_registra_sin_romper(entorno, monkeypatch):
    from app.feed import servicio

    monkeypatch.setenv("NA_FEED_URL", "http://127.0.0.1:9/rss.xml")
    res = servicio.ejecutar_ciclo()
    assert res["motivo"].startswith("TV Perú:") and res["nuevas"] == 0


def test_candado_impide_dos_ciclos_a_la_vez(entorno):
    from app.feed import servicio

    assert servicio._CANDADO.acquire(blocking=False)
    try:
        with pytest.raises(servicio.CicloEnCurso):
            servicio.ejecutar_ciclo()
        assert servicio.lanzar_en_segundo_plano() is False
    finally:
        servicio._CANDADO.release()


def test_planificador_respeta_el_intervalo(entorno):
    from datetime import UTC, datetime, timedelta

    from app.db.models import FeedConfig
    from app.feed import servicio

    cfg = FeedConfig(id=1, intervalo_min=0)
    assert not servicio.toca_ejecutar(cfg)  # apagado
    cfg.intervalo_min = 15
    assert servicio.toca_ejecutar(cfg)  # nunca se ejecutó
    ahora = datetime.now(UTC)
    cfg.ultima_ejecucion = ahora - timedelta(minutes=5)
    assert not servicio.toca_ejecutar(cfg, ahora)
    cfg.ultima_ejecucion = (ahora - timedelta(minutes=16)).replace(
        tzinfo=None
    )  # como lo devuelve SQLite
    assert servicio.toca_ejecutar(cfg, ahora)


# ------------------------------------------------------------------ API
@pytest.fixture
def cliente(entorno, monkeypatch):
    from app.main import app

    with TestClient(app) as c:
        yield c


def _esperar_fin(c, segundos=60):
    fin = time.time() + segundos
    while time.time() < fin:
        st = c.get("/api/feed/status").json()
        if not st["ejecutando"] and st["ultima_ejecucion"]:
            return st
        time.sleep(0.2)
    raise AssertionError("el ciclo no terminó")


def test_api_status_y_config(cliente):
    st = cliente.get("/api/feed/status").json()
    assert st["habilitado"] is False and st["intervalo_min"] == 0 and st["fuente"] == "TV Perú"
    r = cliente.put("/api/feed/config", json={"intervalo_min": 30, "max_por_ciclo": 2})
    assert (
        r.status_code == 200 and r.json()["intervalo_min"] == 30 and r.json()["max_por_ciclo"] == 2
    )
    for malo in ({"intervalo_min": 7}, {"max_por_ciclo": 9}, {"otro": 1}):
        assert cliente.put("/api/feed/config", json=malo).status_code == 422


def test_api_run_apagado_da_503(cliente):
    assert cliente.post("/api/feed/run").status_code == 503


def test_api_run_lanza_el_ciclo_y_el_catalogo_lo_muestra(entorno, monkeypatch):
    monkeypatch.setenv("NA_FEED_ENABLED", "true")
    from app.main import app

    with TestClient(app) as c:
        r = c.post("/api/feed/run")
        assert r.status_code == 202
        st = _esperar_fin(c)
        assert len(st["ultimo_resultado"]["publicadas"]) == 3
        cat = c.get("/api/catalog?orden=recientes").json()
        assert len(cat) == 3
        assert all(i["traduccion_automatica"] and i["fuente_nombre"] == "TV Perú" for i in cat)
        assert cat[0]["fecha_publicacion"] == "2026-11-02"
        assert cat[0]["fuente_url"].startswith("https://www.tvperu.gob.pe/noticias/nacionales/")
        det = c.get(f"/api/catalog/{cat[0]['id']}").json()
        assert det["traduccion_automatica"] and det["fuente_url"] == cat[0]["fuente_url"]
        # el castellano guardado nunca sale por la API pública
        assert not {"titulo_es", "cuerpo_es"} & (set(cat[0]) | set(det))
        assert "Primera oración ficticia de la noticia 1." not in json.dumps(cat)


def test_catalogo_recientes_ordena_por_fecha(temp_db, monkeypatch):
    monkeypatch.setenv("NA_TTS_ENGINE", "fake")
    from app.main import app

    noticias = [
        ("2026-10-01", "Vieja"),
        ("2026-11-02", "Nueva"),
        (None, "Sin fecha"),
    ]
    with TestClient(app) as c:
        for fecha, titulo in noticias:
            cuerpo = {
                "titulo_cni": titulo,
                "cuerpo_cni": "Tee otimimotena katsini.",
                "procedencia": {"tipo": "traduccion_humana"},
            }
            if fecha:
                cuerpo["fecha_publicacion"] = fecha
            assert c.post("/api/news", json=cuerpo).status_code == 201
        assert [i["titulo_cni"] for i in c.get("/api/catalog").json()] == [
            "Vieja",
            "Nueva",
            "Sin fecha",
        ]
        recientes = [i["titulo_cni"] for i in c.get("/api/catalog?orden=recientes").json()]
        assert recientes[-1] == "Vieja" and recientes.index("Nueva") < recientes.index("Vieja")
        item = c.get("/api/catalog").json()[0]
        assert item["traduccion_automatica"] is False and item["fuente_url"] is None
