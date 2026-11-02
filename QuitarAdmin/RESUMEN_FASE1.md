# Resumen de la Fase 1: backend sin rol administrativo

**Estado: Culminada (2026-11-02).**

## 1. Qué se hizo

- Se eliminó del backend toda la lógica de token administrativo. Ninguna ruta responde 403 por
  falta de rol.
- Ahora son públicas: todo `/api/news*` (crear, importar, editar, **borrar**, procesar, sintetizar,
  segmentos, informe editorial y traducción BiTAM), `GET /api/events/summary`,
  `GET /api/experiment/export` (ya no exige modo piloto ni token) y `engine` libre en
  `/api/synthesize` (se sigue validando contra el registro de motores).
- Se conservan las cabeceras de seguridad y la CSP, el límite de tasa por IP y `/docs` oculto en producción.
- `NA_ADMIN_TOKEN` y `NA_EXPORT_TOKEN` desaparecen de los `.env*.example`. Si un `.env` antiguo
  todavía los define, se ignoran sin causar error.

## 2. Archivos

| Archivo | Cambio |
|---|---|
| `backend/app/security.py` | Quitadas `MIN_TOKEN_LEN`, `TOKENS_DE_EJEMPLO`, `token_valido`, `tokens_configurados`, `hay_token_configurado`, `comprobar_token`, `check_admin` y `require_admin` |
| `backend/app/api/news.py` | Router sin `Depends(require_admin)` |
| `backend/app/api/events.py` | `/summary` sin la dependencia |
| `backend/app/api/synthesize.py` | Sin cabeceras de token ni `check_admin` |
| `backend/app/api/experiment.py` | Quitado `_autorizar_export` |
| `backend/app/main.py` | Quitado el aviso de arranque por falta del token |
| `backend/app/schemas.py`, `translation/service.py` | Textos («administrador» → «quien redacta») |
| `.env.example`, `.env.local.example`, `.env.production.example`, `docker-compose.yml` | Sin las variables del token |
| `scripts/e2e_server.py` | Ya no fija `NA_ADMIN_TOKEN` |
| `backend/tests/conftest.py` | Sin `ADMIN` ni `ADMIN_TOKEN` |
| `tests/unit/test_security.py` | Solo cabeceras y límite de tasa, más una prueba de que ya no existe la API del token |
| `tests/integration/test_security_api.py` | «Sin token nada da 403»; crear y borrar sin token; exportación y resumen abiertos; producción también abierta |
| `tests/unit/test_docs_fase6.py` | La clasificación admin/abiertas se sustituye por «ninguna ruta exige token»; los documentos ya no tienen que mencionar `x-admin-token` ni `NA_ADMIN_TOKEN` |
| `tests/unit/test_deploy_artifacts.py` | Los `.env` de ejemplo ya NO deben definir el token |
| `test_imagen_simulada.py`, `test_news_build.py`, `test_translate_api.py`, `test_experiment_api.py`, `test_api_cli.py`, `test_catalog_events.py` | Sin cabeceras de token; las pruebas del 403 pasan a comprobar el acceso abierto |

## 3. Salida real de las pruebas

```
$ uv run ruff check backend eval scripts
All checks passed!
$ uv run ruff format --check backend eval scripts
159 files already formatted

$ uv run pytest -q
FAILED backend/tests/unit/test_deploy_artifacts.py::test_dockerignore_deja_pasar_lo_que_el_runtime_necesita_y_excluye_lo_sensible
1 failed, 337 passed, 9 skipped
```

**El fallo ya existía antes de esta fase**: se comprobó con `git stash`, y sin los cambios falla igual. Falta en
local `frontend/public/models/presentadora_provisional.vrm` (el avatar provisional está fuera del
repositorio), así que no guarda relación con el rol. Las 9 pruebas omitidas lo están por falta del corpus, de eSpeak-NG, de Caddy o
del servicio BiTAM.

Prueba manual (uvicorn real, base de datos temporal, `NA_ADMIN_TOKEN` vacío y piloto apagado):

```
POST   /api/news                  -> 201
GET    /api/news                   -> 200
DELETE /api/news/1                 -> 204
GET    /api/news/1                 -> 404
GET    /api/experiment/export      -> 200
GET    /api/events/summary         -> 200
GET    /api/news/translate/status  -> 200
```

## 4. Desviaciones y pendientes

- La PWA todavía envía `x-admin-token` y tiene el selector de rol: lo resuelve la Fase 2. Mientras
  tanto el servidor ignora esa cabecera, así que nada se rompe.
- La documentación todavía describe el token: lo resuelve la Fase 3.
- El puerto 8791 está reservado por Windows; la prueba manual se hizo en el 8765.
