"""Tarea 1.8 — Material de validación auditiva de la reescritura (script de evaluación, no producción).

Genera unos 50 ítems (nombres propios, siglas, fechas y números grandes) tomados de los
candidatos del corpus y de expresiones numéricas del split dev. Para cada ítem: original,
forma canónica, texto para el TTS (adaptador activo) y, si el ítem está listo para el TTS, su
audio sintetizado con mms-tts-cni (semilla fija). Los ítems bloqueados por falta de P2d se
listan igual, marcados, para cuantificar cuánto depende la reescritura de P2d.

Uso: uv run python -m eval.listening.rewrite_check.build [--no-audio]
Salida: eval/listening/rewrite_check/hoja_escucha.csv (+ audio/*.wav)
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

import yaml
from app.config import CANDIDATES_DIR, get_settings
from app.corpus.loader import load_split
from app.pipeline.normalize.engine import DocumentState, Normalizer
from app.pipeline.tts.adapters.mms_cni import MmsCniAdapter
from app.pipeline.tts.adapters.validate import find_oov

HERE = Path(__file__).parent
SEED = 20261005
NUMERIC_RX = re.compile(r"\d{1,2}/\d{1,2}/\d{4}|\d{4,}|\d+\s?%|S/\.?\s?\d+")


def collect_items(limit: int = 50) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    names = yaml.safe_load((CANDIDATES_DIR / "proper_nouns.yaml").read_text(encoding="utf-8"))
    acr = yaml.safe_load((CANDIDATES_DIR / "acronyms.yaml").read_text(encoding="utf-8"))
    items += [("nombre_propio", n["source_form"]) for n in names[:20]]
    items += [("sigla", a["source_form"]) for a in acr[:15] if a["kind"] == "sigla"][:10]
    seen = set()
    for p in load_split("dev"):
        for m in NUMERIC_RX.finditer(p.cni):
            if m.group(0) not in seen:
                seen.add(m.group(0))
                items.append(("numerico", m.group(0)))
    return items[:limit]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-audio", action="store_true")
    args = ap.parse_args(argv)
    normalizer = Normalizer.from_files()
    adapter = MmsCniAdapter.from_files()
    synth = None
    if not args.no_audio:
        tts_dir = get_settings().models_dir / "facebook__mms-tts-cni"
        if (tts_dir / "model.safetensors").exists():
            import soundfile as sf
            import torch
            from transformers import VitsModel, VitsTokenizer

            tok, model = VitsTokenizer.from_pretrained(tts_dir), VitsModel.from_pretrained(tts_dir)

            def synth(text: str, path: Path, seed: int) -> None:
                torch.manual_seed(seed)
                with torch.no_grad():
                    wav = model(**tok(text, return_tensors="pt")).waveform[0].numpy()
                sf.write(path, wav, model.config.sampling_rate)

    audio_dir = HERE / "audio"
    audio_dir.mkdir(exist_ok=True)
    rows = []
    for i, (kind, original) in enumerate(collect_items()):
        canon = normalizer.normalize(original, DocumentState()).text_canonical
        tts = adapter.adapt(canon).text_tts
        oov = sorted({o.char for o in find_oov(tts, adapter.vocab())})
        status = "listo" if not oov else f"bloqueado (P2d): fuera de vocabulario {''.join(oov)}"
        audio = ""
        if not oov and synth and tts.strip():
            audio = f"audio/{i:03d}.wav"
            synth(tts, HERE / audio, SEED + i)
        rows.append(
            {
                "item": i,
                "tipo": kind,
                "original": original,
                "canonica": canon,
                "texto_tts": tts,
                "estado": status,
                "audio": audio,
                "juicio(aceptable/no_aceptable)": "",
                "comentario": "",
            }
        )
    with open(HERE / "hoja_escucha.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    ready = sum(1 for r in rows if r["estado"] == "listo")
    print(
        f"[1.8] {len(rows)} ítems; {ready} listos para escuchar; {len(rows) - ready} bloqueados "
        "por falta de P2d. Juicio del hablante: pendiente_hablante"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
