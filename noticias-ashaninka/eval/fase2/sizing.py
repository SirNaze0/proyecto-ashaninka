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
ON_DEMAND_USERS = [1, 5, 10, 20]


def build() -> dict:
    path = RESULTS_DIR / "fase_2_rendimiento.json"
    r = json.loads(path.read_text(encoding="utf-8"))
    cores = r["hardware"]["nucleos"]
    ttfa = r["ttfa_ms"]["bajo_demanda_cliente"]
    throughput = r["rendimiento_audio_s_por_s"]
    mms = r["rtf"]["mms_vits"]
    news = r["pseudo_noticias"]
    seg_per_news = news["segmentos"] / news["noticias"]
    audio_per_news = mms["duracion_audio_s"]["media"] * seg_per_news

    ok_levels = [int(k[1:]) for k, v in ttfa.items() if v.get("p95", 1e9) < TARGET_P95_MS]
    max_conc = max(ok_levels) if ok_levels else 0
    per_core = max_conc / cores if cores else 0
    best_tp = max(throughput.values())
    peak_mb = max(r["memoria_pico_mb"].values())

    batch = []
    for n in BATCH_NEWS_PER_DAY:
        wall_s = n * audio_per_news / best_tp
        batch.append(
            {
                "noticias_dia": n,
                "audio_total_min": round(n * audio_per_news / 60, 1),
                "tiempo_sintesis_min_esta_maquina": round(wall_s / 60, 2),
            }
        )
    on_demand = []
    for k in ON_DEMAND_USERS:
        need = math.ceil(k / per_core) if per_core else None
        on_demand.append(
            {
                "usuarios_simultaneos": k,
                "vcpu_estimados": need,
                "medido_en_esta_maquina": k <= max_conc,
            }
        )
    ram_gb = round(peak_mb * RAM_MARGIN / 1024, 2)
    rec_vcpu = max(
        2, next((d["vcpu_estimados"] for d in on_demand if d["usuarios_simultaneos"] == 5), 2) or 2
    )
    sizing = {
        "supuestos": [
            "capacidad bajo demanda lineal con los núcleos",
            f"noticia típica: {round(audio_per_news, 1)} s de audio "
            f"({round(seg_per_news, 2)} segmentos)",
            f"margen de RAM x{RAM_MARGIN}",
        ],
        "nucleos_medidos": cores,
        "concurrencia_max_con_ttfa_p95_<2s": max_conc,
        "usuarios_por_vcpu": round(per_core, 3),
        "rendimiento_max_audio_s_por_s": best_tp,
        "ram_pico_mb": peak_mb,
        "escenarios": {"por_lotes": batch, "bajo_demanda": on_demand},
        "recomendacion": (
            f"Mínimo para un piloto (por lotes + hasta 5 usuarios simultáneos con "
            f"TTFA p95 < 2 s): {rec_vcpu} vCPU y {max(2, math.ceil(ram_gb))} GB de "
            f"RAM, sin GPU. RAM medida: {peak_mb} MB de pico."
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
        "plan (propuesta; el plan no se edita sin aprobación).",
        "",
        "## Supuestos",
        "",
        *[f"- {x}" for x in s["supuestos"]],
        "",
        "## Capacidad medida",
        "",
        "| Medida | Valor |",
        "|---|---|",
        f"| Núcleos de la máquina de medición | {s['nucleos_medidos']} |",
        f"| Concurrencia máxima con TTFA p95 < 2 s | {s['concurrencia_max_con_ttfa_p95_<2s']} |",
        f"| Usuarios simultáneos por vCPU (estimado) | {s['usuarios_por_vcpu']} |",
        f"| Rendimiento máximo (s de audio por s) | {s['rendimiento_max_audio_s_por_s']} |",
        f"| Pico de RAM del servidor | {s['ram_pico_mb']} MB |",
        "",
        "## Escenario 1: síntesis por lotes",
        "",
        "| Noticias por día | Audio total (min) | Tiempo de síntesis en esta máquina (min) |",
        "|---|---|---|",
    ]
    for b in s["escenarios"]["por_lotes"]:
        lines.append(
            f"| {b['noticias_dia']} | {b['audio_total_min']} | "
            f"{b['tiempo_sintesis_min_esta_maquina']} |"
        )
    lines += [
        "",
        "## Escenario 2: bajo demanda con TTFA p95 < 2 s",
        "",
        "| Usuarios simultáneos | vCPU estimados | ¿Medido directamente? |",
        "|---|---|---|",
    ]
    for d in s["escenarios"]["bajo_demanda"]:
        lines.append(
            f"| {d['usuarios_simultaneos']} | {d['vcpu_estimados']} | "
            f"{'sí' if d['medido_en_esta_maquina'] else 'no (extrapolado)'} |"
        )
    lines += ["", "## Recomendación", "", s["recomendacion"], ""]
    return "\n".join(lines)


if __name__ == "__main__":
    build()
