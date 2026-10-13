# syntax=docker/dockerfile:1.7
# Imagen del servicio (Fase 6, tarea 6.1). Dos etapas:
#   1. frontend: compila la PWA (Node) -> frontend/dist
#   2. app: Python 3.11 + uv, eSpeak-NG y ffmpeg; no lleva modelos (van en un volumen, ver `setup`).
# La imagen NO contiene secretos ni datos: el .env y los volúmenes los pone docker-compose.yml.
ARG NODE_VERSION=20
ARG PYTHON_VERSION=3.11
ARG UV_VERSION=0.11.30

# ---------------------------------------------------------------- 1. PWA
FROM node:${NODE_VERSION}-bookworm-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
# tsc --noEmit + vite build (three y el avatar quedan en chunks de carga diferida)
RUN npm run build

# ---------------------------------------------------------------- 2. Servicio
FROM python:${PYTHON_VERSION}-slim-bookworm AS app
COPY --from=ghcr.io/astral-sh/uv:${UV_VERSION} /uv /uvx /bin/

# espeak-ng: línea base de la voz; ffmpeg: conversiones y herramientas de evaluación;
# libsndfile1: codificación Opus/MP3 de soundfile
RUN apt-get update \
    && apt-get install -y --no-install-recommends espeak-ng ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Dependencias primero (capa que cambia poco). --frozen: exactamente lo de uv.lock (torch CPU).
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Código del servicio. `eval/` solo aporta la descarga de modelos (eval.fase1.download_models).
COPY backend ./backend
COPY eval ./eval
COPY scripts/verify_models.py ./scripts/verify_models.py
COPY models.lock.json LICENSES.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev
COPY --from=frontend /build/frontend/dist ./frontend/dist

# Usuario sin privilegios y carpetas de los volúmenes (se crean con su dueño para que los
# volúmenes con nombre las hereden)
RUN useradd --system --uid 10001 --home-dir /home/app --create-home app \
    && mkdir -p /data /srv/static /models /export \
    && chown -R app:app /data /srv/static /models /export
USER app

# Valores de producción por defecto; docker-compose.yml los vuelve a fijar (ganan al .env).
ENV NA_ENV=production \
    NA_DATABASE_URL=sqlite:////data/noticias.db \
    NA_STATIC_DIR=/srv/static \
    NA_MODELS_DIR=/models \
    NA_FRONTEND_DIST=/app/frontend/dist \
    NA_TRUST_PROXY=true \
    NA_TTS_PRELOAD=true \
    NA_TTS_WORKERS=1

EXPOSE 8000
VOLUME ["/data", "/srv/static", "/models", "/export"]

# Vivo (no exige el modelo): el arranque con el modelo cargado puede tardar un minuto
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"]

# --forwarded-allow-ips: el puerto 8000 solo es alcanzable desde Caddy (red interna de Compose)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
