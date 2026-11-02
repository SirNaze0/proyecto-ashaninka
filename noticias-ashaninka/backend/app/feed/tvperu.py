"""Lector del RSS de TV Perú (``https://www.tvperu.gob.pe/rss.xml``).

Formato observado el 2026-11-02 (RSS 2.0 de Drupal, 15 ``item``):

- ``title``, ``link`` (``/noticias/{categoria}/{slug}``), ``pubDate`` (RFC 822, UTC), ``guid``
  («144385 at https://www.tvperu.gob.pe») y ``description`` con el **cuerpo completo** en HTML.
- El cuerpo trae párrafos ``<p>``, enlaces «[Lee también: …]», tuits incrustados (``blockquote``),
  vídeos (``iframe``) y, al final, «TAMBIÉN TE PUEDE INTERESAR:» con titulares relacionados y pies de foto.
- El documento empieza con un salto de línea antes de ``<?xml``: se recorta antes de parsear.

Solo biblioteca estándar (``urllib``, ``xml.etree``, ``html.parser``). ``robots.txt`` pide
``Crawl-delay: 10``: el lector hace UNA petición por ciclo.
"""

from __future__ import annotations

import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import urlparse

from app.pipeline.segment import Segmenter

UA_POR_DEFECTO = (
    "Mozilla/5.0 (compatible; NoticiasAshaninka/1.0; lector RSS de un proyecto de tesis "
    "sin fines comerciales)"
)
MAX_BYTES = 5 * 1024 * 1024
# Recorte por noticia (decisión del 2026-11-02: «resumen corto»): BiTAM tarda ~2–6 s por oración
MAX_ORACIONES = 12
MAX_CARACTERES = 2500
MAX_CARACTERES_ORACION = 1000  # límite del servicio BiTAM por oración
MAX_CARACTERES_TITULO = 300

_FIN_DEL_CUERPO = re.compile(r"^tambi[eé]n te puede interesar", re.IGNORECASE)
_LEE_TAMBIEN = re.compile(r"^\[?\s*(lee|lea|mira|ver) tambi[eé]n\b", re.IGNORECASE)
_IGNORAR_DENTRO = {"blockquote", "aside", "script", "style", "iframe", "figure", "figcaption"}


class FuenteNoDisponible(RuntimeError):
    """No se pudo contactar con la fuente (sin red, DNS, tiempo agotado)."""


class FuenteError(RuntimeError):
    """La fuente respondió, pero con un error HTTP o con un documento que no se puede leer."""


@dataclass
class ItemFuente:
    guid: str
    url: str
    titulo: str
    publicado_en: datetime | None
    categoria: str | None
    parrafos: list[str] = field(default_factory=list)


# ------------------------------------------------------------------ descarga
def descargar_rss(url: str, timeout: float = 30.0, user_agent: str = "") -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": user_agent or UA_POR_DEFECTO,
            "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.5",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            datos = r.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as e:  # antes que URLError: es subclase
        raise FuenteError(f"la fuente respondió {e.code}") from e
    except TimeoutError as e:
        raise FuenteNoDisponible(f"la fuente no respondió en {timeout:g} s") from e
    except urllib.error.URLError as e:
        if isinstance(e.reason, TimeoutError):
            raise FuenteNoDisponible(f"la fuente no respondió en {timeout:g} s") from e
        raise FuenteNoDisponible(f"no se pudo conectar con la fuente ({e.reason})") from e
    except OSError as e:
        raise FuenteNoDisponible(f"no se pudo conectar con la fuente ({e})") from e
    if len(datos) > MAX_BYTES:
        raise FuenteError(f"el feed supera {MAX_BYTES // (1024 * 1024)} MB")
    return datos


# ------------------------------------------------------------------ HTML del cuerpo -> párrafos
class _Parrafos(HTMLParser):
    """Texto de cada ``<p>`` que no esté dentro de un tuit, vídeo, recuadro o script."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parrafos: list[str] = []
        self._ignorar = 0
        self._en_p = 0
        self._buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in _IGNORAR_DENTRO:
            self._ignorar += 1
        elif tag == "p":
            self._en_p += 1
            self._buf = []
        elif tag == "br" and self._en_p:
            self._buf.append(" ")

    def handle_endtag(self, tag):
        if tag in _IGNORAR_DENTRO:
            self._ignorar = max(0, self._ignorar - 1)
        elif tag == "p" and self._en_p:
            self._en_p -= 1
            if not self._ignorar:
                self.parrafos.append(" ".join("".join(self._buf).split()))
            self._buf = []

    def handle_data(self, data):
        if self._en_p and not self._ignorar:
            self._buf.append(data)


def parrafos_del_html(html: str) -> list[str]:
    """Párrafos del cuerpo: sin vacíos ni «Lee también»; se corta en «También te puede interesar»."""
    p = _Parrafos()
    p.feed(html or "")
    p.close()
    salida: list[str] = []
    for texto in p.parrafos:
        limpio = texto.replace("\xa0", " ").strip()
        if _FIN_DEL_CUERPO.match(limpio):
            break
        if not limpio or _LEE_TAMBIEN.match(limpio):
            continue
        salida.append(limpio)
    return salida


# ------------------------------------------------------------------ RSS
def _categoria(url: str) -> str | None:
    partes = [x for x in urlparse(url).path.split("/") if x]
    return partes[1] if len(partes) >= 3 and partes[0] == "noticias" else None


def _fecha(texto: str | None) -> datetime | None:
    if not texto:
        return None
    try:
        d = parsedate_to_datetime(texto.strip())
    except (TypeError, ValueError):
        return None
    return d.astimezone(UTC) if d.tzinfo else d.replace(tzinfo=UTC)


def parsear_rss(datos: bytes) -> list[ItemFuente]:
    """Items del feed, en el orden del documento (el más reciente primero en TV Perú)."""
    try:
        raiz = ET.fromstring(datos.lstrip())
    except ET.ParseError as e:
        raise FuenteError(f"el feed no es XML válido ({e})") from e
    canal = raiz.find("channel")
    if canal is None:
        raise FuenteError("el feed no tiene <channel>")
    items: list[ItemFuente] = []
    for it in canal.findall("item"):
        url = (it.findtext("link") or "").strip()
        titulo = " ".join((it.findtext("title") or "").split())
        guid = (it.findtext("guid") or url).strip()
        if not (url and titulo and guid):
            continue
        items.append(
            ItemFuente(
                guid=guid,
                url=url,
                titulo=titulo,
                publicado_en=_fecha(it.findtext("pubDate")),
                categoria=_categoria(url),
                parrafos=parrafos_del_html(it.findtext("description") or ""),
            )
        )
    return items


# ------------------------------------------------------------------ recorte
def recortar(
    parrafos: list[str],
    max_oraciones: int = MAX_ORACIONES,
    max_caracteres: int = MAX_CARACTERES,
    segmenter: Segmenter | None = None,
) -> list[str]:
    """Primeras oraciones completas (sin partir ninguna) dentro de los dos límites.

    Usa el mismo ``Segmenter`` que la traducción, así que el recorte coincide con las oraciones que
    luego recibe BiTAM. Las oraciones de más de 1.000 caracteres (tablas, listas pegadas) se omiten.
    """
    seg = segmenter or Segmenter.from_files()
    por_parrafo: dict[int, list[str]] = {}
    n = total = 0
    for span in seg.segment("\n".join(parrafos)):
        texto = span.text.strip()
        if not texto or len(texto) > MAX_CARACTERES_ORACION:
            continue
        if n >= max_oraciones or (n and total + len(texto) > max_caracteres):
            break
        por_parrafo.setdefault(span.paragraph_idx, []).append(texto)
        n += 1
        total += len(texto) + 1
    return [" ".join(v) for _, v in sorted(por_parrafo.items())]


def titulo_recortado(titulo: str) -> str:
    return (
        titulo
        if len(titulo) <= MAX_CARACTERES_TITULO
        else titulo[: MAX_CARACTERES_TITULO - 1] + "…"
    )
