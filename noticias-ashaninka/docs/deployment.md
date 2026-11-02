# Despliegue y operación (Fase 6)

Guía para poner el servicio en un servidor con **un solo comando** (`docker compose up`), operarlo y
asegurarlo. Para desarrollo local sin Docker, véase el [README](../README.md).

```
 navegador ──HTTPS──► Caddy :443/:80 ──red interna──► app :8000 (FastAPI + PWA) ──► volúmenes
   (PWA, SW)         · certificado automático          · no publica puertos         na_data    SQLite (WAL)
                     · zstd/gzip solo para texto                                     na_static  audio + manifiestos
                     · Range intacto en /static/audio                                na_models  mms-tts-cni (CC-BY-NC)
                     · HSTS, límite de cuerpo                                        na_export  exportaciones y copias
```

Solo Caddy publica puertos. La aplicación **no** es alcanzable sin pasar por el proxy, que además
aporta el HTTPS que exigen la PWA y su Service Worker (limitación 44).

## 1. Requisitos

| Qué | Mínimo | Fuente |
|---|---|---|
| Servidor | **2 vCPU y 2 GB de RAM** (3 GB de límite de memoria para el contenedor), sin GPU, 20 GB de disco | `docs/sizing.md` (Fase 2): el modo por lotes sirve hasta 50 noticias por día; pico medido de RAM con un trabajador: 1 058 MB |
| Software | Docker 24 o superior con `docker compose` v2 | — |
| Red | Un dominio con registro DNS (A/AAAA) hacia el servidor y los puertos **80 y 443** abiertos | Let's Encrypt los necesita para emitir el certificado |

El **bajo demanda** (`/api/synthesize`) es solo un respaldo: con 4 u 8 clientes simultáneos no cumple
TTFA p95 < 2 s (Fase 2). El servicio principal sintetiza **por lotes** y sirve archivos estáticos.

## 2. Primer despliegue

```bash
git clone <repositorio> && cd <repositorio>/noticias-ashaninka
cp .env.production.example .env
# edite .env: NA_DOMAIN=noticias.su-dominio.org

docker compose --profile setup run --rm setup    # una vez: baja el modelo de voz y verifica sus SHA-256
docker compose up -d --build                     # construye la imagen y levanta app + Caddy
```

Comprobación:

```bash
curl -s https://su-dominio/api/health            # {"status":"ok","version":"..."}
curl -s https://su-dominio/api/health/ready      # {"status":"ok","db":true,"static":true,"tts":true}
docker compose ps                                # app: healthy
```

`/api/health/ready` responde 503 (`"tts": false`) si falta el modelo: ejecute de nuevo el paso `setup`.

**Pruebas locales con HTTPS:** `NA_DOMAIN=localhost` hace que Caddy use su propio certificado
(`https://localhost`; el navegador pedirá confiar en él). Con `NA_DOMAIN=:80` solo hay HTTP y la PWA y el
Service Worker **no funcionan**.

### Licencia del modelo de voz

`facebook/mms-tts-cni` es **CC-BY-NC 4.0 (uso no comercial)**. El servicio muestra el aviso de voz
sintética y la licencia en cada audio (ver `LICENSES.md`). No lo use en un servicio comercial.

## 3. Cargar noticias

Las noticias llegan ya traducidas con el contrato del plan (§2). Se cargan desde la **Sala de redacción**
de la PWA (abierta a todos desde QuitarAdmin) o, por lotes, con la CLI **dentro del contenedor**:

```bash
docker compose cp noticias.json app:/export/noticias.json
docker compose exec app python -m app.cli import /export        # lee los JSON de la carpeta
docker compose exec app python -m app.cli process --all          # segmentación, normalización, G2P
docker compose exec app python -m app.batch build --all          # sintetiza por lotes -> /srv/static
```

**Noticias automáticas de TV Perú** (opcional): con `NA_FEED_ENABLED=true` el servidor descarga, traduce y
publica las últimas noticias de TV Perú cada X minutos (se elige en el tablón). Necesita un servicio BiTAM
accesible en `NA_TRANSLATOR_URL`, que **no** forma parte de este `docker compose`; sin él, las noticias
quedan en cola. Ver `docs/tvperu.md` y las limitaciones 78 a 81.

Para el **experimento real** hacen falta ≥ 4 noticias con `revisado_por_hablante: true` (P4). Mientras
no las haya, el servidor se niega a iniciar sesiones (409), salvo en modo piloto (`NA_EXPERIMENT_PILOTO=true`,
que marca todo como piloto: **no usarlo con participantes reales**).

## 4. Seguridad

### Sin roles: toda la API es pública (QuitarAdmin, 2026-11)

Ya **no hay token administrativo** (`NA_ADMIN_TOKEN` y `NA_EXPORT_TOKEN` se retiraron; si un `.env`
antiguo los define, se ignoran). Las rutas que antes eran administrativas responden a cualquiera:
**cualquier visitante puede crear, editar y borrar noticias y descargar los datos del experimento.**
Fue una decisión consciente del responsable del proyecto; ver la limitación 77 de `docs/limitations.md`.

| Endpoint | Para qué |
|---|---|
| `GET /api/events/summary` | conteo de eventos del cliente |
| `/api/news` (POST, GET), `/api/news/import`, `/api/news/{id}` (GET, PUT, DELETE), `/api/news/{id}/process`, `/api/news/{id}/segments` y `/api/news/{id}/editorial-report` | gestión de noticias (Sala de redacción o CLI) |
| `GET /api/news/translate/status` | estado del traductor BiTAM para la Redacción (sondea `/salud`; nunca falla) |
| `POST /api/news/translate` | borrador en asháninka de una noticia en castellano con el traductor BiTAM (no guarda nada). Requiere el servicio aparte `traductor/` y `NA_TRANSLATOR_URL`; sin ellos responde 503. El servicio **no** forma parte de este `docker compose` (GPU y pesos no redistribuibles; ver `traductor/README.md`) |
| `GET /api/experiment/export` | exportación del experimento (ZIP) |
| `GET /api/synthesize/{id}?engine=…` con un motor distinto del configurado | benchmarks |

```bash
curl https://su-dominio/api/events/summary
```

- Lo que sigue protegiendo el servicio: cabeceras de seguridad y CSP, el límite de tasa por IP
  (`NA_RATE_LIMIT_PER_MIN`), `/docs` oculto en producción y las copias de SQLite (`scripts/backup.sh`).
- Si el servicio se expone fuera de una red de confianza, ponga una autenticación delante (por ejemplo
  `basicauth` de Caddy en `/api/news*` y `/api/experiment/export`) o restaure el rol desde el historial de git.
- La exportación **por HTTP** está abierta. En el campo también se puede usar la CLI:

```bash
docker compose exec app python -m app.cli experiment export --out /export/exp-$(date +%F)
docker compose cp app:/export/exp-$(date +%F) ./exportacion
```

La exportación contiene códigos anónimos, no datos personales (`privacy.py` lo verifica), pero **no la
suba al repositorio** (`data/export/` está en `.gitignore`).

### Lo que ya hace el servicio

- **Cabeceras** en toda respuesta: `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`,
  `Permissions-Policy` (sin cámara, micrófono ni geolocalización) y una **CSP** estricta (`default-src 'self'`,
  sin scripts externos; `connect-src` admite `blob:` porque three.js lee las texturas del avatar así).
  HSTS se envía en producción y por HTTPS. Comprobado en Chromium real: cero violaciones de CSP en C1 a C4 y
  en el flujo del experimento.
- **Límite de tasa** por IP (`NA_RATE_LIMIT_PER_MIN`, 1 200 por minuto por defecto) en las escrituras de la
  API y la síntesis; responde 429 con `Retry-After`. Varios celulares tras un mismo Wi-Fi comparten IP: no lo
  baje en el campo. La IP real sale de Caddy (`NA_TRUST_PROXY=true`, ya fijado en Compose).
- **Producción** (`NA_ENV=production`): no se publican `/docs`, `/redoc` ni `/openapi.json`.
- **Contenedores:** la aplicación corre como usuario sin privilegios, con `no-new-privileges` y sin
  capacidades (`cap_drop: ALL`); la imagen no lleva el `.env`, los datos ni los modelos.

### Lo que debe hacer quien despliega

- Cortafuegos: solo 22 (SSH), 80 y 443. Docker publica puertos por encima de `ufw`: no añada `ports:` a la app.
- Mantener `.env` fuera del repositorio (`chmod 600 .env`) y el sistema operativo actualizado.
- `GET /api/experiment/sessions/{código}` devuelve el progreso de un código de participante; los códigos son
  correlativos (`P001`…), de modo que alguien podría enumerarlos. No contiene datos personales (limitación 60).

## 5. Copias de seguridad

| Volumen | Contenido | Copia |
|---|---|---|
| `na_data` | **SQLite**: noticias, sesiones, respuestas, eventos | **Sí, obligatoria** |
| `na_export` | exportaciones y copias | Sí |
| `caddy_data` | certificados de Caddy | Recomendable (los límites de Let's Encrypt) |
| `caddy_config` | configuración que Caddy genera sola | No |
| `na_static` | audio y manifiestos | No: se regenera con `app.batch build --all` |
| `na_models` | modelo de voz | No: se vuelve a bajar y verificar con `setup` |

```bash
scripts/backup.sh [carpeta]     # copia consistente con la API de respaldo de SQLite (segura con el servidor activo)
```

Restaurar: `docker compose stop app`, copie el archivo a `/data/noticias.db` del volumen `na_data`
(`docker run --rm -v noticias-ashaninka_na_data:/data -v "$PWD":/b alpine cp /b/noticias-FECHA.db /data/noticias.db`)
y `docker compose start app`. Programe el script con `cron` (por ejemplo, cada noche) y copie el resultado
fuera del servidor.

## 6. Actualizar

```bash
git pull
docker compose up -d --build            # reconstruye solo lo que cambió; los volúmenes se conservan
docker compose --profile setup run --rm setup    # solo si cambió la revisión del modelo (models.lock.json)
```

## 7. Solución de problemas

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| `502`/`503` de Caddy | La aplicación aún carga el modelo (hasta ~90 s) o no está sana | `docker compose logs -f app`; espere a `healthy` |
| `/api/health/ready` → `"tts": false` | Falta el modelo de voz o no coincide con `models.lock.json` | `docker compose --profile setup run --rm setup` |
| Error de certificado | El dominio no apunta al servidor o 80/443 están cerrados | Revise el DNS y el cortafuegos; `docker compose logs caddy` |
| La PWA no se instala ni funciona sin conexión | Se sirve por HTTP | Use HTTPS (dominio real o `localhost`) |
| `429` | Límite de tasa de una IP compartida | Suba `NA_RATE_LIMIT_PER_MIN` |
| El audio no avanza ni reanuda | Un proxy comprime o corta `Range` | Use el `Caddyfile` del repositorio (el audio no se comprime) |
| Se lleva mucha RAM | Varios trabajadores de síntesis | `NA_TTS_WORKERS=1` en `.env` (servidor de 2 GB) |

## 8. Verificación de este documento

Qué se comprobó y qué **no** (detalle exacto y cifras en `eval/results/fase_6.json`):

- **Comprobado automáticamente:** estructura y coherencia del `Dockerfile`, `docker-compose.yml`, `Caddyfile`
  y `.dockerignore` (pruebas de `backend/tests/unit/test_deploy_artifacts.py`); `docker compose config` sobre el
  Compose real con el `.env` de producción; el arranque de la aplicación con **solo lo que el Dockerfile copia a
  la imagen** (sin `data/`, `docs/` ni `.env`); que ninguna ruta exige token (QuitarAdmin), las cabeceras y la CSP (incluida
  Chromium real); los SHA-256 de los pesos contra `models.lock.json`.
- **No comprobado en esta máquina:** `docker build`, `docker compose up` y el HTTPS real con Let's Encrypt
  (el demonio de Docker estaba apagado y no hay dominio público); `caddy validate` (no hay binario de Caddy);
  el banco de pruebas de las Fases 2 a 4 en el servidor (6.3); y que **una persona ajena** reproduzca el sistema
  solo con este texto (6.4). Al desplegar por primera vez, ejecute los comandos de la sección 2 y revise la
  sección 7: si algo falla en `docker build` o en el `Caddyfile`, es la primera prueba real de esos archivos.
