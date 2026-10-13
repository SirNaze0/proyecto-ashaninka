# Arquitectura y latencias medidas

> **Archivo generado** por `uv run python -m eval.fase6.architecture` a partir de
> `eval/results/fase_1.json` … `fase_5.json`. No lo edite a mano: cambie la medición y regenere.

## Diagrama

```
 noticias en asháninka (JSON, contrato del plan §2)
        │  CLI  app.cli import   (API /api/news: administrativa, con token)
        ▼
┌───────────────────────────── BACKEND (FastAPI, un contenedor) ─────────────────────────────┐
│ [1] Ingesta ─► [2] Normalización (2-0…2f) ─► [3] G2P ─► [4] TTSEngine ─► [5] Alineación     │
│                          │                              ├ mms_vits (principal)    │        │
│                  texto canónico ──► adaptador MMS       └ espeak_ng (línea base)  ▼        │
│                                                     [6] Visemas ─► seg_NNN.json (tiempos)  │
│  por lotes:   /static/news/{id}/manifest.json + audio por contenido (Opus/MP3, con Range)  │
│  bajo demanda: /api/synthesize/{id} (NDJSON por oración, solo respaldo)                    │
│  /api/catalog · /api/events · /api/experiment/*  (públicos)   ·  admin: token              │
│  seguridad: cabeceras + CSP + límite de tasa   ·   SQLite (WAL) en un volumen              │
└───────────────────────────────────────────────────────────────────────────────────────────┘
        ▲ HTTPS (Caddy: certificado automático, zstd/gzip solo texto, Range intacto)
        │
┌──────────────────────────── PWA (Preact, < 3 MB de carga inicial) ────────────────────────┐
│ condiciones C1 texto · C2 voz · C3 voz + texto resaltado · C4 + avatar VRM (carga diferida)│
│ Service Worker (sin conexión, 206 a Range) · cola de eventos y respuestas en IndexedDB     │
│ experimento: consentimiento → 4 bloques en orden de Williams → cuestionarios → exportación │
└───────────────────────────────────────────────────────────────────────────────────────────┘
```

## Latencia por etapa (medida)

| Etapa | Qué hace | Medido | Fuente |
|---|---|---|---|
| 2 · segmentación | oraciones y párrafos | p50 0,0062 ms · p95 0,0140 ms (n = 5000) | `fase_1.json` |
| 2 · normalización | unificación, números, siglas, reescritura | p50 0,1473 ms · p95 0,3741 ms (n = 5200) | `fase_1.json` |
| 2e · adaptador MMS | ortografía canónica → ortografía del modelo | p50 0,1879 ms · p95 0,4985 ms (n = 5200) | `fase_1.json` |
| 3 · G2P | segmentación grafémica | p50 0,0377 ms · p95 0,0953 ms (n = 5200) | `fase_1.json` |
| 4 · TTS `mms_vits` | síntesis VITS en CPU, sin GPU | RTF 0,2546 (DE 0,0273; p95 0,3032); carga en frío 4352 ms; audio medio 5,42 s | `fase_2.json` |
| 4 · TTS `espeak_ng` | línea base GPL | RTF 0,0105 (DE 0,0050); carga en frío 153 ms | `fase_2.json` |
| 4 · inteligibilidad objetiva | CER de ida y vuelta TTS→ASR, split test | `mms_vits` 0,0516 · `espeak_ng` 0,2291 | `fase_2.json` |
| 5 · alineación | error del centro de palabra frente al alineador CTC | media 63,9 ms · mediana 34,0 ms (n = 211) | `fase_3.json` |
| 6 · visemas y avatar | desfase sistemático de la boca (correlación con la plantilla) | -10,8 ms (IC 95 %: -18,5 a -2,1); total estimado 26 a 55 ms | `fase_3.json` |

## Entrega de audio (servidor)

| Modo | 1 cliente | 4 clientes | 8 clientes | Meta TTFA p95 < 2 s |
|---|---|---|---|---|
| **Por lotes** (principal) | p50 21,1 ms · p95 43,7 ms | p95 48,8 ms | p95 65,6 ms | **cumple** |
| Bajo demanda (respaldo), TTFA del cliente | p95 2357 ms | p95 5067 ms | p95 8559 ms | **no cumple** |

RAM pico del servicio en síntesis (4 hilos × 4 trabajadores): 1484 MB con 1 cliente y 2156 MB con 8. Con un trabajador (configuración de producción, `docs/sizing.md`): unos 1 058 MB.

## Cliente (PWA, Chromium con CPU 4× más lenta y 4G simulada)

| Medida | Resultado | Meta | Fuente |
|---|---|---|---|
| Carga inicial (paquete, gzip) | 18,7 KB; transferido hasta el primer audio, máx. 0,099 MB (C3) | < 3 MB | `fase_4.json` |
| TTFA clic → primer audio, por lotes, en frío | p50 87,5 ms · p95 113,0 ms | p95 < 2 s | `fase_4.json` |
| Arranque completo (navegación → primer audio), en frío | p50 892 ms · p95 948 ms | p95 < 2 s | `fase_4.json` |
| Desfase del resaltado | |p95| 15,8 ms | ≤ 80 ms | `fase_4.json` |
| Cuadros por segundo con avatar (con GPU) | 60 | 60 | `fase_4.json` |

## Experimento y análisis (simulación sintética, no datos reales)

- Exportación frente a la verdad simulada: diferencia máxima de 3 ms en el tiempo de escucha y 1 ms en el tiempo en pantalla (`fase_5.json`).
- Potencia: N mínimo de 64 participantes para 0,80 con d = 0,5 (estimación bajo el modelo simulado).

## Lo que NO está medido

- **En un servidor real:** todas las cifras anteriores son de la máquina de desarrollo (Intel de 12 hilos, 12 hilos lógicos, 15,8 GB de RAM, Windows-10-10.0.26200-SP0). La comparación local frente a servidor (tarea 6.3) está **pendiente**.
- **En un Android de gama media físico:** la CPU 4× más lenta y el 4G son simulados (limitación 36).
- **Costo de la capa de seguridad** (cabeceras, CSP y límite de tasa por petición): no se midió por separado.
- **Tiempo de `docker build` y tamaño de la imagen:** no se midieron (el demonio de Docker no estaba activo).

Véase también: [`docs/sizing.md`](sizing.md) (dimensionamiento del servidor), [`docs/deployment.md`](deployment.md),
[`docs/limitations.md`](limitations.md) y [`docs/metrics.md`](metrics.md).
