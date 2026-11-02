# PROMPT: Fase 3. Documentación y medición

> Copia todo lo que está debajo de la línea en una sesión de Claude Code abierta en
> `C:\Users\Marco\Downloads\proyecto-ashaninka\proyecto-ashaninka`.
> Antes, lee `NoticiasTVPeru/PLAN_TVPERU.md`, `CLAUDE.md`, `RESUMEN_FASE1.md` y `RESUMEN_FASE2.md`.

---

# ROL

Actúa como responsable de documentación y evaluación de la tesis. Debes documentar la función y medirla con datos reales, sin inventar cifras.

# CONTEXTO

- Las métricas se definen en `docs/metrics.md` ANTES de medir.
- `docs/limitations.md` termina en la 77.

# TAREAS

1. Crear `docs/tvperu.md` y actualizar `pwa.md`, `translation.md`, `deployment.md`, `README.md`, `CHANGELOG.md` y `CLAUDE.md`.
2. Limitaciones 78 a 81.
3. Definir la medición en `docs/metrics.md` y ejecutar `eval/tvperu/run.py` (un ciclo real con BiTAM) → `eval/results/tvperu.json`.

# PRUEBAS OBLIGATORIAS (criterio de cierre)

| # | Prueba | Resultado esperado |
|---|---|---|
| 1 | `uv run pytest backend/tests/unit/test_docs_fase6.py` | Verde |
| 2 | `eval/results/tvperu.json` con cifras reales | Generado |

# RESTRICCIONES

- Si BiTAM no está disponible, se declara y la medición queda pendiente: nunca se inventan cifras.
- Comentarios, documentos y commits en español.

# AL TERMINAR

Escribe `NoticiasTVPeru/RESUMEN_FASE3.md` con:

1. Qué se hizo.
2. Los archivos.
3. La salida real de las pruebas.
4. Desviaciones y pendientes.

Después marca la fase como **Culminada** en `PLAN_TVPERU.md` y haz un commit en español.
