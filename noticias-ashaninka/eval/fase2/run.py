"""Métricas de la Fase 2 -> eval/results/fase_2.json (nunca se escriben a mano).

Reúne: rendimiento (2.8), dimensionamiento (2.9), inteligibilidad (2.10), tokenización (2.2b),
verificación del hook de duraciones (50 oraciones), codificación (tasas reales de la caché del
banco), disponibilidad (segmentos de dev con audio) y cobertura de pruebas.

Uso: uv run python -m eval.fase2.run
"""

from __future__ import annotations

import json
import statistics
from datetime import UTC, datetime
from pathlib import Path

from app.config import MMS_ASR_REVISION, MMS_TTS_REVISION, RESULTS_DIR, ROOT, get_settings
from app.corpus.loader import load_split
from app.pipeline.normalize.engine import DocumentState, Normalizer
from app.pipeline.tts.adapters.mms_cni import MmsCniAdapter
from app.pipeline.tts.espeak import ESpeakEngine, find_espeak
from app.pipeline.tts.mms_vits import MmsVitsEngine

from eval.rtf_ttfa.bench import OUT as BENCH_OUT
from eval.rtf_ttfa.bench import git_commit, hardware


def load(name: str) -> dict | None:
    p = RESULTS_DIR / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def hook_check(n: int = 50) -> dict:
    norm, ad = Normalizer.from_files(), MmsCniAdapter.from_files()
    eng = MmsVitsEngine()
    checked = max_off = 0
    for p in load_split("dev"):
        t = ad.adapt(norm.normalize(p.cni, DocumentState()).text_canonical).text_tts
        if not t or ad.oov_after(t):
            continue
        r = eng.synthesize(t, checked)
        off = abs(r.durations.total_samples - len(r.wav)) // r.durations.hop_samples
        max_off = max(max_off, off)
        checked += 1
        if checked == n:
            break
    return {
        "oraciones": checked,
        "desfase_max_frames": int(max_off),
        "verificado": checked >= n and max_off <= 1,
        "tokenizacion": eng.tokenization,
    }


def encoding_stats() -> dict:
    opus, mp3, opus_bps, mp3_bps = [], [], [], []
    for meta in Path(BENCH_OUT).glob("static_c1/audio/*/*.json"):
        m = json.loads(meta.read_text(encoding="utf-8"))["meta"]
        opus.append(m["opus_kbps"])
        mp3.append(m["mp3_kbps"])
        opus_bps.append(m["opus_kbps"] * 1000 / 8)
        mp3_bps.append(m["mp3_kbps"] * 1000 / 8)
    if not opus:
        return {"estado": "no_medido (ejecuta eval.rtf_ttfa.bench http)"}
    return {
        "archivos": len(opus),
        "opus_kbps_objetivo": get_settings().opus_kbps,
        "opus_kbps_real_media": round(statistics.fmean(opus), 2),
        "opus_bytes_por_s": round(statistics.fmean(opus_bps)),
        "mp3_kbps_real_media": round(statistics.fmean(mp3), 2),
        "mp3_bytes_por_s": round(statistics.fmean(mp3_bps)),
    }


def availability() -> dict:
    norm, ad = Normalizer.from_files(), MmsCniAdapter.from_files()
    from app.pipeline.segment import Segmenter

    seg = Segmenter.from_files()
    total = ready = complete = 0
    pairs = load_split("dev")
    for p in pairs:
        state = DocumentState()
        flags = []
        for s in seg.segment(p.cni):
            c = norm.normalize(s.text, state).text_canonical
            ok = not ad.oov_after(c)
            flags.append(ok)
        total += len(flags)
        ready += sum(flags)
        complete += all(flags) and bool(flags)
    return {
        "base": "883 oraciones de dev tratadas como noticias",
        "segmentos_con_audio_pct": round(100 * ready / total, 2),
        "noticias_completas_pct": round(100 * complete / len(pairs), 2),
    }


def main() -> int:
    perf = load("fase_2_rendimiento.json") or {}
    intel = load("fase_2_inteligibilidad.json")
    tok = load("fase_2_tokenizacion.json")
    cov = ROOT / "coverage.json"
    espeak_ver = ESpeakEngine().version() if find_espeak(get_settings().espeak_path) else None
    rtf = perf.get("rtf", {})
    ttfa = perf.get("ttfa_ms", {})
    c1 = ttfa.get("bajo_demanda_cliente", {}).get("c1", {})
    payload = {
        "fase": 2,
        "commit": git_commit(),
        "fecha": datetime.now(UTC).isoformat(timespec="seconds"),
        "hardware": hardware(),
        "versiones_fijadas": {
            "mms-tts-cni": MMS_TTS_REVISION,
            "mms-1b-all": MMS_ASR_REVISION,
            "espeak-ng": espeak_ver or "no instalado",
        },
        "adapter_activo": MmsCniAdapter.from_files().id,
        "tokenizacion_mms": {
            "elegida": tok["decision"] if tok else "manual",
            "experimento": tok["diferencia_T2_menos_T1"] if tok else None,
        },
        "configuracion_por_defecto": perf.get("configuracion_por_defecto"),
        "carga_en_frio_ms": perf.get("carga_en_frio_ms"),
        "rtf": rtf,
        "ttfa_ms": ttfa,
        "rendimiento_audio_s_por_s": perf.get("rendimiento_audio_s_por_s"),
        "memoria_pico_mb": perf.get("memoria_pico_mb"),
        "pseudo_noticias": perf.get("pseudo_noticias"),
        "duraciones_hook": hook_check(),
        "codificacion": encoding_stats(),
        "disponibilidad": availability(),
        "inteligibilidad_cer_test": (
            {**intel["motores"], "diferencia_pareada": intel["diferencia_mms_menos_espeak"]}
            if intel
            else "no_medido (ejecuta eval.fase2.intelligibility.run)"
        ),
        "dimensionamiento": perf.get("dimensionamiento"),
        "metas": {
            "rtf_menor_1": (
                rtf.get("mms_vits", {}).get("media", 9) < 1
                if isinstance(rtf.get("mms_vits"), dict)
                else None
            ),
            "ttfa_p95_menor_2s_c1": c1.get("p95", 1e9) < 2000 if c1 else None,
        },
        "cobertura_tests_pct": (
            round(json.loads(cov.read_text())["totals"]["percent_covered"], 2)
            if cov.exists()
            else "no_medido"
        ),
    }
    out = RESULTS_DIR / "fase_2.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[fase2] métricas escritas en {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
