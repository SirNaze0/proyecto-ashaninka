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


---

# Definición de las métricas de la Fase 3 (alineación, visemas y avatar)

> Escrito **antes** de medir (2026-10-12), con el mismo criterio que la Fase 2: las cifras se
> reportan aunque no cumplan las metas y estas definiciones no se ajustan después de ver los
> resultados. Todo el material sale del split **dev**; el split test no se usa en esta fase.

## Material

- **Selección.** Las primeras 40 noticias de dev (orden de id) cuya única oración tiene audio y
  dura entre 2 y 12 s (`eval/fase3/prepare.py`, `selection.json`). Los 40 clips de 3.7 y 3.8 y las
  oraciones de 3.2 salen de esa misma lista. Se sintetiza con `mms_vits`, adaptador H1, semilla
  derivada del texto, y se usa el Opus que oye el usuario.
- **Avatar.** Modelo VRM provisional (`VRM1_Constraint_Twist_Sample`, pixiv, redistribución
  permitida), con las texturas recomprimidas a 1024 px. **No es la presentadora final.**

## Métricas

| Métrica | Definición | Unidad | Meta |
|---|---|---|---|
| **Error de alineación (3.2)** | Para cada palabra: tiempo de VITS (`durations.char_times`) − tiempo del alineador forzado CTC de `mms-1b-all` (adaptador `cni`) sobre el mismo audio, en inicio, fin y centro. Se reporta sesgo (con signo), MAE, mediana, p90 y fracción dentro de 50 y 80 ms. IC 95 % del MAE del centro: bootstrap por oración (1000 remuestreos, semilla fija) | ms | informativa |
| **Error contra anotación manual (3.2)** | Error medio de los límites de palabra y de fonema contra 20 oraciones anotadas a mano en Praat (`eval/fase3/praat.py`). **Requiere a una persona**; sin anotaciones queda `pendiente` | ms | informativa |
| **Apertura de la boca renderizada** | Se dibuja el avatar fotograma a fotograma (50 Hz). La máscara de la boca sale de comparar el reposo con cada vocal VRM al 100 %; la apertura es la diferencia media de gris con el reposo dentro de la máscara, normalizada por la de la forma `aa`. 1 = boca abierta | 0..1 | — |
| **Desfase directo (3.8)** | Correlación cruzada normalizada (lags de ±300 ms) entre la envolvente RMS del audio (ventana de 40 ms, 50 Hz) y la apertura renderizada. El lag del máximo, refinado con una parábola, es el desfase; positivo = la boca va después del audio. Por clip; se reportan media, mediana, p95 y **máximo en valor absoluto** | ms | **máximo ≤ 80 ms** |
| **Error del reloj del cliente** | En reproducción real en Chromium, desviación del instante usado para evaluar los visemas respecto de una recta ajustada (mínimos cuadrados) a `audio.currentTime` frente a `performance.now()` durante todo el clip. Se reporta el máximo en valor absoluto y el p95 | ms | parte del presupuesto de 80 ms |
| **Desfase total estimado** | Desfase directo (peor clip) + error del reloj (máximo). No incluye la latencia de salida de audio del dispositivo, que no se puede medir desde el navegador sin hardware | ms | ≤ 80 ms |
| **LSE-D / LSE-C (3.8)** | SyncNet (`syncnet_v2`, Chung y Zisserman) como en Wav2Lip: distancia media mínima entre rasgos de vídeo y audio con desplazamientos de ±15 fotogramas (LSE-D, menor = mejor sincronía) y mediana − mínimo de esa distancia (LSE-C, mayor = mejor). Vídeo a 25 fps, recorte de 224×224 del rostro (cámara fija: no se usa detector de caras) | adimensional | informativa |
| **Control negativo de SyncNet** | Las mismas métricas con el audio de OTRO clip (desplazamiento circular de la lista). Si LSE-C no baja claramente, SyncNet no discrimina con este avatar | adimensional | — |
| **FPS** | Fotogramas por segundo medidos con `requestAnimationFrame` durante la reproducción real: (a) Chromium con GPU/ANGLE del equipo de desarrollo, (b) con la CPU 4× más lenta (CDP `Emulation.setCPUThrottlingRate`) y (c) con renderizado por software (SwiftShader) | fps | 60 (equipo) · ≥ 20 (umbral de degradación del plan) |
| **Peso** | Tamaño del paquete inicial (gzip) y de los fragmentos de carga diferida (three, three-vrm, VRM) medidos con `vite build` | KB / MB | inicial < 3 MB; VRM final ≤ 2 MB |

## Limitaciones declaradas de antemano

1. CTC emite picos de ~20 ms: el inicio de palabra es posterior y el fin anterior al sonido real. El
   **centro** de palabra es la medida de referencia.
2. La correlación audio–boca mide cuándo coinciden las energías, no la fonética: una boca que se abre en
   las vocales y se cierra en las consonantes correlaciona bien, pero no prueba que los visemas sean los
   correctos (el mapa es SUPUESTO-LING, pendiente de P1).
3. SyncNet se entrenó con rostros reales; con un avatar estilizado su valor absoluto no es comparable
   con el de vídeos reales (riesgo R8). El control negativo mide si discrimina.
4. Los FPS sin GPU real no representan un Android de gama media; la verificación en dispositivo
   (criterio de cierre de la Fase 4) sigue pendiente.

## Revisión del desfase directo (2026-10-12, tras la primera medición)

> Esta sección se escribió **después** de ejecutar el desfase directo definido arriba y se
> declara como tal. La definición original no se borra: sus resultados se siguen reportando.

**Qué pasó.** El estimador definido de antemano (correlación cruzada por clip entre la envolvente
RMS del audio y la apertura de la boca) dio correlaciones bajas (r mediana ≈ 0,3) y lags que saltan
a ±190–210 ms, el periodo silábico del habla: el máximo de la curva es ambiguo. Con eso, el
«máximo en valor absoluto sobre los clips» es ruido del estimador, no desfase del sistema.

**Calibración (`docs/metrics.md` no la tenía prevista).** Se desplazó la señal de la boca de cada
clip en cantidades conocidas (±40 y ±80 ms) y se midió cuánto sigue cada estimador ese
desplazamiento (error relativo: `lag(d) − lag(0) − d`, independiente del desfase real del sistema):

| Estimador | Descripción | MAE | Máximo |
|---|---|---|---|
| `energia` (por clip) | el definido de antemano | 60,2 ms | 680 ms |
| `plantilla` (por clip) | boca vs campanas gaussianas en las vocales según el alineador CTC | 30,3 ms | 680 ms |
| `energia_agrupado` | promedio de las curvas de los 40 clips | 0,4 ms | 0,7 ms |
| `plantilla_agrupado` | ídem con la plantilla CTC | 1,7 ms | 2,7 ms |

**Regla adoptada** (fijada antes de calcular el desfase con los estimadores nuevos; la primera
versión de la calibración usaba el error absoluto y ya dejaba ver que el desfase sistemático era de
unos pocos ms, así que esa información no era ciega):

1. El desfase **sistemático** del sistema es el pico de la curva **agrupada** de los 40 clips, con IC 95 % por
   bootstrap sobre los clips. El estimador principal es `plantilla_agrupado` (usa el alineador CTC, que no
   depende de las duraciones de VITS) y `energia_agrupado` es la comprobación independiente.
2. El criterio «≤ 80 ms» se evalúa sobre ese desfase sistemático (valor y límite superior del IC).
3. Los lags por clip se reportan, pero **no concluyen**: su error de calibración (30–60 ms de media y
   hasta 680 ms) es del orden del propio criterio. Un clip individual con |lag| > 80 ms no prueba un
   desfase real. Para verificar el criterio clip a clip hace falta un método con más resolución
   (por ejemplo, anotar a mano o grabar la pantalla con audio real).
