# Dimensionamiento del servidor (tarea 2.9)

> GENERADO por `uv run python -m eval.fase2.sizing` a partir de `eval/results/fase_2_rendimiento.json`. Reemplaza la estimación preliminar del §7 del plan (es una propuesta: el plan no se edita sin aprobación).

## Supuestos

- rendimiento de síntesis lineal con los núcleos (aproximación)
- noticia típica: 27.7 s de audio (5.58 segmentos), media de las pseudo-noticias del banco
- margen de RAM x1.25

Máquina de medición: 16 núcleos. Rendimiento por vCPU: 0.593 s de audio por s.

## Bajo demanda: TTFA del cliente p95 por configuración

| Configuración | Hilos × trabajadores | 1 cliente | 4 clientes | 8 clientes | Niveles que cumplen p95 < 2 s | Rendimiento máx. (s/s) | RAM pico (MB) |
|---|---|---|---|---|---|---|---|
| principal | 4 × 4 | 2357 ms | 5067 ms | 8559 ms | ninguno | 9.494 | 2156.2 |
| latencia | 8 × 1 | 1875 ms | 5947 ms | 10391 ms | [1] | 7.249 | 1634.2 |

Servir noticias ya sintetizadas (modo por lotes): niveles con TTFA p95 < 2 s = [1, 4, 8].

## Síntesis por lotes

| Noticias por día | Audio total (min) | Tiempo en esta máquina (min) | vCPU para terminar en 1 h |
|---|---|---|---|
| 50 | 23.1 | 2.43 | 1 |
| 500 | 230.7 | 24.29 | 7 |

## Recomendación

Modo principal = por lotes (el plan lo prevé). Para sintetizar hasta 50 noticias/día y servirlas como archivos estáticos (TTFA p95 medido < 70 ms con 8 clientes): 2 vCPU y 2 GB de RAM, sin GPU, con NA_TTS_WORKERS=1 (pico de RAM medido con 1 trabajador: 1057.8 MB). Bajo demanda, la meta TTFA p95 < 2 s solo se cumplió con 1 cliente y la configuración de latencia (8 hilos, 1 trabajador) en una CPU de 16 núcleos; con 4 u 8 clientes simultáneos no se cumple. El bajo demanda queda como respaldo para noticias aún no sintetizadas.
