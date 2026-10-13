"""Fase 6: token administrativo cerrado por defecto, cabeceras y límite de tasa (unidades)."""

import asyncio

import pytest
from app import security
from fastapi import HTTPException

pytestmark = pytest.mark.smoke

BUENO = "token-administrativo-0123456789"


@pytest.fixture(autouse=True)
def _sin_tokens(monkeypatch):
    for k in ("NA_ADMIN_TOKEN", "NA_EXPORT_TOKEN", "NA_TRUST_PROXY", "NA_ENV"):
        monkeypatch.delenv(k, raising=False)


@pytest.mark.parametrize(
    ("token", "valido"),
    [
        (BUENO, True),
        ("a" * 16, True),
        ("a" * 15, False),
        ("", False),
        (None, False),
        ("cambiar-por-un-token-largo-y-aleatorio", False),  # el valor de .env.example
        ("CHANGEME", False),
    ],
)
def test_token_valido(token, valido):
    assert security.token_valido(token) is valido


def test_cerrado_por_defecto_sin_token_configurado():
    assert not security.hay_token_configurado()
    with pytest.raises(HTTPException) as e:
        security.check_admin(BUENO)  # aunque coincida con «nada», no hay nada contra qué comparar
    assert e.value.status_code == 403 and "NA_ADMIN_TOKEN" in e.value.detail


def test_un_token_corto_o_de_ejemplo_no_abre_nada(monkeypatch):
    for malo in ("corto", "changeme", "cambiar-por-un-token-largo-y-aleatorio"):
        monkeypatch.setenv("NA_ADMIN_TOKEN", malo)
        assert not security.hay_token_configurado()
        with pytest.raises(HTTPException):
            security.check_admin(malo)


def test_token_correcto_incorrecto_y_alias(monkeypatch):
    monkeypatch.setenv("NA_ADMIN_TOKEN", BUENO)
    security.check_admin(BUENO)
    security.check_admin(None, BUENO)  # cualquiera de las dos cabeceras
    for malo in (None, "", BUENO + "x", BUENO[:-1], "otro-token-administrativo-01"):
        with pytest.raises(HTTPException) as e:
            security.check_admin(malo)
        assert e.value.status_code == 403
    monkeypatch.delenv("NA_ADMIN_TOKEN")
    monkeypatch.setenv("NA_EXPORT_TOKEN", "token-de-exportacion-0123456")  # alias de la Fase 5
    security.check_admin("token-de-exportacion-0123456")


def test_require_admin_lee_las_dos_cabeceras(monkeypatch):
    monkeypatch.setenv("NA_ADMIN_TOKEN", BUENO)
    security.require_admin(x_admin_token=BUENO, x_export_token=None)
    security.require_admin(x_admin_token=None, x_export_token=BUENO)
    with pytest.raises(HTTPException):
        security.require_admin(x_admin_token=None, x_export_token=None)


# ------------------------------------------------------------------ límite de tasa
class Reloj:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


def _mw(reloj):
    async def app(scope, receive, send):  # pragma: no cover - no se invoca en estas pruebas
        pass

    return security.RateLimitMiddleware(app, reloj=reloj)


def test_cubeta_de_fichas_agota_y_repone():
    reloj = Reloj()
    mw = _mw(reloj)
    assert [mw._permitir("ip", 60) for _ in range(60)] == [0.0] * 60  # capacidad = límite
    espera = mw._permitir("ip", 60)
    assert espera == pytest.approx(1.0)  # 60 por minuto = 1 por segundo
    assert mw._permitir("otra", 60) == 0.0  # otra IP no se ve afectada
    reloj.t += 1.0
    assert mw._permitir("ip", 60) == 0.0  # se repuso una ficha
    assert mw._permitir("ip", 60) > 0.0
    reloj.t += 3600
    assert [mw._permitir("ip", 60) for _ in range(60)] == [0.0] * 60  # nunca pasa de la capacidad
    assert mw._permitir("ip", 60) > 0.0


def test_que_rutas_se_limitan():
    lim = security._limitada
    assert lim("POST", "/api/events") and lim("POST", "/api/experiment/responses")
    assert lim("GET", "/api/synthesize/3") and lim("DELETE", "/api/news/1")
    assert not lim("GET", "/api/catalog") and not lim("GET", "/static/news/1/manifest.json")
    assert not lim("GET", "/api/health") and not lim("GET", "/api/health/ready")
    assert not lim("POST", "/otra")


def test_ip_solo_confia_en_x_forwarded_for_si_se_configura(monkeypatch):
    mw = _mw(Reloj())
    scope = {
        "client": ("10.0.0.5", 1234),
        "headers": [(b"x-forwarded-for", b"203.0.113.7, 10.0.0.1")],
    }
    assert mw._ip(scope) == "10.0.0.5"  # un cliente no puede falsear su IP
    monkeypatch.setenv("NA_TRUST_PROXY", "true")
    assert mw._ip(scope) == "203.0.113.7"


def test_respuesta_429_con_retry_after(monkeypatch):
    monkeypatch.setenv("NA_RATE_LIMIT_PER_MIN", "2")
    enviados = []
    llamadas = []

    async def app(scope, receive, send):
        llamadas.append(1)

    mw = security.RateLimitMiddleware(app, reloj=Reloj())

    async def send(m):
        enviados.append(m)

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/events",
        "headers": [],
        "client": ("1.1.1.1", 1),
    }

    async def correr():
        for _ in range(3):
            await mw(scope, None, send)

    asyncio.run(correr())
    assert len(llamadas) == 2
    inicio = enviados[0]
    assert inicio["status"] == 429
    assert dict(inicio["headers"])[b"retry-after"] == b"30"  # 2 por minuto -> una ficha cada 30 s


def test_limite_cero_o_invalido(monkeypatch):
    monkeypatch.setenv("NA_RATE_LIMIT_PER_MIN", "0")
    assert security.limite_por_minuto() == 0  # 0 = sin límite
    monkeypatch.setenv("NA_RATE_LIMIT_PER_MIN", "mucho")
    assert security.limite_por_minuto() == security.LIMITE_POR_DEFECTO


def test_csp_no_permite_scripts_ni_estilos_externos():
    partes = dict(p.split(" ", 1) for p in security.CSP.split("; "))
    assert partes["default-src"] == "'self'" and partes["script-src"] == "'self'"
    assert partes["object-src"] == "'none'" and partes["frame-ancestors"] == "'none'"
    assert "http" not in security.CSP  # ningún origen externo
