"""Verificación de privacidad de la exportación (tarea 5.5).

La exportación no debe traer identificadores personales: ni columnas con esos nombres ni valores que
parezcan correos, enlaces, teléfonos o documentos. El único identificador es el código anónimo
del participante (``P007``), que no se puede vincular a una persona sin la lista del equipo.
"""

from __future__ import annotations

import re
from typing import Any

from app.experiment.instrumentos import detectar_pii

# Un nombre de columna es sospechoso si alguno de sus términos (separados por «_») está aquí
PALABRAS_PROHIBIDAS = frozenset(
    {
        "nombre",
        "apellido",
        "dni",
        "documento",
        "telefono",
        "celular",
        "email",
        "correo",
        "direccion",
        "latitud",
        "longitud",
        "lat",
        "lon",
        "geo",
        "ip",
        "agent",
        "device",
        "dispositivo",
        "imei",
    }
)
COLUMNAS_PROHIBIDAS = frozenset({"edad", "session_id"})  # edad exacta; el UUID del dispositivo
# Columnas que llevan cifras por definición (fecha ISO; JSON con claves cerradas y valores escalares)
SIN_REGLA_NUMERICA = frozenset({"t_client", "payload"})
_UUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)


def columna_sospechosa(nombre: str) -> bool:
    n = nombre.lower()
    return n in COLUMNAS_PROHIBIDAS or bool(set(n.split("_")) & PALABRAS_PROHIBIDAS)


def verificar_sin_pii(tablas: dict[str, list[dict[str, Any]]]) -> list[str]:
    """Devuelve la lista de problemas encontrados (vacía = la exportación es privada)."""
    problemas: list[str] = []
    for tabla, filas in tablas.items():
        columnas = {c for f in filas for c in f}
        for c in sorted(columnas):
            if columna_sospechosa(c):
                problemas.append(f"{tabla}: columna prohibida «{c}»")
        for i, f in enumerate(filas):
            for c, v in f.items():
                if not isinstance(v, str):
                    continue
                pii = detectar_pii(v, numeros=c not in SIN_REGLA_NUMERICA)
                if pii:
                    problemas.append(f"{tabla}[{i}].{c}: parece contener {pii}")
                elif _UUID.search(v):
                    problemas.append(f"{tabla}[{i}].{c}: contiene un identificador de dispositivo")
    return problemas
