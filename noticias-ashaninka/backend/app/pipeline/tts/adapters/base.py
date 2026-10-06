"""Interfaz de los adaptadores ortográficos (2e): ortografía canónica -> ortografía del motor TTS."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.pipeline.types import AdaptedText


class OrthographyAdapter(ABC):
    id: str

    @abstractmethod
    def adapt(self, text_canonical: str) -> AdaptedText:
        """Devuelve el texto en la ortografía del motor y el mapa de caracteres canónico->motor."""

    @abstractmethod
    def vocab(self) -> set[str]:
        """Conjunto de símbolos que acepta el motor."""
