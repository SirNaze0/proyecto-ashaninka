# NoticiasTVPeru: el tablón se llena solo con noticias de TV Perú en asháninka

Esta carpeta documenta la función que **rellena el tablón de noticias de forma automática**. Cada X minutos,
o al pulsar «Refrescar ahora», el servidor:

1. toma las últimas noticias de **TV Perú**;
2. traduce un resumen al asháninka con el traductor **BiTAM**;
3. genera la voz sintética;
4. las publica en el tablón marcadas como **«Traducción automática sin revisar»**, con un enlace a la noticia
   original.

## Estado de las fases

| Fase | Alcance | Prompt | Resumen | Estado |
|---|---|---|---|---|
| 1 | Backend: lector del RSS, ciclo de ingesta, planificador, API `/api/feed`, CLI, catálogo «recientes» | [PROMPT_FASE1](PROMPT_FASE1.md) | [RESUMEN_FASE1](RESUMEN_FASE1.md) | **Culminada** |
| 2 | PWA: barra «Noticias de TV Perú» en el tablón, etiqueta y enlace a la fuente | [PROMPT_FASE2](PROMPT_FASE2.md) | [RESUMEN_FASE2](RESUMEN_FASE2.md) | **Culminada** |
| 3 | Documentación y medición real con BiTAM | [PROMPT_FASE3](PROMPT_FASE3.md) | [RESUMEN_FASE3](RESUMEN_FASE3.md) | **Culminada** |
| 4 | Verificación integral, prueba manual y este README | [PROMPT_FASE4](PROMPT_FASE4.md) | [RESUMEN_FASE4](RESUMEN_FASE4.md) | **Culminada** |
| 5 | Traducción en trozos: el ciclo traduce en la mitad de tiempo | [PROMPT_FASE5](PROMPT_FASE5.md) | [RESUMEN_FASE5](RESUMEN_FASE5.md) | **Culminada** |

Plan completo: [PLAN_TVPERU.md](PLAN_TVPERU.md). Documentación técnica:
`noticias-ashaninka/docs/tvperu.md`.

## Qué hay en el proyecto

El proyecto es el artefacto de una tesis: un **servicio web de noticias en asháninka (`cni`)** con texto, voz
sintética y avatar (código en `noticias-ashaninka/`; mapa completo en `noticias-ashaninka/README.md`). Esta
función añade:

| Parte | Dónde |
|---|---|
| Lector del RSS de TV Perú (solo biblioteca estándar), limpieza del HTML y recorte (≤ 12 oraciones, ≤ 2.500 caracteres) | `backend/app/feed/tvperu.py` |
| Ciclo: registra las noticias nuevas (sin duplicar), traduce, procesa, sintetiza y publica | `backend/app/feed/servicio.py` |
| Planificador de fondo (solo con `NA_FEED_ENABLED=true`) | `backend/app/feed/planificador.py` |
| API `GET /api/feed/status`, `PUT /api/feed/config`, `POST /api/feed/run` | `backend/app/api/feed.py` |
| Tablas `FeedItem` (guid único) y `FeedConfig` (intervalo, noticias por ciclo, último resultado) | `backend/app/db/models.py` |
| Catálogo `?orden=recientes` con `traduccion_automatica`, `fuente_url` y `fuente_nombre` | `backend/app/api/catalog.py` |
| Barra del tablón: «Actualizar cada», «Refrescar ahora» y estado | `frontend/src/app/components/FeedBar.tsx`, `feed.ts` |
| Etiqueta en las tarjetas y aviso con enlace a la original | `NewsList.tsx`, `Presentation.tsx` |
| Medición | `eval/tvperu/run.py` → `eval/results/tvperu.json` |

## Cómo ejecutarlo

Todos los comandos se ejecutan desde `noticias-ashaninka/`. Hay dos procesos:

- el **traductor BiTAM**, en el puerto 8100;
- el **backend con la PWA**, en el puerto 8000.

El backend funciona sin el traductor, pero entonces las noticias de TV Perú se quedan en cola.

### 0. Requisitos

| Qué | Para qué |
|---|---|
| `git`, `curl` y `bash` (en Windows, Git Bash) | `init.sh` y `run.sh` |
| Node.js 20 o superior, con `npm` | Compilar la PWA |
| GPU NVIDIA con ≥ 6 GB de VRAM y CUDA 12.4 (probado en una GTX 1060) | BiTAM. También corre en CPU, pero entonces cada noticia tarda muchos minutos |
| Entrega de BiTAM (`bitam_modelos_entrega/`, 2,1 GB, CC BY-NC) | **No está en GitHub**: se pide aparte (ver abajo) |
| Modelo base `facebook/nllb-200-distilled-1.3B` (~5,5 GB) | Lo descarga BiTAM de Hugging Face la **primera vez**, así que esa vez necesita internet |
| Internet | Descargar el RSS de `https://www.tvperu.gob.pe/rss.xml` |

#### El modelo de traducción no viene con el repositorio

Al clonar desde GitHub se obtiene el **código** del servicio (`traductor/`), pero **no el modelo**. Los pesos de
BiTAM son de la tesis de un colega, tienen licencia CC BY-NC y no se pueden redistribuir. Además, ocupan más de
lo que GitHub admite sin Git LFS.

| Pieza | Dónde está | En GitHub |
|---|---|---|
| Servicio (`traductor/servidor.py`, `run.sh`, `run.ps1`) | `noticias-ashaninka/traductor/` | Sí |
| Entrega de BiTAM: adaptadores `modelos/v5_es2cni` (es→cni, 1,1 GB) y `v3_cni2es`, y el paquete `bitam` | `bitam_modelos_entrega/` | **No**: hay que pedírsela al autor de BiTAM o al dueño del proyecto |
| Modelo base NLLB-200 1.3B | Se descarga solo de Hugging Face a `~/.cache/huggingface` | No (es público) |

Para tenerlo listo:

1. Copie y descomprima `bitam_modelos_entrega/` **junto a** la carpeta del repositorio:

   ```
   proyecto-ashaninka/            <- carpeta contenedora
   ├── bitam_modelos_entrega/     <- aquí (fuera del repositorio)
   │   └── modelos/v5_es2cni/
   └── proyecto-ashaninka/        <- repositorio clonado
       └── noticias-ashaninka/traductor/
   ```

   O, si la deja en otra ruta, indíquela con `BITAM_MODELS_DIR=/ruta/a/bitam_modelos_entrega/modelos`.
2. Arranque el traductor una vez **con internet** para que baje NLLB (~5,5 GB). Después puede funcionar sin
   conexión con `HF_HUB_OFFLINE=1`.

**Sin el modelo**, el resto del proyecto funciona: el tablón, la voz, la PWA y el experimento. Pero las noticias
de TV Perú se quedan en cola y la Redacción indica «traductor no disponible». Más detalles en
`noticias-ashaninka/traductor/README.md`.

### 1. Instalación (una vez)

```bash
./init.sh --with-tts                       # uv, Python 3.11, dependencias, .env, base SQLite, voz MMS y avatar
(cd frontend && npm ci && npm run build)   # compila la PWA a frontend/dist (la sirve el backend)
(cd traductor && uv sync)                  # entorno PROPIO de BiTAM (torch 2.6 cu124); no se mezcla con el backend
cp .env.local.example .env                 # trae NA_TRANSLATOR_URL=http://127.0.0.1:8100 y NA_FEED_ENABLED=true
```

Si ya tiene un `.env`, basta con añadirle `NA_TRANSLATOR_URL=http://127.0.0.1:8100` y `NA_FEED_ENABLED=true`.
Las demás variables `NA_FEED_*` tienen valores por defecto razonables (ver el paso 5).

Para comprobar el entorno sin modificar nada: `./init.sh --check`.

### 2. Arranque (dos terminales)

**Terminal 1: el traductor.**

```bash
cd traductor && ./run.sh 8100 auto          # Git Bash / Linux
```

```powershell
cd traductor; .\run.ps1                     # PowerShell (Windows)
```

Tarda unos 20–30 s en cargar. Para comprobar que responde:

```bash
curl -s http://127.0.0.1:8100/salud         # modelo, dispositivo (cuda) y dtype (float16 en la GTX 1060)
```

**Terminal 2: el backend con la PWA.**

```bash
uv run uvicorn app.main:app                     # http://127.0.0.1:8000
curl -s http://127.0.0.1:8000/api/feed/status   # debe responder "habilitado": true
```

Después, abra **http://127.0.0.1:8000/#/noticias** en el navegador.

### 3. Uso desde el tablón

- Arriba del tablón está la barra **«Noticias de TV Perú»**:
  - **Actualizar cada:** apagado, 15 min, 30 min, 1 h, 3 h o 6 h. El intervalo se guarda en el servidor, así
    que sigue funcionando aunque cierre el navegador, mientras uvicorn esté encendido.
  - **Refrescar ahora:** lanza un ciclo en ese momento. La barra muestra «Actualizando…» y el tablón se recarga
    solo al terminar. Un ciclo de 3 noticias tarda unos 9–10 min en una GTX 1060.
  - **Estado:** cuándo fue la última actualización, cuántas noticias se publicaron, cuántas quedan en cola y
    cuándo será la próxima ejecución. Si algo falla, muestra el motivo («sin publicar: …»).
- Las noticias de TV Perú aparecen primero, con dos etiquetas: **«Traducción automática sin revisar»** y
  **«Fuente: TV Perú»**.
- Al abrir una, se ve un aviso con el enlace **«Ver la noticia original en TV Perú»** y se puede escuchar. Los
  segmentos que no tienen voz se muestran solo como texto.
- Una noticia ya publicada no se repite, porque se reconoce por el `guid` del RSS.

### 4. Uso desde la terminal o la API

```bash
uv run python -m app.cli feed run           # ejecuta un ciclo y espera a que termine (útil desde cron)
uv run python -m app.cli feed status        # configuración, cola y último resultado

curl -X POST http://127.0.0.1:8000/api/feed/run      # 202 = lanzado; 409 = ya hay uno; 503 = función apagada
curl -X PUT  http://127.0.0.1:8000/api/feed/config -H "Content-Type: application/json" \
     -d '{"intervalo_min":30,"max_por_ciclo":1}'     # intervalo ∈ {0,15,30,60,180,360}; de 1 a 5 por ciclo
```

### 5. Configuración (`.env`)

| Variable | Defecto | Para qué |
|---|---|---|
| `NA_FEED_ENABLED` | `false` (`true` en `.env.local.example`) | Activa el planificador y «Refrescar ahora» |
| `NA_FEED_URL` | `https://www.tvperu.gob.pe/rss.xml` | Fuente |
| `NA_FEED_USER_AGENT` | vacío (UA propio) | Por si la fuente rechaza el UA por defecto |
| `NA_FEED_TIMEOUT` | `30` | Espera de la descarga del RSS (s) |
| `NA_FEED_INTERVALO_MIN` | `0` | Intervalo inicial, si la base aún no tiene uno |
| `NA_FEED_TRANSLATOR_TIMEOUT` | `900` | Espera del traductor dentro del ciclo (s) |
| `NA_FEED_TRANSLATOR_LOTE` | `4` | Textos por petición a BiTAM en el ciclo (0 = la noticia entera) |
| `NA_TRANSLATOR_URL` | vacío | **Imprescindible**: sin BiTAM, las noticias se quedan en cola |

### 6. Apagar

Pulse `Ctrl+C` en cada terminal. Apague el traductor cuando no lo use, porque ocupa unos 5 GB de VRAM.

Las noticias publicadas, la cola y el intervalo quedan guardados en `data/noticias.db`. Al volver a arrancar, el
planificador sigue donde lo dejó.

### 7. Problemas frecuentes

| Síntoma | Causa y solución |
|---|---|
| La barra dice «La actualización automática está apagada en el servidor.» | `NA_FEED_ENABLED` no vale `true` en `.env`. Cámbielo y reinicie uvicorn |
| Estado «sin publicar: traductor no disponible», con noticias en cola | BiTAM está apagado o `NA_TRANSLATOR_URL` está vacío. Arranque el traductor: el siguiente ciclo las publica |
| `no se encuentra .../config.yaml` al arrancar el traductor | Los pesos no están donde se buscan. Falta la entrega de BiTAM (no viene de GitHub) o está en otra ruta: cópiela junto al repositorio o defina `BITAM_MODELS_DIR` (ver `traductor/README.md`) |
| El traductor falla al descargar de Hugging Face | La primera vez necesita internet para bajar NLLB (~5,5 GB); después puede usar `HF_HUB_OFFLINE=1` |
| El estado muestra un error de la fuente | TV Perú no responde, rechaza el UA (pruebe con `NA_FEED_USER_AGENT`) o cambió el formato del RSS (limitación 79) |
| «Ya hay una actualización en curso.» | Es el candado que impide dos ciclos a la vez: espere a que termine el que está en marcha |
| Algunos párrafos de una noticia no tienen audio | Es lo esperado: los segmentos con nombres en castellano sin reescritura (P2d) se muestran solo como texto |
| La PWA no aparece (404 o página en blanco) | Falta compilarla: `(cd frontend && npm run build)` |

## Pruebas

```bash
uv run pytest backend/tests/unit/test_feed_tvperu.py backend/tests/integration/test_feed_servicio.py
(cd frontend && npx vitest run tests/feed.test.ts && npx playwright test e2e/tvperu.spec.ts)
scripts/verify.sh                       # toda la batería
```

Las pruebas **nunca contactan a TV Perú**: usan un RSS ficticio con la misma estructura
(`backend/tests/fixtures/tvperu_rss_muestra.xml`) servido en local, el traductor `fake` y la voz `fake`. Las
E2E simulan `/api/feed/*` con `page.route`. Resultados de la verificación final: `RESUMEN_FASE4.md`.

**Avatar (resuelto el 2026-11-03):** `./init.sh` descarga y reduce el VRM provisional en `frontend/public/models/presentadora_provisional.vrm`, así que `test_dockerignore_…` ya pasa. Si clonó antes, vuelva a ejecutar `./init.sh` y recompile la PWA.

## Rendimiento medido (2026-11-02, GTX 1060 de 6 GB)

- Un ciclo de **3 noticias tardó 933 s (≈ 15,5 min)**. Casi todo el tiempo se va en la traducción en lote (de
  198 a 341 s por noticia); la voz tarda de 17 a 41 s por noticia.
- 17 de 26 segmentos con voz (65 %). El resto queda como «solo texto», sobre todo por nombres propios en castellano
  sin reescritura (P2d).
- **Fase 5 (traducción en trozos de 4):** la traducción de 3 noticias bajó de 978 s a 494 s (−49,5 %), con la
  fidelidad intacta (chrF++ 26,32 frente a 26,39 en el dev). Un ciclo de 3 noticias tarda ahora unos 9–10 min (estimado).
- **Recomendación:** intervalo de 15–30 min. El intervalo cuenta desde que termina el ciclo anterior, así que nunca
  se solapan.

## Posibles mejoras (no implementadas)

- **Recortar menos texto por noticia.** Hoy se traducen hasta 12 oraciones y 2.500 caracteres. Bajar a unas 6
  oraciones (título y entradilla) reduciría el tiempo de traducción casi a la mitad, porque el tiempo es
  proporcional a las oraciones, a cambio de que cada noticia del tablón diga menos. Es una decisión editorial,
  no técnica: el código ya lo admite cambiando `MAX_ORACIONES` y `MAX_CARACTERES` en
  `backend/app/feed/tvperu.py`. Convendría hacerlo configurable (`NA_FEED_MAX_ORACIONES`) y medirlo como se hizo
  en las Fases 3 y 5.
- **Parámetros de generación de BiTAM** (haz, longitud máxima). Acelerarían mucho más, pero cambian la calidad
  del modelo, y esa evaluación pertenece a la tesis de BiTAM, no a este sistema.

## Mejora futura propuesta: publicar el tablón en la nube (no implementada)

Hoy **todo corre en local**, por decisión del usuario. Esta es la propuesta para cuando se suba a la nube. El
visitante solo vería el tablón y cada noticia, presentada según su internet.

### 1. Tablón público de solo lectura

Desde QuitarAdmin, toda la API es pública. En la nube, cualquiera podría borrar noticias (`DELETE /api/news/{id}`),
lanzar ciclos de TV Perú o exportar los datos del experimento.

- **Propuesta:** una variable `NA_MODO_PUBLICO=true` y un middleware ASGI puro con una **lista de rutas
  permitidas**:
  - catálogo, noticia y audio;
  - `POST /api/events` (telemetría);
  - salud.
- Todo lo demás bajo `/api` respondería 404, también `/docs`.
- No es un rol ni un token: en ese despliegue las escrituras simplemente no existirían.
- Una ruta nueva quedaría cerrada por defecto.
- El planificador de TV Perú no arrancaría en la nube.

### 2. Interfaz solo para el visitante

En modo público, la PWA solo mostraría **«Noticias»** y **«Ajustes»**. Quedarían ocultos:
- la pantalla de traducción y la Redacción;
- la barra de TV Perú;
- el experimento (salvo que se habilite).

Para que no pesen en la carga del visitante, la Redacción y el traductor se cargarían bajo demanda.

### 3. Presentación según la conexión (automática, con opción de cambiarla a mano)

| Modo | Cuándo se elegiría |
|---|---|
| **C4 – Avatar** | El 3D (three.js) y el VRM bajarían en menos de ~10 s, no hay ahorro de datos, hay WebGL y ≥ 2 GB de memoria |
| **C3 – Voz y texto resaltado** | 3G, ahorro de datos o sin WebGL (el audio Opus de 24 kbps cabe) |
| **C2 – Solo voz** | Solo si el visitante lo elige |
| **C1 – Solo texto** | 2G, o sin red si la noticia no está guardada |

- **Señales:**
  - `navigator.connection` (tipo de red, velocidad y ahorro de datos; existe en Chrome y Android);
  - la velocidad medida al descargar el catálogo, como respaldo en Safari y Firefox;
  - WebGL;
  - la memoria del equipo.
- **Durante la noticia:**
  - si el avatar no carga a tiempo, bajaría a voz con un aviso;
  - si el audio se atasca, se ofrecería «Solo texto».
- **Selector:** «Modo: Automático / Avatar / Voz y texto / Solo voz / Solo texto», recordado en el navegador.
- El experimento no cambiaría: su condición la fija el cuadrado latino.
- La regla se escribiría en `docs/pwa.md` y se mediría antes de darla por buena.

### 4. Preparación del servidor

- **Avatar:**
  - el VRM no está en git ni en la imagen Docker;
  - antes de subirlo hay que **comprobar su licencia**;
  - si no se puede redistribuir, la PWA usaría siempre C3.
- **Caddy:** caché `immutable` para el audio y los assets con hash.
- **Servidor:** basta uno pequeño sin GPU, de 2 vCPU y 2 GB (`docs/deployment.md`).

### 5. ¿Dónde correría el traductor BiTAM?

| Opción | Ventajas | Desventajas |
|---|---|---|
| **A. BiTAM en el PC del dueño, que publica en la nube** (recomendada) | La más barata: el servidor no necesita GPU. Ya está probada y medida (9–10 min por ciclo). Los pesos (CC BY-NC) no salen del PC | El tablón solo se actualiza con el PC encendido. Hay que construir la sincronización PC → nube (SSH o un endpoint protegido solo para eso) |
| **B. Máquina con GPU en la nube** | Autónoma 24/7; todo en un sitio | La más cara (del orden de cientos de USD al mes si está siempre encendida); BiTAM en Docker con CUDA; hay que subir los pesos y volver a medir |
| **C. Máquina solo con CPU** | Autónoma y más barata que B | Muy lenta (sin medir; se calculan decenas de minutos por noticia); necesita unos 8 GB de RAM y compite con los visitantes |
| **D. GPU bajo demanda (serverless)** | Se paga solo por los minutos del ciclo | Arranque en frío (~1 min) en cada ciclo; ata a un proveedor; la más compleja; los pesos quedan en un tercero |

## Avisos

- ⚠️ **Contenido sin revisar.** BiTAM tiene un chrF++ de ≈ 25: es un borrador. Las noticias se publican marcadas y
  nunca son aptas para el experimento real (P4).
- ⚠️ **Derechos.** TV Perú (IRTP) es un medio estatal. Se atribuye y enlaza cada noticia y solo se traduce un
  resumen, pero **no se verificó la licencia de reutilización**: confírmela antes de un despliegue público
  (limitación 80).
- ⚠️ **GPU.** BiTAM ocupa unos 5 GB de VRAM mientras está encendido, y un ciclo la usa durante minutos.
- ⚠️ **API pública.** Desde QuitarAdmin no hay roles: cualquiera puede cambiar el intervalo o pulsar
  «Refrescar ahora». El candado evita ciclos simultáneos y el límite de tasa frena el abuso.
- **El formato del feed puede cambiar** (limitación 79). Si eso pasa, el estado del tablón muestra el error y no
  se publica nada.
- **Nunca se inventa asháninka.** Todo el texto `cni` sale de BiTAM, y la interfaz en asháninka (`cni.json`)
  sigue pendiente de un hablante.
