# Changelog

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
