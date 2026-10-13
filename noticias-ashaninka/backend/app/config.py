"""Configuración central. Lee variables NA_* del entorno (y de .env si existe)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Raíz del repositorio: backend/app/config.py -> ../../
ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

PIPELINE_DIR = ROOT / "backend" / "app" / "pipeline"
NORMALIZE_RESOURCES = PIPELINE_DIR / "normalize" / "resources"
G2P_RULES = PIPELINE_DIR / "g2p" / "rules"
ADAPTERS_DIR = PIPELINE_DIR / "tts" / "adapters"
VISEME_RESOURCES = PIPELINE_DIR / "viseme" / "resources"
MMS_VOCAB = ROOT / "backend" / "tests" / "fixtures" / "mms_cni_vocab.json"
CORPUS_DIR = ROOT / "data" / "corpus" / "americasnlp2021"
CANDIDATES_DIR = ROOT / "data" / "candidates"
DOCS_DIR = ROOT / "docs"
RESULTS_DIR = ROOT / "eval" / "results"
STATIC_DIR = ROOT / "static"

# Versiones fijadas (ver PLAN_DESARROLLO.md §3.2 y PROMPT_FASE1.md)
AMERICASNLP_COMMIT = "d3f519c6b38299d8149311e65a369047350e6849"
MMS_TTS_REVISION = "a744890bf8b52fd17ed322d8d995dec6cf77809b"
MMS_ASR_REVISION = "3d33597edbdaaba14a8e858e2c8caa76e3cec0cd"


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "si", "sí"}


def _opt_float(value: str | None) -> float | None:
    return float(value) if value not in (None, "") else None


@dataclass(frozen=True)
class Settings:
    database_url: str
    mms_adapter: str
    allow_candidates: bool
    models_dir: Path
    tts_engine: str
    torch_threads: int
    tts_workers: int
    espeak_path: str | None
    espeak_voice: str
    opus_kbps: int
    max_news_chars: int
    max_concurrent_synth: int
    static_dir: Path
    viseme_smooth_ms: float | None  # None = usar el valor del mapa de visemas
    viseme_lead: float | None


def get_settings() -> Settings:
    db = os.getenv("NA_DATABASE_URL", "sqlite:///data/noticias.db")
    # Las rutas relativas de SQLite se resuelven desde la raíz del repositorio
    if db.startswith("sqlite:///") and not db.startswith("sqlite:////"):
        rel = db.removeprefix("sqlite:///")
        if not Path(rel).is_absolute():
            db = "sqlite:///" + (ROOT / rel).as_posix()
    return Settings(
        database_url=db,
        mms_adapter=os.getenv("NA_MMS_ADAPTER", "H1"),
        allow_candidates=_bool(os.getenv("NA_ALLOW_CANDIDATES")),
        models_dir=ROOT / os.getenv("NA_MODELS_DIR", "models"),
        tts_engine=os.getenv("NA_TTS_ENGINE", "mms_vits"),
        torch_threads=int(os.getenv("NA_TORCH_THREADS", "0")),  # 0 = valor por defecto de torch
        tts_workers=int(os.getenv("NA_TTS_WORKERS", "1")),
        espeak_path=os.getenv("NA_ESPEAK_PATH") or None,
        espeak_voice=os.getenv("NA_ESPEAK_VOICE", "es"),
        opus_kbps=int(os.getenv("NA_OPUS_KBPS", "24")),
        max_news_chars=int(os.getenv("NA_MAX_NEWS_CHARS", "20000")),
        max_concurrent_synth=int(os.getenv("NA_MAX_CONCURRENT_SYNTH", "8")),
        static_dir=ROOT / os.getenv("NA_STATIC_DIR", "static"),
        viseme_smooth_ms=_opt_float(os.getenv("NA_VISEME_SMOOTH_MS")),
        viseme_lead=_opt_float(os.getenv("NA_VISEME_LEAD")),
    )
