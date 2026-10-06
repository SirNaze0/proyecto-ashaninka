# Definición de las métricas de rendimiento (Fase 2)

> Escrito **antes** de medir (2026-10-06). Las cifras se reportan aunque no cumplan las metas, y
> estas definiciones no se ajustan después de ver los resultados.

## Métricas

| Métrica | Definición | Unidad | Estadísticos |
|---|---|---|---|
| **RTF** (*real-time factor*) | Tiempo de síntesis en caliente ÷ duración del audio generado, por segmento. El tiempo de síntesis va desde el texto validado hasta el WAV en memoria; **no** incluye codificar ni escribir en disco. | adimensional | media, desviación estándar, p50, p95, n |
| **Carga en frío** | Tiempo de `warmup()` de un motor recién creado (leer el modelo y prepararlo). | ms | valor por motor |
| **TTFA del servidor** (bajo demanda) | Tiempo desde que la solicitud llega al endpoint `/api/synthesize/{id}` hasta que el servidor emite el primer evento NDJSON `segment` (audio ya escrito en la caché). Es el campo `t_ms` de ese evento. | ms | p50, p95, p99, n |
| **TTFA del cliente** (bajo demanda) | Medido desde un cliente HTTP real en la misma máquina: desde que se envía la solicitud hasta que se reciben los **primeros bytes** del primer archivo de audio (Opus), es decir, recibir el evento `segment` + `GET` del audio + primer bloque. | ms | p50, p95, p99, n |
| **TTFA por lotes** | Con la caché ya caliente: `GET` del manifiesto + `GET` de los primeros bytes del audio del primer segmento con audio. | ms | p50, p95, p99, n |
| **Rendimiento** | Segundos de audio producidos ÷ segundos de reloj, con la caché fría, para cada nivel de concurrencia. | s de audio / s | valor por nivel |
| **Memoria** | Pico de memoria residente (RSS) del proceso servidor con el modelo cargado y bajo carga (`psutil`, muestreo cada 0,2 s). | MB | pico |

## Protocolo

- **Noticias.** No hay noticias reales, así que se usan pseudo-noticias armadas con oraciones del split *dev* que quedan **listas para el TTS**. Se concatenan en un orden aleatorio con semilla fija hasta sumar entre 300 y 500 caracteres. Son al menos 100 noticias distintas, y todas cumplen el criterio del plan: "hasta 500 caracteres".
- **Motores.** `mms_vits` (adaptador activo, tokenización por defecto) y `espeak_ng` en modo `texto-es`, si está instalado.
- **Caliente o frío.** El RTF y los TTFA se miden con el modelo ya cargado; la carga en frío se reporta aparte. Los TTFA del modo bajo demanda se miden con la **caché de audio fría**, porque si no se estaría midiendo la caché y no la síntesis. Para eso cada nivel de concurrencia usa una carpeta estática nueva.
- **Concurrencia.** Con 1, 4 y 8 clientes simultáneos, cada nivel envía al menos 100 solicitudes, y cada solicitud pide una noticia distinta.
- **Configuración.** Se hace un barrido de `NA_TORCH_THREADS` ∈ {1, 4, 8, 16} × `NA_TTS_WORKERS` ∈ {1, 2, 4}, con al menos 30 síntesis por combinación (RTF y rendimiento). La configuración por defecto es la de **mayor rendimiento cuyo RTF p95 sea < 1**. Con esa configuración se miden los TTFA.
- **Entorno.** El servidor es uvicorn real (HTTP en `127.0.0.1`) en un proceso separado. El cliente es `httpx`, con un hilo por cliente simultáneo. Cada resultado guarda el commit, el hardware, las versiones fijadas, la semilla, los hilos de torch, los trabajadores y el `adapter_id`.

## Metas (PLAN_DESARROLLO.md, criterios de aceptación)

- RTF < 1,0 (se reportan la media y la desviación).
- TTFA p95 < 2 s para noticias de hasta 500 caracteres. Se evalúa con 1 cliente; con 4 y 8 clientes se reporta para el dimensionamiento.
