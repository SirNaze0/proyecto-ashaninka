# QuitarAdmin: el servicio de noticias en asháninka sin rol administrativo

Esta carpeta documenta el cambio que **quitó la distinción entre «Ciudadano» y «Administrador»**
del proyecto. Hoy cualquier visitante puede leer, publicar, editar y borrar noticias, traducir con
BiTAM y descargar los datos del experimento.

## Estado de las fases

| Fase | Alcance | Prompt | Resumen | Estado |
|---|---|---|---|---|
| 1 | Backend: token eliminado, rutas públicas, `.env*`, pruebas de Python | [PROMPT_FASE1](PROMPT_FASE1.md) | [RESUMEN_FASE1](RESUMEN_FASE1.md) | **Culminada** |
| 2 | PWA: sin selector de rol ni token; Redacción abierta | [PROMPT_FASE2](PROMPT_FASE2.md) | [RESUMEN_FASE2](RESUMEN_FASE2.md) | **Culminada** |
| 3 | Evaluación de la Fase 6 y documentación | [PROMPT_FASE3](PROMPT_FASE3.md) | [RESUMEN_FASE3](RESUMEN_FASE3.md) | **Culminada** |
| 4 | Verificación integral y este README | [PROMPT_FASE4](PROMPT_FASE4.md) | [RESUMEN_FASE4](RESUMEN_FASE4.md) | **Culminada** |

Plan completo: [PLAN_QUITAR_ADMIN.md](PLAN_QUITAR_ADMIN.md).

## Qué es el proyecto

Es el artefacto de una tesis: un **servicio web de noticias en asháninka (`cni`)** que presenta cada noticia
como texto, como voz sintética y con un avatar, y que sirve para medir cuál de esas formas se comprende mejor.
El código vive en `noticias-ashaninka/`:

| Parte | Qué hace | Dónde |
|---|---|---|
| Pipeline de texto | Segmenta, normaliza (números, fechas, siglas), adapta la ortografía para la voz y hace G2P | `backend/app/pipeline/` |
| Voz | MMS-TTS `cni` (principal; CC-BY-NC 4.0) y eSpeak-NG (línea base); caché por contenido, modo por lotes y NDJSON | `backend/app/pipeline/tts/`, `backend/app/batch/` |
| Avatar | Visemas a partir de los tiempos reales y avatar VRM con carga diferida | `backend/app/pipeline/viseme/`, `frontend/src/avatar/` |
| PWA | Preact; condiciones C1 (texto), C2 (voz), C3 (voz + resaltado) y C4 (+ avatar); funciona sin conexión; Sala de redacción | `frontend/` |
| Experimento | Cuadrado de Williams 4×4, cuestionarios, exportación y análisis | `backend/app/experiment/`, `eval/fase5/` |
| Traductor | BiTAM es→cni como **servicio aparte** (entorno propio y GPU) que genera borradores para la Redacción | `traductor/`, `backend/app/translation/` |
| Despliegue | Docker + Caddy (HTTPS), cabeceras, CSP y límite de tasa | `Dockerfile`, `docker-compose.yml`, `Caddyfile` |

## Qué cambió con QuitarAdmin

| Antes | Ahora |
|---|---|
| Selector «Ciudadano / Administrador» y formulario del token en la cabecera | Sin selector: la **Sala de redacción** aparece siempre en la navegación |
| `require_admin` respondía 403 sin un `NA_ADMIN_TOKEN` válido | Ninguna ruta pide token; `NA_ADMIN_TOKEN` y `NA_EXPORT_TOKEN` ya no existen (si siguen en un `.env`, se ignoran) |
| `/api/news*` (crear, editar, borrar, procesar, sintetizar, traducir) solo con token | Públicas |
| `/api/experiment/export` solo en modo piloto o con token | Pública (sin información personal) |
| `/api/events/summary` y elegir `engine` en `/api/synthesize`, solo con token | Públicos |
| — | Se mantienen las cabeceras, la CSP, el límite de tasa por IP y `/docs` oculto en producción |

> ⚠️ **Advertencia de seguridad.** Sin autenticación, quien llegue al servidor puede **borrar noticias** y
> **descargar las respuestas del experimento**. Úselo en una red de confianza o en una demostración. Para
> exponerlo en Internet, ponga autenticación delante (p. ej. `basicauth` de Caddy en `/api/news*` y
> `/api/experiment/export`) o vuelva al rol desde el historial de git (el commit anterior a
> `feat(backend): QuitarAdmin Fase 1`). Está documentado como la limitación 77 de
> `noticias-ashaninka/docs/limitations.md`.

## Cómo ejecutarlo

Todos los comandos se ejecutan desde `noticias-ashaninka/`.

### 1. Instalación (una vez)

```bash
./init.sh                 # uv, Python 3.11, dependencias, .env, SQLite y corpus (con verificación de hash)
./init.sh --with-tts      # además, la voz MMS y comprobar eSpeak-NG
./init.sh --with-data     # además, noticias de prueba
(cd frontend && npm ci)   # dependencias de la PWA
```

En Windows, `init.sh` corre con Git Bash. El `.env` se crea a partir de `.env.example`. Para usar el
traductor local, copie en su lugar `.env.local.example` (trae `NA_TRANSLATOR_URL=http://127.0.0.1:8100`).
Ya no hace falta ningún token.

### 2. Arranque local

```bash
(cd frontend && npm run build)              # compila la PWA (el backend sirve frontend/dist)
uv run uvicorn app.main:app --reload        # API y PWA en http://127.0.0.1:8000 (docs en /docs)
```

Abra `http://127.0.0.1:8000`: **Traductor · Noticias · Estudio TV · Sala de redacción · Ajustes**. Desde la
Sala de redacción se cargan noticias (archivo `.txt`, `.csv` o `.json`, o texto pegado), se publican
(`process` → síntesis por lotes) y se abren en el estudio C4.

Cargar noticias por lotes con la CLI (opcional):

```bash
uv run python -m app.cli import CARPETA        # JSON con el contrato de ingesta (PLAN_DESARROLLO.md §2)
uv run python -m app.cli import --from-corpus dev --limit 20   # o pseudo-noticias del corpus (requiere el corpus)
uv run python -m app.cli process --all
uv run python -m app.batch build --all         # audio por lotes -> static/
```

### 3. Traductor BiTAM (opcional, necesita GPU)

```bash
cd traductor && uv sync          # entorno propio (torch 2.6 cu124); NO se mezcla con el backend
./run.sh 8100 auto               # Windows: .\run.ps1
```

Arránquelo **antes** que el backend. Los pesos están fuera del repositorio (`BITAM_MODELS_DIR`) y no son
redistribuibles. Sin el servicio, la Redacción lo indica y `POST /api/news/translate` responde 503. Más
detalles en `noticias-ashaninka/traductor/README.md` y `docs/translation.md`.

### 4. Producción con Docker

```bash
cp .env.production.example .env                  # complete NA_DOMAIN
docker compose --profile setup run --rm setup    # una vez: descarga la voz y verifica sus SHA-256
docker compose up -d --build                     # app + Caddy con HTTPS automático
```

Guía completa: `docs/deployment.md`. En esta máquina **nunca se construyó la imagen** (el demonio de
Docker está apagado); los artefactos se validan con pruebas y con `docker compose config`.

### 5. Experimento

```bash
NA_EXPERIMENT_PILOTO=true uv run uvicorn app.main:app     # piloto con pseudo-noticias (nunca con participantes reales)
curl -o experimento.zip http://127.0.0.1:8000/api/experiment/export     # exportación (pública)
uv run python -m app.cli experiment export --out DIR      # o con la CLI
uv run python -m eval.fase5.analysis DIR                  # análisis
```

El modo real necesita 4 noticias revisadas por un hablante (P4). El consentimiento y los ítems de comprensión
siguen siendo marcadores, pendientes del comité de ética y de un hablante.

## Pruebas

```bash
scripts/verify.sh [--sin-e2e]                  # todo: ruff, pytest, traductor, vitest, tipos, build, E2E y fase_6.json
uv run pytest                                  # backend (uv run pytest -m smoke = subconjunto rápido)
(cd frontend && npm test && npm run typecheck && npm run build && npm run e2e)
(cd traductor && BITAM_FAKE=1 uv run pytest)   # servicio BiTAM sin GPU
```

Resultados de la última verificación (2026-11-02, en `RESUMEN_FASE4.md`): pytest 337 aprobadas, 9 omitidas
y 1 fallo previo; vitest 102/102; E2E 39 aprobadas y 4 omitidas; traductor 15/15.

**Avatar (resuelto el 2026-11-03):** `./init.sh` descarga y reduce el VRM provisional en `frontend/public/models/presentadora_provisional.vrm`, así que `test_dockerignore_…` ya pasa. Si clonó antes, vuelva a ejecutar `./init.sh` y recompile la PWA.

## Reglas del proyecto que siguen vigentes

- **No se inventan datos lingüísticos en asháninka.** `cni.json` sigue con `null` hasta que lo traduzca un
  hablante; los recursos llevan su estado (`validado`, `candidato-corpus` o `SUPUESTO-LING`).
- La voz MMS es CC-BY-NC 4.0 (uso no comercial); el aviso de voz sintética se mantiene.
- three y three-vrm se cargan con `import()` dinámico (la carga inicial queda por debajo de 3 MB).
- Los documentos generados (`docs/architecture.md`, `docs/normalization_rules.md`, `data/DATA_DICTIONARY.md`)
  se regeneran con sus comandos; no se editan a mano.

## Documentos relacionados

- `noticias-ashaninka/README.md`: mapa de las Fases 1 a 6.
- `noticias-ashaninka/docs/deployment.md`, `pwa.md`, `translation.md` y `limitations.md`.
- `noticias-ashaninka/CHANGELOG.md`, entrada «QuitarAdmin».
- `MejoraEIntegracion/`: la integración previa del traductor BiTAM.
