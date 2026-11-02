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

Todos los comandos se ejecutan desde `noticias-ashaninka/`.

### 1. Instalación (una vez)

```bash
./init.sh --with-tts                 # dependencias, base de datos y voz MMS (o ./init.sh si ya estaba)
(cd frontend && npm ci && npm run build)
(cd traductor && uv sync)            # entorno propio de BiTAM (torch 2.6 cu124; necesita GPU)
cp .env.local.example .env           # trae NA_TRANSLATOR_URL=http://127.0.0.1:8100 y NA_FEED_ENABLED=true
```

Los pesos de BiTAM van **fuera del repositorio** (`bitam_modelos_entrega/` junto a la carpeta del proyecto, o
la ruta que indique `BITAM_MODELS_DIR`).

### 2. Arranque

```bash
(cd traductor && ./run.sh 8100 auto)        # primero el traductor (Windows: .\run.ps1); espere unos 30 s
uv run uvicorn app.main:app                 # después el backend con la PWA: http://127.0.0.1:8000
```

### 3. Uso

- Abra **Noticias** (`#/noticias`). Arriba está la barra **«Noticias de TV Perú»**:
  - **Actualizar cada:** apagado, 15 min, 30 min, 1 h, 3 h o 6 h. Se guarda en el servidor.
  - **Refrescar ahora:** lanza un ciclo en ese momento. La barra muestra «Actualizando…» y, al terminar, el
    tablón se recarga solo.
  - **Estado:** última actualización, cuántas se publicaron, cuántas quedan en cola y la próxima ejecución, o el
    motivo del fallo (p. ej. «traductor no disponible»).
- Las noticias de TV Perú aparecen primero, con las etiquetas **«Traducción automática sin revisar»** y
  **«Fuente: TV Perú»**. Al abrirlas se ve un aviso con el enlace **«Ver la noticia original en TV Perú»**.
- Desde la terminal: `uv run python -m app.cli feed run`, que ejecuta un ciclo y espera a que termine, y
  `uv run python -m app.cli feed status`. Las noticias por ciclo se cambian con:

```bash
curl -X PUT http://127.0.0.1:8000/api/feed/config -H "Content-Type: application/json" -d '{"max_por_ciclo":1}'
```

### 4. Configuración (`.env`)

| Variable | Defecto | Para qué |
|---|---|---|
| `NA_FEED_ENABLED` | `false` (`true` en `.env.local.example`) | Activa el planificador y «Refrescar ahora» |
| `NA_FEED_URL` | `https://www.tvperu.gob.pe/rss.xml` | Fuente |
| `NA_FEED_USER_AGENT` | vacío (UA propio) | Por si la fuente rechaza el UA por defecto |
| `NA_FEED_TIMEOUT` | `30` | Espera de la descarga del RSS (s) |
| `NA_FEED_INTERVALO_MIN` | `0` | Intervalo inicial |
| `NA_FEED_TRANSLATOR_TIMEOUT` | `900` | Espera del traductor dentro del ciclo (s) |
| `NA_FEED_TRANSLATOR_LOTE` | `4` | Textos por petición a BiTAM en el ciclo (0 = noticia entera) |
| `NA_TRANSLATOR_URL` | vacío | **Imprescindible**: sin BiTAM, las noticias quedan en cola |

## Pruebas

```bash
uv run pytest backend/tests/unit/test_feed_tvperu.py backend/tests/integration/test_feed_servicio.py
(cd frontend && npx vitest run tests/feed.test.ts && npx playwright test e2e/tvperu.spec.ts)
scripts/verify.sh                       # toda la batería (ver «Fallo conocido»)
```

Las pruebas **nunca contactan a TV Perú**: usan un RSS ficticio con la misma estructura
(`backend/tests/fixtures/tvperu_rss_muestra.xml`) servido en local, el traductor `fake` y la voz `fake`. Las
E2E simulan `/api/feed/*` con `page.route`. Resultados de la verificación final: `RESUMEN_FASE4.md`.

**Fallo conocido, previo y ajeno a esta función:** `test_dockerignore_…` exige
`frontend/public/models/presentadora_provisional.vrm`, que no está en git. Si copia el VRM provisional a esa
ruta, la prueba pasa.

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
