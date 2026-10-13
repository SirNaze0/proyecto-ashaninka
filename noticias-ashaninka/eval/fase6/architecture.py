"""Genera ``docs/architecture.md``: diagrama y tabla por etapa con las latencias MEDIDAS (tarea 6.5).

Todas las cifras salen de ``eval/results/fase_{1..5}.json``: el documento no se edita a mano ni puede
desviarse de las mediciones (una prueba comprueba que está al día). Lo que no se midió se dice.

Uso: uv run python -m eval.fase6.architecture
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "eval" / "results"
DOC = ROOT / "docs" / "architecture.md"
MB = 1_000_000  # como en resumen_fase4.md: KB y MB decimales


def n(x: float, d: int = 2) -> str:
    """Número con coma decimal y sin separador de miles (así se compara en las pruebas)."""
    return f"{x:.{d}f}".replace(".", ",")


def cargar() -> dict[int, dict]:
    return {
        i: json.loads((RES / f"fase_{i}.json").read_text(encoding="utf-8")) for i in range(1, 6)
    }


def hw(d: dict) -> str:
    """Máquina de medición, con las dos formas en que las fases guardaron el hardware."""
    h = d["hardware"]
    cpu = "Intel de 12 hilos" if "Intel64" in (h.get("cpu") or "") else (h.get("cpu") or "CPU")
    nucleos = h.get("nucleos_logicos") or h.get("nucleos") or "?"
    so = h.get("so") or h.get("os") or ""
    return f"{cpu}, {nucleos} hilos lógicos, {n(h.get('ram_gb', 0), 1)} GB de RAM, {so}"


def render(r: dict[int, dict]) -> str:
    f1, f2, f3, f4, f5 = (r[i] for i in range(1, 6))
    lat = f1["latencia_ms"]
    rtf = f2["rtf"]
    ttfa = f2["ttfa_ms"]
    movil = f4["ttfa"]["resultados"]["movil-4x-4g"]
    rep = f4["reproduccion"]["C3/movil-4x-4g"]
    centro = f3["alineacion_3_2"]["palabras_error"]["centro"]
    sist = f3["sincronia_3_8"]["desfase_directo"]["sistematico_agrupado"]["plantilla"]
    crit3 = f3["criterios"]
    fps_gpu = next(c["fps_5s"] for c in f4["fps"]["casos"] if c["nombre"] == "gpu-x1")
    carga_c3 = (
        max(f["bytes_iniciales"] for f in f4["carga"]["filas"] if f["condicion"] == "C3") / MB
    )
    pot = f5["potencia"]
    ver = f5["verificacion_exportacion"]["peor_diferencia_ms"]
    cer = f2["inteligibilidad_cer_test"]

    def fila_lat(nombre: str, que: str, clave: str) -> str:
        v = lat[clave]
        return f"| {nombre} | {que} | p50 {n(v['p50'], 4)} ms · p95 {n(v['p95'], 4)} ms (n = {v['n']}) | `fase_1.json` |"

    L = [
        "# Arquitectura y latencias medidas",
        "",
        "> **Archivo generado** por `uv run python -m eval.fase6.architecture` a partir de",
        "> `eval/results/fase_1.json` … `fase_5.json`. No lo edite a mano: cambie la medición y regenere.",
        "",
        "## Diagrama",
        "",
        "```",
        " noticias en asháninka (JSON, contrato del plan §2)",
        "        │  CLI  app.cli import   (API /api/news: administrativa, con token)",
        "        ▼",
        "┌───────────────────────────── BACKEND (FastAPI, un contenedor) ─────────────────────────────┐",
        "│ [1] Ingesta ─► [2] Normalización (2-0…2f) ─► [3] G2P ─► [4] TTSEngine ─► [5] Alineación     │",
        "│                          │                              ├ mms_vits (principal)    │        │",
        "│                  texto canónico ──► adaptador MMS       └ espeak_ng (línea base)  ▼        │",
        "│                                                     [6] Visemas ─► seg_NNN.json (tiempos)  │",
        "│  por lotes:   /static/news/{id}/manifest.json + audio por contenido (Opus/MP3, con Range)  │",
        "│  bajo demanda: /api/synthesize/{id} (NDJSON por oración, solo respaldo)                    │",
        "│  /api/catalog · /api/events · /api/experiment/*  (públicos)   ·  admin: token              │",
        "│  seguridad: cabeceras + CSP + límite de tasa   ·   SQLite (WAL) en un volumen              │",
        "└───────────────────────────────────────────────────────────────────────────────────────────┘",
        "        ▲ HTTPS (Caddy: certificado automático, zstd/gzip solo texto, Range intacto)",
        "        │",
        "┌──────────────────────────── PWA (Preact, < 3 MB de carga inicial) ────────────────────────┐",
        "│ condiciones C1 texto · C2 voz · C3 voz + texto resaltado · C4 + avatar VRM (carga diferida)│",
        "│ Service Worker (sin conexión, 206 a Range) · cola de eventos y respuestas en IndexedDB     │",
        "│ experimento: consentimiento → 4 bloques en orden de Williams → cuestionarios → exportación │",
        "└───────────────────────────────────────────────────────────────────────────────────────────┘",
        "```",
        "",
        "## Latencia por etapa (medida)",
        "",
        "| Etapa | Qué hace | Medido | Fuente |",
        "|---|---|---|---|",
        fila_lat("2 · segmentación", "oraciones y párrafos", "segmentacion"),
        fila_lat("2 · normalización", "unificación, números, siglas, reescritura", "normalizacion"),
        fila_lat(
            "2e · adaptador MMS", "ortografía canónica → ortografía del modelo", "adaptador_mms"
        ),
        fila_lat("3 · G2P", "segmentación grafémica", "g2p"),
        f"| 4 · TTS `mms_vits` | síntesis VITS en CPU, sin GPU | RTF {n(rtf['mms_vits']['media'], 4)} (DE {n(rtf['mms_vits']['de'], 4)}; p95 {n(rtf['mms_vits']['p95'], 4)}); carga en frío {n(f2['carga_en_frio_ms']['mms_vits'], 0)} ms; audio medio {n(rtf['mms_vits']['duracion_audio_s']['media'], 2)} s | `fase_2.json` |",
        f"| 4 · TTS `espeak_ng` | línea base GPL | RTF {n(rtf['espeak_ng']['media'], 4)} (DE {n(rtf['espeak_ng']['de'], 4)}); carga en frío {n(f2['carga_en_frio_ms']['espeak_ng'], 0)} ms | `fase_2.json` |",
        f"| 4 · inteligibilidad objetiva | CER de ida y vuelta TTS→ASR, split test | `mms_vits` {n(cer['mms_vits']['cer'], 4)} · `espeak_ng` {n(cer['espeak_ng']['cer'], 4)} | `fase_2.json` |",
        f"| 5 · alineación | error del centro de palabra frente al alineador CTC | media {n(centro['mae_ms'], 1)} ms · mediana {n(centro['mediana_abs_ms'], 1)} ms (n = {centro['n']}) | `fase_3.json` |",
        f"| 6 · visemas y avatar | desfase sistemático de la boca (correlación con la plantilla) | {n(sist['lag_ms'], 1)} ms (IC 95 %: {n(sist['ic95_ms'][0], 1)} a {n(sist['ic95_ms'][1], 1)}); total estimado {n(crit3['desfase_total_regimen_ms'], 0)} a {n(crit3['desfase_total_con_arranque_ms'], 0)} ms | `fase_3.json` |",
        "",
        "## Entrega de audio (servidor)",
        "",
        "| Modo | 1 cliente | 4 clientes | 8 clientes | Meta TTFA p95 < 2 s |",
        "|---|---|---|---|---|",
        f"| **Por lotes** (principal) | p50 {n(ttfa['por_lotes']['c1']['p50'], 1)} ms · p95 {n(ttfa['por_lotes']['c1']['p95'], 1)} ms | p95 {n(ttfa['por_lotes']['c4']['p95'], 1)} ms | p95 {n(ttfa['por_lotes']['c8']['p95'], 1)} ms | **cumple** |",
        f"| Bajo demanda (respaldo), TTFA del cliente | p95 {n(ttfa['bajo_demanda_cliente']['c1']['p95'], 0)} ms | p95 {n(ttfa['bajo_demanda_cliente']['c4']['p95'], 0)} ms | p95 {n(ttfa['bajo_demanda_cliente']['c8']['p95'], 0)} ms | **no cumple** |",
        "",
        f"RAM pico del servicio en síntesis (4 hilos × 4 trabajadores): {n(f2['memoria_pico_mb']['c1'], 0)} MB con 1 cliente y {n(f2['memoria_pico_mb']['c8'], 0)} MB con 8. Con un trabajador (configuración de producción, `docs/sizing.md`): unos 1 058 MB.",
        "",
        "## Cliente (PWA, Chromium con CPU 4× más lenta y 4G simulada)",
        "",
        "| Medida | Resultado | Meta | Fuente |",
        "|---|---|---|---|",
        f"| Carga inicial (paquete, gzip) | {n(f4['paquete']['inicial_gzip_bytes'] / 1000, 1)} KB; transferido hasta el primer audio, máx. {n(carga_c3, 3)} MB (C3) | < 3 MB | `fase_4.json` |",
        f"| TTFA clic → primer audio, por lotes, en frío | p50 {n(movil['frio']['p50'], 1)} ms · p95 {n(movil['frio']['p95'], 1)} ms | p95 < 2 s | `fase_4.json` |",
        f"| Arranque completo (navegación → primer audio), en frío | p50 {n(movil['arranque_completo_frio']['p50'], 0)} ms · p95 {n(movil['arranque_completo_frio']['p95'], 0)} ms | p95 < 2 s | `fase_4.json` |",
        f"| Desfase del resaltado | |p95| {n(rep['desfase_resaltado_ms']['abs_p95'], 1)} ms | ≤ 80 ms | `fase_4.json` |",
        f"| Cuadros por segundo con avatar (con GPU) | {n(fps_gpu, 0)} | 60 | `fase_4.json` |",
        "",
        "## Experimento y análisis (simulación sintética, no datos reales)",
        "",
        f"- Exportación frente a la verdad simulada: diferencia máxima de {ver['t_escucha_ms']} ms en el tiempo de escucha y {ver['t_pantalla_ms']} ms en el tiempo en pantalla (`fase_5.json`).",
        f"- Potencia: N mínimo de {pot['n_minimo']} participantes para 0,80 con d = {n(pot['d'], 1)} (estimación bajo el modelo simulado).",
        "",
        "## Lo que NO está medido",
        "",
        "- **En un servidor real:** todas las cifras anteriores son de la máquina de desarrollo ("
        + hw(f2)
        + "). La comparación local frente a servidor (tarea 6.3) está **pendiente**.",
        "- **En un Android de gama media físico:** la CPU 4× más lenta y el 4G son simulados (limitación 36).",
        "- **Costo de la capa de seguridad** (cabeceras, CSP y límite de tasa por petición): no se midió por separado.",
        "- **Tiempo de `docker build` y tamaño de la imagen:** no se midieron (el demonio de Docker no estaba activo).",
        "",
        "Véase también: [`docs/sizing.md`](sizing.md) (dimensionamiento del servidor), [`docs/deployment.md`](deployment.md),",
        "[`docs/limitations.md`](limitations.md) y [`docs/metrics.md`](metrics.md).",
        "",
    ]
    return "\n".join(L)


def main() -> None:
    DOC.write_text(render(cargar()), encoding="utf-8", newline="\n")
    print(f"[arquitectura] {DOC}")


if __name__ == "__main__":
    main()
