"""Definición y validación de los cuestionarios (fuente: ``resources/questionnaire.yaml``)."""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path
from typing import Any

import yaml

RESOURCES = Path(__file__).parent / "resources"
KINDS = ("post_noticia", "final")

# Patrones de datos personales que no deben llegar ni en el comentario libre (tarea 5.5)
_PII = [
    ("correo", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")),
    ("enlace o usuario", re.compile(r"https?://|www\.|(?<!\w)@\w{3,}")),
    ("número largo (teléfono o documento)", re.compile(r"(?:\d[\s.-]?){7,}")),
]


def detectar_pii(texto: str, numeros: bool = True) -> str | None:
    """Nombre del tipo de dato personal que parece contener ``texto`` (o ``None``).

    ``numeros=False`` omite la regla de números largos, para columnas que por definición llevan
    cifras (fechas ISO, JSON con claves cerradas) y la darían como falso positivo.
    """
    for nombre, rx in _PII:
        if not numeros and nombre.startswith("número"):
            continue
        if rx.search(texto):
            return nombre
    return None


@cache
def cargar() -> dict[str, Any]:
    return yaml.safe_load((RESOURCES / "questionnaire.yaml").read_text(encoding="utf-8"))


def items(kind: str) -> list[dict[str, Any]]:
    if kind not in KINDS:
        raise ValueError(f"tipo de cuestionario desconocido: {kind}")
    return cargar()[kind]


def validar(kind: str, answers: dict[str, Any]) -> dict[str, Any]:
    """Valida ``answers`` contra el instrumento y devuelve una copia limpia.

    Lanza ``ValueError`` con un mensaje claro: claves desconocidas o faltantes, valores fuera de
    rango, opciones inválidas, ranking que no es permutación o texto con datos personales.
    """
    defs = {i["id"]: i for i in items(kind)}
    extra = set(answers) - set(defs)
    if extra:
        raise ValueError(f"ítems desconocidos: {sorted(extra)}")
    limpio: dict[str, Any] = {}
    for iid, d in defs.items():
        v = answers.get(iid)
        if v is None or v == "":
            if d.get("opcional"):
                continue
            raise ValueError(f"falta responder: {iid}")
        tipo = d["tipo"]
        if tipo == "binario":
            if isinstance(v, bool) or v not in (0, 1):
                raise ValueError(f"{iid}: debe ser 0 o 1")
        elif tipo == "entero":
            if isinstance(v, bool) or not isinstance(v, int) or not d["min"] <= v <= d["max"]:
                raise ValueError(f"{iid}: debe ser un entero entre {d['min']} y {d['max']}")
        elif tipo == "opcion":
            if v not in d["opciones"]:
                raise ValueError(f"{iid}: opción no válida")
        elif tipo == "texto":
            if not isinstance(v, str) or len(v) > d["max"]:
                raise ValueError(f"{iid}: texto de hasta {d['max']} caracteres")
            pii = detectar_pii(v)
            if pii:
                raise ValueError(f"{iid}: parece contener datos personales ({pii})")
            v = v.strip()
        limpio[iid] = v
    if kind == "final":
        ranks = sorted(limpio[f"rank_{c}"] for c in ("C1", "C2", "C3", "C4"))
        if ranks != [1, 2, 3, 4]:
            raise ValueError("el ranking debe usar los puestos 1, 2, 3 y 4 una sola vez")
    return limpio


def comprension(answers: dict[str, Any]) -> float:
    """Proporción de aciertos de los 4 ítems de comprensión (0-1)."""
    return sum(answers[f"comp_{i}"] for i in range(1, 5)) / 4


def aceptabilidad(answers: dict[str, Any]) -> float:
    return (answers["acep_facilidad"] + answers["acep_agrado"] + answers["acep_confianza"]) / 3
