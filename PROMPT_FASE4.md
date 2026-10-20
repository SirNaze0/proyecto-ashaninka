Lee @CLAUDE.md, @CLAUDE.local.md, @PLAN_DESARROLLO.md v1.2, @resumen_fase2.md y @resumen_fase3.md.

Primero (actualización rápida de documentos): Ya instalé eSpeak-NG y ejecuté `bench rtf`, `intelligibility.run` y `eval.fase2.run` (RTF espeak_ng = 0,0105; CER espeak_ng = 0,2291 [0,2203; 0,2382], precisión por palabra = 0,0511; escrito en `eval/results/fase_2.json`). Actualiza las tablas y pendientes de `resumen_fase2.md`, `resumen_fase3.md` (raíz y `noticias-ashaninka/`), `docs/intelligibility.md` y `PLAN_DESARROLLO.md` quitando a eSpeak-NG de la lista de pendientes y reflejando que las tareas 2.3, 2.8 y 2.10 quedaron 100 % cerradas.

Segundo (objetivo principal de esta sesión): Con las Fases 1, 2 y 3 implementadas y aprobadas, EJECUTA DE PRINCIPIO A FIN TODA LA FASE 4 de @PLAN_DESARROLLO.md (PWA en Preact, las 4 condiciones experimentales C1–C4, resaltado sincronizado, Service Worker / caché offline, accesibilidad e instrumentación) de forma autónoma y continua:

1. IMPLEMENTACIÓN COMPLETA DE LA FASE 4:
   - Las 4 condiciones del experimento intra-sujeto en `frontend/` (Preact + TypeScript + Vite):
     - C1 (Solo texto): Muestra la noticia normalizada/original sin controles de voz ni carga de audio/avatar.
     - C2 (Solo voz): Reproduce los segmentos de audio Opus (y MP3 de respaldo) desde `/static/news/{id}/manifest.json` v1.1 en modo por lotes (con respaldo a `/api/synthesize/{id}` NDJSON), mostrando el aviso obligatorio de voz sintética CC-BY-NC, sin mostrar el cuerpo del texto ni el avatar.
     - C3 (Voz + texto sincronizado): Reproduce el audio y resalta en tiempo real palabra por palabra / fragmento usando `alignment` de `/static/news/{id}/seg_NNN.json` y `AudioClock` (`frontend/src/avatar/clock.ts`). Los segmentos bloqueados (sin P2d, 16,6 %) se muestran claramente como solo texto con su aviso sin romper la reproducción continua.
     - C4 (Voz + texto + avatar): Integra `AvatarPanel`, `VisemeTrack` y `degradation.ts` (`sin-webgl`, `fps-bajos`, `avatar-ok`) junto con el texto resaltado y el audio sincronizado.
   - API y Listado de Noticias: Implementa en `backend/app/api/` los endpoints previstos en la Fase 4 para listar noticias, servir manifiestos/detalle y registrar eventos/telemetría del experimento.
   - PWA, Service Worker y Presupuesto (< 3 MB): Configura Web App Manifest, Service Worker para caché offline de la app y noticias, y mantén la carga diferida de `three` + `@pixiv/three-vrm` + VRM para cumplir estrictamente el límite < 3 MB.

2. PRUEBAS, MEDICIÓN EN CHROMIUM REAL Y CIERRE DE FASE 4:
   - Escribe todas las pruebas unitarias e integración en `backend/tests/` (`pytest`) y `frontend/tests/` (`vitest`), más las pruebas E2E en Chromium real con Playwright verificando C1, C2, C3, C4, resaltado sincronizado, segmentos bloqueados, degradación y modo offline.
   - Verifica que `uv run pytest`, `uv run ruff check`, `uv run ruff format --check`, `npm test`, `npm run typecheck` y `npm run build` pasen con 0 errores (ahora con los 123 tests de Python pasando incluido eSpeak).
   - Ejecuta los scripts de evaluación de la Fase 4 (`eval/fase4/...`), guarda todas las métricas reales en `eval/results/fase_4.json` y genera `resumen_fase4.md` (en la raíz y en `noticias-ashaninka/`) y actualiza `PLAN_DESARROLLO.md`.

Trabaja de corrido hasta entregarme la Fase 4 100 % implementada, probada y medida.
