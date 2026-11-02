# Resumen de la Fase 1: backend (lector del feed y ciclo de ingesta)

**Estado: Culminada (2026-11-02).**

## 1. Qué se hizo

- **Lector del RSS** (`backend/app/feed/tvperu.py`, solo biblioteca estándar):
  - `descargar_rss` (`urllib`, UA propio, ≤ 5 MB) con errores tipados `FuenteNoDisponible` y `FuenteError`.
  - `parsear_rss` (`xml.etree`, con `lstrip()` porque el XML real empieza con un salto de línea).
  - `parrafos_del_html` (`html.parser`): toma los `<p>` que no están dentro de `blockquote`, `aside`,
    `script`, `iframe` o `figure`, quita los «[Lee también: …]» y los párrafos vacíos, y corta en «TAMBIÉN TE
    PUEDE INTERESAR».
  - `recortar` (≤ 12 oraciones, ≤ 2.500 caracteres, nunca parte una oración; usa el mismo `Segmenter`
    que la traducción).
- **Tablas nuevas** en `backend/app/db/models.py`: `FeedItem` (`guid` único, texto en castellano ya recortado,
  `publicado_en`, `estado`, `intentos`, `news_id`) y `FeedConfig` (una fila: `intervalo_min`, `max_por_ciclo`,
  última ejecución y último resultado). Las crea `init_db`; no hace falta migración.
- **Ciclo** (`backend/app/feed/servicio.py::ejecutar_ciclo`), con un candado para que no corran dos a la vez:
  1. descarga el feed y registra los `guid` nuevos;
  2. toma las 3 noticias pendientes más recientes;
  3. las traduce con BiTAM, las importa con procedencia `traduccion_automatica` **no revisada**, las
     procesa y sintetiza el audio.
  - Si el traductor no está disponible, las noticias siguen `pendiente` y no se publica nada en castellano.
  - Si falla la traducción o el pipeline, la noticia pasa a `error`; al tercer intento, a `descartada`.
  - Si la noticia solo tiene vídeo, se marca `descartada` al registrarla.
- **Planificador** (`backend/app/feed/planificador.py`): un hilo daemon que se arranca en el `lifespan` (solo
  con `NA_FEED_ENABLED=true`). Revisa cada 30 s si venció el intervalo guardado en la base, así que los cambios
  hechos desde la PWA se aplican sin reiniciar.
- **API** (`backend/app/api/feed.py`):
  - `GET /api/feed/status`;
  - `PUT /api/feed/config` (intervalo de 0, 15, 30, 60, 180 o 360 min y de 1 a 5 noticias por ciclo; si no,
    422);
  - `POST /api/feed/run` (202; 409 si ya hay un ciclo en curso; 503 si la función está apagada).
- **CLI:** `uv run python -m app.cli feed run|status`.
- **Catálogo** (`backend/app/api/catalog.py`):
  - `?orden=recientes` (por fecha de publicación o de ingreso; el orden por defecto no cambia);
  - campos nuevos `traduccion_automatica`, `fuente_url` y `fuente_nombre` («TV Perú»), en la lista y en el
    detalle;
  - el castellano guardado nunca se expone.
- **Configuración:** `NA_FEED_ENABLED`, `NA_FEED_URL`, `NA_FEED_USER_AGENT`, `NA_FEED_TIMEOUT` y
  `NA_FEED_INTERVALO_MIN`, documentadas en los tres `.env*.example` (`true` solo en `.env.local.example`).
  `conftest.py` fuerza `NA_FEED_ENABLED=false` en las pruebas, para que un `.env` local nunca active peticiones
  reales.

## 2. Archivos

| Archivo | Cambio |
|---|---|
| `backend/app/feed/__init__.py`, `tvperu.py`, `servicio.py`, `planificador.py` | **Nuevos** |
| `backend/app/api/feed.py` | **Nuevo** |
| `backend/app/db/models.py` | `FeedItem` y `FeedConfig` |
| `backend/app/config.py` | Campos `feed_*` |
| `backend/app/main.py` | Router `/api/feed` y planificador en el `lifespan` |
| `backend/app/api/catalog.py` | `orden`, `traduccion_automatica`, `fuente_url` y `fuente_nombre` |
| `backend/app/cli.py` | Comando `feed` |
| `.env.example`, `.env.local.example`, `.env.production.example` | Variables `NA_FEED_*` |
| `backend/tests/conftest.py` | `NA_FEED_ENABLED=false` en `temp_db` |
| `backend/tests/fixtures/tvperu_rss_muestra.xml` | **Nuevo**: RSS **ficticio** con la estructura del real (sin contenido de TV Perú) |
| `backend/tests/unit/test_feed_tvperu.py` | **Nuevo**: 12 pruebas (smoke) |
| `backend/tests/integration/test_feed_servicio.py` | **Nuevo**: 11 pruebas |

## 3. Salida real de las pruebas

```
$ uv run pytest -q backend/tests/unit/test_feed_tvperu.py
12 passed in 3.11s
$ uv run pytest -q backend/tests/integration/test_feed_servicio.py
11 passed, 1 warning in 8.77s
$ uv run ruff check backend          All checks passed!
$ uv run pytest -q
1 failed, 360 passed, 9 skipped      (el fallo previo del VRM provisional, ajeno a esta fase)
```

Ciclo **real** contra `https://www.tvperu.gob.pe/rss.xml`, con el traductor `fake`, TTS `fake` y una base temporal:

```
$ NA_TRANSLATOR_ENGINE=fake NA_TTS_ENGINE=fake uv run python -m app.cli feed run
"nuevas": 15,
"publicadas": [ {news_id 1: "Gobierno lidera trabajo articulado …"}, {2: "Ciberataque golpea supermercados …"},
                {3: "Reniec suspende temporalmente todos sus servicios …"} ],
"errores": 0, "pendientes": 12, "motivo": null,
"audio": {"segmentos": 0, "bloqueados": 57, "errores": 0}, "duracion_s": 1.17
```

El UA propio no lo bloqueó TV Perú. Los 57 segmentos aparecen bloqueados porque el traductor `fake` devuelve
castellano en minúsculas, y la validación estricta del adaptador MMS rechaza esas letras, como debe. Con BiTAM la
salida es asháninka; eso se mide en la Fase 3.

## 4. Desviaciones y pendientes

- **Las tablas van en `db/models.py`, no en `feed/models.py`:** así `init_db` las registra siempre, aunque nadie
  haya importado el paquete `feed`.
- **«Ejecutando» no es una columna:** se calcula con el candado en memoria. Si fuera una columna y el proceso
  muriera a mitad de un ciclo, el indicador podía quedarse marcado para siempre.
- **Orden de proceso:** se eligen las 3 más recientes, pero se procesan de la más antigua a la más nueva, para que
  el `id` crezca con la fecha.
- La primera lectura registra las 15 noticias del feed. Las 12 que no entran en el primer ciclo se publican en los
  siguientes (3 por ciclo), siempre empezando por la más reciente.
- **Pendiente para la Fase 3:** un ciclo con BiTAM real. El servicio no estaba encendido; hay pesos, entorno y
  GPU.
