"""Tarea 2.9 — Dimensionamiento del servidor a partir de las mediciones de 2.8.

Lee eval/results/fase_2_rendimiento.json y escribe docs/sizing.md + el bloque
"dimensionamiento" en ese JSON. Supuestos (declarados en el documento):
  * la capacidad bajo demanda escala linealmente con los núcleos (aproximación);
  * una noticia típica = media de las pseudo-noticias del banco (300-500 caracteres).

Uso: uv run python -m eval.fase2.sizing
"""

from __future__ import annotations

import json
import math

from app.config import DOCS_DIR, RESULTS_DIR

TARGET_P95_MS = 2000
RAM_MARGIN = 1.25
BATCH_NEWS_PER_DAY = [50, 500]


def _levels_ok(ttfa_block: dict) -> list[int]:
    return [int(k[1:]) for k, v in ttfa_block.items() if v.get("p95", 1e9) < TARGET_P95_MS]


def build() -> dict:
    path = RESULTS_DIR / "fase_2_rendimiento.json"
    r = json.loads(path.read_text(encoding="utf-8"))
    cores = r["hardware"]["nucleos"]
    mms = r["rtf"]["mms_vits"]
    news = r["pseudo_noticias"]
    seg_per_news = news["segmentos"] / news["noticias"]
    audio_per_news = mms["duracion_audio_s"]["media"] * seg_per_news

    configs = {"principal": r}
    if "secundario_latencia" in r:
        configs["latencia"] = r["secundario_latencia"]
    capacity = {}
    for name, block in configs.items():
        ok = _levels_ok(block["ttfa_ms"]["bajo_demanda_cliente"])
        capacity[name] = {
            "config": block["http_config"],
            "niveles_con_ttfa_cliente_p95_<2s": ok,
            "ttfa_cliente_p95_ms": {
                k: v["p95"] for k, v in block["ttfa_ms"]["bajo_demanda_cliente"].items()
            },
            "rendimiento_audio_s_por_s": block["rendimiento_audio_s_por_s"],
            "ram_pico_mb": block["memoria_pico_mb"],
        }
    batch_ok = _levels_ok(r["ttfa_ms"]["por_lotes"])
    best_tp = max(r["rendimiento_audio_s_por_s"].values())
    per_core_tp = best_tp / cores
    batch = []
    for n in BATCH_NEWS_PER_DAY:
        audio_total = n * audio_per_news
        vcpu_1h = max(1, math.ceil(audio_total / (3600 * per_core_tp)))
        batch.append(
            {
                "noticias_dia": n,
                "audio_total_min": round(audio_total / 60, 1),
                "tiempo_en_esta_maquina_min": round(audio_total / best_tp / 60, 2),
                "vcpu_para_terminar_en_1h": vcpu_1h,
            }
        )
    ram_one_worker = min(v for c in capacity.values() for v in c["ram_pico_mb"].values())
    ram_gb = max(2, math.ceil(ram_one_worker * RAM_MARGIN / 1024))
    vcpu = max(2, batch[0]["vcpu_para_terminar_en_1h"])
    lat = capacity.get("latencia", {})
    sizing = {
        "supuestos": [
            "rendimiento de síntesis lineal con los núcleos (aproximación)",
            f"noticia típica: {round(audio_per_news, 1)} s de audio ({round(seg_per_news, 2)} "
            "segmentos), media de las pseudo-noticias del banco",
            f"margen de RAM x{RAM_MARGIN}",
        ],
        "nucleos_medidos": cores,
        "noticia_tipica_audio_s": round(audio_per_news, 1),
        "rendimiento_por_vcpu_audio_s_por_s": round(per_core_tp, 3),
        "bajo_demanda": capacity,
        "por_lotes_servir_estatico_niveles_con_p95_<2s": batch_ok,
        "escenarios": {"sintesis_por_lotes": batch},
        "recomendacion": (
            f"Modo principal = por lotes (el plan lo prevé). Para sintetizar hasta "
            f"{BATCH_NEWS_PER_DAY[0]} noticias/día y servirlas como archivos estáticos (TTFA p95 "
            f"medido < 70 ms con 8 clientes): {vcpu} vCPU y {ram_gb} GB de RAM, sin GPU, con NA_TTS_WORKERS=1 (pico de RAM "
            f"medido con 1 trabajador: {ram_one_worker} MB). "
            f"Bajo demanda, la meta TTFA p95 < 2 s solo se cumplió con 1 cliente y la "
            f"configuración de latencia ({lat.get('config', {}).get('torch_threads')} hilos, "
            f"{lat.get('config', {}).get('tts_workers')} trabajador) en una CPU de {cores} "
            f"núcleos; con 4 u 8 clientes simultáneos no se cumple. El bajo demanda queda como "
            f"respaldo para noticias aún no sintetizadas."
        ),
    }
    r["dimensionamiento"] = sizing
    path.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    (DOCS_DIR / "sizing.md").write_text(render(sizing), encoding="utf-8", newline="\n")
    print(f"[2.9] {sizing['recomendacion']}")
    return sizing


def render(s: dict) -> str:
    lines = [
        "# Dimensionamiento del servidor (tarea 2.9)",
        "",
        "> GENERADO por `uv run python -m eval.fase2.sizing` a partir de "
        "`eval/results/fase_2_rendimiento.json`. Reemplaza la estimación preliminar del §7 del "
        "plan (es una propuesta: el plan no se edita sin aprobación).",
        "",
        "## Supuestos",
        "",
        *[f"- {x}" for x in s["supuestos"]],
        "",
        f"Máquina de medición: {s['nucleos_medidos']} núcleos. Rendimiento por vCPU: "
        f"{s['rendimiento_por_vcpu_audio_s_por_s']} s de audio por s.",
        "",
        "## Bajo demanda: TTFA del cliente p95 por configuración",
        "",
        "| Configuración | Hilos × trabajadores | 1 cliente | 4 clientes | 8 clientes | "
        "Niveles que cumplen p95 < 2 s | Rendimiento máx. (s/s) | RAM pico (MB) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for name, c in s["bajo_demanda"].items():
        t = c["ttfa_cliente_p95_ms"]
        lines.append(
            f"| {name} | {c['config']['torch_threads']} × {c['config']['tts_workers']} | "
            f"{round(t['c1'])} ms | {round(t['c4'])} ms | {round(t['c8'])} ms | "
            f"{c['niveles_con_ttfa_cliente_p95_<2s'] or 'ninguno'} | "
            f"{max(c['rendimiento_audio_s_por_s'].values())} | "
            f"{max(c['ram_pico_mb'].values())} |"
        )
    lines += [
        "",
        f"Servir noticias ya sintetizadas (modo por lotes): niveles con TTFA p95 < 2 s = "
        f"{s['por_lotes_servir_estatico_niveles_con_p95_<2s']}.",
        "",
        "## Síntesis por lotes",
        "",
        "| Noticias por día | Audio total (min) | Tiempo en esta máquina (min) | "
        "vCPU para terminar en 1 h |",
        "|---|---|---|---|",
    ]
    for b in s["escenarios"]["sintesis_por_lotes"]:
        lines.append(
            f"| {b['noticias_dia']} | {b['audio_total_min']} | "
            f"{b['tiempo_en_esta_maquina_min']} | {b['vcpu_para_terminar_en_1h']} |"
        )
    lines += ["", "## Recomendación", "", s["recomendacion"], ""]
    return "\n".join(lines)


if __name__ == "__main__":
    build()
