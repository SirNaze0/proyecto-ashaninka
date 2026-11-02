# Resumen de la Fase 2: backend (cliente, mayúsculas y endpoint)

> **Estado:** culminada el 2026-11-02 · **Rama:** `mejora` (sin commit todavía)
> **Prompt:** `PROMPT_FASE2.md` · **Siguiente:** `PROMPT_FASE3.md` (Redacción en la PWA)

## 1. Qué se hizo

- **Nuevo módulo `backend/app/translation/`:**
  - `client.py`:
    - `HttpTranslator` llama al servicio BiTAM de la Fase 1 con `urllib`, de la stdlib, así que el
      backend no gana dependencias. Trocea en lotes de 64 y aplica un timeout.
    - Errores tipados: `TraductorNoDisponible` cuando no está configurado o no conecta o no
      responde; `TraductorError` cuando responde con error, con JSON inválido o con un número de
      traducciones distinto.
    - `FakeTranslator` para pruebas: **no produce asháninka**, solo marca el texto con `[fake-bitam]`.
    - `get_translator()` elige el motor según `NA_TRANSLATOR_ENGINE`.
  - `service.py`:
    - `dividir()` reutiliza el `Segmenter` del pipeline, que ya trae abreviaturas castellanas (Dra., Sr., EE.UU.…).
    - Límites: título de 300 caracteres, cuerpo de 8.000, 80 oraciones y 1.000 caracteres por
      oración. Se validan **antes** de llamar al modelo.
    - `restaurar_mayusculas()` es **determinista**. Copia de la oración fuente la forma de los
      nombres propios y las siglas: `satipo` → `Satipo`, `peru` → `Perú`, `onu` → `ONU`. Además pone
      mayúscula inicial. No inventa formas.
    - `traducir_noticia()` hace **una sola llamada por lotes** con el título y todas las oraciones.
      Devuelve un borrador con los párrafos, los pares `es` / `cni_modelo` (crudo) / `cni`
      (restaurado), una procedencia `traduccion_automatica` con `revisado_por_hablante=false` y avisos.
- **`POST /api/news/translate`** en `backend/app/api/news.py`:
  - Hereda `require_admin` del router: sin token responde 403.
  - **No escribe en la base de datos.**
  - Respuestas: 422 por límites, 503 si el traductor no está disponible y 502 si el traductor responde con error.
  - El docstring del módulo documenta la excepción consciente: el administrador recibe los pares castellano/asháninka que él mismo envió.
- **Esquemas** `TranslateIn`, `TranslateOut` y `OracionTraducidaOut` en `schemas.py`, con `extra="forbid"`.
- **Configuración:** `NA_TRANSLATOR_ENGINE` (`http`), `NA_TRANSLATOR_URL` (vacío = desactivado) y
  `NA_TRANSLATOR_TIMEOUT` (120). Están documentadas en `.env.example` y `.env.production.example`.
- **`docs/deployment.md`** documenta la ruta administrativa nueva, como exige la regla de la Fase 6.
- **Nuevo marcador `traductor`** de pytest, para la prueba contra el servicio real. Si el servicio no está, la prueba se salta.

## 2. Archivos

| Archivo | Tipo |
|---|---|
| `backend/app/translation/__init__.py`, `client.py`, `service.py` | nuevo |
| `backend/app/api/news.py` | modificado: endpoint `translate_news` |
| `backend/app/schemas.py` | modificado: esquemas de traducción |
| `backend/app/config.py` | modificado: `translator_engine/url/timeout` |
| `.env.example`, `.env.production.example` | modificado: sección del traductor |
| `docs/deployment.md` | modificado: fila `POST /api/news/translate` |
| `pyproject.toml` | modificado: marcador `traductor` |
| `backend/tests/unit/test_translation_service.py` | nuevo: mayúsculas (8 casos + 1), segmentación, borrador, avisos y límites |
| `backend/tests/unit/test_translation_client.py` | nuevo: servidor HTTP falso (éxito y lotes de 64, 500, JSON inválido, recuento distinto, timeout, conexión rechazada) y configuración |
| `backend/tests/integration/test_translate_api.py` | nuevo: 403, 200 sin escritura, publicación con el flujo normal, 422, 503 y la prueba `traductor` |
| `backend/tests/integration/test_security_api.py` | modificado: la ruta entra en la lista `ADMINISTRATIVOS` |

## 3. Pruebas obligatorias (salida real)

| # | Prueba | Resultado | Estado |
|---|---|---|---|
| 1 | `test_translation_service.py` | Verde (incluido en la fila 9) | ✅ |
| 2 | `test_translation_client.py` (servidor falso: éxito, 500, timeout, conexión rechazada) | Verde | ✅ |
| 3 | `/api/news/translate` sin token | `403` (también con token incorrecto) | ✅ |
| 4 | Con token y `fake` | `200`, `traduccion_automatica`, `revisado_por_hablante=false` y **0 filas `News`** | ✅ |
| 5 | Sin URL / servicio caído | `503` (el mensaje nombra `NA_TRANSLATOR_URL`) | ✅ |
| 6 | 8.001 caracteres (y otros 6 casos inválidos) | `422` | ✅ |
| 7 | `test_docs_fase6.py` + `test_security.py` + `test_deploy_artifacts.py` + `test_security_api.py` | `99 passed, 2 skipped`, 1 fallo **anterior y ajeno** (ver §5) | ✅* |
| 8 | `ruff check backend eval scripts` · `ruff format --check backend eval scripts` | `All checks passed!` · `156 files already formatted` | ✅ |
| 9 | `pytest -m smoke` · `pytest -m "not traductor"` | `119 passed, 2 skipped` · `346 passed, 12 skipped`. En ambos, el único fallo es el anterior de §5 | ✅* |
| 10 | Prueba manual: servicio BiTAM (fp16) + backend + `curl` | `403` sin token. `200` en **16,8 s** con token (ver §4) | ✅ |
| extra | `NA_TRANSLATOR_URL=http://127.0.0.1:8100 pytest -m traductor` (servicio real) | `1 passed` | ✅ |

\* Hay un fallo que no se debe a esta fase: `test_dockerignore_deja_pasar_lo_que_el_runtime_necesita…`.
Exige que exista `frontend/public/models/presentadora_provisional.vrm`, pero ese archivo está en
`.gitignore` (`frontend/.gitignore: public/models/*.vrm`) y **no existe en este checkout**. Fallaría
igual sin estos cambios. Se arregla copiando el VRM de la presentadora a esa ruta.

## 4. Respuesta real de la prueba manual (punto 10)

Entrada (castellano, escrita para la prueba):

> **Lluvias afectan a comunidades de Satipo**
> Las lluvias de esta semana hicieron crecer el río Ene. Varias familias de Puerto Ocopa dejaron sus casas.
>
> La Municipalidad de Satipo envió alimentos y agua. Los niños no fueron a la escuela el lunes.

Salida: `HTTP 200` en 16,8 s, con `"segundos": 16.782` dentro del modelo, y
`procedencia.version = bitam_v5_seed13_20261018T230715Z_es2cni`.

| Párrafo | Castellano | `cni_modelo` (BiTAM, crudo) | `cni` (mayúsculas restauradas) |
|---|---|---|---|
| título | Lluvias afectan a comunidades de Satipo | ompoña ompoña oshiyakantari anampiki satipo | Ompoña ompoña oshiyakantari anampiki **Satipo** |
| 0 | Las lluvias de esta semana hicieron crecer el río Ene. | inkani osarentsi osarentsi oshokakeri eni. | Inkani osarentsi osarentsi oshokakeri eni. |
| 0 | Varias familias de Puerto Ocopa dejaron sus casas. | kantashiyetachari ashaninkapaye portoki okopaji meka ibankokipe | Kantashiyetachari ashaninkapaye portoki okopaji meka ibankokipe |
| 1 | La Municipalidad de Satipo envió alimentos y agua. | pishiyakantero shiyakantsipe sanipaye pishiyakantakotero pankirentsipe aisati nija | Pishiyakantero … aisati nija |
| 1 | Los niños no fueron a la escuela el lunes. | meka jananekipe te ijatakeji obametantatsiri ishaninkape | Meka jananekipe te ijatakeji obametantatsiri ishaninkape |

Lo que muestra este ejemplo (no es una evaluación de calidad, que no corresponde a esta tesis):

- La restauración funciona cuando BiTAM **copia** el nombre (`satipo` → `Satipo`).
- **No puede** restaurar los nombres que BiTAM **adapta** a la morfología asháninka: «Puerto Ocopa»
  → `portoki okopaji`, «Ene» → `eni`. Es lo esperado: la regla solo copia formas idénticas y no inventa.
- En el párrafo 1, el modelo no reprodujo «Satipo». Por eso el borrador **siempre** pasa por la
  revisión del administrador y, para el experimento, por la de un hablante.
- La salida a veces no lleva el punto final. Se publica tal cual.
- **Latencia:** 16,8 s para 5 oraciones, más que los 16,1 s para 20 de la Fase 1, porque la suite
  completa de pytest corría en paralelo y ocupaba la CPU. La medición oficial se repite en la Fase 4 sin carga.

## 5. Desviaciones respecto al plan

1. **Código 502** cuando el servicio responde con error (el plan solo hablaba de 503). Así se distingue «no está» (503) de «falló» (502).
2. **Entorno del backend:** este checkout no lo tenía instalado. Se ejecutaron `uv sync` y
   `uv sync --group eval` (pillow y pandas, necesarios para cargar todas las pruebas). `uv.lock` **no cambió**.
3. **Prueba de conexión rechazada:** en Windows el sistema reintenta el SYN y el cliente agota el
   tiempo en lugar de recibir un rechazo. Se acepta cualquiera de los dos mensajes, porque ambos son `TraductorNoDisponible` → 503.
4. Se añadió la ruta a `ADMINISTRATIVOS` de `test_security_api.py`, además de la clasificación automática de `test_docs_fase6.py`.

## 6. Pendientes para las fases siguientes

- **Fase 3:**
  - la PWA llama a `POST /api/news/translate` con `x-admin-token` y muestra `oraciones` para revisar;
  - usa `paragraphs` y `procedencia` para rellenar el borrador;
  - trata los errores 503, 502, 422 y 403.
- **Fase 4:**
  - medir cuántos nombres propios se recuperan antes y después de la restauración, y cuántos se pierden por adaptación morfológica;
  - repetir la latencia sin carga concurrente.
- Copiar `presentadora_provisional.vrm` a `frontend/public/models/` antes de `scripts/verify.sh`.
