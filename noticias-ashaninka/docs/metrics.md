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

---

# Fase 4: interfaz web (PWA), condiciones C1–C4

> Esta sección se escribió el 2026-10-12, **antes** de construir el banco de pruebas de la Fase 4
> (`eval/fase4/`, `frontend/scripts/fase4_bench.mjs`). Si una definición cambia después, se agrega una
> revisión fechada debajo, como en la Fase 3, sin borrar esta.

## Material

- **Noticias.** Las primeras 30 noticias de dev (por id) con **todas** sus oraciones sintetizadas o
  bloqueadas (sin errores), de 1 a 6 oraciones, más las noticias con al menos un segmento bloqueado que
  existan en esa muestra (para medir C3/C4 con bloqueados). Selección con regla fija en
  `eval/fase4/prepare.py`; se sintetiza con `mms_vits`, adaptador H1, y se sirve el Opus real.
- **Servidor.** `uvicorn` local sirviendo `frontend/dist` y `/static` en el mismo origen. Por lotes
  (manifiesto ya generado). El modo bajo demanda solo se prueba funcionalmente.
- **Navegador.** Chromium de Playwright 1.64 (la versión del `package.json`), con GPU del equipo salvo
  indicación. Perfil nuevo en cada medición «en frío».
- **Perfil móvil simulado.** CPU 4× más lenta (`Emulation.setCPUThrottlingRate`, rate 4) y red 4G de
  referencia: 9 Mbps de bajada, 1,5 Mbps de subida y 150 ms de latencia (`Network.emulateNetworkConditions`),
  que es el perfil «Regular 4G» de Chrome DevTools. Se reporta también sin limitación.

## Métricas

| Métrica | Definición | Unidad | Meta |
|---|---|---|---|
| **Carga inicial** | Suma de `encodedDataLength` de todas las respuestas (CDP `Network.loadingFinished`) desde la navegación a la noticia (condición C3, caché y Service Worker vacíos) hasta el evento `canplay` del audio del primer segmento. Incluye *shell*, catálogo, manifiesto, JSON del segmento y primer audio. **Excluye** el avatar de carga diferida (three, three-vrm, VRM), que solo se descarga en C4; se reporta aparte (`carga_c4`) | MB | **< 3 MB** |
| **TTFA del cliente (por lotes)** | Desde el clic en «Reproducir» hasta el primer evento `playing` del audio. 30 noticias × 3 repeticiones, en frío (caché vacía) y en caliente (Service Worker con la noticia guardada). Se reportan media, DE, p50, p95 y p99 | ms | **p95 < 2000 ms** |
| **TTFA de arranque completo** | Desde la navegación hasta `playing` tras el clic automático en «Reproducir». Informativa: incluye carga del *shell* | ms | informativa |
| **Hueco entre segmentos** | Para cada par de segmentos consecutivos con audio: instante de `playing` del segmento k+1 − instante de `ended` del k. Negativo = solapamiento por precarga | ms | mediana ≤ 50 ms; p95 ≤ 150 ms |
| **Desfase del resaltado** | En cada cambio de fragmento activo, el cliente registra el instante del cambio en el reloj de audio (`AudioClock.now()`) y se resta el `t0` del fragmento en `seg_NNN.json`. Es el error del resaltado frente al audio estimado, **sin** la latencia de salida del dispositivo. Se reportan media, p95 y máximo en valor absoluto, en C3 y C4, sin limitación y con CPU 4× | ms | **\|p95\| ≤ 80 ms** |
| **Cobertura del resaltado** | Fracción de fragmentos con `t1 > t0` que se resaltaron al menos una vez durante la reproducción completa | % | 100 % |
| **FPS en C4** | `requestAnimationFrame` durante 5 s de reproducción: (a) GPU del equipo, (b) con CPU 4× más lenta, (c) sin GPU (SwiftShader). Como en la Fase 3 | fps | 60 (equipo) · ≥ 20 (umbral de degradación) |
| **Degradación** | Los tres casos de `degradation.ts` en C4 dentro de la PWA: sin WebGL → `sin-webgl`; CPU 20× → `fps-bajos`; normal → `avatar-ok`. Debe: mostrar imagen fija, mantener audio y texto, registrar el evento en la cola y recibirlo el servidor | caso/resultado | los 3 casos correctos |
| **Segmentos bloqueados** | En C3/C4 se muestran como solo texto con su aviso; en C2 se omiten con aviso. En todos los casos la reproducción continúa hasta el último segmento | sí/no | sí |
| **Offline** | Se reproduce una noticia completa, se guarda para uso sin conexión, se pasa a modo sin red (`context.setOffline`) y se recarga: la app debe abrir, listar las noticias guardadas y reproducir la noticia completa (C1–C3; C4 si el avatar se había cargado antes) | sí/no | sí |
| **Cola de eventos** | Eventos generados sin red se guardan en IndexedDB y llegan al servidor al volver la conexión, sin duplicados (`event_id`) | % entregados | 100 %, 0 duplicados |
| **Accesibilidad** | Violaciones de axe-core (reglas WCAG 2.1 A y AA) en la lista y en C1–C4. Se cuentan por impacto | n | **0 críticas y 0 graves** |
| **Peso del *shell*** | Paquete inicial (gzip) por `vite build`, calculado desde `dist/.vite/manifest.json` | KB | < 3 MB (referencia) |

## Reglas fijadas de antemano

1. Las metas no se ajustan después de ver los datos. Si una no se cumple, se reporta con su causa.
2. El TTFA de la meta es el **por lotes** en la configuración con CPU 4× y 4G, caché fría; los demás
   valores se reportan como contexto.
3. Se descartan (y se cuentan) las repeticiones en que el navegador rechace `play()` por la política de
   reproducción automática; el banco de pruebas hace un gesto de usuario real (clic) antes.
4. La carga inicial se mide con el Service Worker aún sin instalar (primera visita).

## Limitaciones declaradas de antemano

1. La red 4G y la CPU 4× son **simuladas**: no sustituyen a un Android de gama media real (criterio de
   cierre de la tarea 4.7). Esa verificación es un pendiente que requiere el dispositivo.
2. El desfase del resaltado se mide contra el reloj estimado del audio; no incluye la latencia de salida de
   audio del dispositivo ni la del navegador (no medible sin hardware). La Fase 3 estimó el error del reloj.
3. Las noticias son pseudo-noticias del corpus AmericasNLP (frases sueltas, 1–6 oraciones); no son
   representativas de noticias reales más largas. El TTFA por lotes no depende de la longitud de la noticia
   (solo del primer segmento), pero la precarga y el hueco entre segmentos sí.
4. El modelo VRM es provisional (2,41 MB) y los textos de interfaz en asháninka están pendientes de
   traducción por un hablante.

## Revisión del material (2026-10-12, antes de medir)

> Se escribió **antes** de ejecutar cualquier medición de la Fase 4; no usa ningún resultado.

El corpus AmericasNLP trae **una oración por línea**, de modo que «las primeras 30 noticias de dev
con 1 a 6 oraciones» no existe tal cual. La selección definitiva (`eval/fase4/prepare.py`) es:
**30 pseudo-noticias, cada una con 3 líneas consecutivas del split dev** (líneas 1-2 en el párrafo
1 y línea 3 en el párrafo 2), desde la línea 1 y en orden, sin descartar ninguna. Los segmentos
bloqueados (sin P2d) entran tal como vienen. Reemplaza al párrafo «Noticias» de la sección *Material*.
El split test no se usa.
