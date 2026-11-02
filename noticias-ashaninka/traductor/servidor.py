"""Servicio local de traducción castellano→asháninka con BiTAM (tesis de una compañera).

Corre en su PROPIO entorno (traductor/pyproject.toml): BiTAM exige transformers 4.57.3 y
torch 2.6.0, incompatibles con el backend. El backend lo llama por HTTP (Fase 2 de
MejoraEIntegracion). Arranque: ``run.ps1`` / ``run.sh`` (escucha SOLO en 127.0.0.1).

Endpoints:
  POST /traducir  {"texts": [...]} -> {"translations": [...], "modelo", "version"}
                  (una oración por elemento; máx. 64 oraciones y 1000 caracteres por oración)
  GET  /salud     modelo, run, dispositivo y dtype reales, versiones, tiempo de carga, VRAM

Variables de entorno:
  BITAM_MODELS_DIR  carpeta ``modelos/`` de la entrega (fuera del repositorio; los pesos no se
                    redistribuyen)
  BITAM_DEVICE      auto | cuda | cpu (por defecto: auto)
  BITAM_DTYPE       float16 | bfloat16 | float32 | config (por defecto: float16 en GPUs sin bf16
                    nativo, como pretende ``bitam``; ``config`` = el de la entrega, bfloat16)
  BITAM_FAKE=1      traductor falso para pruebas: NO carga el modelo y NO produce asháninka
                    (devuelve el texto marcado con ``[fake-bitam]``)
"""

from __future__ import annotations

import os
import re
import time
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Annotated, Any, Protocol

from fastapi import FastAPI, Request
from pydantic import BaseModel, Field, StringConstraints

MODELO = "BiTAM es2cni"
DIRECCION = "es2cni"
MAX_ORACIONES = 64
MAX_CARACTERES = 1000
# Run del modelo entregado; se lee de la primera línea de modelos/v5_es2cni/config.yaml
_RE_RUN = re.compile(r"\((bitam_[^)\s]+)\)")


class Motor(Protocol):
    version: str
    dispositivo: str
    dtype: str

    def traducir(self, textos: Sequence[str]) -> list[str]: ...


@dataclass
class MotorFalso:
    """Para pruebas sin GPU ni pesos. No imita asháninka: marca el texto de entrada."""

    version: str = "fake"
    dispositivo: str = "cpu"
    dtype: str = "none"
    llamadas: list[list[str]] = field(default_factory=list)

    def traducir(self, textos: Sequence[str]) -> list[str]:
        self.llamadas.append(list(textos))
        return [f"[fake-bitam] {t.strip().lower()}" if t.strip() else "" for t in textos]


class MotorBitam:
    """Envuelve ``bitam.BitamTranslator`` (dirección es2cni) de la entrega.

    Replica ``BitamTranslator.load`` solo para poder pasar, además del dispositivo, el dtype de
    cómputo como *override* de la configuración (no se modifica el código de la entrega).
    """

    def __init__(self, models_dir: str | None, device: str | None, dtype: str | None) -> None:
        from bitam import api as bitam_api
        from bitam.config import load_config
        from bitam.inference import Translator
        from bitam.utils.logging import set_level

        set_level("WARNING")
        model_dir = bitam_api._models_dir(models_dir) / bitam_api.DIRECTIONS[DIRECCION]
        cfg_path = model_dir / "config.yaml"
        if not cfg_path.is_file():
            raise FileNotFoundError(f"no se encuentra {cfg_path}; define BITAM_MODELS_DIR")
        overrides: dict[str, Any] = {}
        if device:
            overrides["device"] = device
        if dtype:
            overrides["compute_dtype"] = dtype
        cfg = load_config(
            cfg_path,
            overrides={"model": overrides} if overrides else None,
            project_root=bitam_api.PACKAGE_DIR,
        )
        translator = Translator.from_config(cfg, DIRECCION, model_dir / "peft")
        self._tr = bitam_api.BitamTranslator(translator, DIRECCION, model_dir)
        self.version = leer_run(self._tr.model_dir / "config.yaml")
        modelo = self._tr._translator.model  # TranslationModel de bitam (atributos públicos)
        param = next(modelo.model.parameters())
        self.dispositivo = str(param.device)
        self.dtype = str(param.dtype).removeprefix("torch.")

    def traducir(self, textos: Sequence[str]) -> list[str]:
        return self._tr.translate_batch(list(textos), batch_size=8)


def leer_run(config_yaml: Path) -> str:
    """Nombre del run entrenado, tal como lo declara el comentario inicial de config.yaml."""
    try:
        primera = config_yaml.read_text(encoding="utf-8").splitlines()[0]
    except (OSError, IndexError):
        return "desconocida"
    m = _RE_RUN.search(primera)
    return m.group(1) if m else "desconocida"


def _version(paquete: str) -> str | None:
    try:
        return version(paquete)
    except PackageNotFoundError:
        return None


def _vram_max_mb() -> float | None:
    try:
        import torch
    except ImportError:
        return None
    if not torch.cuda.is_available():
        return None
    return round(torch.cuda.max_memory_allocated() / 2**20, 1)


def dtype_por_defecto() -> str | None:
    """dtype de cómputo cuando BITAM_DTYPE no está definido.

    La config entregada pide ``bfloat16`` y ``bitam`` pretende pasar a ``float16`` en GPUs sin bf16
    (``model.resolve_compute_dtype``), pero en torch 2.6 ``torch.cuda.is_bf16_supported()`` cuenta
    la EMULACIÓN y devuelve True en GPUs anteriores a Ampere (p. ej. GTX 1060, sm_61), así que el
    respaldo nunca se activa y bf16 corre emulado. Aquí se aplica la intención del código: fp16 si
    la GPU no tiene bf16 nativo (capacidad < 8.0); en otro caso, lo que diga la config.
    """
    try:
        import torch
    except ImportError:
        return None
    if torch.cuda.is_available() and torch.cuda.get_device_capability(0) < (8, 0):
        return "float16"
    return None


def crear_motor() -> Motor:
    if os.environ.get("BITAM_FAKE") == "1":
        return MotorFalso()
    device = os.environ.get("BITAM_DEVICE") or None
    # BITAM_DTYPE=config conserva el dtype de la entrega (bfloat16) sin ajuste automático.
    dtype = os.environ.get("BITAM_DTYPE") or dtype_por_defecto()
    if dtype == "config" or device == "cpu":
        dtype = None
    return MotorBitam(os.environ.get("BITAM_MODELS_DIR") or None, device, dtype)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Se carga UNA vez (~20-30 s y ~3 GB): nunca dentro de una petición.
    t0 = time.perf_counter()
    app.state.motor = crear_motor()
    app.state.carga_s = round(time.perf_counter() - t0, 2)
    yield


app = FastAPI(title="Traductor BiTAM es→cni (local)", lifespan=lifespan)

Oracion = Annotated[str, StringConstraints(max_length=MAX_CARACTERES)]


class Peticion(BaseModel):
    texts: list[Oracion] = Field(min_length=1, max_length=MAX_ORACIONES)


class Respuesta(BaseModel):
    translations: list[str]
    modelo: str
    version: str


@app.post("/traducir", response_model=Respuesta)
def traducir(req: Peticion, request: Request) -> Respuesta:
    # Endpoint síncrono: FastAPI lo ejecuta en un hilo; BitamTranslator serializa con su candado.
    motor: Motor = request.app.state.motor
    return Respuesta(translations=motor.traducir(req.texts), modelo=MODELO, version=motor.version)


@app.get("/salud")
def salud(request: Request) -> dict[str, Any]:
    motor: Motor = request.app.state.motor
    return {
        "modelo": MODELO,
        "direccion": DIRECCION,
        "version": motor.version,
        "dispositivo": motor.dispositivo,
        "dtype": motor.dtype,
        "fake": isinstance(motor, MotorFalso),
        "carga_s": request.app.state.carga_s,
        "vram_max_mb": _vram_max_mb(),
        "limites": {"max_oraciones": MAX_ORACIONES, "max_caracteres": MAX_CARACTERES},
        "versiones": {
            p: _version(p) for p in ("torch", "transformers", "peft", "bitam-infer", "numpy")
        },
    }
