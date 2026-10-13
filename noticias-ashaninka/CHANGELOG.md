# Changelog

## Fase 6 — Despliegue, seguridad y kit de escucha (2026-10-13)

### Añadido
- **Seguridad (`backend/app/security.py`):** token administrativo `NA_ADMIN_TOKEN` (alias `NA_EXPORT_TOKEN`) en la cabecera `x-admin-token`, **cerrado por defecto**; protege `/api/events/summary`, `/api/news*`, la exportación y la elección del motor en `/api/synthesize`. Cabeceras de seguridad y CSP en toda respuesta, HSTS por HTTPS, límite de tasa por IP y `NA_ENV=production` (sin `/docs`). `/api/health/ready`.
- **Contenedores (6.1, 6.2):** `Dockerfile` multi-etapa (Node → PWA; Python 3.11 + uv + eSpeak-NG + ffmpeg, usuario sin privilegios), `docker-compose.yml` (solo Caddy publica puertos, volúmenes con nombre, servicio `setup` para el modelo), `Caddyfile` (HTTPS automático, zstd/gzip solo para texto, audio con `Range` e inmutable), `.dockerignore` y `.env.production.example`.
- **Reproducibilidad (6.4):** `models.lock.json` con los SHA-256 de los pesos (contrastados con Hugging Face) y `scripts/verify_models.py` (`init.sh` los verifica), `app.cli db-backup`, `scripts/backup.sh` y `scripts/verify.sh` (toda la batería en un comando).
- **Kit de escucha (5.7, `eval/listening/inteligibilidad_mos/`):** construcción con MMS y eSpeak (mismo volumen, clave fuera del zip, repetidos), hoja HTML sin conexión y puntuación (acierto y CER por palabra clave, MOS, bootstrap por oyente, alfa de Krippendorff verificado con el ejemplo publicado, fiabilidad, desglose por variante), con un simulador de oyentes para probarlo.
- **Documentación (6.5):** `docs/deployment.md`, `docs/architecture.md` (generado con las latencias medidas), README con el mapa de las Fases 1 a 6, `LICENSES.md` corregido y limitaciones 59 a 69.
- `eval/fase6/run.py` → `eval/results/fase_6.json` (Docker con exactitud: lo no construido queda «pendiente»).

### Cambiado
- Los endpoints administrativos exigen token (pruebas, specs de Playwright, `scripts/e2e_server.py` y el banco de la Fase 4 se adaptaron).
- `_PwaFiles` normaliza la ruta: la cabecera inmutable de `assets/` no se aplicaba en Windows.
- `connect-src` de la CSP admite `blob:` (texturas del avatar, descubierto con Chromium real).

### Pendiente (requiere personas o infraestructura)
- `docker build`/`up` y HTTPS reales, banco de pruebas en el servidor (6.3), README probado por una persona ajena (6.4) y sesiones de escucha con hablantes.

## Fase 5 — Instrumentación del experimento (2026-10-12)

### Añadido
- **5.2 Asignación:** cuadrado de Williams 4×4 con rotación de noticias, determinista a partir del código anónimo (`backend/app/experiment/latin.py`); las 4 noticias del experimento se fijan en `ExperimentMaterial` (`pool.py`), con preferencia por las que no tienen segmentos bloqueados.
- **5.1/5.3/5.4 Flujo y registro:** consentimiento, 4 bloques en el orden asignado, cuestionario tras cada noticia y final (`frontend/src/app/experiment.ts`, `components/ExperimentFlow.tsx`); guardia de rutas que impide cambiar la condición; IndexedDB v2 y cola de respuestas idempotente. API `/api/experiment` (config, sesiones, respuestas, cierre, exportación) y siete tipos de evento nuevos en `/api/events`.
- **5.5 Privacidad:** código anónimo, edad por rangos, comentario filtrado y verificación automática de la exportación (`privacy.py`) con control negativo.
- **5.6 Exportación:** CSV, JSON y Parquet (`app.cli experiment export`), `manifest.json` con hashes y `data/DATA_DICTIONARY.md` generado desde `export.COLUMNAS`.
- **5.7 Análisis (paquete reproducible, `eval/fase5/`):** simulación sintética por la API real, modelo mixto, Friedman, Wilcoxon, bootstrap, sensibilidad, potencia y cobertura por réplicas; consolidado en `eval/results/fase_5.json`.
- Pruebas: 43 de Python del experimento y 9 de la evaluación, 24 de vitest y 3 E2E en Chromium real.

### Cambiado
- `/api/events`: nuevos tipos (`consent`, `block-start`, `block-end`, `read-done`, `questionnaire-submit`, `session-finish`, `abandon`) y claves de payload (`posicion`, `participant`, `blocks`).
- IndexedDB `na-events` pasa a la versión 2 (migración que conserva los eventos pendientes). `Presentation` admite `experiment` y `onDone` sin cambiar su uso anterior.
- Grupo `eval`: `pandas`, `statsmodels` y `pyarrow`.

### Pendiente (requiere personas)
- Texto del consentimiento y su audio (comité de ética), ítems de comprensión (hablante), noticias revisadas (P4), piloto con 2–3 personas (5.8) y pruebas de escucha (5.7).

## Fase 4 — Interfaz web (PWA) y condiciones C1–C4 (2026-10-12)

### Añadido
- **4.1:** PWA en `frontend/src/app/` (Preact + TypeScript): rutas por hash, lista de noticias, ajustes, i18n `es.json`/`cni.json` (asháninka **pendiente de traducción**, con respaldo al castellano), Web App Manifest e íconos.
- **4.2:** reproductor por segmentos (`player.ts`, `queue.ts`): dos `<audio>` alternos con precarga, Opus con respaldo MP3, velocidad 0,75–1,25×, repetir párrafo, pausa, teclado, segmentos bloqueados saltados sin cortar y respaldo bajo demanda por NDJSON.
- **4.3:** resaltado sincronizado del fragmento **original** con `spans` de `seg_NNN.json` y `AudioClock` (`highlight.ts`); tamaños de texto 100–200 %.
- **4.4:** Service Worker propio (`sw.ts`, `sw-logic.ts`): *shell* precargado sin el avatar, audio y tiempos en caché con respuestas `206` a `Range`, catálogo red primero, «guardar para escuchar sin conexión» y cola de eventos en IndexedDB.
- **4.5:** avisos de voz y avatar sintéticos, licencia (CC-BY-NC), variante dialectal y marca de pseudo-noticia.
- **4.6:** componente único con las condiciones **C1 solo texto, C2 solo voz, C3 voz + texto, C4 voz + texto + avatar** (carga diferida de three y del VRM; degradación `sin-webgl` / `fps-bajos` / `avatar-ok` registrada).
- **4.7:** banco de pruebas del cliente en Chromium real (`frontend/scripts/fase4_bench.mjs`, `eval/fase4/`) y `eval/results/fase_4.json`.
- **API:** `GET /api/catalog`, `/api/catalog/{id}`, `/api/catalog/{id}/meta` (nunca devuelven el castellano), `POST /api/events` (por lotes, idempotente, con lista cerrada de claves) y `GET /api/events/summary`; tabla `ClientEvent`. `app.main` sirve `frontend/dist` y comprime con gzip solo los archivos de texto.
- Pruebas: 24 de vitest nuevas (41 en total), 18 E2E de Playwright en Chromium real (incluye axe-core) y 8 de Python para la API y 9 para la evaluación.
- `docs/pwa.md`, `docs/metrics.md` (Fase 4, escrita antes de medir) y `docs/limitations.md` (36–45).

### Corregido
- `eval/results/fase_2.json`/resúmenes: la línea base eSpeak-NG (RTF 0,0105; CER 0,2291) quedó **cerrada**; tareas 2.3, 2.8 y 2.10 al 100 %. La reejecución en el equipo Intel de 12 núcleos cambió el RTF de `mms_vits` a 0,2546.
- `AvatarPanel`: `role="img"` (axe-core: `aria-prohibited-attr`).

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
- Aprobada. Modo por lotes como modo principal; bajo demanda solo como respaldo. La línea base eSpeak-NG se cerró el 2026-10-12 (ver Fase 4).

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
