# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Layout

The git root holds planning docs and the pre-commit config; **all code lives in `noticias-ashaninka/`** (run every command from there). Project docs are in Spanish; write code comments, docs and commit messages in Spanish to match.

- `PLAN_DESARROLLO.md`, `PROMPT_FASE1.md`, `PROMPT_FASE2.md`, `PROMPT_PLAN_DESARROLLO.md`: thesis plan and per-phase prompts (Fase 5 onward — experiment instrumentation, deployment — is planned, not built).
- `resumen_fase1.md` … `resumen_fase3.md` (`resumen_fase4.md` included): results of finished phases (also copied inside `noticias-ashaninka/`). Numbers there come from real runs in `eval/results/*.json`.

The project is a thesis artifact: a news service in Asháninka (`cni`) with TTS voice, text and (external) avatar. Phases implemented: 1 (text pipeline), 2 (speech synthesis, caching, streaming), 3 (alignment, visemes, VRM avatar), 4 (PWA in `frontend/`, conditions C1–C4).

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
```

Pytest markers: `smoke`, `corpus` (needs downloaded AmericasNLP corpus in `data/corpus/`), `eval` (needs torch/transformers eval group). Experiments are run as modules, e.g. `uv run python -m eval.fase2.run`, `python -m eval.rtf_ttfa.bench all` (~1 h). Pre-commit (configured at the git root) runs ruff, ruff format check, shellcheck and the smoke tests via `scripts/venv_exec.sh`.

Config is env-driven via `.env` (copy of `.env.example`, all vars prefixed `NA_`): `NA_TTS_ENGINE` (`mms_vits` | `espeak_ng` | `fake` for tests), `NA_TORCH_THREADS`/`NA_TTS_WORKERS`, `NA_MMS_ADAPTER`, `NA_ALLOW_CANDIDATES`, etc.

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
- **Delivery:** `backend/app/batch/` (content-hash cache, manifest with JSON Schema, per-fragment timings; idempotent, tables `AudioAsset`/`SynthesisRun`) for batch mode; `backend/app/api/synthesize.py` streams NDJSON one event per sentence (`/api/synthesize/{id}`), `/static` serves audio with `Range`. SQLite runs in WAL mode with a commit per segment (fixes a lock with simultaneous streams).
- Persistence: SQLModel in `backend/app/db/`; `services.py` orchestrates; `cli.py` is the entry for import/process/report.

## Linguistic data conventions

- **Never invent Asháninka linguistic data.** Every rule/resource entry (YAML under `pipeline/**/resources`, `rules/`, `adapters/*.yaml`) carries a status: `validado`, `candidato-corpus`, or `SUPUESTO-LING` (pending validation by a speaker/linguist, items P1, P2a, P2d, P7…). Keep markers on new assumptions; `candidato-corpus` entries are only used when `NA_ALLOW_CANDIDATES=true` and are flagged per segment.
- `docs/normalization_rules.md`, `docs/corpus_report.md` and `data/candidates/*.yaml` are **generated** (`build-docs`, `corpus report/extract`) — regenerate rather than hand-edit.
- Evaluation: define metrics before measuring (`docs/metrics.md`), evaluate intelligibility only on the **test** split, and never tune on it. Generated outputs under `static/`, `eval/rtf_ttfa/out/`, `data/corpus/`, `models/` are git-ignored.
- Licensing: the MMS voice is CC-BY-NC 4.0 (non-commercial); keep the synthetic-voice notice and license metadata in audio assets (`LICENSES.md`).

## Preferencias de sesión

- Toda comunicación, planes y reportes deben ser siempre en español.
