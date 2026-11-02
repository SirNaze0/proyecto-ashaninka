# Plan: quitar el rol Administrador/Ciudadano

## 1. Contexto y decisión

Hasta ahora el servicio distinguía dos roles:

- **Interfaz (PWA).** La cabecera (`Masthead.tsx`) tenía un selector «Ciudadano / Administrador». Al
  elegir «Administrador» pedía un token, lo comprobaba contra `GET /api/news` y lo guardaba solo en
  memoria. Con el token comprobado se mostraba la Sala de redacción.
- **Servidor.** `backend/app/security.py::require_admin` cerraba con 403 (si no había un `NA_ADMIN_TOKEN`
  de 16 caracteres o más) estas rutas:
  - todo `/api/news*`: crear, importar, editar, **borrar**, procesar, sintetizar, segmentos,
    informe editorial y traducción BiTAM;
  - `GET /api/events/summary`;
  - `GET /api/experiment/export` (abierto solo en modo piloto o con token);
  - un `engine` distinto del configurado en `/api/synthesize`.

**Decisión del responsable del proyecto (2026-11-02):** quitar **toda** la distinción. Cualquier
visitante puede publicar, editar y borrar noticias, traducir con BiTAM y descargar los datos del
experimento.

**Lo que se conserva**, porque no depende del rol: las cabeceras de seguridad y la CSP, el límite de
tasa por IP (`RateLimitMiddleware`), `/docs` oculto con `NA_ENV=production`, el contenedor sin
root y Caddy.

## 2. Riesgos aceptados

| Riesgo | Mitigación que queda |
|---|---|
| Cualquiera puede borrar o modificar noticias en un despliegue público | Copias de SQLite (`db-backup`, `scripts/backup.sh`); desplegar solo en red cerrada o detrás de una autenticación de Caddy si hiciera falta |
| Cualquiera puede descargar las respuestas del experimento | Los datos no contienen información personal (`privacy.py`, con prueba de control negativo) |
| Cualquiera puede pedir el motor eSpeak-NG o lanzar síntesis costosas | Límite de tasa por IP; el motor se sigue validando contra el registro |
| La tesis describía la Fase 6 con token | Nota en `resumen_fase6.md` y nueva entrada en `docs/limitations.md` |

## 3. Fases

| Fase | Alcance | Criterio de cierre | Estado |
|---|---|---|---|
| 1 | Backend: `security.py`, rutas, `main.py`, `.env*`, pruebas de Python | `ruff` y `uv run pytest` en verde; `curl` sin token: DELETE da 204 y la exportación da 200 | Pendiente |
| 2 | PWA: `role.ts`, `App`, `Masthead`, `Newsroom`, i18n, CSS, vitest y E2E | `npm test`, `typecheck`, `build` y `e2e` en verde | Pendiente |
| 3 | Evaluación (`eval/fase6`) y documentación | `docs/architecture.md` regenerado; las pruebas de documentación en verde | Pendiente |
| 4 | Verificación integral y README | `scripts/verify.sh` en verde; `rg` sin restos; README | Pendiente |

### Fase 1. Backend
- `security.py`: eliminar `MIN_TOKEN_LEN`, `TOKENS_DE_EJEMPLO`, `token_valido`,
  `tokens_configurados`, `hay_token_configurado`, `comprobar_token`, `check_admin` y `require_admin`.
- `api/news.py`: el router sin la dependencia `require_admin`.
- `api/events.py`: `/summary` abierto.
- `api/synthesize.py`: sin cabeceras de token; `engine` libre, pero validado.
- `api/experiment.py`: sin `_autorizar_export`.
- `main.py`: sin el aviso de token en producción.
- `.env.example`, `.env.local.example` y `.env.production.example`: sin `NA_ADMIN_TOKEN` ni `NA_EXPORT_TOKEN`.
- Pruebas: `conftest.py`, `test_security.py`, `test_security_api.py`, `test_docs_fase6.py`,
  `test_deploy_artifacts.py`, `test_imagen_simulada.py`, `test_news_build.py`,
  `test_translate_api.py` y `test_experiment_api.py`.

### Fase 2. PWA
- Borrar `role.ts`; sacar `role` y `token` de `App.tsx` y `ctx.ts`.
- `Masthead.tsx`: sin selector ni formulario; el enlace a la Redacción siempre visible fuera de la
  sesión experimental.
- `newsroom.ts` y `Newsroom.tsx`: llamadas sin token.
- `es.json` y `cni.json`: sin las claves `role.*` que queden sin uso. `noticiero.css`: sin los estilos de rol.
- Pruebas: `tests/newsroom*.test.ts`, `e2e/*.spec.ts`, `e2e/helpers.ts`, `scripts/e2e_server.py` y
  `frontend/scripts/fase4_bench.mjs`.

### Fase 3. Evaluación y documentación
- `eval/fase6/run.py` y `architecture.py`; regenerar `docs/architecture.md`.
- `docs/deployment.md`, `pwa.md`, `translation.md`, `limitations.md`, `avatar.md`, `metrics.md`,
  `README.md`, `traductor/README.md`, `CHANGELOG.md` y `CLAUDE.md`.
- Los documentos históricos no se reescriben; se añade una nota.

### Fase 4. Verificación y README
- `scripts/verify.sh`, más una prueba manual con `uvicorn` y `curl`.
- `QuitarAdmin/README.md`.

## 4. Reglas que se mantienen
- No se inventa texto en asháninka (`cni.json` sigue con `null`).
- Los middlewares siguen siendo ASGI puros.
- Three/VRM se cargan con `import()` dinámico (presupuesto inicial < 3 MB).
- Comentarios, documentos y commits en español.
