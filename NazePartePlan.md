# NazeParte · Plan de la sesión

> Archivo de seguimiento **temporal de esta sesión** (no es instrucción permanente del proyecto).

## Sesión 2026-10-19 · Pantalla de traducción como entrada principal

### Diagnóstico

- **PWA** (Preact, `noticias-ashaninka/frontend/src/app/`) con **enrutador por hash** propio
  (`router.ts`): `#/` lista de noticias · `#/noticia/{id}?c=C1..C4` · `#/ajustes` ·
  `#/experimento/...`. `App.tsx` decide qué componente se muestra.
- **Voz y avatar dependen de una noticia guardada en la base.** `Presentation.tsx` reproduce el
  manifiesto por lotes (`/static/news/{id}/manifest.json`) o el respaldo NDJSON
  (`/api/synthesize/{id}`); los visemas y tiempos (`seg_NNN.json`) se generan en el backend.
  **No existe un endpoint para sintetizar texto libre.** Crear noticias (`POST /api/news`) exige
  `require_admin`.
- **El contrato con el traductor ya está escrito** en `PLAN_DESARROLLO.md` §2: el traductor de la
  compañera entrega texto cni a `POST /api/news` con
  `procedencia.tipo = "traduccion_automatica"`. Después ese texto pasa por el pipeline, la síntesis
  por lotes y `Presentation` (C2–C4: voz, resaltado, avatar).
- **CSP `connect-src 'self'`** (`backend/app/security.py`): la PWA no puede llamar directamente a
  un servicio externo. El traductor deberá exponerse en el mismo origen (ruta del backend).
- **No hay ningún servicio, endpoint ni cliente de traducción** en el repositorio.
- **i18n:** `es.json` completo; `cni.json` con las mismas claves en `null` (nunca se inventa texto).
- **Guardia del experimento** (`guardia()` en `experiment.ts`): con sesión activa redirige cualquier
  ruta distinta de la fase actual; la nueva pantalla queda bloqueada igual, sin cambios.
- **Avatar:** `frontend/src/avatar/AvatarPanel.tsx` funciona sin audio (queda en reposo), se carga
  con `import()` diferido y degrada a imagen fija sin WebGL.

### Alternativas evaluadas

| Alternativa | Decisión | Motivo |
|---|---|---|
| Nueva ruta `#/` con `TranslatePanel` y lista en `#/noticias` | **Elegida** | Amplía el enrutador existente sin duplicar cabecera, ajustes, i18n ni Service Worker |
| Endpoint `/api/translate` o proxy en backend ya | Descartada | Inventaría un contrato que no existe; la API del traductor no está definida |
| Botón «Escuchar / ver con avatar» para el texto traducido | Descartada (por ahora) | Exige un endpoint nuevo de síntesis de texto libre (debería ir con `require_admin` y abre riesgo de abuso de CPU) o crear noticias desde la PWA pública |
| Reutilizar `Presentation` con texto en memoria | Descartada | Depende de `id`, manifiesto, tiempos y visemas del backend; adaptarlo es reescribirlo |
| Página HTML aparte (como `visor.html`) | Descartada | Duplicaría cabecera, ajustes, i18n y SW |
| Dejar la lista en `#/` y el traductor en otra ruta | Descartada | No cumple «entrada principal» |
| Emitir eventos de degradación del avatar desde la portada | Descartada | `EventQueue` adjunta la condición y la noticia del contexto actual: saldrían con datos de la última noticia abierta y contaminarían el análisis |

### Solución

1. `router.ts`: ruta `translate` en `#/` (y por defecto); la lista pasa a `#/noticias`.
2. `translator.ts` (nuevo): interfaz `Translator`, implementación por defecto
   `TRADUCTOR_PENDIENTE` (no llama a ninguna URL, no devuelve texto) y reductor puro de estados
   `inicial | cargando | resultado | error | pendiente`.
3. `components/TranslatePanel.tsx` (nuevo): avatar en reposo **al costado** del texto (pedido del
   usuario), aviso de servicio pendiente, `<textarea>`, botón Traducir, zona de resultado con
   estados, nota sobre voz/avatar y enlace a las noticias.
4. `App.tsx`: renderiza la pantalla y añade «Traductor» y «Noticias» a la navegación.
5. `Presentation.tsx`: «Volver a la lista» → `#/noticias`; constantes del avatar compartidas en `data.ts`.
6. i18n (`es.json` y claves `null` en `cni.json`), estilos mínimos y `docs/pwa.md`.
7. Pruebas: unitarias (router, reductor, traductor pendiente) y E2E (portada, navegación, axe).
8. Git: clon de `https://github.com/SirNaze0/proyecto-ashaninka.git`, rama
   `feature/pantalla-traduccion`, commit y push (autorizado por el usuario).

### Tareas

- [x] Rutas y navegación
- [x] Cliente del traductor y reductor de estados
- [x] Pantalla con avatar al costado
- [x] i18n, estilos y documentación
- [x] Pruebas unitarias y E2E actualizadas
- [x] Verificación completa
- [x] Commit y push en rama nueva (`feature/pantalla-traduccion`)

### Riesgos

- E2E que abrían la lista en `/`: se actualizan a `#/noticias`.
- El VRM (~2,5 MB) y three se descargan al abrir la portada, pero en diferido: el paquete inicial
  (presupuesto < 3 MB, `eval/fase4/bundle.py`) no cambia de forma relevante.
- Las E2E de C1 que exigen «ninguna petición a `/models/`» abren la noticia directamente y no pasan
  por la portada.

### Pendientes para integrar el traductor real

1. Acordar con la compañera la API (entrada, salida, versión, límites de longitud y la ortografía de
   salida, pregunta abierta P7).
2. Ruta del mismo origen en el backend (proxy) con límite de tamaño y de peticiones, e implementar
   `Translator` en `frontend/src/app/translator.ts` apuntando a ella.
3. Voz y avatar del resultado: vía contrato §2 (`POST /api/news` con token + `process` + `batch`) o
   un endpoint protegido de síntesis de texto libre. Decisión del tesista y su asesor.
4. Traducción de los textos de la interfaz al asháninka por un hablante (`cni.json`).
