# noticias-ashaninka

Artefacto de tesis: **servicio web de noticias en lengua asháninka con síntesis de voz, texto y
avatar**. Fases implementadas:

- **Fase 1, pipeline de texto:** corpus, ingesta, normalización, adaptador ortográfico del TTS y G2P.
- **Fase 2, síntesis de voz:** motores intercambiables, duraciones, caché, modo por lotes y modo bajo demanda con streaming.

> La voz y el avatar del servicio son **sintéticos**. El modelo de voz `facebook/mms-tts-cni`
> tiene licencia **CC-BY-NC 4.0 (uso no comercial)**. Ver [LICENSES.md](LICENSES.md).

## Instalación (cualquier máquina)

Requisitos del sistema: `git`, `curl` y `bash` (en Windows basta con Git Bash). El script no usa
`sudo`: si falta algo, te dice cómo instalarlo.

```bash
./init.sh
```

El script hace lo siguiente:

- Instala `uv` y Python 3.11, y luego las dependencias.
- Crea `.env` y la base SQLite.
- Descarga el corpus AmericasNLP 2021 y el vocabulario de `mms-tts-cni`, ambos en versiones fijadas y verificados por SHA-256.
- Configura `pre-commit` y valida los recursos YAML.
- Ejecuta la prueba rápida.

| Opción | Efecto |
|---|---|
| `--with-data` | Genera el informe y los candidatos del corpus, importa las noticias de `data/news/` (o 20 pseudo-noticias del corpus si no hay) y las procesa |
| `--with-audio-eval` | Instala `torch` y `transformers` (CPU) y descarga `mms-tts-cni` (unos 140 MB) |
| `--with-asr-eval` | Además descarga `mms-1b-all` (unos 3,9 GB) para el experimento 1.9 |
| `--with-tts` | Fase 2: igual que `--with-audio-eval` y además verifica eSpeak-NG (se instala aparte) |
| `--with-monolingual` | Descarga el corpus monolingüe iapucp (carpeta `cni`) |
| `--check` | Solo verifica el entorno, sin modificar nada (código 0 si todo está bien) |
| `--reset-db` | Recrea la base de datos (pide confirmación salvo con `--yes`) |

## Uso

```bash
uv run python -m app.cli import data/news/          # noticias JSON con el contrato del §2
uv run python -m app.cli import --from-corpus dev --limit 20   # pseudo-noticias de prueba
uv run python -m app.cli process --all
uv run python -m app.cli report --news 1            # reporte editorial legible
uv run python -m app.cli corpus report              # docs/corpus_report.md
uv run python -m app.cli corpus extract             # data/candidates/*.yaml
uv run python -m app.cli build-docs                 # docs/normalization_rules.md
uv run uvicorn app.main:app --reload                # API en http://127.0.0.1:8000/docs
```

Para convertir noticias de prueba (`.txt`, `.docx`, `.json`, `.csv`) al contrato:

```bash
uv run python scripts/convert_test_news.py ruta/a/noticias --tipo traduccion_automatica
```

### Síntesis de voz (Fase 2)

```bash
uv run python -m app.batch build --all              # modo por lotes -> static/ (caché + manifiestos)
uv run python -m app.batch build --news 3 --engine espeak_ng
uv run python -m app.batch schema                   # docs/manifest.schema.json
NA_TTS_PRELOAD=true uv run uvicorn app.main:app     # servidor con el modelo precargado
```

- **Bajo demanda:** `GET /api/synthesize/{id}` devuelve un stream NDJSON con un evento por oración.
- **Por lotes:** `GET /static/news/{id}/manifest.json`. El audio se sirve con soporte de `Range`.
- **Elegir motor:** con `NA_TTS_ENGINE`, que acepta `mms_vits` (principal, no comercial), `espeak_ng` (línea base GPL) o `fake` (pruebas).
- **Formatos:** ver [docs/manifest_schema.md](docs/manifest_schema.md).

### Evaluación

```bash
uv run pytest --cov --cov-report=json                     # pruebas + cobertura
uv run python -m eval.fase1.mms_orthography.run --n 100   # experimento 1.9 (requiere --with-asr-eval)
uv run python -m eval.listening.rewrite_check.build       # material de escucha (1.8)
uv run python -m eval.fase1.p5_sample                     # lista de 200 palabras para P5
uv run python -m eval.fase1.run                           # métricas -> eval/results/fase_1.json
uv run python -m eval.fase2.tokenization.run              # tokenización T1 vs T2 (2.2b)
uv run python -m eval.rtf_ttfa.bench all                  # RTF, barrido, TTFA HTTP (2.8, ~1 h)
uv run python -m eval.fase2.sizing                        # dimensionamiento (2.9)
uv run python -m eval.fase2.intelligibility.run           # CER sobre el split test (2.10)
uv run python -m eval.fase2.run                           # métricas -> eval/results/fase_2.json
```

## Arquitectura de la Fase 1

```
texto cni ─► segmentación ─► 2a clasificación ─► 2-0 unificación (palabras cni)
                                               ├► 2b verbalización (números, fechas, dinero)
                                               ├► 2c siglas (glosa en 1.ª mención)
                                               └► 2d reescritura castellano→cni (P2d)
          ─► TEXTO CANÓNICO ─┬► G2P (segmentación grafémica; fonemas cuando P1 se valide)
                             └► 2e adaptador MMS (H1) ─► 2f validación estricta ─► texto TTS
```

- **Texto canónico:** es la ortografía del sistema, la mayoritaria del corpus (`k`, `b`, `ts`, `ñ`). Es un SUPUESTO pendiente de P1 y P7.
- **Texto TTS:** es la ortografía con la que se entrenó `mms-tts-cni`. Ese modelo no conoce `k`, `b`, `ñ` ni `z`, y su tokenizador las **elimina en silencio**, así que el adaptador es obligatorio. Ver [docs/mms_orthography.md](docs/mms_orthography.md).
- **Ningún dato lingüístico del asháninka está inventado.** Cada regla tiene uno de estos estados: `validado`, `candidato-corpus` o `SUPUESTO-LING`. Ver [docs/normalization_rules.md](docs/normalization_rules.md).

## Estructura

| Ruta | Contenido |
|---|---|
| `backend/app/pipeline/` | segmentación, normalizador, G2P, adaptador TTS y motores (`tts/`) |
| `backend/app/batch/` | caché por contenido, manifiesto, tiempos y modo por lotes |
| `backend/app/corpus/` | carga, informe y extracción de candidatos del corpus |
| `backend/app/pipeline/**/resources`, `rules`, `adapters/*.yaml` | recursos lingüísticos versionados |
| `data/candidates/` | candidatos extraídos del corpus (evidencia, sin validar) |
| `eval/` | experimentos y métricas; `eval/results/` guarda los resultados reales |
| `docs/` | documentación (parte generada automáticamente) |

## Citas

Si usas este artefacto, cita también el corpus y los modelos: ver [CITATION.md](CITATION.md).
