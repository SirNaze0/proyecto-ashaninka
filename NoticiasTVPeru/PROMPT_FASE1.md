# PROMPT: Fase 1. Backend: lector del feed y ciclo de ingesta

> Copia todo lo que está debajo de la línea en una sesión de Claude Code abierta en
> `C:\Users\Marco\Downloads\proyecto-ashaninka\proyecto-ashaninka`.
> Antes, lee `NoticiasTVPeru/PLAN_TVPERU.md`, `CLAUDE.md`.

---

# ROL

Actúa como ingeniero backend senior (FastAPI, SQLModel y pytest). Vas a crear el paquete `backend/app/feed/`, que descarga el RSS de TV Perú, lo traduce con BiTAM, lo procesa, lo sintetiza y lo publica. También vas a crear un planificador de fondo y la API `/api/feed/*`.

# CONTEXTO

- Feed: `https://www.tvperu.gob.pe/rss.xml`.
  - RSS 2.0 con 15 items.
  - `description` en HTML con el cuerpo completo.
  - El XML empieza con un salto de línea.
  - `robots.txt` pide `Crawl-delay: 10`.
- Funciones que se reutilizan:
  - `translation.traducir_noticia` y `get_translator` (`translation/service.py:111`);
  - `services.import_payloads` (`:38`) y `process_news` (`:194`);
  - `batch.service.run_batch` (`:333`);
  - `pipeline/segment.py::Segmenter`.
- `init_db` usa `create_all`: las tablas nuevas se crean solas, sin migración.
- `test_docs_fase6.py` llama a TODAS las rutas sin token.
- `test_deploy_artifacts.py` exige documentar cada `NA_*` en `.env.example`.
- Patrón de servidor HTTP falso: `tests/unit/test_translation_client.py:23-70`.

# TAREAS

1. `feed/tvperu.py`: `descargar_rss`, `parsear_rss` y `recortar` (≤ 12 oraciones y ≤ 2.500 caracteres). Solo biblioteca estándar.
2. `feed/models.py`: `FeedItem` (guid único) y `FeedConfig` (una sola fila).
3. `feed/servicio.py::ejecutar_ciclo`, con candado.
   - Traductor caído → la noticia queda `pendiente`.
   - 3 errores → `descartada`.
4. `feed/planificador.py`: hilo daemon en el `lifespan`. Solo arranca con `NA_FEED_ENABLED=true`.
5. `api/feed.py`: `GET /status`, `PUT /config` y `POST /run` (202, 409 o 503). CLI `app.cli feed run|status`.
6. Catálogo: `orden=recientes`, `fuente_url` y `traduccion_automatica`.
7. Variables `NA_FEED_*` en los tres `.env*.example`.

# PRUEBAS OBLIGATORIAS (criterio de cierre)

| # | Prueba | Resultado esperado |
|---|---|---|
| 1 | `test_feed_tvperu.py`: parseo de un RSS de muestra, fechas, categoría y recorte | Verde |
| 2 | `test_feed_servicio.py`: ciclo con feed falso, `FakeTranslator` y TTS `fake` | Publica 3, con procedencia automática no revisada y `apta_experimento=False`; un segundo ciclo no duplica | Verde |
| 3 | Traductor caído → todo `pendiente`; candado → 409; configuración no válida → 422; feed apagado → 503 | Verde |
| 4 | `uv run ruff check …` y `uv run pytest` | Verde (salvo el fallo previo del VRM) |
| 5 | Ciclo real contra TV Perú con el traductor `fake` (`app.cli feed run`) | Publica noticias; copiar la salida al resumen |

# RESTRICCIONES

- Nunca se inventa texto en asháninka: el texto `cni` sale de BiTAM (o del motor `fake` en las pruebas).
- Las noticias quedan como `traduccion_automatica` y `revisado_por_hablante=False`.
- Sin dependencias nuevas; los middlewares ASGI puros no se tocan.
- Comentarios, documentos y commits en español.

# AL TERMINAR

Escribe `NoticiasTVPeru/RESUMEN_FASE1.md` con:

1. Qué se hizo.
2. Los archivos.
3. La salida real de las pruebas.
4. Desviaciones y pendientes.

Después marca la fase como **Culminada** en `PLAN_TVPERU.md` y haz un commit en español.
