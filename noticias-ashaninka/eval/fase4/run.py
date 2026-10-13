"""Fase 4 — consolida las mediciones en ``eval/results/fase_4.json`` (convención del plan §5).

No mide nada por sí mismo: reúne lo que dejan ``prepare``, ``bundle``, el banco del cliente
(``frontend/scripts/fase4_bench.mjs``) y el informe JSON de Playwright, y lo contrasta con los
criterios de cierre fijados en ``docs/metrics.md``. Lo que falta queda ``pendiente``, nunca se
rellena.

Uso: uv run python -m eval.fase4.run
"""

from __future__ import annotations

import json
import platform
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import psutil

from eval.fase4 import bundle
from eval.fase4.prepare import OUT, ROOT

RES = ROOT / "eval" / "results"
MB = 1024 * 1024


def leer(p: Path) -> dict | list | None:
    return json.loads(p.read_text("utf-8")) if p.exists() else None


def git(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    except Exception:
        return ""


def hardware(fps: dict | None) -> dict:
    gpu = None
    for c in (fps or {}).get("casos", []):
        if c["nombre"] == "gpu-x1":
            gpu = c.get("renderer")
    return {
        "so": platform.platform(),
        "cpu": platform.processor(),
        "nucleos_logicos": psutil.cpu_count(),
        "ram_gb": round(psutil.virtual_memory().total / 2**30, 1),
        "gpu_chromium": gpu,
    }


def criterio(meta: str, valor, cumple: bool | None, nota: str = "") -> dict:
    return {
        "meta": meta,
        "valor": valor,
        "cumple": cumple if cumple is not None else "pendiente",
        "nota": nota,
    }


def criterios(d: dict) -> dict:
    c: dict[str, dict] = {}
    carga = d.get("carga")
    if carga:
        mx = max(carga["resumen"][k]["inicial_max_mb"] for k in carga["resumen"])
        c["carga_inicial_menor_3mb"] = criterio(
            "< 3 MB (shell + primer segmento; el avatar es carga diferida)",
            {"max_mb_transferidos": round(mx, 3)},
            mx * 1e6 < 3 * MB,
        )
    t = d.get("ttfa")
    if t:
        r = t["resultados"]
        v = {p: r[p]["frio"]["p95"] for p in ("sin-limite", "movil-4x-4g")}
        c["ttfa_p95_menor_2s_por_lotes"] = criterio(
            "p95 < 2000 ms, clic → primer audio, por lotes, caché fría",
            {
                "p95_ms": v,
                "p95_ms_arranque_completo": {p: r[p]["arranque_completo_frio"]["p95"] for p in v},
            },
            max(v.values()) < 2000,
            "perfil móvil = CPU 4× más lenta + 4G simulada",
        )
    rep = d.get("reproduccion")
    if rep:
        casos = {k: v for k, v in rep.items() if v["completas"]}
        peor = max(v["desfase_resaltado_ms"]["abs_p95"] for v in casos.values())
        peor_max = max(v["desfase_resaltado_ms"]["abs_max"] for v in casos.values())
        c["desfase_resaltado_p95_le_80ms"] = criterio(
            "|p95| ≤ 80 ms frente al reloj del audio (sin latencia de salida del dispositivo)",
            {"abs_p95_ms": round(peor, 2), "abs_max_ms": round(peor_max, 2)},
            peor <= 80,
        )
        cob = min(v["cobertura_pct"] for v in casos.values())
        c["cobertura_resaltado_100"] = criterio("100 %", {"min_pct": round(cob, 2)}, cob >= 100)
        med = max(v["huecos_ms"]["p50"] for v in casos.values())
        p95 = max(v["huecos_ms"]["p95"] for v in casos.values())
        c["hueco_entre_segmentos"] = criterio(
            "mediana ≤ 50 ms y p95 ≤ 150 ms",
            {"peor_mediana_ms": med, "peor_p95_ms": p95},
            med <= 50 and p95 <= 150,
        )
        c["reproduccion_completa"] = criterio(
            "todas las noticias se reproducen hasta el final",
            {k: f"{v['completas']}/{v['noticias']}" for k, v in rep.items()},
            all(v["completas"] == v["noticias"] for v in rep.values()),
        )
    f = d.get("fps")
    if f:
        gpu = next((x for x in f["casos"] if x["nombre"] == "gpu-x1"), None)
        gpu4 = next((x for x in f["casos"] if x["nombre"] == "gpu-cpu4x"), None)
        if gpu and gpu4:
            c["fps_60_c4_con_gpu"] = criterio(
                "60 FPS con la GPU del equipo (y con la CPU 4× más lenta)",
                {"x1": gpu["fps_5s"], "cpu4x": gpu4["fps_5s"], "modo": [gpu["modo"], gpu4["modo"]]},
                gpu["modo"] == "avatar" and gpu["fps_5s"] >= 59 and gpu4["fps_5s"] >= 59,
                "no verificado en un Android de gama media real",
            )
    g = d.get("degradacion")
    if g:
        esperado = {
            "A-sin-webgl": "sin-webgl",
            "B-cpu-20x-software": "fps-bajos",
            "C-normal-gpu": None,
        }
        ok = {}
        for x in g["casos"]:
            razon = next((e["razon"] for e in x["eventos"] if e["tipo"] == "degradacion"), None)
            ok[x["nombre"]] = {
                "modo": x["modo"],
                "razon": razon,
                "correcto": razon == esperado[x["nombre"]]
                and (x["modo"] == "fijo") == (esperado[x["nombre"]] is not None),
            }
        c["degradacion_probada"] = criterio(
            "los 3 casos: sin-webgl, fps-bajos y avatar-ok",
            ok,
            all(v["correcto"] for v in ok.values()),
        )
    o = d.get("offline")
    if o:
        c["offline"] = criterio(
            "abre y reproduce la noticia completa sin red (C1–C3)",
            {"casos": len(o["filas"])},
            o["ok"],
        )
    e = d.get("eventos")
    if e:
        c["cola_de_eventos"] = criterio(
            "100 % entregados al volver la red y 0 duplicados",
            {
                "entregados_pct": round(e["entregados_pct"], 1),
                "nuevos_al_reenviar": e["nuevos_al_reenviar"],
            },
            e["entregados_pct"] >= 100
            and e["nuevos_al_reenviar"] == 0
            and e["pendientes_al_volver"] == 0,
        )
    pw = d.get("e2e")
    if pw:
        c["e2e_chromium"] = criterio(
            "todas las pruebas E2E pasan (incluye axe-core: 0 violaciones críticas o graves)",
            {k: pw[k] for k in ("total", "pasaron", "fallaron", "omitidas")},
            pw["fallaron"] == 0 and pw["total"] > 0,
        )
    c["android_gama_media_real"] = criterio(
        "verificación en un Android de gama media real", None, None, "requiere el dispositivo"
    )
    return c


def e2e_resumen() -> dict | None:
    r = leer(OUT / "e2e.json")
    if not r:
        return None
    est = r["stats"]
    return {
        "total": est["expected"] + est["unexpected"] + est["skipped"] + est["flaky"],
        "pasaron": est["expected"],
        "fallaron": est["unexpected"],
        "omitidas": est["skipped"],
        "duracion_s": round(est["duration"] / 1000, 1),
    }


def main() -> None:
    fps = leer(OUT / "fps.json")
    d = {
        "fase": 4,
        "commit": git("rev-parse", "HEAD"),
        "fecha": datetime.now(UTC).isoformat(timespec="seconds"),
        "hardware": hardware(fps),
        "navegador": leer(OUT / "navegador.json"),
        "material": {
            "noticias": leer(OUT / "selection.json"),
            "regla": "30 pseudo-noticias de 3 líneas consecutivas del split dev (docs/metrics.md)",
        },
        "paquete": bundle.medir() if (bundle.DIST / "sw.js").exists() else None,
        "carga": leer(OUT / "carga.json"),
        "ttfa": leer(OUT / "ttfa.json"),
        "reproduccion": leer(OUT / "reproduccion.json"),
        "fps": fps,
        "degradacion": leer(OUT / "degradacion.json"),
        "offline": leer(OUT / "offline.json"),
        "eventos": leer(OUT / "eventos.json"),
        "e2e": e2e_resumen(),
    }
    d["criterios"] = criterios(d)
    RES.mkdir(parents=True, exist_ok=True)
    (RES / "fase_4.json").write_text(json.dumps(d, indent=1, ensure_ascii=False), "utf-8")
    for k, v in d["criterios"].items():
        print(
            f"{'OK ' if v['cumple'] is True else ('-- ' if v['cumple'] == 'pendiente' else 'NO ')}{k}: {v['valor']}"
        )


if __name__ == "__main__":
    main()
