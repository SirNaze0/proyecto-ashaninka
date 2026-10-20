Lee @CLAUDE.md, @CLAUDE.local.md, @PLAN_DESARROLLO.md v1.2 y @resumen_fase5.md.

Primero: doy por APROBADA formalmente la Fase 5 con fecha de hoy (2026-10-12). Actualiza el estado de la Fase 5 a "APROBADA el 2026-10-12" en `resumen_fase5.md` (raíz y `noticias-ashaninka/`) y en `PLAN_DESARROLLO.md`.

Segundo (objetivo principal de esta sesión): Crea una rama nueva `feat/fase6-despliegue` a partir de `feat/fase5-experimento` y EJECUTA DE PRINCIPIO A FIN TODA LA FASE 6 de @PLAN_DESARROLLO.md (Despliegue con Docker/Caddy, HTTPS, endurecimiento de seguridad de endpoints como `/api/events/summary`, kit/herramienta para las pruebas de escucha 5.7 en `eval/listening/`, reproducibilidad en un comando y verificación final de punta a punta) de forma autónoma y continua:

1. IMPLEMENTACIÓN COMPLETA DE LA FASE 6:
   - Seguridad y Producción en Backend (`backend/app/`): Protege `/api/events/summary` (y cualquier otro endpoint administrativo/diagnóstico previsto en la Fase 6) con token (`NA_EXPORT_TOKEN` o equivalente), añade cabeceras de seguridad, endpoint `/api/health` y configuración lista para producción.
   - Contenedores y Proxy Inverso (`Dockerfile`, `docker-compose.yml`, `Caddyfile`):
     - Implementa un `Dockerfile` multi-etapa limpio (compila `frontend/dist` con Node y empaqueta el backend Python con `uv`, `eSpeak-NG` y `ffmpeg`).
     - Configura `docker-compose.yml` y `Caddyfile` (HTTPS automático, compresión gzip/zstd para activos de texto respetando `Range` en `/static/audio/`, volúmenes persistentes para SQLite, caché estática, modelos y exportaciones).
   - Kit de sesiones de escucha (tarea 5.7 `eval/listening/`): Deja implementado y probado el módulo para generar el paquete de evaluación con hablantes (inteligibilidad humana y MOS) y el script que calcula CER/WER humano, MOS e intervalos de confianza / acuerdo cuando se llenen las respuestas.
   - Documentación final de despliegue y operación (`docs/deployment.md` o lo que indique la Fase 6 del plan) y actualización del `README.md` general con el mapa completo de las Fases 1 a 6.

2. VERIFICACIÓN, PRUEBAS Y CIERRE TOTAL DEL PLAN (FASES 1 A 6):
   - Escribe las pruebas unitarias y de integración de la Fase 6 en `backend/tests/` (seguridad de endpoints, healthcheck, kit de escucha `eval/listening/` y validación de los archivos de despliegue).
   - Verifica que `uv run pytest`, `uv run ruff check`, `uv run ruff format --check`, `npm test`, `npm run typecheck`, `npm run build` y `npm run e2e` pasen con 0 errores.
   - Si Docker está disponible y corriendo en el sistema, verifica el build; si el demonio de Docker no está activo localmente, valida los artefactos por test y repórtalo con exactitud en `eval/results/fase_6.json` y `resumen_fase6.md`.
   - Genera `eval/results/fase_6.json`, redacta `resumen_fase6.md` (en la raíz y en `noticias-ashaninka/`), actualiza `PLAN_DESARROLLO.md` y `CLAUDE.md` dejando las Fases 1 a 6 completadas, y haz el commit final en `feat/fase6-despliegue`.

Trabaja de corrido hasta entregarme la Fase 6 (y todo el PLAN_DESARROLLO.md) 100 % implementado, probado y documentado.
