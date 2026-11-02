# Resumen de la Fase 3: Redacción en la PWA

> **Estado:** culminada el 2026-11-02 · **Rama:** `mejora`
> **Prompt:** `PROMPT_FASE3.md` · **Siguiente:** `PROMPT_FASE4.md` (medición, documentación y cierre)

## 1. Qué se hizo

- **Nueva tarjeta «Traducir desde castellano»**, la primera de la Sala de redacción (`components/Newsroom.tsx`):
  - Muestra el **estado real** del traductor:
    - *comprobando*;
    - *disponible*, con el modelo, el run y el dispositivo;
    - *no disponible*, con el motivo que da el servidor y un botón «Volver a comprobar».
  - Los campos `titulo_es` y `cuerpo_es` salieron del `<details>` donde estaban escondidos.
    Tienen los límites del servidor (300 y 8.000 caracteres) y un contador.
  - El botón «Traducir con BiTAM» se desactiva si el traductor no está disponible. Mientras
    traduce muestra una barra de progreso accesible y un botón «Cancelar» (`AbortController`).
  - Al terminar, rellena el borrador, que sigue editable: título, párrafos y procedencia
    `traduccion_automatica` / BiTAM es2cni / run / **no revisada**. Además muestra:
    - el aviso del servidor (borrador, revisar con un hablante);
    - una tabla plegable con los pares oración castellano/asháninka.
  - **No pisa texto en asháninka sin preguntar**: pide confirmación si el borrador ya tiene texto.
  - Si se edita el castellano después de traducir, avisa de que el borrador ya no le corresponde. No borra nada.
  - Errores con mensaje propio: 403 (token), 503 (no disponible), 422 (demasiado largo), 502 o sin conexión (falló) y cancelación.
- **`newsroom.ts`**:
  - `traducir()` y `estadoTraductor()` (esta nunca lanza error).
  - `aplicarTraduccion()`, función pura que conserva el castellano y los metadatos, y **nunca** deja la traducción marcada como revisada.
  - `validarCastellano()`, `tieneTextoCni()` y `TranslateError` (estado y cancelación).
- **Backend:** nuevo `GET /api/news/translate/status`.
  - Es administrativo, solo lee y nunca falla.
  - Sondea `/salud` del servicio con una espera de 5 s.
  - Implementación: `estado_traductor()` en `translation/client.py`, más `HttpTranslator.salud()` y `FakeTranslator.salud()`.
  - Está documentado en `docs/deployment.md` e incluido en `ADMINISTRATIVOS` de `test_security_api.py`.
- **i18n:** 20 claves `newsroom.translate.*` nuevas en `es.json`. Los pasos y las etiquetas
  del castellano están actualizados. **`cni.json` recibe las mismas claves con `null`**: es la
  convención del archivo, que espera la traducción de un hablante, y no se inventa texto. La
  clave obsoleta `newsroom.translatorPending` se eliminó de los dos archivos.
- **Estilos** en `noticiero.css`: `.room-tr-down`, `.room-tr-actions` y la tabla `.tr-pairs` con
  cabecera fija. Usan los tokens existentes (`--surface`, `--border`, `--muted`), así que se ven
  bien en tema claro y oscuro (axe en los dos).
- La pantalla pública `TranslatePanel` **no se tocó**. Sigue sin traducción en vivo, porque el ciudadano solo consume noticias ya traducidas.

## 2. Archivos

| Archivo | Tipo |
|---|---|
| `frontend/src/app/components/Newsroom.tsx` | modificado: tarjeta de traducción, estado, cancelación y confirmación |
| `frontend/src/app/newsroom.ts` | modificado: cliente del traductor y volcado al borrador |
| `frontend/src/app/i18n/es.json`, `cni.json` | modificado: claves `newsroom.translate.*` (`null` en cni) |
| `frontend/src/app/noticiero.css` | modificado: estilos de la tarjeta y la tabla |
| `frontend/tests/newsroom-translate.test.ts` | nuevo: 15 pruebas de Vitest |
| `frontend/e2e/newsroom-translate.spec.ts` | nuevo: 9 E2E con `page.route` |
| `backend/app/translation/client.py`, `__init__.py` | modificado: `salud()` y `estado_traductor()` |
| `backend/app/api/news.py` | modificado: `GET /api/news/translate/status` |
| `backend/tests/integration/test_translate_api.py`, `test_security_api.py` | modificado: 4 pruebas de estado y lista de rutas administrativas |
| `docs/deployment.md` | modificado: fila de la ruta de estado |

## 3. Pruebas obligatorias (salida real)

| # | Prueba | Resultado | Estado |
|---|---|---|---|
| 1 | Vitest `tests/newsroom-translate.test.ts`: `aplicarTraduccion` (campos, procedencia, castellano conservado, pureza, recorte), `traducir` (éxito, 403, 422, 502, 503, sin red, abort) y `estadoTraductor` | Verde | ✅ |
| 2 | `npm test` (suite completa) | `Test Files 9 passed (9)`, `Tests 105 passed (105)` | ✅ |
| 3 | `npm run typecheck` | `tsc --noEmit` sin errores | ✅ |
| 4 | `npm run build` + `eval.fase4.bundle` | Inicial **39.033 B gzip** de un presupuesto de 3.145.728 (`cumple_presupuesto_inicial: true`). three, three-vrm, GLTFLoader y el visor siguen **diferidos** (234.349 B), y el precache del SW no incluye el avatar | ✅ |
| 5 | E2E `newsroom-translate.spec.ts`: éxito (borrador, pares, aviso, procedencia no revisada, aviso de borrador desactualizado), confirmación para no pisar texto, errores 503/422/502/403 con el borrador intacto, no disponible con botón desactivado y «Volver a comprobar», cancelación | `9 passed` | ✅ |
| 6 | axe en la Redacción con el borrador y la tabla abierta, en claro y oscuro | 0 violaciones graves o críticas | ✅ |
| 7 | `npm run e2e` completo | **`41 passed`, `4 skipped`, 0 fallos (1,9 min)**. Incluye `csp.spec`, `noticiero.spec` y `translate.spec`. Los 4 saltados son del avatar 3D (`avatar.spec`, `avatar-sin-webgl` ×2, `avatar-software`) porque falta el VRM de la presentadora (ver §5) | ✅ |
| 8 | Prueba manual con el servicio real: traducir → publicar → abrir en C4 | **Se pasa al recorrido completo de la Fase 4** (prueba 5 de `PROMPT_FASE4.md`), que es la misma comprobación con la voz MMS real. Este checkout no tiene el modelo de voz descargado | ⏭ |

Backend tras el endpoint de estado: `test_translate_api.py`, `test_translation_client.py`,
`test_docs_fase6.py` y `test_security_api.py` dan `82 passed, 1 skipped` (el saltado es la prueba
`traductor`, porque el servicio estaba apagado). `ruff check` y `ruff format --check` están limpios.

## 4. Desviaciones respecto al plan

1. **Endpoint nuevo `GET /api/news/translate/status`** (backend, no previsto en el prompt). Sin él,
   la PWA no puede mostrar el estado real que pide el punto 2 del prompt. Es administrativo, solo
   lee y queda cubierto por las pruebas de seguridad.
2. **`cni.json`** no estaba «vacío», sino con todas las claves en `null`. Se siguió esa convención.
3. **Prueba manual 8** pasada a la Fase 4 (ver la tabla).
4. Hay dos claves que ya existían solo en `es.json` (`studio.onAir` y `newsroom.import.release`).
   No forman parte de este trabajo y no se tocaron.

## 5. Pendientes

- **VRM de la presentadora:** `frontend/public/models/presentadora_provisional.vrm` no existe en
  este checkout (`.gitignore`) ni en ninguna carpeta de Descargas. Por eso se saltan 4 E2E del
  avatar y falla `test_dockerignore_deja_pasar…`. Hay que copiarlo desde donde esté o regenerarlo
  con `scripts/optimize_vrm.py`, como indica `LICENSES.md`.
- Fase 4: recorrido completo con la voz real, medición ortográfica y documentación.
