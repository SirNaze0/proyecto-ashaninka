# Resumen de la Fase 6: despliegue, seguridad, kit de escucha y reproducibilidad

> **Proyecto:** Servicio web de noticias en lengua asháninka con síntesis de voz, texto y avatar
> **Fecha:** 2026-10-13 · **Repositorio:** `Proyecto` (código en `noticias-ashaninka/`) · **Rama:** `feat/fase6-despliegue` · **Base:** Fase 5 (aprobada el 2026-10-12)
> **Estado:** implementada y verificada con lo que hay en la máquina de desarrollo; **pendiente de aprobación**. **La imagen de Docker no se construyó ni se arrancó** (el demonio de Docker estaba apagado): los artefactos se validaron por pruebas y por `docker compose config`, y el `docker build`, el HTTPS real, el banco de pruebas en un servidor, la prueba del README por una persona ajena y las sesiones de escucha con hablantes siguen **pendientes**.

Las cifras vienen de ejecuciones reales (`eval/results/fase_6.json` y las pruebas de `scripts/verify.sh`). Los criterios se definieron **antes** de construir, en `docs/metrics.md` (sección «Fase 6»); la revisión posterior del kit de escucha está fechada y no ajusta nada con resultados.

**Qué NO demuestra esta fase.** (1) El kit de escucha se probó con **oyentes simulados**: demuestra que recupera valores conocidos, no cuál voz se entiende mejor ni cuán natural suena. (2) Los archivos de despliegue son coherentes con el código y con lo que el servicio necesita, pero **ningún contenedor se ha ejecutado**: el primer `docker compose up` real es su primera prueba. (3) Las latencias de `docs/architecture.md` son de la máquina de desarrollo, no de un servidor.

---

## 1. Qué hace el sistema hoy

```
navegador ──HTTPS──► Caddy :80/:443 ──red interna──► app :8000 (FastAPI + PWA) ──► volúmenes
                     · certificado automático        · no publica puertos        na_data (SQLite WAL)
                     · zstd/gzip solo para texto     · usuario sin privilegios    na_static · na_models · na_export
                     · Range intacto en el audio     · cap_drop ALL
```

- **Endpoints administrativos cerrados por defecto.** `GET /api/events/summary`, todo `/api/news*`, `GET /api/experiment/export` y elegir un motor distinto del configurado en `/api/synthesize` exigen `x-admin-token` (`NA_ADMIN_TOKEN`; el alias `NA_EXPORT_TOKEN` sigue valiendo). Sin un token válido (16 caracteres o más, no de ejemplo) responden **403 aunque el servicio esté en línea**. Lo que usa la PWA sigue abierto.
- **Cabeceras y CSP en toda respuesta** (`nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`, CSP sin orígenes externos), HSTS por HTTPS o en producción, **límite de tasa** por IP (429 con `Retry-After`) y `NA_ENV=production` sin `/docs`, `/redoc` ni `/openapi.json`.
- **Salud:** `/api/health` (vivo) y `/api/health/ready` (base de datos, carpeta de audio escribible y motor de voz; solo booleanos, 503 si falta el modelo).
- **Un comando:** `docker compose up -d --build` (tras `docker compose --profile setup run --rm setup`, que baja el modelo y verifica sus SHA-256) y `scripts/verify.sh` para toda la batería.

## 2. Qué se implementó

| Tarea | Componente | Dónde está |
|---|---|---|
| Seguridad | token administrativo, cabeceras con CSP, límite de tasa, producción, `/api/health/ready` | `backend/app/security.py`, `main.py`, `api/*` |
| 6.1 Contenedores | `Dockerfile` multi-etapa (Node → PWA; Python 3.11 + uv + eSpeak-NG + ffmpeg; usuario no root; healthcheck), `.dockerignore` | `Dockerfile`, `.dockerignore` |
| 6.2 Servidor | Compose (solo Caddy publica puertos, volúmenes con nombre, servicio `setup`) y Caddyfile (HTTPS automático, compresión solo de texto, audio con `Range` e inmutable, HSTS) | `docker-compose.yml`, `Caddyfile`, `.env.production.example` |
| 6.3 Banco de pruebas final | **Pendiente** (no hay servidor) | — |
| 6.4 Reproducibilidad | SHA-256 de los pesos (`models.lock.json`, `scripts/verify_models.py`, verificados por `init.sh`), `db-backup`, `scripts/backup.sh`, `scripts/verify.sh` | `scripts/`, `models.lock.json` |
| 6.5 Documentación | despliegue, arquitectura con latencias medidas (generada), README con el mapa de las Fases 1 a 6, `LICENSES.md` corregido, limitaciones 59–69 | `docs/deployment.md`, `docs/architecture.md`, `README.md` |
| 5.7 Kit de escucha | construir (MMS y eSpeak, mismo volumen, clave aparte, repetidos), hoja HTML sin conexión, puntuar (acierto y CER por palabra, MOS, bootstrap por oyente, alfa de Krippendorff, fiabilidad, por variante) y simulador | `eval/listening/inteligibilidad_mos/` |
| Consolidación | `eval/fase6/run.py` → `fase_6.json` (con el estado exacto de Docker) | `eval/fase6/` |

## 3. Resultados

### Pruebas y calidad (`scripts/verify.sh`, exit 0)

| Comprobación | Resultado |
|---|---|
| `ruff check` y `ruff format --check` | **0 errores** |
| `uv run pytest` | **314 pasaron de 316**, 2 omitidas, 0 fallos (una sin eSpeak por diseño; la otra, `caddy validate`, porque no hay binario de Caddy) |
| · seguridad | 55 de 55 |
| · despliegue (artefactos, `docker compose config` real, la app con el *layout* de la imagen) | 31 de 32 (la omitida es `caddy validate`) |
| · kit de escucha | 22 de 22 |
| · documentación | 15 de 15 |
| `npm test` (vitest) | **65 de 65** |
| `npm run typecheck` / `npm run build` | **0 errores** |
| `npm run e2e` (Chromium real) | **27 de 27** (6 nuevas de CSP; las 21 previas pasan con los endpoints protegidos) |

### Seguridad

- Cada endpoint administrativo da 403 sin token, con uno incorrecto, con uno corto o de ejemplo, y con el correcto deja de darlo. Se clasifican **por comportamiento** recorriendo el esquema OpenAPI: una prueba falla si aparece una escritura pública que no esté en la lista consciente de las 4 que usa la PWA.
- **CSP verificada en Chromium real:** cero violaciones en C1 a C4 (con avatar WebGL), lista, ajustes, Service Worker y el recorrido completo del experimento. La prueba descubrió que `connect-src` debía admitir `blob:` (three.js lee las texturas del avatar así); se corrigió y quedó documentado.
- **Hallazgo en Windows:** `_PwaFiles` no aplicaba la cabecera inmutable de `assets/` porque Starlette entrega la ruta con `\`; lo destapó la prueba que arranca la app con el *layout* de la imagen. En Linux (Docker) funcionaba; ya es portable.

### Contenedores y despliegue

| Comprobación | Estado |
|---|---|
| Estructura de `Dockerfile`, `docker-compose.yml`, `Caddyfile`, `.dockerignore` y `.env` | **Validada por pruebas** (versiones fijadas, usuario no root, healthcheck, solo Caddy publica puertos, audio sin compresión, todo lo que se copia existe y no está excluido, secretos y modelos fuera del contexto) |
| `docker compose config` con el `.env` de producción (Docker 29.8.0, Compose v5.5.1) | **Válido**: servicios `app` y `caddy` (+ `setup` por perfil), solo Caddy publica 80 y 443, 6 volúmenes |
| La aplicación arranca con **solo lo que el `Dockerfile` copia** (sin `data/`, `docs/` ni `.env`) | **Cumple**: salud, PWA, assets inmutables, HSTS, `/docs` apagado, administrativos 403, proceso, lotes, `Range` 206, NDJSON y exportación cerrada |
| **`docker build` y `docker compose up`** | **PENDIENTE: no se construyó ni se arrancó.** El demonio de Docker no estaba activo: *«failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine … The system cannot find the file specified»*. `eval.fase6.run` lo intenta solo cuando `docker info` responde |
| `caddy validate` y HTTPS real con un dominio | **PENDIENTE** (no hay binario de Caddy ni dominio público) |

### Modelos (6.4)

Los **12 archivos** de `mms-tts-cni` y `mms-1b-all` coinciden con `models.lock.json`. Los tres archivos de pesos (`.safetensors`) coinciden además con el SHA-256 que publica Hugging Face y el commit con la revisión fijada; los JSON pequeños no tienen SHA-256 publicado y son de primer uso (limitación 66). `init.sh` ya los verifica.

### Kit de escucha (5.7)

- **Kit real construido** (`eval/listening/inteligibilidad_mos/out/`, fuera del repositorio): 24 oraciones del split **test** × MMS y eSpeak = 48 audios + 5 repetidos = **53 audios (3,6 min, 5,5 MB)**, todos con el mismo volumen (RMS 0,0800), con la clave **fuera** del zip.
- **Verificación con 30 oyentes SIMULADOS** (acierto verdadero 0,85 y 0,55; MOS 3,6 y 2,2): el kit recupera el acierto de MMS **0,838** [0,813; 0,861] y el de eSpeak **0,527** [0,494; 0,561] (ambos IC contienen la verdad), el MOS **3,47** y **2,16** (a menos de 0,2) y la diferencia de acierto 0,271 a 0,351 (verdadera: 0,30). El alfa de Krippendorff ordinal del MOS es 0,386. La implementación del alfa reproduce los valores publicados por Krippendorff (2011): 0,743, 0,815 y 0,849.
- **No es una medición.** La inteligibilidad y el MOS reales, por variante, requieren a un hablante (limitación 69).

### Regresión

| Qué | Resultado |
|---|---|
| Criterios automáticos de la Fase 5 tras proteger los endpoints | **Iguales**: 13 cumplidos, 0 en fallo (cobertura 0,945–0,955; N mínimo 64) |
| Carga inicial de la PWA con seguridad y el flujo del experimento | **0,024 MB** gzip (< 3 MB) |

## 4. Cómo se usa

Comandos en Git Bash dentro de `Proyecto/noticias-ashaninka`.

```bash
# Servidor (Docker): ver docs/deployment.md
cp .env.production.example .env        # completar NA_DOMAIN y NA_ADMIN_TOKEN
docker compose --profile setup run --rm setup && docker compose up -d --build
scripts/backup.sh                      # copia consistente de la base de datos

# Verificación completa en un comando
scripts/verify.sh [--sin-e2e]          # lint, pytest, vitest, tipos, build, E2E y eval/results/fase_6.json

# Pruebas de escucha (con un hablante)
uv run python -m eval.listening.inteligibilidad_mos.build
uv run python -m eval.listening.inteligibilidad_mos.score respuestas_*.csv

uv run python scripts/verify_models.py           # SHA-256 de los modelos
uv run python -m eval.fase6.architecture         # regenera docs/architecture.md desde los JSON
curl -H "x-admin-token: $NA_ADMIN_TOKEN" https://su-dominio/api/events/summary
```

## 5. Criterios de cierre

| Criterio | Estado |
|---|---|
| Endpoints administrativos cerrados por defecto y protegidos con token | **Cumple** |
| Cabeceras, CSP (sin violaciones en Chromium real) y límite de tasa | **Cumple** |
| `Dockerfile` multi-etapa con eSpeak-NG y ffmpeg; Compose y Caddy | **Cumple como artefactos validados** (estructura, `compose config`, app con el *layout* de la imagen) |
| **La imagen se construye y arranca** (`docker build`, `docker compose up`) | **PENDIENTE**: demonio de Docker apagado |
| HTTPS automático real con un dominio (`caddy validate`) | **PENDIENTE** |
| Hashes de los modelos verificados | **Cumple** (12 de 12) |
| Kit de escucha listo y probado | **Cumple** (kit real construido; verificado con oyentes simulados) |
| Documentación de despliegue, arquitectura con latencias medidas y README de las Fases 1 a 6 | **Cumple** (generada y comprobada contra el código y las mediciones) |
| Verificación en un comando | **Cumple** (`scripts/verify.sh`, exit 0) |
| 6.3 Banco de pruebas repetido en el servidor | **PENDIENTE** (no hay servidor) |
| 6.4 Una persona ajena reproduce el sistema solo con el README | **PENDIENTE** (requiere a la persona) |
| 5.7 Sesiones de escucha con hablantes | **PENDIENTE** |

## 6. Pendientes que se arrastran

| Pendiente | Impacto | Acción |
|---|---|---|
| **`docker build` / `up` reales y HTTPS con dominio** | Los archivos de despliegue no se han ejecutado nunca | Encender Docker Desktop y ejecutar la sección 2 de `docs/deployment.md`; `uv run python -m eval.fase6.run` lo registra |
| **Banco de pruebas en el servidor (6.3)** | No hay comparación local frente a servidor | Repetir las Fases 2 a 4 con `BASE` apuntando al servidor |
| **README probado por una persona ajena (6.4)** | Criterio de cierre del plan sin cumplir | Pedir a una persona revisora que lo siga |
| **Escucha con hablantes (5.7)** | No hay inteligibilidad ni MOS reales | Aplicar el kit a ≥ 3 personas por variante |
| Consentimiento del comité, ítems de comprensión, noticias revisadas (P4), piloto con personas | El experimento real no puede arrancar | Heredados de la Fase 5 |
| Interfaz en asháninka, Android físico, VRM final | Heredados de la Fase 4 | Hablante, dispositivo, pista de VRoid |
| P1, P2a–P2d, P5, Praat | Heredados de las Fases 1 a 3 | Lingüista, hablantes, compañera |

Las limitaciones completas están en `docs/limitations.md` (puntos 59 a 69, nuevos en esta fase).
