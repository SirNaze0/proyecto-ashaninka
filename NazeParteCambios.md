# NazeParte · Cambios de la sesión

> Archivo de seguimiento **temporal de esta sesión** (no es instrucción permanente del proyecto).

## Sesión 2026-10-19

### Archivos modificados (rutas relativas a `noticias-ashaninka/`)

| Archivo | Cambio | Motivo |
|---|---|---|
| `backend/app/main.py` | `NA_FRONTEND_DIST` vacío equivale a no definida | Con el valor de `.env.example` la PWA no se montaba (`/` → 404) en una instalación nueva |
| `frontend/src/app/router.ts` | Ruta `translate` en `#/` (y por defecto); lista en `#/noticias` (`NEWS_HREF`); `#/noticia/<id mal formado>` sigue llevando a la lista | La traducción es la entrada principal sin perder la lista |
| `frontend/src/app/translator.ts` (nuevo) | Interfaz `Translator`, `TRADUCTOR_PENDIENTE` (sin peticiones, sin texto), `TraductorNoDisponible`, reductor `reducir` con estados `inicial/cargando/resultado/error/pendiente` | Preparar la integración sin inventar API ni traducciones |
| `frontend/src/app/components/TranslatePanel.tsx` (nuevo) | Pantalla: avatar al costado (reutiliza `AvatarPanel` con `import()` diferido), aviso de servicio pendiente, `<textarea>`, botón, resultado con estados, nota de voz/avatar, enlace a noticias | Pedido de la sesión (con el avatar al costado del texto) |
| `frontend/src/app/App.tsx` | Renderiza `TranslatePanel`; navegación «Traductor · Noticias · Ajustes» con `aria-current` | Acceso a ambas pantallas |
| `frontend/src/app/data.ts` | Constantes `VRM_URL` y `FALLBACK_IMG` compartidas | Evitar duplicarlas sin importar el avatar de forma estática |
| `frontend/src/app/components/Presentation.tsx` | Usa las constantes compartidas; «Volver a la lista» → `#/noticias` | La lista cambió de ruta |
| `frontend/src/app/i18n/es.json`, `cni.json` | 14 claves nuevas (`translate.*`, `nav.translate`, `nav.news`); en `cni.json` todas `null` | No se inventa texto en asháninka |
| `frontend/src/app/styles.css` | Estilos de la pantalla (dos columnas desde 720 px, apilado en móvil) y navegación que se ajusta en pantallas estrechas | Diseño pedido |
| `frontend/tests/app-logic.test.ts` | Expectativas del enrutador para las rutas nuevas | Cambio intencional de `#/` |
| `frontend/tests/translator.test.ts` (nuevo) | 8 pruebas: traductor pendiente sin `fetch`, estados, textos i18n | Estados de carga, error y resultado sin traducción ficticia en la app |
| `frontend/e2e/translate.spec.ts` (nuevo) | Entrada principal con avatar al costado; estado pendiente sin peticiones; navegación traductor → noticias → C4 (voz y avatar) → lista → traductor | Verificación pedida |
| `frontend/e2e/conditions.spec.ts`, `offline-a11y.spec.ts`, `csp.spec.ts`, `experiment.spec.ts` | La lista se abre en `#/noticias`; axe y CSP también sobre la pantalla de traducción; tras abandonar el experimento se vuelve a `#/` (traductor) | Cambio de la ruta de la lista |
| `docs/pwa.md` | Diagrama de rutas y sección «Pantalla de traducción» | Documentación de la PWA |

No se modificaron `CLAUDE.md`, el backend (aparte del arreglo de `main.py`), el Service Worker, la
voz, el avatar ni el experimento.

### Preparación del entorno (sin cambios de código)

- `./init.sh --with-tts --with-data`, la descarga del modelo `facebook/mms-tts-cni` (SHA-256
  verificados) y el VRM provisional generado con `scripts/optimize_vrm.py`, como indica
  `frontend/README.md`.
- `npx playwright install chromium` para las E2E.

### Pruebas y resultados

| Comando | Resultado |
|---|---|
| `npm test` (vitest) | **75 passed** (7 archivos) |
| `npm run typecheck` | sin errores |
| `npm run build` | correcto; three y three-vrm siguen en chunks diferidos |
| `npm run e2e` (Playwright, Chromium real: gpu, experimento, sin-webgl, software) | 1.ª ejecución: 28 passed, 2 failed (ver abajo); **2.ª: 30 passed** |
| `uv run pytest` (suite completa) | **314 passed, 2 skipped** (sin Caddy, sin eSpeak-NG) |
| `uv run ruff check` / `ruff format --check` | sin errores / 149 archivos ya formateados |
| `eval.fase4.bundle.medir()` | paquete inicial 27,9 KB gzip (presupuesto 3 MB: cumple); el avatar no entra en el precache |
| Servidor real (`uvicorn`, voz MMS) + capturas a 1280 px y 390 px | portada con avatar al costado (escritorio) y apilado (móvil); estado «pendiente»; `#/noticias` lista 20 noticias |

**Fallos de la 1.ª ejecución (en las pruebas, no en la app) y corrección:**

1. `translate.spec.ts`: contaba las peticiones de la carga diferida del avatar (three-vrm, VRM,
   texturas `blob:`). Ahora espera a que el avatar cargue y solo admite `POST /api/events` y
   `/assets`/`/models`.
2. `experiment.spec.ts`: tras abandonar se vuelve a `#/`, que ahora es el traductor. Se comprueba la
   pantalla de traducción y luego que la lista sigue accesible en `#/noticias`.

### Git

- Repositorio: `https://github.com/SirNaze0/proyecto-ashaninka.git`, rama
  `feature/pantalla-traduccion` (commit y push autorizados por el usuario). `package-lock.json` no se
  incluye: `npm install` en Windows lo modificó sin relación con esta tarea.
