# PROMPT: Fase 3. Evaluación y documentación

> Copia todo lo que está debajo de la línea en una sesión de Claude Code abierta en
> `C:\Users\Marco\Downloads\proyecto-ashaninka\proyecto-ashaninka`.
> Antes, lee `QuitarAdmin/PLAN_QUITAR_ADMIN.md`, `RESUMEN_FASE1.md` y `RESUMEN_FASE2.md`.

---

# ROL

Actúa como responsable técnico de la documentación de la tesis. Debes dejar la evaluación de la
Fase 6 y toda la documentación coherentes con un servicio sin rol administrativo, sin falsear los
resultados históricos.

# CONTEXTO

- `eval/fase6/run.py` y `eval/fase6/architecture.py` mencionan el token. `docs/architecture.md`
  es un archivo **generado** con `uv run python -m eval.fase6.architecture`.
- Documentos que hablan del token: `docs/deployment.md`, `pwa.md`, `translation.md`, `limitations.md`,
  `avatar.md`, `metrics.md`, `README.md`, `traductor/README.md`, `CHANGELOG.md` y `CLAUDE.md` (raíz).
- Los históricos (`resumen_fase6.md`, `resumen_ui_noticiero.md`) recogen ejecuciones reales: no se reescriben.

# TAREAS

1. Quitar los criterios del token de `eval/fase6`, regenerar `eval/results/fase_6.json`
   (`uv run python -m eval.fase6.run --sin-build`) y regenerar `docs/architecture.md`.
2. Actualizar la documentación que está viva. En `docs/limitations.md` añadir que la API no tiene autenticación.
3. Añadir una nota de supersesión al final de `resumen_fase6.md` (en la raíz y en `noticias-ashaninka/`).
4. Entrada nueva en `CHANGELOG.md`.

# PRUEBAS OBLIGATORIAS (criterio de cierre)

| # | Prueba | Resultado esperado |
|---|---|---|
| 1 | `uv run pytest backend/tests/unit/test_docs_fase6.py` | Verde |
| 2 | `uv run pytest` | Verde |
| 3 | `uv run ruff check backend eval scripts` | Sin errores |

# AL TERMINAR

Escribe `QuitarAdmin/RESUMEN_FASE3.md` y haz un commit en español.
