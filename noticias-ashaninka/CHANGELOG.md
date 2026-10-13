# Changelog

## Fase 3 — Alineación, visemas y avatar (2026-10-12)

### Añadido
- **3.1:** comparativa de TalkingHead y three + three-vrm (`docs/avatar_decision.md`, `frontend/bench/`). **Se adopta three-vrm.**
- **3.2:** alineación por palabra y fonema (`pipeline/viseme/align.py`) y su validación contra el alineador forzado CTC de `mms-1b-all` (`eval/fase3/alignment.py`, `ctc.py`). Kit de anotación de Praat (`eval/fase3/praat.py`), pendiente de una persona.
- **3.3:** `pipeline/viseme/resources/map.yaml`, mapa grafema → visema `SUPUESTO-LING` versionado por hash (entra en `all_resource_paths()` y en `docs/normalization_rules.md`).
- **3.4:** pista de visemas con coarticulación y suavizado configurable (`pipeline/viseme/track.py`, `NA_VISEME_SMOOTH_MS`, `NA_VISEME_LEAD`). `seg_NNN.json` incluye `alignment` y `visemes`; el manifiesto sube a la **versión 1.1** (compatible con la 1.0).
- **3.5:** visor del avatar en `frontend/` (Vite + Preact + TypeScript): carga diferida de three-vrm, reloj sincronizado al audio, parpadeo, mirada, 4 gestos procedurales, `AvatarPanel` listo para la Fase 4 y `scripts/optimize_vrm.py`.
- **3.6:** degradación (sondeo de FPS de 2 s y detección de WebGL) con registro del evento; probada en Chromium real.
- **3.7:** captura de 40 clips MP4 a partir del split dev (`frontend/scripts/capture.mjs`, `eval/fase3/lipsync.py`).
- **3.8:** desfase directo (con calibración por desplazamientos conocidos), LSE-D y LSE-C con SyncNet y control negativo; peso del paquete (`eval/fase3/bundle.py`). `eval/results/fase_3.json`.
- Pruebas: 17 de visemas y alineación, 14 de utilidades de evaluación, 2 de integración del manifiesto y 17 del cliente (vitest).

### Cambiado
- `docs/metrics.md`: métricas de la Fase 3 definidas antes de medir y, aparte y fechada, la revisión del desfase directo tras la primera medición.
- `README`/`docs`: `docs/avatar.md`, `docs/avatar_decision.md`, `docs/manifest_schema.md` (1.1) y `docs/limitations.md` (26–35).

### Cierre de la Fase 2 (2026-10-12)
- Aprobada. Modo por lotes como modo principal; bajo demanda solo como respaldo. La línea base eSpeak-NG sigue pendiente (la instalación requiere confirmación de administrador).

## Fase 2 — Síntesis de voz (2026-10-06)

### Añadido
- **2.0:**
  - etiqueta `fase1`;
  - `pre-commit` desde la raíz del repositorio `Proyecto` (con `scripts/venv_exec.sh`);
  - `init.sh` detecta el repositorio con `git rev-parse` y busca eSpeak-NG;
  - opción `--with-tts`.
- **2.1:**
  - interfaz `TTSEngine`;
  - `FakeEngine`;
  - registro de motores con un solo parámetro (`NA_TTS_ENGINE`) y `EnginePool`.
- **2.2:** `MmsVitsEngine` con un *forward hook* sobre `duration_predictor`. Las duraciones se verifican en cada síntesis (`sum(frames) × hop == len(audio)`), y se mantiene la regresión R13 del tokenizador.
- **2.2b, hallazgo:** `VitsTokenizer` rompe el intercalado de blancos porque el blanco de MMS es la letra `a`. Experimento T1/T2 con regla fijada antes de ejecutar: **se adopta el intercalado manual (T2)** (CER −0,0034, p = 0,046).
- **2.3:** `ESpeakEngine` (línea base en modo `texto-es`; el modo por fonemas queda deshabilitado sin P1).
- **2.4 y 2.5:**
  - metadatos completos por audio (licencia, variante, aviso de voz sintética);
  - Opus (25,8 kbps reales) y MP3 con `soundfile`;
  - caché por contenido;
  - manifiesto por noticia con JSON Schema;
  - tiempos por fragmento original.
- **2.6:** modo por lotes idempotente (`python -m app.batch`) y tablas `AudioAsset` y `SynthesisRun`.
- **2.7:**
  - streaming NDJSON (`/api/synthesize/{id}`);
  - `/static` con soporte de `Range`;
  - límites 413 y 503;
  - precarga opcional (`NA_TTS_PRELOAD`).
- **2.8 a 2.10:**
  - banco de pruebas de rendimiento;
  - dimensionamiento;
  - CER sobre el split test;
  - figuras;
  - `docs/metrics.md`, `docs/sizing.md`, `docs/manifest_schema.md`, `docs/intelligibility.md` y `docs/tokenization.md`.

### Corregido
- Bloqueo de SQLite con varios streams simultáneos: commit por segmento, modo WAL y `busy_timeout`.
- `torch` y `transformers` pasan a ser dependencias principales: `init.sh` sin opciones ya no los desinstala.

### Resultados
- RTF de `mms_vits`: 0,19 ± 0,007.
- TTFA p95 del cliente con 1 usuario: 2357 ms (**no cumple** la meta de 2 s); con la configuración de latencia, 1875 ms.
- Por lotes: < 70 ms p95.
- CER en test: 0,0516.
- Ver `resumen_fase2.md`.

## Fase 1 — Actualización posterior a la aprobación (2026-10-05)

### Añadido
- Hipótesis H2 (`ñ→y`) y H3 (`ñ→n`) del adaptador MMS, con una regla de decisión fijada antes de ejecutar.
- El experimento 1.9 agrega la consistencia en palabras con `ñ` (en el espacio MMS de cada hipótesis) y comparaciones pareadas frente a la hipótesis activa.

### Escucha de la ñ
- `eval/listening/enye_ab/`: kit de escucha A/B a ciegas (20 palabras con ñ, 60 pares H1/H2/H3, 4 controles), página HTML sin conexión, instrucciones para la persona oyente y script de puntuación con prueba binomial exacta.

### Resultado
- Ninguna supera a H1 de forma significativa (H2: −0,0008, IC [−0,0034; 0,0025]; H3: −0,0016, IC [−0,0046; 0,0013]). **Se mantiene H1.**
- La `ñ` queda pendiente de una escucha dirigida con un hablante.

## Fase 1 — Pipeline de texto (2026-10-05)

### Añadido
- **Esqueleto e `init.sh` (1.1, 1.1b):**
  - Instalación idempotente sin `sudo`.
  - Versiones fijadas y verificación SHA-256 del corpus y del vocabulario de MMS.
  - Opciones `--with-data`, `--with-audio-eval`, `--with-asr-eval`, `--with-monolingual`, `--check` y `--reset-db`.
  - `shellcheck` en `pre-commit`.
- **Corpus AmericasNLP (1.0):**
  - Carga con verificación de hashes.
  - Informe que reproduce el §3.2 del plan (`docs/corpus_report.md`, sin diferencias).
  - Extractores deterministas de candidatos (numerales, siglas, préstamos, nombres propios, variantes ortográficas y grafemas), solo sobre train y dev.
- **Modelo de datos (1.2):**
  - `News`, `Provenance` (obligatoria), `Segment` (texto canónico y TTS, dos mapas de alineación, fonemas, marcas, `unresolved`, hash de recursos, adaptador) y `ResourceVersion`.
- **Ingesta (1.3):**
  - API REST (CRUD, import, process, segments, editorial-report) que nunca expone el texto en castellano.
  - CLI.
  - Conversor de noticias de prueba (txt, docx, json, csv).
  - Pseudo-noticias del corpus para pruebas.
- **Segmentación (1.4):** párrafos y oraciones con offsets conservados, abreviaturas y enumeraciones.
- **Normalizador (1.5, 1.5b, 1.5c):**
  - Sub-etapas 2-0, 2a, 2b, 2c y 2d.
  - Detector editorial que marca sin modificar.
  - Mapa de alineación original↔canónico verificado por pruebas.
  - `docs/normalization_rules.md` generado.
- **G2P por reglas (1.6):**
  - Segmentación grafémica con `char_spans`.
  - Inventario candidato generado desde el corpus.
  - Justificación en `docs/g2p.md`.
- **Adaptador MMS y experimento (1.9):**
  - `OrthographyAdapter`, hipótesis H0 y H1 en YAML, validación estricta 2f (`OutOfVocabularyError`).
  - Regresión con `VitsTokenizer`.
  - Experimento TTS→ASR con CER, IC por bootstrap y comparación pareada (`docs/mms_orthography.md`).
- **Escucha (1.8) y P5:** hoja de validación auditiva con audio y lista de muestreo de 200 palabras.
- **Métricas:** `eval/results/fase_1.json`, generado por `eval/fase1/run.py`.
