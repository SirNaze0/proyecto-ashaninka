"""Seguridad de la API (Fase 6): cabeceras y límite de tasa.

- **Sin roles.** Desde QuitarAdmin (2026-11) no hay token administrativo: todas las rutas son
  públicas, incluidas las de escritura de noticias y la exportación del experimento. Lo único que
  frena el abuso es el límite de tasa por IP (ver ``docs/limitations.md``).
- **Cabeceras** de seguridad y CSP en toda respuesta. HSTS solo cuando la conexión es HTTPS.
- **Límite de tasa** por IP, en memoria, para las rutas públicas de escritura y la síntesis.

Los middlewares son ASGI puros (no ``BaseHTTPMiddleware``) para no interferir con el streaming
NDJSON de ``/api/synthesize`` ni con las respuestas parciales (``Range``) de ``/static``.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

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
