# PROMPT: Fase 2 de la integración. Backend (cliente, mayúsculas y endpoint)

> Copia todo lo que está debajo de la línea en una sesión de Claude Code abierta en
> `C:\Users\Marco\Downloads\proyecto-ashaninka\proyecto-ashaninka`.
> Documentos que hay que leer antes: `MejoraEIntegracion/PLAN_INTEGRACION.md`,
> `MejoraEIntegracion/RESUMEN_FASE1.md`, `CLAUDE.md` y `PLAN_DESARROLLO.md` §2 (contrato de datos).

---

# ROL

Actúa como ingeniero backend senior (FastAPI, SQLModel y pruebas). Vas a conectar el backend del
servicio de noticias con el servicio BiTAM de la Fase 1, para que el **administrador** obtenga un
borrador en asháninka a partir de una noticia en castellano.

# CONTEXTO

- El servicio BiTAM escucha en `http://127.0.0.1:8100`: `POST /traducir {texts}` y `GET /salud`.
  Su salida va **en minúsculas** (ortografía MINEDU 2024, sin tildes y con las vocales dobles colapsadas).
- `backend/app/pipeline/normalize/classify.py:152` reconoce los nombres propios por la mayúscula, así
  que sin mayúsculas no los reconoce.
- `backend/app/api/news.py` ya define el router `/api/news` con
  `dependencies=[Depends(require_admin)]`.
- `backend/tests/unit/test_docs_fase6.py` clasifica las rutas según su comportamiento.
- Hay una prueba que exige documentar en `.env.example` toda variable `NA_*` que lea el código.
- Patrón de motor falso: `backend/app/pipeline/tts/fake.py`.

# TAREAS

1. `backend/app/translation/__init__.py`, `client.py`:
   - `Translator` (protocolo) con `translate_batch(list[str]) -> TranslationResult`; el resultado
     incluye `translations`, `modelo` y `version`.
   - `HttpTranslator`: POST con la stdlib (`urllib.request`), sin añadir dependencias, y timeout.
     Si no hay conexión lanza `TraductorNoDisponible`; si el servicio responde 4xx o 5xx lanza `TraductorError`.
   - `FakeTranslator`: es determinista, devuelve el texto en minúsculas con un prefijo marcador, y
     **nunca simula asháninka real**.
   - `get_translator()` elige el motor según `NA_TRANSLATOR_ENGINE`.
2. `backend/app/config.py`: añadir `translator_engine` (`http`), `translator_url` (vacío =
   desactivado) y `translator_timeout` (120). Documentarlos en `.env.example` y en `.env.production.example`.
3. `backend/app/translation/service.py`:
   - `dividir_parrafos(cuerpo_es)` separa por líneas en blanco.
   - `dividir_oraciones(parrafo)` reutiliza `pipeline/segment.py::Segmenter` con abreviaturas del
     castellano (Sr., Dra., etc.).
   - `restaurar_mayusculas(fuente_es, salida_cni)` es **determinista**: (a) pone mayúscula a la
     primera letra de la oración; (b) si un token de la salida coincide, sin distinguir mayúsculas ni
     tildes, con un token de la fuente que empieza en mayúscula y no está al inicio de la oración,
     copia la forma de la fuente (`texas` → `Texas`, `pichanaki` → `Pichanaki`). No inventa formas nuevas.
   - `traducir_noticia(titulo_es, cuerpo_es)` devuelve `{titulo_cni, paragraphs, oraciones:
     [{es, cni}], procedencia: {tipo: "traduccion_automatica", sistema: "BiTAM es2cni", version,
     revisado_por_hablante: false, revisor_id: null}}`.
4. `POST /api/news/translate` en `backend/app/api/news.py`:
   - Esquemas Pydantic `TranslateIn` y `TranslateOut` en `schemas.py`.
   - Límites: título de 300 caracteres como máximo, cuerpo de 8.000 caracteres y 80 oraciones. Si se pasan, responde 422.
   - Si el servicio no está configurado o no responde, 503 con un mensaje claro en español.
   - **No escribe en la base de datos.**
   - Debe declararse **antes** de `/{news_id}` para que no haya choque de rutas.
5. Marcador de pytest `traductor` en `pyproject.toml`, para las pruebas contra el servicio real
   (fuera del `smoke`).

# PRUEBAS OBLIGATORIAS (criterio de cierre)

| # | Prueba | Resultado esperado |
|---|---|---|
| 1 | `test_translation_service.py`: párrafos, oraciones con abreviaturas y mayúsculas (inicio, nombre propio, palabra que no está en la fuente sin tocar, tildes) | Verde |
| 2 | `test_translation_client.py`: `HttpTranslator` contra un servidor HTTP falso local (éxito, 500, timeout, conexión rechazada) | Errores tipados correctos |
| 3 | `test_api_translate.py` sin token | 403 |
| 4 | Ídem, con token y `NA_TRANSLATOR_ENGINE=fake` | 200, procedencia `traduccion_automatica` y `revisado_por_hablante=false`. No se crea ninguna fila `News` |
| 5 | Ídem, sin URL configurada o con el servicio caído | 503 |
| 6 | Ídem, con 8.001 caracteres | 422 |
| 7 | `uv run pytest backend/tests/unit/test_docs_fase6.py backend/tests/unit/test_security.py backend/tests/unit/test_deploy_artifacts.py` | Verde (la ruta nueva queda clasificada como protegida y `.env.example` está completo) |
| 8 | `uv run ruff check backend eval scripts` y `uv run ruff format --check backend eval scripts` | Sin errores |
| 9 | `uv run pytest -m smoke` y `uv run pytest` | Verde |
| 10 | Prueba manual con el servicio de la Fase 1 encendido: `curl -X POST http://127.0.0.1:8000/api/news/translate -H "x-admin-token: …" -H "Content-Type: application/json" -d '{"titulo_es": "…", "cuerpo_es": "…"}'` | 200 con un borrador real. Copiar la respuesta al resumen |

# RESTRICCIONES

- Los cambios de `CLAUDE.md` mandan: `require_admin`, middlewares ASGI puros y nada de texto asháninka inventado.
- No se toca el pipeline de normalización. La restauración de mayúsculas vive en `translation/`.
- Comentarios en español.

# AL TERMINAR

Escribe `MejoraEIntegracion/RESUMEN_FASE2.md` con:

1. Qué se hizo.
2. Archivos.
3. La salida real de las pruebas.
4. La respuesta de ejemplo del punto 10.
5. Desviaciones y pendientes.

Después marca la Fase 2 como **Culminada** en el `README.md` de la carpeta.
