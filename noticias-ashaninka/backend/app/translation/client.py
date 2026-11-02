"""Clientes del traductor BiTAM: servicio HTTP local (``traductor/servidor.py``) o falso para pruebas.

Contrato del servicio (Fase 1 de MejoraEIntegracion):
  POST {url}/traducir  {"texts": [...]}  ->  {"translations": [...], "modelo": str, "version": str}
  máx. 64 oraciones por petición y 1000 caracteres por oración (si no, 422)

Se usa ``urllib`` de la biblioteca estándar para no añadir dependencias al backend.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from app.config import Settings, get_settings

# Límites del servicio (traductor/servidor.py): se trocea por debajo de ellos
LOTE_MAX = 64
CARACTERES_MAX_ORACION = 1000


class TraductorNoDisponible(RuntimeError):
    """El servicio no está configurado o no responde (conexión rechazada, tiempo agotado)."""


class TraductorError(RuntimeError):
    """El servicio respondió, pero con un error o con una respuesta inválida."""

    def __init__(self, mensaje: str, status: int | None = None):
        super().__init__(mensaje)
        self.status = status


@dataclass(frozen=True)
class TranslationResult:
    translations: list[str]
    modelo: str
    version: str


class Translator(Protocol):
    def translate_batch(self, texts: Sequence[str]) -> TranslationResult: ...


class HttpTranslator:
    """Llama al servicio BiTAM local. Trocea en lotes de ``LOTE_MAX`` oraciones."""

    def __init__(self, url: str, timeout: float = 120.0):
        self.url = url.rstrip("/")
        self.timeout = timeout

    def _post(self, texts: list[str]) -> dict:
        req = urllib.request.Request(
            f"{self.url}/traducir",
            data=json.dumps({"texts": texts}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:  # antes que URLError: es subclase
            raise TraductorError(f"el traductor respondió {e.code}", status=e.code) from e
        except TimeoutError as e:  # incluye socket.timeout (alias desde Python 3.10)
            raise TraductorNoDisponible(f"el traductor no respondió en {self.timeout:g} s") from e
        except urllib.error.URLError as e:
            if isinstance(e.reason, TimeoutError):
                raise TraductorNoDisponible(
                    f"el traductor no respondió en {self.timeout:g} s"
                ) from e
            raise TraductorNoDisponible(f"no se pudo conectar con el traductor ({e.reason})") from e
        except (ConnectionError, OSError) as e:
            raise TraductorNoDisponible(f"no se pudo conectar con el traductor ({e})") from e
        except ValueError as e:  # JSON inválido
            raise TraductorError("respuesta del traductor no es JSON válido") from e

    def translate_batch(self, texts: Sequence[str]) -> TranslationResult:
        textos = list(texts)
        salidas: list[str] = []
        modelo = version = ""
        for k in range(0, len(textos), LOTE_MAX):
            lote = textos[k : k + LOTE_MAX]
            d = self._post(lote)
            trad = d.get("translations")
            if not isinstance(trad, list) or len(trad) != len(lote):
                raise TraductorError("el traductor devolvió un número de traducciones distinto")
            salidas.extend(str(t) for t in trad)
            modelo, version = str(d.get("modelo", "")), str(d.get("version", ""))
        return TranslationResult(salidas, modelo or "BiTAM es2cni", version or "desconocida")


class FakeTranslator:
    """Para pruebas: NO produce asháninka. Devuelve la entrada en minúsculas (como BiTAM, que
    normaliza a minúsculas) marcada con ``[fake-bitam]`` al final, para que nunca se confunda con
    una traducción real."""

    modelo = "BiTAM es2cni (fake)"
    version = "fake"

    def __init__(self) -> None:
        self.llamadas: list[list[str]] = []

    def translate_batch(self, texts: Sequence[str]) -> TranslationResult:
        self.llamadas.append(list(texts))
        out = [f"{t.strip().lower()} [fake-bitam]" if t.strip() else "" for t in texts]
        return TranslationResult(out, self.modelo, self.version)


def get_translator(settings: Settings | None = None) -> Translator:
    """Motor según ``NA_TRANSLATOR_ENGINE`` (``http`` | ``fake``)."""
    s = settings or get_settings()
    if s.translator_engine == "fake":
        return FakeTranslator()
    if s.translator_engine != "http":
        raise TraductorNoDisponible(f"NA_TRANSLATOR_ENGINE desconocido: {s.translator_engine!r}")
    if not s.translator_url:
        raise TraductorNoDisponible(
            "traductor no configurado: defina NA_TRANSLATOR_URL (p. ej. http://127.0.0.1:8100)"
        )
    return HttpTranslator(s.translator_url, s.translator_timeout)
