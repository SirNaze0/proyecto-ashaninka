"""Traducción BiTAM (MejoraEIntegracion, Fase 2): segmentación, límites y restauración de mayúsculas.

Usa el motor falso: no necesita el servicio ni la GPU. Las salidas "cni" de estas pruebas son
cadenas de prueba, no asháninka real.
"""

from __future__ import annotations

import pytest
from app.translation import (
    FakeTranslator,
    TextoDemasiadoLargo,
    TranslationResult,
    restaurar_mayusculas,
    traducir_noticia,
)
from app.translation.service import MAX_ORACIONES, dividir

pytestmark = pytest.mark.smoke


# ------------------------------------------------------------------ mayúsculas
@pytest.mark.parametrize(
    ("fuente", "salida", "esperado"),
    [
        # nombre propio fuera del inicio -> forma de la fuente
        ("Me mudé a Texas.", "nosabikashita texas.", "Nosabikashita Texas."),
        # BiTAM quita tildes: se recupera la forma exacta de la fuente
        ("Llegó al Perú ayer.", "ijatake peru", "Ijatake Perú"),
        # sigla, incluso al inicio de la oración fuente
        ("ONU informó sobre Pichanaki.", "onu ikantake pichanaki", "ONU ikantake Pichanaki"),
        # palabra que no está en la fuente: no se toca (solo la mayúscula inicial)
        ("El río creció.", "osheki inkani", "Osheki inkani"),
        # nombre propio al INICIO de la fuente es ambiguo: no se usa para la regla 1
        ("Pichanaki tiene agua.", "abc pichanaki", "Abc pichanaki"),
        # fuente en minúscula inicial: no se fuerza mayúscula
        ("y luego Lima.", "ari lima", "ari Lima"),
        # dígitos y signos intactos
        ("Son 25 niños en Satipo.", "25 jananeki satipo.", "25 Jananeki Satipo."),
        # nombre compuesto
        ("Viajó a San Ramón.", "ijatake san ramon", "Ijatake San Ramón"),
    ],
)
def test_restaurar_mayusculas(fuente: str, salida: str, esperado: str) -> None:
    assert restaurar_mayusculas(fuente, salida) == esperado


def test_restaurar_mayusculas_no_inventa_ni_borra_palabras() -> None:
    salida = "isaikayeti isha anampiki"
    r = restaurar_mayusculas("Mi abuela vive en la comunidad.", salida)
    assert r.lower() == salida  # solo cambia mayúsculas
    assert restaurar_mayusculas("Hola.", "") == ""


# ------------------------------------------------------------------ segmentación
def test_dividir_por_parrafos_y_oraciones_con_abreviaturas() -> None:
    cuerpo = "La Dra. Rojas llegó. Habló con todos.\n\nEl Sr. Pérez respondió."
    assert dividir(cuerpo) == [
        (0, "La Dra. Rojas llegó."),
        (0, "Habló con todos."),
        (1, "El Sr. Pérez respondió."),
    ]


# ------------------------------------------------------------------ borrador completo
def test_traducir_noticia_arma_el_borrador() -> None:
    fake = FakeTranslator()
    b = traducir_noticia(
        "Lluvias en Satipo", "Llovió mucho. El río creció.\n\nNo hay heridos.", fake
    )
    # UNA sola llamada por lotes: título + 3 oraciones
    assert fake.llamadas == [
        ["Lluvias en Satipo", "Llovió mucho.", "El río creció.", "No hay heridos."]
    ]
    assert b.titulo_cni == "Lluvias en Satipo [fake-bitam]"
    assert b.paragraphs == [
        "Llovió mucho. [fake-bitam] El río creció. [fake-bitam]",
        "No hay heridos. [fake-bitam]",
    ]
    assert [o.parrafo for o in b.oraciones] == [-1, 0, 0, 1]
    assert b.oraciones[1].cni_modelo == "llovió mucho. [fake-bitam]"
    assert b.procedencia == {
        "tipo": "traduccion_automatica",
        "sistema": "BiTAM es2cni",
        "version": "fake",
        "revisado_por_hablante": False,
        "revisor_id": None,
    }
    assert any("hablante" in a for a in b.avisos)


class _VaciaEnUna:
    def translate_batch(self, texts):
        return TranslationResult(["", *(f"x{i}" for i in range(1, len(texts)))], "m", "v")


def test_avisa_si_una_oracion_vuelve_vacia() -> None:
    b = traducir_noticia("Título", "Una oración.", _VaciaEnUna())
    assert b.titulo_cni == ""
    assert any("sin traducción" in a for a in b.avisos)


# ------------------------------------------------------------------ límites
@pytest.mark.parametrize(
    ("titulo", "cuerpo", "fragmento"),
    [
        ("", "Algo.", "faltan"),
        ("T" * 301, "Algo.", "título"),
        ("T", "a" * 8001, "cuerpo"),
        ("T", " ".join(["Hola."] * (MAX_ORACIONES + 1)), "oraciones"),
        ("T", "a" * 1001 + ".", "divídalas"),
    ],
)
def test_limites(titulo: str, cuerpo: str, fragmento: str) -> None:
    fake = FakeTranslator()
    with pytest.raises(TextoDemasiadoLargo, match=fragmento):
        traducir_noticia(titulo, cuerpo, fake)
    assert fake.llamadas == []  # se valida ANTES de llamar al modelo
