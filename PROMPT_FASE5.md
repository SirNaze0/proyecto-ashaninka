Lee @CLAUDE.md, @CLAUDE.local.md, @PLAN_DESARROLLO.md v1.2 y @resumen_fase4.md.

Primero: doy por APROBADA formalmente la Fase 4 con fecha de hoy (2026-10-12). Actualiza el estado de la Fase 4 a "APROBADA el 2026-10-12" en `resumen_fase4.md` (raíz y `noticias-ashaninka/`) y en `PLAN_DESARROLLO.md` (dejando documentados los pendientes externos de Android físico, traducción de UI y modelo VRM final).

Segundo (objetivo principal de esta sesión): Crea una rama nueva `feat/fase5-experimento` a partir de `feat/fase4-pwa` y EJECUTA DE PRINCIPIO A FIN TODA LA FASE 5 de @PLAN_DESARROLLO.md (Diseño e instrumentación del experimento intra-sujeto C1–C4, cuadrado latino, cuestionarios, exportación de datos y paquete de análisis estadístico reproducible) de forma autónoma y continua:

1. IMPLEMENTACIÓN COMPLETA DE LA FASE 5:
   - Asignación experimental y Cuadrado Latino (4x4): Implementa la lógica determinista de asignación de participantes a las secuencias del cuadrado latino balanceado (4 condiciones C1, C2, C3, C4 x 4 noticias aptas sin segmentos bloqueados por defecto, o marcando covariable si los tienen), garantizando contrabalanceo de orden y noticia.
   - Flujo guiado del participante en la PWA (`frontend/`) y Backend (`backend/app/api/`):
     - Consentimiento informado / pantalla de inicio de sesión experimental (con código/ID anónimo de participante, sin PII).
     - Paso automático por los 4 bloques asignados en el orden del cuadrado latino (bloqueando el cambio libre de condición durante una sesión experimental activa).
     - Cuestionario post-noticia (comprensión / carga / aceptabilidad según defina el plan) y cuestionario final post-experimento, guardados localmente en IndexedDB y sincronizados con el backend de forma idempotente.
   - Exportación y Pipeline de Análisis Estadístico (`eval/fase5/` o `scripts/`):
     - Comando/endpoint de exportación limpia de sesiones, eventos (`ClientEvent`), tiempos de lectura/escucha, degradaciones y respuestas de cuestionarios (CSV/JSON/Parquet listos para análisis).
     - Scripts reproducibles de análisis estadístico de la Fase 5 (modelos mixtos / pruebas no paramétricas intra-sujeto / bootstrap definidos antes en `docs/metrics.md`), probados de punta a punta con una simulación sintética de participantes para demostrar que el pipeline de evaluación de la tesis funciona completo.

2. VERIFICACIÓN, PRUEBAS Y CIERRE DE FASE 5:
   - Escribe todas las pruebas unitarias e integración en `backend/tests/` (`pytest`), `frontend/tests/` (`vitest`) y pruebas E2E en Chromium real (`Playwright`) recorriendo una sesión experimental completa de principio a fin (4 condiciones + cuestionarios + exportación).
   - Verifica que `uv run pytest`, `uv run ruff check`, `uv run ruff format --check`, `npm test`, `npm run typecheck`, `npm run build` y `npm run e2e` pasen con 0 errores.
   - Ejecuta la verificación/simulación de `eval/fase5/...`, genera `eval/results/fase_5.json`, redacta `resumen_fase5.md` (en la raíz y en `noticias-ashaninka/`), actualiza `PLAN_DESARROLLO.md` y `CLAUDE.md`, y deja todo comiteado en `feat/fase5-experimento`.

Trabaja de corrido hasta entregarme la Fase 5 100 % implementada, probada y verificada.
