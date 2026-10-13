# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Layout

The git root holds planning docs and the pre-commit config; **all code lives in `noticias-ashaninka/`** (run every command from there). Project docs are in Spanish; write code comments, docs and commit messages in Spanish to match.

- `PLAN_DESARROLLO.md`, `PROMPT_FASE1.md`, `PROMPT_FASE2.md`, `PROMPT_PLAN_DESARROLLO.md`: thesis plan and per-phase prompts (all six phases are implemented; what still needs people or infrastructure is listed in each `resumen_faseN.md`).
- `resumen_fase1.md` … `resumen_fase3.md` (`resumen_fase4.md`, `resumen_fase5.md` and `resumen_fase6.md` included): results of finished phases (also copied inside `noticias-ashaninka/`). Numbers there come from real runs in `eval/results/*.json`.

The project is a thesis artifact: a news service in Asháninka (`cni`) with TTS voice, text and (external) avatar. Phases implemented: 1 (text pipeline), 2 (speech synthesis, caching, streaming), 3 (alignment, visemes, VRM avatar), 4 (PWA in `frontend/`, conditions C1–C4), 5 (experiment: Williams Latin square, questionnaires, export, analysis package), 6 (Docker + Caddy deployment, admin-token security, listening-test kit, one-command verification).

## Commands (from `noticias-ashaninka/`)

```bash
./init.sh [--with-tts|--with-data|--check|...]   # bootstrap: uv, Python 3.11, deps, .env, SQLite, corpus (hash-verified), pre-commit
uv run pytest                                    # all tests (testpaths = backend/tests)
uv run pytest -m smoke                           # fast subset (also the pre-commit hook)
uv run pytest backend/tests/unit/test_verbalize.py::test_name   # single test
uv run pytest --cov --cov-report=json            # coverage (pipeline, corpus, batch)
uv run ruff check backend eval scripts           # lint (line length 100, E501 ignored)
uv run ruff format --check backend eval scripts
uv run uvicorn app.main:app --reload             # API, docs at /docs
uv run python -m app.cli import|process|report|corpus report|corpus extract|build-docs
uv run python -m app.batch build --all [--news N] [--engine espeak_ng]   # batch audio -> static/
(cd frontend && npm test && npm run typecheck && npm run build && npm run e2e)   # PWA (Fase 4): vitest, tsc, build, Playwright en Chromium real
uv run python -m eval.fase4.run                  # consolida eval/results/fase_4.json (antes: prepare, serve, frontend/scripts/fase4_bench.mjs)
uv run python -m app.cli experiment export --out DIR [--incluir-piloto] [--format csv,json,parquet]   # Fase 5: exportación
uv run python -m app.cli experiment dictionary   # regenera data/DATA_DICTIONARY.md (generado: no editar a mano)
uv run python -m eval.fase5.analysis DIR         # análisis estadístico de una exportación real (excluye el piloto)
uv run python -m eval.fase5.run                  # simulación sintética + análisis + criterios -> eval/results/fase_5.json (~4 min)
scripts/verify.sh [--sin-e2e]                    # Fase 6: ruff, pytest, vitest, tipos, build, E2E y eval/results/fase_6.json en un comando
uv run python -m eval.fase6.run [--sin-build]    # consolida fase_6.json (Docker con exactitud: build solo si `docker info` responde)
uv run python -m eval.fase6.architecture         # regenera docs/architecture.md desde eval/results/fase_*.json (generado: no editar a mano)
uv run python scripts/verify_models.py [--descargar|--generar]   # SHA-256 de los modelos contra models.lock.json
uv run python -m app.cli db-backup --out FILE    # copia consistente de SQLite (scripts/backup.sh la usa dentro de Docker)
uv run python -m eval.listening.inteligibilidad_mos.build|score   # kit de escucha 5.7 (clave.csv NUNCA va en el zip que se entrega)
docker compose --profile setup run --rm setup && docker compose up -d --build   # despliegue (docs/deployment.md)
```

Pytest markers: `smoke`, `corpus` (needs downloaded AmericasNLP corpus in `data/corpus/`), `eval` (needs torch/transformers eval group). Experiments are run as modules, e.g. `uv run python -m eval.fase2.run`, `python -m eval.rtf_ttfa.bench all` (~1 h). Pre-commit (configured at the git root) runs ruff, ruff format check, shellcheck and the smoke tests via `scripts/venv_exec.sh`.

Config is env-driven via `.env` (copy of `.env.example`; production: `.env.production.example`; all vars prefixed `NA_`, every one the code reads must be documented in `.env.example` — a test enforces it): `NA_TTS_ENGINE` (`mms_vits` | `espeak_ng` | `fake` for tests), `NA_TORCH_THREADS`/`NA_TTS_WORKERS`, `NA_MMS_ADAPTER`, `NA_ALLOW_CANDIDATES`, etc.

## Architecture

Text flows through `backend/app/pipeline/` and then into audio:

```
cni text → segment → classify → unify / verbalize (numbers, dates) / acronyms / rewrite es→cni
        → CANONICAL TEXT → G2P (grapheme segmentation)
                         → MMS orthography adapter → strict validation → TTS text
        → TTSEngine → WAV + real durations → Opus/MP3 in content-addressed cache → manifest / NDJSON stream
```

- **Two orthographies.** The canonical text uses the corpus-majority orthography (`k`, `b`, `ts`, `ñ`); `facebook/mms-tts-cni` was trained on a different one and its tokenizer silently drops `k/b/ñ/z`, so the adapter (`pipeline/tts/adapters/`, hypotheses in `mms_cni.yaml`, selected by `NA_MMS_ADAPTER`) plus strict validation is mandatory before synthesis.
- **MMS tokenization:** HF `VitsTokenizer` breaks MMS input (blank token is the letter `a`); the repo uses a manual tokenizer (`NA_MMS_TOKENIZATION=manual`, see `docs/tokenization.md`). Don't switch to `hf` without reading that.
- **Engines** implement `TTSEngine` (`pipeline/tts/base.py`), registered in `registry.py` with an instance pool; `mms_vits.py` exposes real per-token durations via a hook verified on every synthesis. `espeak.py` is a GPL baseline; `fake.py` is for tests.
- **Segments blocked without P2d** (Spanish→cni rewrite) are never synthesized, only delivered as text.
- **PWA (Fase 4):** `frontend/src/app/` (Preact). One `Presentation` component renders C1 text / C2 voice / C3 voice+highlight / C4 +avatar; `player.ts` (2 `<audio>`), `highlight.ts` (uses `spans` of `seg_NNN.json`), `events.ts` (IndexedDB queue -> `/api/events`), `sw.ts` (hand-written Service Worker: 206 for `Range`). three/three-vrm/VRM must stay behind `import()` (initial budget < 3 MB). `cni.json` is empty on purpose (pending a speaker's translation): never invent Asháninka UI text. `app.main` serves `frontend/dist`. See `docs/pwa.md`.
- **Experiment (Fase 5):** `backend/app/experiment/` — `latin.py` (Williams 4×4 + news rotation from the anonymous participant code, pure/deterministic), `pool.py` (fixes the 4 experiment news; prefers ones without blocked segments), `instrumentos.py` + `resources/questionnaire.yaml` (single source of truth for validation and the PWA; every item has a status, comprehension items are `PENDIENTE-HABLANTE`), `export.py` (CSV/JSON/Parquet; `COLUMNAS` generates `data/DATA_DICTIONARY.md`), `privacy.py` (no PII, tested with a negative control). API `/api/experiment` (sessions, idempotent responses, finish; export is closed unless `NA_EXPERIMENT_PILOTO` or `NA_EXPORT_TOKEN`). PWA: `frontend/src/app/experiment.ts` (state machine, `guardia()` route lock, `ResponseQueue`, IndexedDB v2 in `db.ts`) and `components/ExperimentFlow.tsx`. **Real mode needs 4 speaker-reviewed news (P4); `NA_EXPERIMENT_PILOTO=true` accepts corpus pseudo-news and marks everything `piloto`, which never enters the confirmatory analysis.** Consent text and comprehension items are placeholders pending the ethics committee and a speaker: never invent them. Analysis/simulation in `eval/fase5/` (synthetic participants go through the real API; seed and parameters are declared in `docs/metrics.md` before running). E2E for the experiment runs on its own server (`scripts/e2e_server.py --experimento`, Playwright project `experimento`). See `docs/pwa.md`.
- **Security & deployment (Fase 6):** `backend/app/security.py` — `require_admin` (header `x-admin-token`, alias `x-export-token`) is **closed by default**: without a valid `NA_ADMIN_TOKEN` (≥ 16 chars, not an example value) it answers 403. It protects `/api/events/summary`, all of `/api/news*`, `/api/experiment/export` and a non-default `engine` in `/api/synthesize`. **Any new write endpoint must use `require_admin`** unless it is one of the 4 the PWA needs (`test_docs_fase6.py` classifies routes by behaviour and fails otherwise). Security headers + CSP (`connect-src` allows `blob:` because three.js reads avatar textures that way) and the per-IP rate limit are pure-ASGI middlewares (don't switch to `BaseHTTPMiddleware`: it would break NDJSON streaming and `Range`). `NA_ENV=production` hides `/docs`. `Dockerfile` (Node → PWA; Python 3.11 + uv + eSpeak-NG + ffmpeg, non-root), `docker-compose.yml` (only Caddy publishes ports; models are NOT baked in, the `setup` service downloads them and checks `models.lock.json`) and `Caddyfile` (compress text only, never audio/NDJSON). **Docker was never built or run here (daemon off):** artifacts are validated by `test_deploy_artifacts.py` + `test_imagen_simulada.py` + `docker compose config`; say so, don't claim a build. `docs/architecture.md` is generated.
- **Delivery:** `backend/app/batch/` (content-hash cache, manifest with JSON Schema, per-fragment timings; idempotent, tables `AudioAsset`/`SynthesisRun`) for batch mode; `backend/app/api/synthesize.py` streams NDJSON one event per sentence (`/api/synthesize/{id}`), `/static` serves audio with `Range`. SQLite runs in WAL mode with a commit per segment (fixes a lock with simultaneous streams).
- Persistence: SQLModel in `backend/app/db/`; `services.py` orchestrates; `cli.py` is the entry for import/process/report.

## Linguistic data conventions

- **Never invent Asháninka linguistic data.** Every rule/resource entry (YAML under `pipeline/**/resources`, `rules/`, `adapters/*.yaml`) carries a status: `validado`, `candidato-corpus`, or `SUPUESTO-LING` (pending validation by a speaker/linguist, items P1, P2a, P2d, P7…). Keep markers on new assumptions; `candidato-corpus` entries are only used when `NA_ALLOW_CANDIDATES=true` and are flagged per segment.
- `docs/normalization_rules.md`, `docs/corpus_report.md` and `data/candidates/*.yaml` are **generated** (`build-docs`, `corpus report/extract`) — regenerate rather than hand-edit.
- Evaluation: define metrics before measuring (`docs/metrics.md`), evaluate intelligibility only on the **test** split, and never tune on it. Generated outputs under `static/`, `eval/rtf_ttfa/out/`, `data/corpus/`, `models/` are git-ignored.
- Licensing: the MMS voice is CC-BY-NC 4.0 (non-commercial); keep the synthetic-voice notice and license metadata in audio assets (`LICENSES.md`).

## Preferencias de sesión

- Toda comunicación, planes y reportes deben ser siempre en español.
