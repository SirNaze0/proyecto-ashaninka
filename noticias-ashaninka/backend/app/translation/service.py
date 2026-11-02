"""Traducción de una noticia (castellano → asháninka) en un BORRADOR para revisión de quien redacta.

- Segmenta con el ``Segmenter`` del pipeline (abreviaturas castellanas ya incluidas en
  ``segmentation.yaml``) y envía UNA oración por elemento: BiTAM trunca a 128 tokens.
- BiTAM devuelve minúsculas (ortografía MINEDU 2024). Sin mayúsculas, ``classify`` no reconoce los
  nombres propios, así que se restauran de forma DETERMINISTA (``restaurar_mayusculas``).
- No guarda nada: quien redacta revisa y publica con el flujo normal (``POST /api/news``).
- La procedencia sale como ``traduccion_automatica`` y ``revisado_por_hablante=False``: solo un
  hablante puede cambiarlo (contrato §2 de PLAN_DESARROLLO.md, regla 4).
"""

from __future__ import annotations

import re
import time
import unicodedata
from dataclasses import dataclass, field

from app.pipeline.segment import Segmenter
from app.translation.client import CARACTERES_MAX_ORACION, Translator

MAX_CARACTERES_TITULO = 300
MAX_CARACTERES_CUERPO = 8000
MAX_ORACIONES = 80

# Palabras: solo letras (incluye tildes y ñ); los dígitos y signos no se tocan
_PALABRA = re.compile(r"[^\W\d_]+")


class TextoDemasiadoLargo(ValueError):
    """La noticia supera los límites de traducción (se responde 422)."""


@dataclass(frozen=True)
class OracionTraducida:
    parrafo: int  # -1 = título
    es: str
    cni_modelo: str  # salida cruda de BiTAM (minúsculas)
    cni: str  # tras restaurar mayúsculas


@dataclass
class BorradorTraduccion:
    titulo_cni: str
    paragraphs: list[str]
    oraciones: list[OracionTraducida]
    procedencia: dict
    modelo: str
    segundos: float
    avisos: list[str] = field(default_factory=list)


def _clave(palabra: str) -> str:
    """Comparación sin mayúsculas ni tildes (BiTAM quita las tildes: «Perú» → «peru»)."""
    base = unicodedata.normalize("NFD", palabra.lower())
    return "".join(c for c in base if unicodedata.category(c) != "Mn")


def restaurar_mayusculas(fuente_es: str, salida_cni: str) -> str:
    """Restaura mayúsculas en la salida de BiTAM usando SOLO la oración fuente (determinista).

    1. Una palabra de la salida que coincide (sin mayúsculas ni tildes) con una palabra de la fuente
       escrita con mayúscula inicial FUERA del inicio de oración (nombre propio o sigla) recupera la
       forma exacta de la fuente: ``texas`` → ``Texas``, ``peru`` → ``Perú``, ``onu`` → ``ONU``.
       También cuentan las siglas en mayúsculas al inicio de la fuente (``ONU informó…``).
    2. Si la fuente empieza con mayúscula, la primera letra de la salida pasa a mayúscula.

    No inventa formas: solo copia de la fuente o pone mayúscula inicial. Un nombre propio que
    está al inicio de la oración fuente es ambiguo y no se usa en la regla 1.
    """
    palabras = list(_PALABRA.finditer(fuente_es))
    propios: dict[str, str] = {}
    for i, m in enumerate(palabras):
        w = m.group()
        sigla = len(w) > 1 and w.isupper()
        if (i > 0 and w[0].isupper()) or sigla:
            propios.setdefault(_clave(w), w)

    salida = _PALABRA.sub(lambda m: propios.get(_clave(m.group()), m.group()), salida_cni)

    primera_fuente = re.search(r"[^\W\d_]", fuente_es)
    if primera_fuente and primera_fuente.group().isupper():
        m = re.search(r"[^\W\d_]", salida)
        if m:
            salida = salida[: m.start()] + m.group().upper() + salida[m.end() :]
    return salida


def dividir(cuerpo_es: str, segmenter: Segmenter | None = None) -> list[tuple[int, str]]:
    """(índice de párrafo, oración) del cuerpo; los párrafos se separan por saltos de línea."""
    seg = segmenter or Segmenter.from_files()
    return [(s.paragraph_idx, s.text) for s in seg.segment(cuerpo_es)]


def _validar(titulo_es: str, cuerpo_es: str, oraciones: list[tuple[int, str]]) -> None:
    if not titulo_es.strip() or not cuerpo_es.strip():
        raise TextoDemasiadoLargo("faltan el título o el cuerpo en castellano")
    if len(titulo_es) > MAX_CARACTERES_TITULO:
        raise TextoDemasiadoLargo(f"el título supera {MAX_CARACTERES_TITULO} caracteres")
    if len(cuerpo_es) > MAX_CARACTERES_CUERPO:
        raise TextoDemasiadoLargo(f"el cuerpo supera {MAX_CARACTERES_CUERPO} caracteres")
    if len(oraciones) > MAX_ORACIONES:
        raise TextoDemasiadoLargo(f"el cuerpo tiene más de {MAX_ORACIONES} oraciones")
    largas = [i + 1 for i, (_, o) in enumerate(oraciones) if len(o) > CARACTERES_MAX_ORACION]
    if largas:
        raise TextoDemasiadoLargo(
            f"oraciones de más de {CARACTERES_MAX_ORACION} caracteres: {largas}; divídalas"
        )


def traducir_noticia(titulo_es: str, cuerpo_es: str, translator: Translator) -> BorradorTraduccion:
    """Traduce título y cuerpo en UNA sola llamada por lotes y arma el borrador."""
    oraciones = dividir(cuerpo_es)
    _validar(titulo_es, cuerpo_es, oraciones)
    titulo = " ".join(titulo_es.split())
    fuentes = [titulo, *(o for _, o in oraciones)]

    t0 = time.perf_counter()
    res = translator.translate_batch(fuentes)
    segundos = round(time.perf_counter() - t0, 3)

    traducidas = [
        OracionTraducida(p, es, crudo, restaurar_mayusculas(es, crudo))
        for (p, es), crudo in zip([(-1, titulo), *oraciones], res.translations, strict=True)
    ]
    n_parrafos = max((p for p, _ in oraciones), default=-1) + 1
    paragraphs = [
        " ".join(o.cni.strip() for o in traducidas if o.parrafo == p and o.cni.strip())
        for p in range(n_parrafos)
    ]
    avisos = [
        "Traducción automática (BiTAM, chrF++ ≈ 25): es un borrador; debe revisarla un hablante "
        "antes de usarla en el experimento."
    ]
    vacias = sum(1 for o in traducidas if o.es.strip() and not o.cni.strip())
    if vacias:
        avisos.append(f"{vacias} oración(es) sin traducción: revíselas a mano.")
    return BorradorTraduccion(
        titulo_cni=traducidas[0].cni,
        paragraphs=[p for p in paragraphs if p],
        oraciones=traducidas,
        procedencia={
            "tipo": "traduccion_automatica",
            "sistema": "BiTAM es2cni",
            "version": res.version,
            "revisado_por_hablante": False,
            "revisor_id": None,
        },
        modelo=res.modelo,
        segundos=segundos,
        avisos=avisos,
    )
