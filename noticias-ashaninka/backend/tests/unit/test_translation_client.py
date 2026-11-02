"""Cliente HTTP del traductor BiTAM contra un servidor falso local (sin GPU ni modelo)."""

from __future__ import annotations

import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from app.config import get_settings
from app.translation import (
    FakeTranslator,
    HttpTranslator,
    TraductorError,
    TraductorNoDisponible,
    get_translator,
)

pytestmark = pytest.mark.smoke


class _Servidor:
    """Servidor HTTP mínimo que imita ``POST /traducir`` del servicio BiTAM."""

    def __init__(self, modo: str = "ok"):
        self.modo = modo
        self.peticiones: list[list[str]] = []
        padre = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):  # silencio en las pruebas
                pass

            def do_POST(self):
                textos = json.loads(self.rfile.read(int(self.headers["Content-Length"])))["texts"]
                padre.peticiones.append(textos)
                if padre.modo == "lento":
                    time.sleep(2)
                if padre.modo == "500":
                    self.send_response(500)
                    self.end_headers()
                    return
                if padre.modo == "basura":
                    cuerpo = b"esto no es json"
                elif padre.modo == "cuenta":
                    cuerpo = json.dumps({"translations": ["solo una"]}).encode()
                else:
                    cuerpo = json.dumps(
                        {
                            "translations": [t.lower() for t in textos],
                            "modelo": "BiTAM es2cni",
                            "version": "run-x",
                        }
                    ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(cuerpo)))
                self.end_headers()
                try:
                    self.wfile.write(cuerpo)
                except ConnectionError:  # el cliente ya abandonó (prueba de tiempo agotado)
                    pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def cerrar(self):
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture
def servidor():
    creados: list[_Servidor] = []

    def crear(modo: str = "ok") -> _Servidor:
        s = _Servidor(modo)
        creados.append(s)
        return s

    yield crear
    for s in creados:
        s.cerrar()


def test_exito_y_troceo_en_lotes_de_64(servidor) -> None:
    s = servidor()
    textos = [f"Oración {i}." for i in range(130)]
    r = HttpTranslator(s.url).translate_batch(textos)
    assert r.translations == [t.lower() for t in textos]
    assert (r.modelo, r.version) == ("BiTAM es2cni", "run-x")
    assert [len(p) for p in s.peticiones] == [64, 64, 2]


@pytest.mark.parametrize(
    ("modo", "error"),
    [("500", TraductorError), ("basura", TraductorError), ("cuenta", TraductorError)],
)
def test_respuestas_invalidas(servidor, modo, error) -> None:
    with pytest.raises(error):
        HttpTranslator(servidor(modo).url).translate_batch(["a", "b"])


def test_error_http_conserva_el_estado(servidor) -> None:
    with pytest.raises(TraductorError) as e:
        HttpTranslator(servidor("500").url).translate_batch(["a"])
    assert e.value.status == 500


def test_tiempo_agotado(servidor) -> None:
    with pytest.raises(TraductorNoDisponible, match="no respondió"):
        HttpTranslator(servidor("lento").url, timeout=0.3).translate_batch(["a"])


def test_conexion_rechazada() -> None:
    with socket.socket() as sk:  # puerto libre que nadie escucha
        sk.bind(("127.0.0.1", 0))
        puerto = sk.getsockname()[1]
    # Linux rechaza al instante ("no se pudo conectar"); Windows reintenta el SYN y suele agotar el
    # tiempo ("no respondió"). En ambos casos es "no disponible" (-> 503 en la API).
    with pytest.raises(TraductorNoDisponible, match="conectar|no respondió"):
        HttpTranslator(f"http://127.0.0.1:{puerto}", timeout=2).translate_batch(["a"])


def test_get_translator_segun_el_entorno(monkeypatch) -> None:
    monkeypatch.setenv("NA_TRANSLATOR_ENGINE", "fake")
    assert isinstance(get_translator(), FakeTranslator)

    monkeypatch.setenv("NA_TRANSLATOR_ENGINE", "http")
    monkeypatch.setenv("NA_TRANSLATOR_URL", "")
    with pytest.raises(TraductorNoDisponible, match="NA_TRANSLATOR_URL"):
        get_translator()

    monkeypatch.setenv("NA_TRANSLATOR_URL", "http://127.0.0.1:8100/")
    monkeypatch.setenv("NA_TRANSLATOR_TIMEOUT", "30")
    t = get_translator()
    assert isinstance(t, HttpTranslator)
    assert (t.url, t.timeout) == ("http://127.0.0.1:8100", 30.0)

    monkeypatch.setenv("NA_TRANSLATOR_ENGINE", "otro")
    with pytest.raises(TraductorNoDisponible, match="desconocido"):
        get_translator()


def test_valores_por_defecto(monkeypatch) -> None:
    for v in ("NA_TRANSLATOR_ENGINE", "NA_TRANSLATOR_URL", "NA_TRANSLATOR_TIMEOUT"):
        monkeypatch.delenv(v, raising=False)
    s = get_settings()
    assert (s.translator_engine, s.translator_url, s.translator_timeout) == ("http", "", 120.0)


def test_en_trozos_conserva_el_orden_y_los_metadatos():
    from app.translation import EnTrozos, FakeTranslator

    fake = FakeTranslator()
    textos = [f"Texto {i}" for i in range(10)]
    r = EnTrozos(fake, 4).translate_batch(textos)
    assert [len(x) for x in fake.llamadas] == [4, 4, 2]
    assert r.translations == [f"texto {i} [fake-bitam]" for i in range(10)]
    assert (r.modelo, r.version) == (fake.modelo, fake.version)
    assert EnTrozos(fake, 0).translate_batch(textos).translations == r.translations  # todo junto
    assert len(fake.llamadas[-1]) == 10
    assert EnTrozos(fake, 4).translate_batch([]).translations == []
