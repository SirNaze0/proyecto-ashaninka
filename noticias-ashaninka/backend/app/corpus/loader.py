"""Carga del corpus AmericasNLP 2021 asháninka–castellano con verificación de hashes.

El corpus no se redistribuye: lo descarga ``init.sh`` en ``data/corpus/americasnlp2021/``.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from app.config import CORPUS_DIR

SPLITS = ("train", "dev", "test")

# SHA-256 de los archivos en el commit d3f519c (calculados el 2026-10-05)
EXPECTED_SHA256 = {
    "train.cni": "dd528a5b61284dde62d1c957a8e7bdbad296f40cb9ed128b592e5aaa9bdf6d84",
    "train.es": "d86a5aecc2b9ea0e1ac684cb1984d8fb6420482c8d750d3ed58d04739348002e",
    "dev.cni": "90c85ba9bee92e3ff871e3128a6d2f376387978d108538f552d87874b9f35161",
    "dev.es": "5ea9455bee5e67f56db261a7969cf410a8f833305afc669cc6d5ee39ef7b10d3",
    "test.cni": "9927b2daa5a4d607945cfed06bfd83a83517fa455af31d0753e911d9a0a1e004",
    "test.es": "a30e58fe429dcaeaf17699e38e2e23ffc13722ae530c4c724f9855d26c73aa8f",
}


class CorpusError(RuntimeError):
    pass


@dataclass(frozen=True)
class Pair:
    split: str
    line: int  # 1-based, como en un editor de texto
    cni: str
    es: str

    @property
    def ref(self) -> str:
        return f"{self.split}:{self.line}"


def corpus_available(base: Path = CORPUS_DIR) -> bool:
    return all((base / name).exists() for name in EXPECTED_SHA256)


def verify(base: Path = CORPUS_DIR) -> None:
    for name, expected in EXPECTED_SHA256.items():
        path = base / name
        if not path.exists():
            raise CorpusError(f"Falta {path}. Ejecuta ./init.sh para descargar el corpus.")
        got = hashlib.sha256(path.read_bytes()).hexdigest()
        if got != expected:
            raise CorpusError(f"Hash distinto en {name}: esperado {expected}, obtenido {got}")


def read_lines(path: Path) -> list[str]:
    # splitlines() para ser robustos a CRLF; se conserva el contenido tal cual
    return path.read_text(encoding="utf-8").splitlines()


def load_split(split: str, base: Path = CORPUS_DIR, check: bool = True) -> list[Pair]:
    if split not in SPLITS:
        raise ValueError(f"split desconocido: {split}")
    if check:
        verify(base)
    cni = read_lines(base / f"{split}.cni")
    es = read_lines(base / f"{split}.es")
    if len(cni) != len(es):
        raise CorpusError(f"{split}: {len(cni)} líneas cni frente a {len(es)} es")
    return [Pair(split, i + 1, c, e) for i, (c, e) in enumerate(zip(cni, es, strict=True))]
