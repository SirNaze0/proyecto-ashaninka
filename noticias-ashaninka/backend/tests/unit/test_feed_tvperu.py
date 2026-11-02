"""Lector del RSS de TV Perú (NoticiasTVPeru): parseo, limpieza del HTML, recorte y descarga."""

import threading
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from app.feed import tvperu

pytestmark = pytest.mark.smoke

MUESTRA = Path(__file__).resolve().parents[1] / "fixtures" / "tvperu_rss_muestra.xml"


@pytest.fixture(scope="module")
def items():
    return tvperu.parsear_rss(MUESTRA.read_bytes())


def test_parsea_los_items_aunque_el_xml_empiece_con_salto_de_linea(items):
    assert MUESTRA.read_bytes().startswith(b"\n")
    assert [i.guid.split()[0] for i in items] == ["144001", "144002", "144003", "144004", "144005"]
    primero = items[0]
    assert primero.titulo == "Noticia ficticia uno de prueba"
    assert primero.url.startswith("https://www.tvperu.gob.pe/noticias/nacionales/")
    assert primero.categoria == "nacionales"
    assert primero.publicado_en == datetime(2026, 11, 2, 18, 3, 41, tzinfo=UTC)


def test_limpia_el_html_del_cuerpo(items):
    # sin «Lee también», sin tuits incrustados, sin párrafos vacíos y cortado en «TAMBIÉN TE PUEDE INTERESAR»
    assert items[0].parrafos == [
        "Primera oración ficticia de la noticia 1. Segunda oración ficticia con un enlace.",
        "Tercera oración ficticia de la noticia 1.",
    ]
    assert items[1].parrafos[-1] == "Cuarta oración ficticia. Quinta oración ficticia."
    assert items[4].parrafos == []  # solo vídeo: nada que traducir


@pytest.mark.parametrize(
    ("html", "esperado"),
    [
        ("<p>Uno.</p><p>[Lee también: algo]</p><p>Dos.</p>", ["Uno.", "Dos."]),
        ("<p>Uno.</p><p>También te puede interesar:</p><p>Otro titular</p>", ["Uno."]),
        ("<p>Uno<br>dos.</p><aside><p>Recuadro</p></aside>", ["Uno dos."]),
        (
            "<p>&nbsp;</p><script>var x;</script><p>Texto&nbsp;con&nbsp;espacios.</p>",
            ["Texto con espacios."],
        ),
    ],
)
def test_parrafos_del_html(html, esperado):
    assert tvperu.parrafos_del_html(html) == esperado


def test_recortar_respeta_oraciones_y_limites():
    parrafos = ["A uno. A dos. A tres.", "B uno. B dos.", "C uno."]
    assert tvperu.recortar(parrafos, max_oraciones=4) == ["A uno. A dos. A tres.", "B uno."]
    # por caracteres: nunca parte una oración y siempre deja al menos una
    assert tvperu.recortar(["Una oración bastante larga. Otra."], max_caracteres=10) == [
        "Una oración bastante larga."
    ]
    larga = "x" * 1001 + "."
    assert tvperu.recortar([larga, "Corta."]) == [
        "Corta."
    ]  # > 1000 caracteres: BiTAM la rechazaría


def test_titulo_recortado():
    assert tvperu.titulo_recortado("corto") == "corto"
    t = tvperu.titulo_recortado("x" * 400)
    assert len(t) == 300 and t.endswith("…")


@pytest.mark.parametrize("roto", [b"no es xml", b"<rss></rss>"])
def test_feed_invalido_da_fuente_error(roto):
    with pytest.raises(tvperu.FuenteError):
        tvperu.parsear_rss(roto)


# ------------------------------------------------------------------ descarga (servidor HTTP local)
class _Servidor:
    def __init__(self, modo: str):
        servidor = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                servidor.ua = self.headers.get("User-Agent")
                if servidor.modo == "403":
                    self.send_response(403)
                    self.end_headers()
                    return
                cuerpo = MUESTRA.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/rss+xml; charset=utf-8")
                self.send_header("Content-Length", str(len(cuerpo)))
                self.end_headers()
                self.wfile.write(cuerpo)

        self.modo, self.ua = modo, None
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}/rss.xml"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def cerrar(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def test_descarga_con_user_agent_propio():
    s = _Servidor("ok")
    try:
        datos = tvperu.descargar_rss(s.url, timeout=5)
        assert len(tvperu.parsear_rss(datos)) == 5
        assert s.ua == tvperu.UA_POR_DEFECTO
        tvperu.descargar_rss(s.url, timeout=5, user_agent="Otro/1.0")
        assert s.ua == "Otro/1.0"
    finally:
        s.cerrar()


def test_errores_de_descarga_tipados():
    s = _Servidor("403")
    try:
        with pytest.raises(tvperu.FuenteError, match="403"):
            tvperu.descargar_rss(s.url, timeout=5)
    finally:
        s.cerrar()
    with pytest.raises(tvperu.FuenteNoDisponible):
        tvperu.descargar_rss("http://127.0.0.1:9/rss.xml", timeout=2)  # puerto cerrado
