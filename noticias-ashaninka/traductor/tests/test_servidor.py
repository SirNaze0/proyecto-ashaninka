"""Pruebas del servicio de traducción con el motor falso (BITAM_FAKE=1): no necesitan GPU ni pesos."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import servidor  # noqa: E402


@pytest.fixture
def cliente(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("BITAM_FAKE", "1")
    with TestClient(servidor.app) as c:
        yield c


def test_salud_motor_falso(cliente: TestClient) -> None:
    r = cliente.get("/salud")
    assert r.status_code == 200
    d = r.json()
    assert d["modelo"] == "BiTAM es2cni"
    assert d["direccion"] == "es2cni"
    assert d["fake"] is True
    assert d["limites"] == {"max_oraciones": 64, "max_caracteres": 1000}
    assert set(d["versiones"]) >= {"torch", "transformers", "peft"}


def test_traducir_devuelve_una_salida_por_oracion(cliente: TestClient) -> None:
    r = cliente.post("/traducir", json={"texts": ["Hola Mundo.", "El río creció."]})
    assert r.status_code == 200
    d = r.json()
    assert d["translations"] == ["[fake-bitam] hola mundo.", "[fake-bitam] el río creció."]
    assert d["modelo"] == "BiTAM es2cni"
    assert d["version"] == "fake"


def test_cadenas_vacias_no_pasan_por_el_modelo(cliente: TestClient) -> None:
    r = cliente.post("/traducir", json={"texts": ["", "   ", "Hola."]})
    assert r.status_code == 200
    assert r.json()["translations"] == ["", "", "[fake-bitam] hola."]


def test_limite_de_oraciones(cliente: TestClient) -> None:
    ok = cliente.post("/traducir", json={"texts": ["a"] * 64})
    assert ok.status_code == 200
    assert cliente.post("/traducir", json={"texts": ["a"] * 65}).status_code == 422


def test_limite_de_caracteres(cliente: TestClient) -> None:
    assert cliente.post("/traducir", json={"texts": ["a" * 1000]}).status_code == 200
    assert cliente.post("/traducir", json={"texts": ["a" * 1001]}).status_code == 422


@pytest.mark.parametrize("cuerpo", [{}, {"texts": []}, {"texts": "hola"}, {"texts": [1]}])
def test_peticiones_invalidas(cliente: TestClient, cuerpo: dict) -> None:
    assert cliente.post("/traducir", json=cuerpo).status_code == 422


@pytest.mark.parametrize(
    ("entorno", "por_defecto", "esperado"),
    [
        ({}, "float16", "float16"),  # GPU sin bf16 nativo: fp16 automático
        ({}, None, None),  # GPU con bf16 nativo o sin GPU: el de la config
        ({"BITAM_DTYPE": "config"}, "float16", None),  # forzar el de la entrega (bf16)
        ({"BITAM_DTYPE": "float32"}, "float16", "float32"),  # override explícito
        ({"BITAM_DEVICE": "cpu"}, "float16", None),  # en CPU bitam usa fp32
    ],
)
def test_seleccion_de_dtype(
    monkeypatch: pytest.MonkeyPatch, entorno: dict, por_defecto: str | None, esperado: str | None
) -> None:
    for var in ("BITAM_FAKE", "BITAM_DTYPE", "BITAM_DEVICE"):
        monkeypatch.delenv(var, raising=False)
    for k, v in entorno.items():
        monkeypatch.setenv(k, v)
    capturado: dict = {}
    monkeypatch.setattr(servidor, "dtype_por_defecto", lambda: por_defecto)
    monkeypatch.setattr(
        servidor, "MotorBitam", lambda models_dir, device, dtype: capturado.update(dtype=dtype)
    )
    servidor.crear_motor()
    assert capturado["dtype"] == esperado


def test_leer_run(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        "# Config de inferencia de BiTAM es2cni (bitam_v5_seed13_20261018T230715Z_es2cni).\nx: 1\n",
        encoding="utf-8",
    )
    assert servidor.leer_run(cfg) == "bitam_v5_seed13_20261018T230715Z_es2cni"
    assert servidor.leer_run(tmp_path / "no_existe.yaml") == "desconocida"
