"""Seguridad de la API (Fase 6): token administrativo, cabeceras y límite de tasa.

- **Cerrado por defecto.** Los endpoints administrativos solo responden con un token válido en la
  cabecera ``x-admin-token`` (o ``x-export-token``, por compatibilidad con la Fase 5). Sin token
  configurado, o con uno corto o de ejemplo, devuelven 403: un despliegue olvidado no queda abierto.
- **Cabeceras** de seguridad y CSP en toda respuesta. HSTS solo cuando la conexión es HTTPS.
- **Límite de tasa** por IP, en memoria, para las rutas públicas de escritura y la síntesis.

Los middlewares son ASGI puros (no ``BaseHTTPMiddleware``) para no interferir con el streaming
NDJSON de ``/api/synthesize`` ni con las respuestas parciales (``Range``) de ``/static``.
"""

from __future__ import annotations

import json
import os
import secrets
import time
from collections.abc import Callable

from fastapi import Header, HTTPException
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

MIN_TOKEN_LEN = 16
# Valores de los archivos de ejemplo: nunca valen como token real
TOKENS_DE_EJEMPLO = frozenset(
    {"changeme", "change-me", "cambiar-esto", "cambiar-por-un-token-largo-y-aleatorio", "secret"}
)
RUTAS_SIN_CSP = ("/docs", "/redoc", "/openapi.json")  # Swagger carga scripts de un CDN

CSP = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' 'unsafe-inline'",  # Preact escribe atributos style en línea
        "img-src 'self' data: blob:",
        "media-src 'self' blob:",
        "connect-src 'self' blob:",  # GLTFLoader (three.js) lee las texturas del VRM como blob:
        "worker-src 'self' blob:",
        "font-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
)
CABECERAS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    "Cross-Origin-Opener-Policy": "same-origin",
}
HSTS = "max-age=31536000; includeSubDomains"


def _bool(v: str | None) -> bool:
    return (v or "").strip().lower() in {"1", "true", "yes", "si", "sí"}


def es_produccion() -> bool:
    return os.getenv("NA_ENV", "development").strip().lower() == "production"


def token_valido(token: str | None) -> bool:
    """Un token sirve si tiene al menos 16 caracteres y no es uno de los valores de ejemplo."""
    return bool(token) and len(token) >= MIN_TOKEN_LEN and token.lower() not in TOKENS_DE_EJEMPLO


def tokens_configurados() -> list[str]:
    """Tokens administrativos válidos del entorno (``NA_ADMIN_TOKEN`` y el alias ``NA_EXPORT_TOKEN``)."""
    cand = (os.getenv("NA_ADMIN_TOKEN"), os.getenv("NA_EXPORT_TOKEN"))
    return [t for t in cand if token_valido(t)]


def hay_token_configurado() -> bool:
    return bool(tokens_configurados())


def comprobar_token(token: str | None) -> bool:
    """Comparación en tiempo constante contra los tokens configurados."""
    if not token:
        return False
    dado = token.encode()
    return any(secrets.compare_digest(dado, t.encode()) for t in tokens_configurados())


def check_admin(*tokens: str | None) -> None:
    """Lanza 403 salvo que algún token dado coincida con uno configurado y válido."""
    if not hay_token_configurado():
        raise HTTPException(
            403,
            "endpoint administrativo deshabilitado: defina NA_ADMIN_TOKEN (16 caracteres o más)",
        )
    if not any(comprobar_token(t) for t in tokens):
        raise HTTPException(403, "token administrativo inválido")


def require_admin(
    x_admin_token: str | None = Header(default=None),
    x_export_token: str | None = Header(default=None),
) -> None:
    """Dependencia de FastAPI para los endpoints administrativos."""
    check_admin(x_admin_token, x_export_token)


# ------------------------------------------------------------------ cabeceras
class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        pedidos = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        confiar = _bool(os.getenv("NA_TRUST_PROXY"))
        https = scope.get("scheme") == "https" or (
            confiar and pedidos.get("x-forwarded-proto", "").lower() == "https"
        )
        hsts = https or es_produccion()
        con_csp = not path.startswith(RUTAS_SIN_CSP)

        async def enviar(message: Message) -> None:
            if message["type"] == "http.response.start":
                h = MutableHeaders(scope=message)
                for k, v in CABECERAS.items():
                    h.setdefault(k, v)
                if con_csp:
                    h.setdefault("Content-Security-Policy", CSP)
                if hsts:
                    h.setdefault("Strict-Transport-Security", HSTS)
            await send(message)

        await self.app(scope, receive, enviar)


# ------------------------------------------------------------------ límite de tasa
LIMITE_POR_DEFECTO = (
    1200  # peticiones por minuto y por IP (varios dispositivos pueden compartir IP)
)
_MAX_CLAVES = 20_000


def limite_por_minuto() -> int:
    try:
        return int(os.getenv("NA_RATE_LIMIT_PER_MIN", str(LIMITE_POR_DEFECTO)))
    except ValueError:
        return LIMITE_POR_DEFECTO


def _limitada(method: str, path: str) -> bool:
    """Escrituras de la API y síntesis: lo que cuesta CPU o llena la base de datos."""
    if path == "/api/health" or path.startswith("/api/health/"):
        return False
    if path.startswith("/api/synthesize"):
        return True
    return path.startswith("/api/") and method in {"POST", "PUT", "PATCH", "DELETE"}


class RateLimitMiddleware:
    """Cubeta de fichas por IP (capacidad = límite por minuto; se repone de forma continua)."""

    def __init__(self, app: ASGIApp, reloj: Callable[[], float] = time.monotonic) -> None:
        self.app = app
        self.reloj = reloj
        self.cubetas: dict[str, tuple[float, float]] = {}

    def _ip(self, scope: Scope) -> str:
        if _bool(os.getenv("NA_TRUST_PROXY")):
            for k, v in scope.get("headers", []):
                if k == b"x-forwarded-for":
                    return v.decode().split(",")[0].strip() or "?"
        c = scope.get("client")
        return c[0] if c else "?"

    def _permitir(self, ip: str, limite: int) -> float:
        """0 si pasa; si no, segundos hasta poder reintentar."""
        ahora = self.reloj()
        fichas, t = self.cubetas.get(ip, (float(limite), ahora))
        fichas = min(float(limite), fichas + (ahora - t) * limite / 60.0)
        if fichas >= 1.0:
            self.cubetas[ip] = (fichas - 1.0, ahora)
            ok = 0.0
        else:
            self.cubetas[ip] = (fichas, ahora)
            ok = (1.0 - fichas) * 60.0 / limite
        if len(self.cubetas) > _MAX_CLAVES:  # evita que la memoria crezca sin límite
            self.cubetas = {k: v for k, v in self.cubetas.items() if v[0] < limite}
        return ok

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        limite = limite_por_minuto()
        if scope["type"] != "http" or limite <= 0 or not _limitada(scope["method"], scope["path"]):
            await self.app(scope, receive, send)
            return
        # la cubeta es por (IP, límite): cambiar el límite en caliente no hereda fichas gastadas
        espera = self._permitir(f"{self._ip(scope)}|{limite}", limite)
        if espera == 0.0:
            await self.app(scope, receive, send)
            return
        cuerpo = json.dumps(
            {"detail": "demasiadas peticiones; reintente en unos segundos"}
        ).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 429,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(cuerpo)).encode()),
                    (b"retry-after", str(max(1, int(espera + 0.999))).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": cuerpo})
