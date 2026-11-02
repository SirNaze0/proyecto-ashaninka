"""Medición de la integración BiTAM (eval.traductor.run): disciplina de splits y auxiliares."""

from __future__ import annotations

from pathlib import Path

import pytest

from eval.traductor.run import (
    candidatos_propios,
    cargar_pares,
    propios_detectados,
    vv_por_100_palabras,
)

pytestmark = pytest.mark.smoke


@pytest.mark.parametrize("split", ["test", "train", "TEST"])
def test_rechaza_cualquier_split_que_no_sea_dev(split: str, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="solo dev"):
        cargar_pares(tmp_path, split)


def test_dev_con_hash_distinto_se_rechaza(tmp_path: Path) -> None:
    (tmp_path / "dev.es").write_text("Hola.\n", encoding="utf-8")
    (tmp_path / "dev.cni").write_text("x\n", encoding="utf-8")
    with pytest.raises(ValueError, match="hash distinto"):
        cargar_pares(tmp_path, "dev")


def test_candidatos_propios_misma_regla_que_la_restauracion() -> None:
    assert candidatos_propios("Me mudé a Texas con la ONU.") == ["Texas", "ONU"]
    assert candidatos_propios("Pichanaki tiene agua.") == []  # inicio: ambiguo
    assert candidatos_propios("ONU informó.") == ["ONU"]  # sigla al inicio sí cuenta


def test_vocales_dobles_por_100_palabras() -> None:
    assert vv_por_100_palabras(["kameetsa piiri", "aa"]) == pytest.approx(100.0)
    assert vv_por_100_palabras(["kametsa piri"]) == 0.0
    assert vv_por_100_palabras([]) == 0.0


def test_propios_detectados_cuenta_ambas_categorias() -> None:
    segs = [
        {"alignment_map": [{"category": "nombre_propio"}, {"category": "nativa"}]},
        {"alignment_map": [{"category": "nombre_propio_nativo"}]},
    ]
    assert propios_detectados(segs) == 2
