# Plan: tablón automático con noticias de TV Perú (traducidas con BiTAM)

| Fase | Estado |
|---|---|
| 1 Backend | Culminada |
| 2 PWA | Culminada |
| 3 Documentación y medición | Culminada |
| 4 Verificación y README | Culminada |

## Contexto
El tablón (`#/noticias`) solo se llena a mano, desde la Sala de redacción o la CLI. El usuario quiere que se
rellene solo con las **últimas noticias de TV Perú**: cada X tiempo, configurable desde la PWA y con un botón
«Refrescar ahora», el sistema las descarga, las traduce al asháninka con BiTAM, las sintetiza y las publica.

Decisiones del usuario (2026-11-02):
- **Publicar con aviso.** Visibles en el tablón, con voz y con la etiqueta «Traducción automática de TV Perú,
  sin revisar» más un enlace a la fuente. No entran en el experimento real, porque `apta_experimento` exige
  revisión (P4).
- **Temporizador en el servidor.** Una tarea de fondo del backend; el intervalo se guarda en la base de datos
  y se maneja desde la PWA.
- **Resumen corto, 3 por ciclo.** Título más los primeros párrafos (≤ 12 oraciones y ≤ 2.500 caracteres), y
  como máximo 3 noticias nuevas por ciclo.

Fuente, comprobada con `curl`: `https://www.tvperu.gob.pe/rss.xml`.
- RSS 2.0 con 15 `item`. Cada uno trae `title`, `link`, `pubDate`, `guid` («144385 at …»),
  `dc:creator` y una `description` en HTML con el **cuerpo completo** (2.100 a 10.500 caracteres).
- El XML empieza con un salto de línea: hay que hacer `lstrip()` antes de parsear.
- La categoría va en la URL (`/noticias/{nacionales|internacionales|politica|locales}/…`).
- `robots.txt` no prohíbe `/rss.xml` y pide `Crawl-delay: 10`. Una petición por ciclo lo cumple.
- WebFetch recibe 403 sin un User-Agent de navegador; `curl` con UA responde 200. Se enviará un UA propio
  y descriptivo, y si TV Perú lo rechazara, uno configurable.

## Organización (mismo formato que `QuitarAdmin/`)
Carpeta `NoticiasTVPeru/` en la raíz git con:
- `PLAN_TVPERU.md`;
- `PROMPT_FASE1..4.md`, con ROL, CONTEXTO, TAREAS, tabla de pruebas, RESTRICCIONES y AL TERMINAR;
- `RESUMEN_FASEN.md` al cerrar cada fase, con la salida real de las pruebas;
- `README.md` al final.

Un commit en español por fase en `mejora`.

## Fase 1. Backend: lector del feed y ciclo de ingesta
Paquete nuevo `backend/app/feed/`, solo con la biblioteca estándar; no se añaden dependencias.
- `tvperu.py`
  - `descargar_rss(url, timeout, ua)`: `urllib`, siguiendo el patrón de errores de
    `translation/client.py:58-83` (`FuenteNoDisponible` y `FuenteError`).
  - `parsear_rss(bytes) -> list[ItemFuente]`: `xml.etree`, tras `lstrip()`. Devuelve `guid`, `link`,
    `titulo`, `fecha` (de `pubDate` a `date`), `categoria` (de la URL) y `parrafos` (HTML → texto con
    `html.parser`; separa por `<p>`, descarta los párrafos vacíos y los de enlaces tipo «Lee también»).
  - `recortar(parrafos, max_oraciones=12, max_chars=2500)`: reutiliza `pipeline/segment.py::Segmenter`
    (el mismo que usa `translation/service.py`) para no partir una oración.
- `models.py`: tablas **nuevas**, que crea `init_db` porque `create_all` añade las tablas que faltan, así
  que no hace falta migración.
  - `FeedItem`: `guid` único, `url`, `titulo_es`, `fecha`, `estado` (`pendiente | publicada | error |
    descartada`), `news_id`, `error`, `intentos` y `created_at`. Deduplica por `guid`, **no** con
    `services._exists`, que compara el texto en asháninka.
  - `FeedConfig` (una sola fila): `intervalo_min` (0 = apagado), `max_por_ciclo` (3), `ultima_ejecucion`,
    `ultimo_resultado` (JSON) y `ejecutando`.
- `servicio.py::ejecutar_ciclo(settings)`, con un `threading.Lock` para que dos ciclos no se solapen:
  1. Descarga y parsea el feed, y registra como `pendiente` los `guid` nuevos.
  2. Toma hasta `max_por_ciclo` pendientes, de la más reciente a la más antigua.
  3. Para cada una llama a `traducir_noticia(titulo, "\n\n".join(recorte), get_translator())`
     (`translation/service.py:111`).
     - Si salta `TraductorNoDisponible`, deja la noticia en `pendiente` y corta el ciclo; se reintenta en el
       siguiente.
     - Si salta `TextoDemasiadoLargo` o `TraductorError`, la marca `error` y suma `intentos`; con 3
       intentos pasa a `descartada`.
  4. Construye `NewsIn`:
     - `titulo_cni = borrador.titulo_cni`;
     - `cuerpo_cni = "\n".join(borrador.paragraphs)`;
     - `titulo_es` y `cuerpo_es` se guardan, pero nunca se exponen;
     - `fecha_publicacion`;
     - `fuente_original = link`;
     - `procedencia = borrador.procedencia` (`traduccion_automatica`, `revisado_por_hablante=False`).
  5. Lo pasa por `import_payloads([...], session)` (`services.py:38`), después por `process_news`
     (`services.py:194`) con commit y, por último, por `run_batch([id])` (`batch/service.py:333`).
     Al terminar, la noticia queda `publicada` con su `news_id`.
  6. Guarda en `FeedConfig` el resumen del ciclo: nuevas, publicadas, errores, `motivo` y duración.
- `planificador.py`: un hilo daemon que se arranca en el `lifespan` de `main.py:30-39` y se detiene tras el
  `yield` mediante un `threading.Event`. Cada 30 s mira si `intervalo_min > 0` y si ya pasó el intervalo
  desde `ultima_ejecucion`; si toca, ejecuta el ciclo. Solo arranca con `NA_FEED_ENABLED=true`.
- Configuración (`config.py`, siguiendo el patrón de `:62-65` y `:93-95`), documentada en `.env.example`,
  `.env.local.example` (con `true`) y `.env.production.example`:

  | Variable | Defecto |
  |---|---|
  | `NA_FEED_ENABLED` | `false` |
  | `NA_FEED_URL` | `https://www.tvperu.gob.pe/rss.xml` |
  | `NA_FEED_USER_AGENT` | — |
  | `NA_FEED_TIMEOUT` | `30` |
  | `NA_FEED_INTERVALO_MIN` | `0`; intervalo inicial si la base no tiene ninguno |

- API `backend/app/api/feed.py`, pública porque ya no hay roles:
  - `GET /api/feed/status`: configuración, si hay un ciclo en marcha, el último resultado, la próxima
    ejecución y los pendientes y errores;
  - `PUT /api/feed/config {intervalo_min ∈ {0,15,30,60,180,360}, max_por_ciclo 1..5}`;
  - `POST /api/feed/run`: lanza el ciclo en un hilo y responde **202**. Responde 409 si ya hay uno en marcha
    y 503 si `NA_FEED_ENABLED=false`. Así `test_docs_fase6.py`, que llama a todas las rutas, no dispara
    peticiones reales a TV Perú.
- CLI: `uv run python -m app.cli feed run|status`, para ejecutarlo a mano o desde cron.
- Catálogo (`api/catalog.py:102-125`):
  - parámetro `orden=recientes` (por `fecha_publicacion` o `created_at` descendente; el orden por defecto
    no cambia);
  - `CatalogItem` añade `fuente_url` (solo cuando `fuente_original` es una URL http(s)) y
    `traduccion_automatica: bool`.
- Pruebas, con el patrón del servidor HTTP falso de `tests/unit/test_translation_client.py:23-70` y
  `FakeTranslator`:
  - el parseo de un RSS real de muestra, guardado en `backend/tests/data/tvperu_rss.xml`, sin cuerpos largos
    y con la fuente citada;
  - el recorte;
  - la deduplicación por `guid`;
  - un ciclo completo con el feed falso y `NA_TTS_ENGINE=fake`: publica 3 noticias, con procedencia
    automática y no revisada, `apta_experimento=False`, `fuente_original` igual a la URL y audio generado;
  - traductor caído → todas quedan `pendiente`;
  - candado (dos ciclos simultáneos → el segundo da 409);
  - la API de configuración (valores no válidos → 422);
  - catálogo con `orden=recientes`;
  - `test_deploy_artifacts` (las variables nuevas están en `.env.example`).

## Fase 2. PWA: controles en el tablón y aviso de la fuente
- `frontend/src/app/feed.ts`: cliente de `GET /api/feed/status`, `PUT /config` y `POST /run`, con funciones
  puras de formato (próxima ejecución, último resultado) que se puedan probar con vitest.
- `components/NewsList.tsx`:
  - pide el catálogo con `orden=recientes`, de modo que la destacada es la última noticia;
  - barra «Noticias de TV Perú» con:
    - un selector **«Actualizar cada»**: apagado, 15 min, 30 min, 1 h, 3 h o 6 h; llama a `PUT /config`;
    - un botón **«Refrescar ahora»**: `POST /run`, se desactiva mientras se ejecuta y consulta el estado
      cada 5 s;
    - el estado: «Última actualización: hace 12 min · 3 publicadas», o el motivo del fallo, p. ej.
      «traductor no disponible»;
  - vuelve a cargar el catálogo al terminar un ciclo y cada 60 s mientras la pestaña está visible.
  - Si el servidor tiene la función apagada (503), la barra lo indica y deja los controles desactivados.
- En cada tarjeta y en la vista de la noticia (`Presentation.tsx`), cuando `traduccion_automatica`, se
  muestra la etiqueta **«Traducción automática sin revisar»** y «Fuente: TV Perú» con un enlace a
  `fuente_url` (`target=_blank rel=noopener`).
- i18n: las claves nuevas van en `es.json`, y en `cni.json` con `null` (nunca se inventa texto).
- El Service Worker no cambia: `/api/catalog` ya va «red primero» (`sw.ts:53-62`) y `/api/feed/*` va
  directo a red.
- Pruebas:
  - vitest de `feed.ts`;
  - E2E con `page.route` simulando `/api/feed/*`: el selector cambia el intervalo, «Refrescar ahora» muestra
    el progreso y recarga, y la etiqueta y el enlace a la fuente se ven;
  - axe en claro y en oscuro;
  - adaptar las E2E que suponen el orden antiguo de la portada (`offline-a11y.spec.ts:26`, con la primera
    tarjeta «Guardada…»).

## Fase 3. Documentación y evaluación
- `docs/tvperu.md`: flujo, configuración, límites, fuente y atribución, y qué pasa cuando el traductor o
  TV Perú no responden.
- Actualizar `docs/pwa.md`, `docs/translation.md`, `docs/deployment.md` (el traductor no corre en Docker:
  en producción, sin `NA_TRANSLATOR_URL` los ciclos quedan en `pendiente`), `README.md`, `CHANGELOG.md` y
  `CLAUDE.md`.
- `docs/limitations.md`, nuevas **78–81**:
  - 78: se publica traducción automática sin revisar;
  - 79: dependencia del HTML y del RSS de TV Perú (si cambian el formato, el lector falla y lo registra);
  - 80: derechos del contenido (medio estatal; se atribuye y se enlaza, pero no se verificó la licencia de
    reutilización);
  - 81: solo se traduce un resumen y los nombres propios se pierden (ver 72).
- Medición real, no inventada: un ciclo con BiTAM encendido y 3 noticias. Se anotan el tiempo de traducción,
  el de síntesis y los segmentos bloqueados en `eval/results/tvperu.json`, con un script
  `eval/tvperu/run.py` definido antes en `docs/metrics.md`.

## Fase 4. Verificación integral y README
- `scripts/verify.sh` (ruff, pytest, traductor, vitest, tipos, build y E2E).
- Prueba manual con `.env.local.example`: traductor encendido, `NA_FEED_ENABLED=true` y uvicorn. En el
  tablón, «Refrescar ahora» debe dejar ver 3 noticias nuevas de TV Perú con voz, etiqueta y fuente. Después
  se pone el intervalo en 15 min y se comprueba en `GET /api/feed/status` la próxima ejecución, y que un
  segundo ciclo no duplica noticias.
- `NoticiasTVPeru/README.md`: qué hace, cómo activarlo, cómo ejecutarlo, pruebas, limitaciones y avisos
  (contenido sin revisar, atribución, uso de GPU).

## Riesgos
- **TV Perú cambia el feed o bloquea el UA:** el ciclo registra el error en el estado; el UA es configurable.
- **BiTAM ocupa la GPU unos 1–2 min por noticia:** como máximo 3 por ciclo y un ciclo a la vez.
- **Síntesis MMS en CPU:** `run_batch` corre en el hilo del ciclo y no bloquea las peticiones.
- **Nombres propios en castellano en la salida:** sin reescritura P2d, esos segmentos quedan como texto sin
  audio. Es el comportamiento que ya existe, y se mide en la Fase 3.

## Verificación
```bash
cd noticias-ashaninka
uv run ruff check backend eval scripts && uv run pytest
(cd frontend && npm test && npm run typecheck && npm run build && npm run e2e)
uv run python -m app.cli feed run      # con BiTAM encendido: 3 noticias publicadas
curl http://127.0.0.1:8000/api/feed/status
```
