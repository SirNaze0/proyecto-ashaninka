# PROMPT: Fase 1. Backend sin rol administrativo

> Copia todo lo que está debajo de la línea en una sesión de Claude Code abierta en
> `C:\Users\Marco\Downloads\proyecto-ashaninka\proyecto-ashaninka`.
> Antes, lee `QuitarAdmin/PLAN_QUITAR_ADMIN.md` y `CLAUDE.md`.

---

# ROL

Actúa como ingeniero backend senior (FastAPI y pytest). Vas a quitar del backend la noción de
administrador: ninguna ruta debe pedir token.

# CONTEXTO

- `noticias-ashaninka/backend/app/security.py:25-105`: lógica del token (`require_admin`, `check_admin`,
  `comprobar_token`, `hay_token_configurado`…). Las líneas 108 en adelante (cabeceras y límite de tasa) se quedan.
- `api/news.py:22`: `router = APIRouter(..., dependencies=[Depends(require_admin)])`.
- `api/events.py:146`: `@router.get("/summary", dependencies=[Depends(require_admin)])`.
- `api/synthesize.py:117-125`: un `engine` distinto del configurado exige `check_admin`.
- `api/experiment.py:279-298`: `_autorizar_export` (solo en piloto o con token).
- `main.py:32-42`: aviso de arranque cuando falta el token en producción.
- `conftest.py:91-99` define `ADMIN`/`ADMIN_TOKEN` y fija `NA_ADMIN_TOKEN`.

# TAREAS

1. Eliminar del backend todo el código de token administrativo y las dependencias que lo usan.
2. Quitar `NA_ADMIN_TOKEN` y `NA_EXPORT_TOKEN` de `.env.example`, `.env.local.example`,
   `.env.production.example` y de cualquier artefacto de despliegue que los mencione.
3. Adaptar las pruebas: borrar las que solo comprobaban el 403 y convertir las de seguridad de la API
   en «las rutas que antes eran administrativas responden sin token».

# PRUEBAS OBLIGATORIAS (criterio de cierre)

| # | Prueba | Resultado esperado |
|---|---|---|
| 1 | `uv run ruff check backend eval scripts` y `uv run ruff format --check backend eval scripts` | Sin errores |
| 2 | `uv run pytest` | Verde |
| 3 | Sin token, `DELETE /api/news/{id}` | 204 |
| 4 | Sin token, `GET /api/experiment/export` | 200 |
| 5 | Sin token, `GET /api/events/summary` | 200 |

# RESTRICCIONES

- Los middlewares siguen siendo ASGI puros. El límite de tasa y las cabeceras no se tocan.
- No se toca el pipeline lingüístico.

# AL TERMINAR

Escribe `QuitarAdmin/RESUMEN_FASE1.md` con qué se hizo, los archivos, la salida real de las pruebas,
las desviaciones y lo pendiente. Después haz un commit en español.
