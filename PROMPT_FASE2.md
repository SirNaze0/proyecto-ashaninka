# PROMPT — Fase 2: Síntesis de voz, interfaz intercambiable y medición de RTF/TTFA

> Copia todo lo que está debajo de la línea en una sesión nueva de Claude Code abierta en
> `C:\Users\Marco\Downloads\Proyecto`. Antes, completa los parámetros entre `[corchetes]`.
> Documentos que la sesión debe leer: `PLAN_DESARROLLO.md` (v1.2), `PROMPT_FASE1.md`,
> `resumen_fase1.md` y `noticias-ashaninka/docs/limitations.md`.

---

# ROL

Actúa como ingeniero de software senior especializado en síntesis de voz (TTS) para lenguas de
bajos recursos y en servicios de baja latencia sobre CPU. Vas a implementar la **Fase 2** del
artefacto de una tesis de Ingeniería de Sistemas: "Servicio web de noticias en lengua asháninka
para mejorar el acceso a información mediante síntesis de voz, texto y avatar". El artefacto es la
base experimental de un artículo para una revista Q1. La reproducibilidad, la trazabilidad y la
honestidad de las mediciones valen más que la sofisticación.

# DOCUMENTOS RECTORES

- `PLAN_DESARROLLO.md` (v1.2) es la especificación. Lee en especial:
  - §1 (decisiones confirmadas);
  - §3 (pendientes P1–P7);
  - §3.1 y §3.2 (normalización, las dos ortografías y el hallazgo de MMS);
  - §4 (arquitectura y el **hook de duraciones** de VITS);
  - §5 **Fase 2** (tareas 2.1 a 2.10 y criterios de cierre);
  - §7 (recursos);
  - §8 (riesgos R3, R4, R13 y R14).
- `resumen_fase1.md` describe el estado real del código y cómo se usa.
- `noticias-ashaninka/docs/limitations.md` lista las limitaciones vigentes.

Si este prompt y el plan se contradicen, **manda el plan**: señala la contradicción y pregunta.

# ESTADO ACTUAL (fin de la Fase 1, aprobada por el tesista el 2026-10-05)

**Repositorio**
- Repositorio git en `C:\Users\Marco\Downloads\Proyecto`, con el código en `noticias-ashaninka/`. Último commit: `3d52e48`.
- `pre-commit` **no está activo**: su configuración está en la subcarpeta y no en la raíz del repositorio.

**Entorno**
- Windows 11, CPU AMD de 16 núcleos, sin GPU. Python 3.11 con `uv`, `torch 2.14.1+cpu` y `transformers 5.18.0` (grupo `eval`).
- Modelos descargados en `noticias-ashaninka/models/`:
  - `facebook/mms-tts-cni@a744890` (VITS, CC-BY-NC 4.0);
  - `facebook/mms-1b-all@3d33597` (ASR, CC-BY-NC 4.0).
- Codificación de audio verificada: `soundfile` 0.12 con libsndfile 1.2.2 escribe **OGG/Opus** y **MP3** sin ffmpeg.
- eSpeak-NG **no está instalado** y ffmpeg tampoco.

**Pipeline de texto disponible** (`backend/app/`)
- **`services.Pipeline.process_text(texto)`** devuelve, por segmento:
  - `text_canonical`;
  - `text_tts`, ya validado contra el vocabulario de MMS; vale `None` si el segmento está bloqueado;
  - `tts_ready`;
  - `alignment_map` (original↔canónico);
  - `tts_char_map` (canónico↔MMS);
  - `phonemes`: por ahora etiquetas `<grafema>`, porque P1 no está validado;
  - `editorial_flags`, `unresolved`, `resources_hash` y `adapter_id`.
- **Adaptador MMS** en `pipeline/tts/adapters/mms_cni.py`:
  - hipótesis **activa: H1** (`k→c/qu`, `b→v`, `ñ→ny`, `tz→ts`, `z→s`);
  - H2 (`ñ→y`) y H3 (`ñ→n`) existen, pero no mejoraron a H1 de forma significativa;
  - la escritura de la `ñ` sigue **pendiente** de la escucha A/B con hablantes (`eval/listening/enye_ab/`).
- **Validación estricta 2f:** lanza `OutOfVocabularyError` si un carácter no está en el vocabulario de MMS. El tokenizador nunca debe eliminar caracteres en silencio (R13).
- **Datos de prueba:**
  - no hay noticias reales en `data/news/`;
  - las pseudo-noticias del corpus se importan con `import --from-corpus dev`;
  - el 83,4 % de los segmentos de dev está listo para el TTS; el resto queda bloqueado por falta de P2d.
- **Resultados de la Fase 1** (`eval/results/`):
  - CER de ida y vuelta: H0 0,150, H1 0,059 (100 oraciones de dev);
  - latencia del pipeline de texto en el p95: alrededor de 1 ms por segmento;
  - 70 pruebas, 98,7 % de cobertura.

# PARÁMETROS (completar antes de ejecutar)

- ESPEAK_NG: `[instalado en <ruta> / no instalado: la sesión indica cómo instalarlo y espera]`
- NOTICIAS_DE_PRUEBA: `[ruta a noticias reales en asháninka / "usar pseudo-noticias del corpus"]`
- RESULTADO_ESCUCHA_ENYE: `[ruta a respuestas_escucha_enye.csv / "pendiente": se mantiene H1]`
- CONCURRENCIA_OBJETIVO: `[1, 4, 8 clientes (por defecto) / otros valores]`
- HABLANTE_BILINGÜE disponible en esta fase: `[sí / no]`

# REGLAS INNEGOCIABLES

Siguen vigentes **todas** las reglas de la Fase 1: no inventar datos lingüísticos, nada se
descarta en silencio y todo número viene de una ejecución real. Además:

1. **Nunca se sintetiza un texto que no pasó la validación 2f.** El motor MMS recibe solo
   `text_tts` validado. Un segmento con `tts_ready=false` **no se sintetiza**: queda en el
   manifiesto como "sin audio (bloqueado)", con el motivo, y el servicio entrega el texto
   (modo degradado).
2. **Toda medición se hace con el modelo ya cargado** (en caliente) y se reporta por separado el
   tiempo de carga en frío. Cada resultado guarda el commit, el hardware, las versiones fijadas, la
   semilla, el número de hilos de torch y el `adapter_id`.
3. **El RTF y el TTFA se reportan aunque no cumplan las metas** (RTF < 1,0; TTFA p95 < 2 s). Si no
   se cumplen, se documenta la causa y no se ajusta la definición de la métrica para que pase.
4. **Licencias visibles:** todo audio lleva en sus metadatos el modelo, la revisión, la licencia,
   el aviso "voz sintética" y la variante dialectal. La de MMS es "no documentada (la de los datos
   de entrenamiento de MMS)". Si el motor es no comercial, se emite una advertencia automática en
   el log y en el manifiesto.
5. **Reproducibilidad del audio:** la semilla de cada segmento se deriva de forma determinista de
   `sha256(text_tts + motor + revisión + adapter_id)`. El mismo texto produce el mismo audio, byte
   a byte, en la misma máquina.
6. **La línea base eSpeak-NG no usa fonemas inventados.** El G2P aún emite etiquetas `<grafema>`
   sin validar (P1), así que el modo "fonemas" de eSpeak queda **deshabilitado** hasta que P1 esté
   validado. Mientras tanto, la línea base se ejecuta en modo `texto-es`: eSpeak-NG lee el texto
   canónico con la voz castellana. Se declara como **línea base ingenua**, no como un TTS asháninka.
7. **El experimento de la Fase 1 no se repite** salvo que cambie la hipótesis activa (ver 2.0c).
8. Si un requisito es ambiguo, **pregunta antes de asumir** (máximo cinco preguntas, al inicio).
9. Fuera de alcance en esta fase:
   - alineación fonema-tiempo validada, visemas y avatar (Fase 3);
   - frontend (Fase 4);
   - Docker y despliegue (Fase 6).

   La única excepción: en esta fase se **capturan y guardan** las duraciones de VITS, aunque su
   validación sea de la Fase 3.

# ALCANCE: TAREAS

## 2.0 Preparación y deuda técnica de la Fase 1

- **2.0a** Etiquetar el estado aprobado: `git tag fase1 3d52e48`. La entrega de esta fase son los archivos cambiados respecto a `fase1`.
- **2.0b** Activar `pre-commit` desde la raíz del repositorio (`Proyecto/.pre-commit-config.yaml`), con ganchos que se ejecuten dentro de `noticias-ashaninka/`: `ruff check`, `ruff format --check`, `shellcheck` y `pytest -m smoke`. Ajustar `init.sh` para que detecte el repositorio con `git rev-parse --show-toplevel` en lugar de buscar `.git` en su propia carpeta.
- **2.0c** Si `RESULTADO_ESCUCHA_ENYE` está disponible:
  1. puntuarlo con `uv run python -m eval.listening.enye_ab.score <csv> --oyente <id>`;
  2. aplicar la regla: se cambia la hipótesis activa solo si una escritura gana a H1 con p < 0,05 (prueba binomial) **y** el oyente acierta ≥ 3 de los 4 controles;
  3. si cambia, actualizar `mms_cni.yaml` (`active`), repetir el experimento 1.9 y documentarlo.

  Si la escucha está pendiente, se mantiene H1 y se registra.
- **2.0d** `init.sh`:
  - detectar eSpeak-NG (`espeak-ng --version`); si falta, mostrar cómo instalarlo según el sistema operativo (en Windows, el instalador MSI oficial de eSpeak-NG) sin instalarlo por su cuenta;
  - agregar la opción `--with-tts`, que equivale a `--with-audio-eval` y además verifica eSpeak-NG.

## 2.1 Interfaz `TTSEngine`

En `backend/app/pipeline/tts/base.py`:

```python
@dataclass(frozen=True)
class EngineInfo:
    engine: str            # "mms_vits" | "espeak_ng" | "fake"
    model: str             # p. ej. "facebook/mms-tts-cni"
    revision: str
    license: str           # p. ej. "CC-BY-NC-4.0"
    commercial_use: bool
    dialect: str           # "no documentada (datos de entrenamiento de MMS)"
    input_kind: str        # "text_tts" | "phonemes" | "text_es"
    sample_rate: int

@dataclass
class AudioResult:
    wav: np.ndarray        # float32 mono
    sample_rate: int
    seed: int
    synth_ms: float        # tiempo de síntesis en caliente
    durations: TokenDurations | None   # solo motores que las exponen (VITS)
    meta: dict             # licencia, adapter_id, aviso de voz sintética, etc.

class TTSEngine(ABC):
    def info(self) -> EngineInfo: ...
    def warmup(self) -> float: ...                 # devuelve el ms de carga en frío
    def synthesize(self, text: str, seed: int) -> AudioResult: ...
```

- Un registro de motores elige la implementación con **un solo parámetro**: `NA_TTS_ENGINE=mms_vits|espeak_ng|fake` en `.env`. Es un criterio de cierre.
- **`FakeEngine`**: produce un tono determinista, con una duración proporcional al texto. Hace posibles las pruebas sin modelos y es la base de las pruebas de contrato que **todos** los motores deben pasar.

## 2.2 `MmsVitsEngine` + hook de duraciones

- **Modelo:** se carga una sola vez desde `models/facebook__mms-tts-cni` (revisión fijada), en CPU y en modo `eval()`, con `torch.set_num_threads(N)` configurable (`NA_TORCH_THREADS`).
- **Entrada:** solo `text_tts` validado. Antes de sintetizar, se verifica que la salida normalizada de `VitsTokenizer` sea idéntica a la entrada (la regresión R13 de la Fase 1). Si no lo es, se lanza un error.
- **Hook de duraciones** (§4 del plan): un *forward hook* sobre `model.duration_predictor` captura `log_duration`. A partir de ahí se reproduce el cálculo del modelo para obtener frames por token: `ceil(exp(log_dur) · mask · length_scale)`, respetando `speaking_rate` y `noise_scale_duration`.
  - **Verificación obligatoria:** la suma de frames × `hop_length` debe coincidir con la longitud del WAV, con una tolerancia de ±1 frame. Se prueba sobre al menos 50 oraciones.
  - Si la implementación de `transformers 5.18` no permite reproducir el cálculo, se documenta y se usa la alternativa del plan (el alineador forzado de MMS), marcándolo. No se inventan tiempos.
- **Mapeo a caracteres:** el tokenizador intercala blancos (`add_blank=True`, y el token de relleno es `"a"`, con id 0). Las duraciones de los tokens blancos se reparten entre los caracteres vecinos con una regla documentada (por ejemplo, mitad y mitad). Así se obtienen tiempos por **carácter de `text_tts`**, que se proyectan a caracteres canónicos y a fragmentos originales con `tts_char_map` y `alignment_map`. Se guarda en `TokenDurations` (tokens, frames, segundos, tiempos por carácter de `text_tts`, tiempos por carácter canónico).
- **Alcance:** esto produce los tiempos. Su validación contra anotaciones manuales es la tarea 3.2 de la Fase 3.

## 2.3 `ESpeakEngine` (línea base)

- Se ejecuta como subproceso de `espeak-ng`, con WAV a stdout o a un archivo temporal y parámetros fijos (voz, velocidad, tono), guardados en los metadatos.
- **Modo `texto-es`** (el único habilitado ahora): lee el texto **canónico** del segmento con la voz castellana. Es la línea base ingenua de "un sintetizador genérico leyendo la ortografía asháninka". Licencia GPL-3.0: sin restricción comercial (R3).
- **Modo `fonemas`:** se implementa la conversión de la segmentación del G2P a la notación `[[…]]` de eSpeak, pero queda deshabilitado (lanza un error explicativo) mientras haya entradas del inventario sin `status: validado` (P1).
- Si eSpeak-NG no está instalado, las pruebas de este motor se omiten (skip) con el motivo, y las métricas quedan como `"no_medido (eSpeak-NG no instalado)"`.

## 2.4 Metadatos y registro de licencias

- Cada audio guarda junto a él un JSON de metadatos: motor, modelo, revisión, licencia, uso comercial, variante, `adapter_id`, `resources_hash`, semilla, `text_tts`, duración, `synth_ms`, hilos, sha256 del archivo y `"sintetico": true`.
- Actualizar `LICENSES.md`: eSpeak-NG y su versión detectada.
- Advertencia automática en el log y en el manifiesto si `commercial_use=false`.

## 2.5 Codificación y caché

- Formatos:
  - **Opus** en OGG, a 24–32 kbps (la tasa concreta se elige midiendo tamaño frente a calidad y se documenta);
  - **MP3** de respaldo;
  - WAV solo como intermedio.

  Se usa `soundfile`, ya verificado. Se reporta el tamaño medio por segundo de audio de cada formato.
- **Caché por contenido:** la ruta del audio es `static/audio/<sha256[:2]>/<sha256>.{opus,mp3,json}`, con sha256 de `text_tts + motor + revisión + adapter_id + parámetros`. El modo por lotes y el bajo demanda comparten la caché: un texto ya sintetizado no se vuelve a sintetizar.
- **Manifiesto por noticia** en `static/news/{id}/manifest.json`. Lleva la versión del esquema, `news_id`, el motor, avisos (voz sintética, licencia y variante) y una lista de segmentos con: `idx`, `paragraph_idx`, `text_orig`, `tts_ready`, `audio: {opus, mp3}` o `null`, `duration_s`, `timings` (URL del JSON con duraciones y mapas) y `blocked_reason`.
- El esquema del manifiesto se documenta en `docs/manifest_schema.md`, con un JSON Schema y una prueba que valida los manifiestos generados contra él.

## 2.6 Modo por lotes

- `uv run python -m app.batch build --all | --news ID [--engine mms_vits]` → caché + manifiestos.
- Idempotente: reutiliza la caché y reporta cuántos segmentos sintetizó y cuántos reutilizó.
- Base de datos: tablas nuevas `AudioAsset` (segmento, motor, formato, ruta, sha256, duración, metadatos) y `SynthesisRun` (motor, modo, inicio, fin, conteos y errores). Las migraciones siguen con `create_all` (limitación ya documentada).

## 2.7 Modo bajo demanda (streaming por oración)

- `GET /api/synthesize/{news_id}?engine=…` responde en streaming con `application/x-ndjson`:
  - un evento `meta` (avisos y número de segmentos);
  - un evento `segment` por oración **en cuanto su audio está escrito en caché**, con sus URLs y su duración;
  - un evento `blocked` para los segmentos sin audio;
  - un evento final `done`.
- Los segmentos se sintetizan en orden. El primero sale apenas está listo; ese es el TTFA del servidor.
- `/static` se sirve con soporte de `Range`, que es la base de las descargas reanudables de la Fase 4.
- **Concurrencia:** la síntesis es CPU-bound y corre en un ejecutor con un número de trabajadores configurable (`NA_TTS_WORKERS`). El modelo se carga una sola vez por proceso. Se documenta la decisión (hilos de torch × trabajadores) con mediciones (2.8).
- Seguridad mínima: límite de tamaño de la noticia y del número de solicitudes concurrentes. Si se supera, se responde 503 con `Retry-After`; nada de colas infinitas.

## 2.8 Banco de pruebas de rendimiento (`eval/rtf_ttfa/`)

**Definiciones** (se escriben en `docs/metrics.md` antes de medir):
- **RTF** = tiempo de síntesis en caliente ÷ duración del audio generado, por segmento.
  Se reportan la media, la desviación estándar, p50 y p95.
- **TTFA del servidor** = tiempo desde que llega la solicitud hasta que se emite el evento NDJSON del primer segmento con audio.
- **TTFA del cliente** = TTFA del servidor + descarga de los primeros bytes del primer audio, medido desde un cliente HTTP real en la misma máquina.
- **TTFA en modo por lotes** = obtener el manifiesto + los primeros bytes del primer audio (caché caliente).

**Protocolo:**
- N ≥ 100 síntesis por motor, con noticias de **hasta 500 caracteres**. Si no hay noticias reales, se arman pseudo-noticias concatenando oraciones de dev **listas para el TTS** hasta 300–500 caracteres, con una muestra fija y semilla.
- Concurrencia: 1, 4 y 8 clientes (o `CONCURRENCIA_OBJETIVO`). Se reportan p50, p95 y p99 del TTFA y el rendimiento en segundos de audio por segundo.
- Barrido de configuración: `NA_TORCH_THREADS` ∈ {1, 4, 8, 16} × `NA_TTS_WORKERS` ∈ {1, 2, 4}, con al menos 30 síntesis por combinación. Se elige la configuración por defecto con estos datos.
- Se reporta el tiempo de carga en frío de cada motor.
- Salida: `eval/results/fase_2_rendimiento.json` + gráficos generados (PNG) en `docs/figures/`.

## 2.9 Dimensionamiento del servidor

- Con los datos de 2.8 se calcula la CPU y la RAM necesarias para sostener los escenarios definidos en `docs/sizing.md`. Como mínimo:
  1. síntesis por lotes de N noticias al día;
  2. bajo demanda con K usuarios simultáneos y TTFA p95 < 2 s.
- La RAM se mide con `psutil` (agregarlo a las dependencias de desarrollo) en el pico de memoria del proceso con el modelo cargado.
- El resultado **reemplaza** la estimación preliminar del §7 del plan. La estimación medida se propone para actualizar el plan, pero no se edita el plan sin aprobación.

## 2.10 Inteligibilidad objetiva (CER de ida y vuelta)

- Método de la tarea 1.9: TTS → `mms-1b-all` (adaptador `cni`) → CER en el espacio canónico, con IC 95 % por bootstrap.
- Se mide sobre el split **test** del corpus: solo las oraciones listas para el TTS, en una muestra fija de 200 con semilla. Es la primera vez que se usa test.
- Se mide **por motor**: `mms_vits` y `espeak_ng` (modo `texto-es`). Para eSpeak se declara que el ASR de MMS puede favorecer al TTS de MMS, porque comparten datos (sesgo a favor de MMS).
- Comparación pareada mms_vits frente a espeak_ng.
- Salida: `eval/results/fase_2_inteligibilidad.json` + `docs/intelligibility.md`.

## 2.11 Pruebas

- **Contrato `TTSEngine`** (parametrizado por motor; `FakeEngine` siempre, los demás si están disponibles): audio float32 mono no vacío; `sample_rate` correcto; determinismo con la misma semilla; metadatos completos; licencia presente.
- **Hook de duraciones:** la suma coincide con la longitud del WAV (±1 frame) en ≥ 50 oraciones; tiempos monótonos; cada carácter de `text_tts` recibe un tiempo; la proyección a caracteres canónicos cubre el 100 % del texto canónico.
- **Caché:** el mismo texto da el mismo hash y no se vuelve a sintetizar; si cambia el `adapter_id`, cambia el hash.
- **Manifiesto:** valida contra el JSON Schema; los segmentos bloqueados no tienen audio y tienen su motivo.
- **Streaming:** orden de eventos `meta` → `segment`/`blocked`… → `done`; el primer evento con audio llega antes de que termine la noticia (con `FakeEngine` con retardo).
- **Concurrencia:** 503 al superar el límite.
- **Regresión R13:** el texto nunca llega al tokenizador con caracteres fuera del vocabulario.
- Se mantiene la cobertura ≥ 90 % en `backend/app/pipeline/` y en el nuevo `backend/app/batch/`.

# MÉTRICAS: `eval/results/fase_2.json`

Las genera `uv run python -m eval.fase2.run`, que reúne los resultados de 2.8, 2.9 y 2.10. **Nunca se escriben a mano.**

```json
{
  "fase": 2,
  "commit": "<hash>", "fecha": "<ISO-8601>",
  "hardware": {"cpu": "...", "nucleos": 16, "ram_gb": 0, "os": "..."},
  "versiones_fijadas": {"mms-tts-cni": "a744890", "mms-1b-all": "3d33597", "espeak-ng": "x.y"},
  "adapter_activo": "mms_cni/H1",
  "configuracion_por_defecto": {"torch_threads": 0, "tts_workers": 0},
  "carga_en_frio_ms": {"mms_vits": 0, "espeak_ng": 0},
  "rtf": {"mms_vits": {"media": 0, "de": 0, "p50": 0, "p95": 0, "n": 0}, "espeak_ng": {}},
  "ttfa_ms": {
    "bajo_demanda_servidor": {"c1": {"p50": 0, "p95": 0, "p99": 0}, "c4": {}, "c8": {}},
    "bajo_demanda_cliente": {"c1": {}, "c4": {}, "c8": {}},
    "por_lotes": {"c1": {}, "c4": {}, "c8": {}}
  },
  "rendimiento_audio_s_por_s": {"c1": 0, "c4": 0, "c8": 0},
  "duraciones_hook": {"oraciones": 0, "desfase_max_frames": 0, "verificado": true},
  "codificacion": {"opus_kbps": 0, "opus_bytes_por_s": 0, "mp3_bytes_por_s": 0},
  "disponibilidad": {"segmentos_con_audio_pct": 0, "noticias_completas_pct": 0},
  "inteligibilidad_cer_test": {
    "mms_vits": {"cer": 0, "ic95": [0, 0]}, "espeak_ng": {"cer": 0, "ic95": [0, 0]},
    "diferencia_pareada": {}
  },
  "dimensionamiento": {"escenarios": [], "recomendacion": "..."},
  "metas": {"rtf_menor_1": true, "ttfa_p95_menor_2s_c1": true},
  "cobertura_tests_pct": 0
}
```

# CRITERIOS DE CIERRE (del plan, §5 Fase 2)

- [ ] RTF < 1,0 y TTFA p95 < 2 s **medidos** en local, con la definición de `docs/metrics.md`. Si no se cumplen, se reportan igual con su causa.
- [ ] Ambos motores son intercambiables con **un solo parámetro** (`NA_TTS_ENGINE`) y pasan las pruebas de contrato. eSpeak puede quedar `no_medido` si no está instalado, con el motivo.
- [ ] CER de ida y vuelta reportado por motor sobre el split test (2.10).
- [ ] Hook de duraciones verificado (suma = longitud del audio ±1 frame) en ≥ 50 oraciones.
- [ ] Modo por lotes idempotente y modo bajo demanda con streaming NDJSON, compartiendo la caché.
- [ ] Manifiestos válidos contra su JSON Schema, con avisos de voz sintética, licencia y variante.
- [ ] Ningún segmento bloqueado se sintetiza; la disponibilidad se reporta.
- [ ] `docs/metrics.md`, `docs/sizing.md`, `docs/manifest_schema.md` y `docs/intelligibility.md` generados o escritos. `docs/limitations.md` y `LICENSES.md` actualizados.
- [ ] `pre-commit` activo desde la raíz y `./init.sh --check` con código 0.
- [ ] `resumen_fase2.md` en la raíz de `Proyecto`, con lo implementado, el uso actual y los resultados (mismo formato que `resumen_fase1.md`).

# FORMA DE TRABAJO

1. **Antes de programar:** lee los documentos rectores y el código de `noticias-ashaninka/` y responde con:
   - (a) tus preguntas bloqueantes (máximo cinco);
   - (b) el orden de implementación;
   - (c) cómo vas a reproducir el cálculo de duraciones de VITS en `transformers 5.18`, después de leer el código fuente instalado (`.venv/Lib/site-packages/transformers/models/vits/`).

   **Espera la confirmación del tesista.**
2. Orden sugerido: 2.0 → 2.1 (con `FakeEngine` y las pruebas de contrato) → 2.2 → 2.4 → 2.5 → 2.6 → 2.7 → 2.3 → 2.8 → 2.10 → 2.9 → métricas y documentación. Las mediciones largas (2.8 y 2.10) corren en segundo plano mientras avanzas con lo demás.
3. Al terminar cada tarea: `ruff`, `pytest` y commit en el repositorio de `Proyecto`, con los ganchos activos y **sin `--no-verify`**. Si una prueba falla, repórtala con su salida; no la desactives.
4. Antes de las mediciones finales, haz commit del código: cada resultado debe apuntar a un commit que lo reproduzca.
5. Registra en `docs/limitations.md` cada supuesto y cada limitación a medida que aparezcan. Como mínimo:
   - la línea base eSpeak es ingenua;
   - el CER de ida y vuelta favorece a MMS;
   - la variante dialectal de la voz no está documentada;
   - la `ñ` está pendiente;
   - los segmentos quedan bloqueados mientras no exista P2d.

# ENTREGABLE FINAL

1. `fase2_entrega.zip` en la raíz de `Proyecto`, con **solo los archivos nuevos o modificados respecto a la etiqueta `fase1`**, conservando la estructura de carpetas: `git diff --name-only fase1 HEAD`. No incluye modelos, corpus, audio generado ni base de datos.
2. `resumen_fase2.md` en la raíz de `Proyecto`.
3. Un resumen breve en el chat con:
   - qué se implementó;
   - las métricas reales de `fase_2.json` (RTF, TTFA p50/p95/p99 por concurrencia, CER por motor, configuración elegida, dimensionamiento);
   - si las metas se cumplieron o no, y por qué;
   - las limitaciones nuevas;
   - los pendientes que se arrastran (P1, P2d, la `ñ`, las escuchas).
4. Después, detente y espera la aprobación antes de pasar a la Fase 3.
