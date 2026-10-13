# noticias-ashaninka

Artefacto de tesis: **servicio web de noticias en lengua asháninka con síntesis de voz, texto y
avatar**, con un experimento intra-sujeto (C1 texto, C2 voz, C3 voz + texto, C4 + avatar) para medir
su efecto en la comprensión. Las seis fases del plan están implementadas; lo que depende de personas
o de infraestructura se declara como **pendiente** y no se inventa.

## Mapa de las fases

| Fase | Qué es | Dónde está el código | Documentos | Resultados |
|---|---|---|---|---|
| **1** Pipeline de texto | corpus AmericasNLP, ingesta, normalización, adaptador ortográfico del TTS, G2P | `backend/app/pipeline/`, `backend/app/corpus/` | [normalization_rules](docs/normalization_rules.md), [mms_orthography](docs/mms_orthography.md), [g2p](docs/g2p.md) | [resumen_fase1](resumen_fase1.md) · `eval/results/fase_1.json` |
| **2** Síntesis de voz | motores `mms_vits` y `espeak_ng`, caché por contenido, modo por lotes y bajo demanda | `backend/app/pipeline/tts/`, `backend/app/batch/`, `backend/app/api/synthesize.py` | [sizing](docs/sizing.md), [manifest_schema](docs/manifest_schema.md), [intelligibility](docs/intelligibility.md) | [resumen_fase2](resumen_fase2.md) · `fase_2.json` |
| **3** Alineación y avatar | tiempos por fonema y palabra, visemas, avatar VRM (three-vrm) con degradación | `backend/app/pipeline/viseme/`, `frontend/src/avatar/` | [avatar](docs/avatar.md), [avatar_decision](docs/avatar_decision.md) | [resumen_fase3](resumen_fase3.md) · `fase_3.json` |
| **4** Interfaz web | PWA en Preact, condiciones C1–C4, Service Worker, cola de eventos | `frontend/src/app/`, `backend/app/api/{catalog,events}.py` | [pwa](docs/pwa.md) | [resumen_fase4](resumen_fase4.md) · `fase_4.json` |
| **5** Experimento | cuadrado de Williams, flujo guiado, cuestionarios, exportación y análisis estadístico | `backend/app/experiment/`, `frontend/src/app/experiment.ts`, `eval/fase5/` | [metrics](docs/metrics.md), [DATA_DICTIONARY](data/DATA_DICTIONARY.md) | [resumen_fase5](resumen_fase5.md) · `fase_5.json` |
| **6** Despliegue y seguridad | Docker + Caddy (HTTPS), endpoints administrativos con token, cabeceras y CSP, kit de escucha 5.7, hashes de modelos | `Dockerfile`, `docker-compose.yml`, `Caddyfile`, `backend/app/security.py`, `eval/listening/inteligibilidad_mos/` | [deployment](docs/deployment.md), [architecture](docs/architecture.md), [limitations](docs/limitations.md) | [resumen_fase6](resumen_fase6.md) · `fase_6.json` |

Las cifras de cada fase salen de ejecuciones reales (`eval/results/*.json`). El plan completo está en
`PLAN_DESARROLLO.md` (en la raíz del repositorio) y las **limitaciones** de cada medición en
[docs/limitations.md](docs/limitations.md).

> La voz y el avatar del servicio son **sintéticos**. El modelo de voz `facebook/mms-tts-cni`
> tiene licencia **CC-BY-NC 4.0 (uso no comercial)**. Ver [LICENSES.md](LICENSES.md).

## De cero a funcionando

### A. En un servidor, con Docker (producción)

Requisitos: Docker con `docker compose` v2, un dominio apuntando al servidor y los puertos 80 y 443
abiertos (2 vCPU y 2 GB de RAM bastan en modo por lotes). Guía completa: [docs/deployment.md](docs/deployment.md).

```bash
cp .env.production.example .env
python -c "import secrets; print(secrets.token_urlsafe(32))"   # -> NA_ADMIN_TOKEN en .env (y NA_DOMAIN)
docker compose --profile setup run --rm setup    # una vez: descarga el modelo de voz y verifica sus SHA-256
docker compose up -d --build                     # app + Caddy con HTTPS automático
curl -s https://su-dominio/api/health/ready      # {"status":"ok","db":true,"static":true,"tts":true}
```

### B. En su máquina, sin Docker (desarrollo)

```bash
./init.sh --with-tts                             # uv, Python 3.11, dependencias, .env, BD, corpus y modelo (ver abajo)
(cd frontend && npm install && npm run build)    # compila la PWA a frontend/dist
uv run python -m app.cli import --from-corpus dev --limit 20 && uv run python -m app.cli process --all
uv run python -m app.batch build --all           # sintetiza por lotes -> static/
uv run uvicorn app.main:app                      # http://127.0.0.1:8000
```

### Verificar todo en un comando

```bash
scripts/verify.sh [--sin-e2e]   # ruff, pytest, vitest, tipos, build, E2E en Chromium real y eval/results/fase_6.json
```

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

### Interfaz web (Fase 4)

```bash
(cd frontend && npm install && npm run build)       # compila la PWA a frontend/dist
uv run uvicorn app.main:app                          # http://127.0.0.1:8000  (PWA + /api + /static)
(cd frontend && npm test && npm run e2e)             # vitest y Playwright en Chromium real
```

Abrir una noticia en una condición: `http://127.0.0.1:8000/#/noticia/1?c=C3` (C1, C2, C3 o C4).

### Experimento (Fase 5)

```bash
NA_EXPERIMENT_PILOTO=true uv run uvicorn app.main:app      # abrir http://127.0.0.1:8000/#/experimento
uv run python -m app.cli experiment export --out data/export [--incluir-piloto] [--format csv,json,parquet]
uv run python -m app.cli experiment dictionary             # regenera data/DATA_DICTIONARY.md
uv run python -m eval.fase5.analysis data/export           # análisis estadístico de una exportación real
uv run python -m eval.fase5.run                            # simulación sintética + análisis -> fase_5.json (~4 min)
```

Sin noticias revisadas por un hablante (P4) el experimento real no arranca; el modo piloto
(`NA_EXPERIMENT_PILOTO=true`) admite pseudo-noticias y marca todo como piloto.

### Pruebas de escucha (tarea 5.7)

```bash
uv run python -m eval.listening.inteligibilidad_mos.build          # kit: MMS y eSpeak, mismo volumen, clave aparte
uv run python -m eval.listening.inteligibilidad_mos.score respuestas_*.csv   # acierto y CER por palabra, MOS, IC, acuerdo
```

El kit (`eval/listening/inteligibilidad_mos/out/kit_escucha.zip`) se entrega a los oyentes; `clave.csv`
no. Instrucciones en [eval/listening/inteligibilidad_mos/INSTRUCCIONES.md](eval/listening/inteligibilidad_mos/INSTRUCCIONES.md).
Sin personas solo se verifica con oyentes **simulados**: la medición real sigue pendiente.

### Seguridad y operación (Fase 6)

- Los endpoints administrativos (`/api/events/summary`, `/api/news*`, la exportación y elegir el motor en
  `/api/synthesize`) están **cerrados por defecto**: exigen la cabecera `x-admin-token` con `NA_ADMIN_TOKEN`.
- Toda respuesta lleva cabeceras de seguridad y una CSP; hay límite de tasa por IP; con `NA_ENV=production`
  no se publican `/docs` ni `/openapi.json`. `GET /api/health` (vivo) y `/api/health/ready` (listo).
- `uv run python scripts/verify_models.py` comprueba los SHA-256 de los modelos contra `models.lock.json`;
  `uv run python -m app.cli db-backup --out copia.db` hace una copia consistente de la base de datos.

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

> El diagrama completo del sistema y las latencias medidas por etapa están en [docs/architecture.md](docs/architecture.md).

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
| `backend/app/experiment/` | Fase 5: cuadrado de Williams, noticias del experimento, cuestionarios, privacidad y exportación |
| `backend/app/security.py` | Fase 6: token administrativo, cabeceras con CSP y límite de tasa |
| `frontend/` | PWA (Preact), avatar (three-vrm) y pruebas vitest y Playwright |
| `Dockerfile`, `docker-compose.yml`, `Caddyfile` | Fase 6: imagen, orquestación y proxy con HTTPS |
| `models.lock.json`, `scripts/` | hashes de los modelos, copias de seguridad y verificación en un comando |
| `backend/app/corpus/` | carga, informe y extracción de candidatos del corpus |
| `backend/app/pipeline/**/resources`, `rules`, `adapters/*.yaml` | recursos lingüísticos versionados |
| `data/candidates/` | candidatos extraídos del corpus (evidencia, sin validar) |
| `eval/` | experimentos y métricas (`fase1`…`fase6`, `listening/`); `eval/results/` guarda los resultados reales |
| `docs/` | documentación (parte generada automáticamente) |

## Citas

Si usas este artefacto, cita también el corpus y los modelos: ver [CITATION.md](CITATION.md).
