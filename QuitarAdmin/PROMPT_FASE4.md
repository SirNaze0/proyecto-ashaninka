# PROMPT: Fase 4. Verificación integral y README

> Copia todo lo que está debajo de la línea en una sesión de Claude Code abierta en
> `C:\Users\Marco\Downloads\proyecto-ashaninka\proyecto-ashaninka`.
> Antes, lee todo `QuitarAdmin/`.

---

# ROL

Actúa como responsable de QA. Comprueba de punta a punta que el servicio funciona sin el rol
administrativo y deja un README que explique el proyecto y cómo ejecutarlo.

# TAREAS

1. Ejecuta `scripts/verify.sh` (o `--sin-e2e` si no hay navegador disponible, y entonces `npm run e2e` por separado).
2. Prueba manual: arranca `uv run uvicorn app.main:app` sin `NA_ADMIN_TOKEN` y con `curl`:
   - `POST /api/news` → 201; `GET /api/news` → 200; `DELETE /api/news/{id}` → 204;
   - `GET /api/experiment/export` → 200; `GET /api/events/summary` → 200.
3. `rg -i "admin_token|require_admin|x-admin-token|puedeVerRedaccion"` → 0 coincidencias fuera
   de los documentos históricos y de `QuitarAdmin/`.
4. Escribe `QuitarAdmin/README.md`: qué es el proyecto, qué cambió, estado de las fases, instalación,
   cómo ejecutar el backend, la PWA, el traductor y Docker, pruebas, advertencias de seguridad y enlaces.

# PRUEBAS OBLIGATORIAS (criterio de cierre)

| # | Prueba | Resultado esperado |
|---|---|---|
| 1 | `scripts/verify.sh` | Verde |
| 2 | Las llamadas `curl` del punto 2 | Los códigos indicados |
| 3 | `rg` del punto 3 | Sin restos |

# AL TERMINAR

Escribe `QuitarAdmin/RESUMEN_FASE4.md` y el `README.md`, y haz un commit en español.
