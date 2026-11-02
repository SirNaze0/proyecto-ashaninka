"""Traducción castellano→asháninka con BiTAM (tesis de una compañera), vía servicio HTTP local.

El modelo corre APARTE (``traductor/``, entorno propio: transformers 4.57 / torch 2.6) y el backend
lo llama por HTTP. Ver ``MejoraEIntegracion/PLAN_INTEGRACION.md``.

- ``client``: motores ``http`` (servicio real) y ``fake`` (pruebas), errores tipados.
- ``service``: segmentación, límites, restauración determinista de mayúsculas y borrador con
  procedencia ``traduccion_automatica`` (nunca revisado por hablante).
"""

from app.translation.client import (
    FakeTranslator,
    HttpTranslator,
    TraductorError,
    TraductorNoDisponible,
    TranslationResult,
    Translator,
    get_translator,
)
from app.translation.service import (
    BorradorTraduccion,
    TextoDemasiadoLargo,
    restaurar_mayusculas,
    traducir_noticia,
)

__all__ = [
    "BorradorTraduccion",
    "FakeTranslator",
    "HttpTranslator",
    "TextoDemasiadoLargo",
    "TraductorError",
    "TraductorNoDisponible",
    "TranslationResult",
    "Translator",
    "get_translator",
    "restaurar_mayusculas",
    "traducir_noticia",
]
