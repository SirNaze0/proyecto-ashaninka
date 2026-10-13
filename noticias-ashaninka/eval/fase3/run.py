"""Fase 3 — consolida las mediciones en ``eval/results/fase_3.json`` (convención del plan §5).

No mide nada por sí mismo: reúne lo que dejan ``prepare``, ``alignment``, ``lipsync``, ``bundle`` y
los scripts de Playwright (``realtime.mjs``, ``degradation.mjs``) y lo contrasta con los criterios
de cierre. Lo que falta queda marcado ``pendiente``, nunca se rellena.

Uso: uv run python -m eval.fase3.run
"""

from __future__ import annotations

import json
import platform
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import psutil

from eval.fase3 import bundle
from eval.fase3.prepare import OUT, ROOT

RES = ROOT / "eval" / "results"


def leer(p: Path) -> dict | None:
    return json.loads(p.read_text("utf-8")) if p.exists() else None


def git(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    except Exception:
        return ""


def hardware() -> dict:
    return {
        "so": platform.platform(),
        "cpu": platform.processor(),
        "nucleos_logicos": psutil.cpu_count(),
        "ram_gb": round(psutil.virtual_memory().total / 2**30, 1),
        "gpu": "no se mide desde Python; ver cliente.configuraciones",
    }


def cliente() -> dict:
    cfg = {}
    for f in sorted(OUT.glob("cliente_*.json")):
        d = json.loads(f.read_text("utf-8"))
        ok = [c for c in d["clips"] if c.get("mode") == "avatar"]
        if not ok:
            cfg[f.stem] = {"config": d["config"], "throttle": d["throttle"], "clips": 0}
            continue
        cfg[f.stem] = {
            "config": d["config"],
            "cpu_throttle": d["throttle"],
            "clips": len(ok),
            "fps_media": round(sum(c["fps_media"] for c in ok) / len(ok), 1),
            "fps_media_minimo": min(c["fps_media"] for c in ok),
            "intervalo_p95_ms_max": max(c["intervalo_p95_ms"] for c in ok),
            "ms_dibujo_p95_max": max(c["ms_dibujo_p95"] for c in ok),
            "error_reloj_max_abs_ms": max(c["error_reloj_ms"]["max_abs"] for c in ok),
            "error_reloj_regimen_max_abs_ms": max(
                c["error_reloj_regimen_ms"]["max_abs"] for c in ok
            ),
            "error_reloj_regimen_p95_abs_ms": max(
                c["error_reloj_regimen_ms"]["p95_abs"] for c in ok
            ),
            "error_reloj_media_con_signo_ms": round(
                sum(c["error_reloj_ms"]["media_con_signo"] for c in ok) / len(ok), 1
            ),
        }
    return {"configuraciones": cfg, "degradacion": leer(OUT / "degradacion.json")}


def main() -> None:
    alin, lip, praat = (
        leer(RES / f)
        for f in ("fase_3_alineacion.json", "fase_3_lipsync.json", "fase_3_praat.json")
    )
    peso = bundle.medir()
    cl = cliente()
    desf = lip["desfase_directo"] if lip else None
    gpu = {k: v for k, v in cl["configuraciones"].items() if "fps_media" in v and "gpu" in k}
    reloj_reg = [v["error_reloj_regimen_max_abs_ms"] for v in gpu.values()]
    reloj_arr = [v["error_reloj_max_abs_ms"] for v in gpu.values()]
    sist = None
    if desf:
        ic = desf["sistematico_agrupado"]["plantilla"]["ic95_ms"]
        sist = max(abs(ic[0]), abs(ic[1]))
    tot_reg = round(sist + max(reloj_reg), 1) if sist is not None and reloj_reg else None
    tot_arr = round(sist + max(reloj_arr), 1) if sist is not None and reloj_arr else None
    fps = {k: v["fps_media"] for k, v in cl["configuraciones"].items() if "fps_media" in v}
    res = {
        "fase": 3,
        "fecha": datetime.now(UTC).isoformat(timespec="seconds"),
        "commit": git("rev-parse", "HEAD"),
        "rama": git("rev-parse", "--abbrev-ref", "HEAD"),
        "hardware": hardware(),
        "decision_3_1": {
            "libreria": "three + @pixiv/three-vrm",
            "descartada": "TalkingHead",
            "detalle": "docs/avatar_decision.md",
            "pesos": peso.get("comparativa_3_1"),
        },
        "peso": peso,
        "alineacion_3_2": alin,
        "alineacion_manual_praat": praat
        or "pendiente: requiere anotación humana (eval/fase3/praat/)",
        "sincronia_3_8": lip,
        "cliente": cl,
        "criterios": {
            "paquete_inicial_menor_3mb": peso["cumple_presupuesto_inicial"],
            "paquete_inicial_gzip_kb": round(peso["inicial_gzip_bytes"] / 1024, 1),
            "avatar_diferido_gzip_kb": round(peso["diferido_gzip_bytes"] / 1024, 1),
            "vrm_provisional_mb": round(peso.get("vrm_provisional_bytes", 0) / 2**20, 2),
            "inicial_mas_avatar_mas_vrm_menor_3mb": (
                peso["inicial_gzip_bytes"]
                + peso["diferido_gzip_bytes"]
                + peso.get("vrm_provisional_bytes", 0)
                < 3 * 2**20
            ),
            "desfase_sistematico_ms": desf["sistematico_agrupado"]["plantilla"]
            if desf
            else "pendiente",
            "desfase_sistematico_peor_cota_ms": sist if sist is not None else "pendiente",
            "error_reloj_regimen_max_ms": max(reloj_reg) if reloj_reg else "pendiente",
            "error_reloj_arranque_max_ms": max(reloj_arr) if reloj_arr else "pendiente",
            "desfase_total_regimen_ms": tot_reg if tot_reg is not None else "pendiente",
            "desfase_total_con_arranque_ms": tot_arr if tot_arr is not None else "pendiente",
            "desfase_total_cumple_80ms": (tot_arr <= 80) if tot_arr is not None else "pendiente",
            "desfase_por_clip": "no concluyente (ver calibración en fase_3_lipsync.json)",
            "clips": lip["clips"] if lip else 0,
            "clips_cumplen_30": bool(lip and lip["clips"] >= 30),
            "fps_media_por_configuracion": fps,
            "fps_60_con_gpu": all(v >= 55 for v in (fps[k] for k in gpu)) if gpu else "pendiente",
            "fps_software_sin_gpu_menor_20": any(v < 20 for k, v in fps.items() if "software" in k),
        },
    }
    (RES / "fase_3.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), "utf-8")
    print(json.dumps(res["criterios"], indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
