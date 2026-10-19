# PWA y condiciones experimentales (Fase 4)

Cliente en `frontend/` (Preact + TypeScript + Vite). Sirve las 4 condiciones intra-sujeto del
experimento con un único componente (`src/app/components/Presentation.tsx`) y funciona sin conexión.

```
#/ traductor (entrada, servicio pendiente) ──► #/noticias
catálogo (/api/catalog) ──► lista (#/noticias) ──► #/noticia/{id}?c=C1..C4
manifiesto 1.1 (/static/news/{id}/manifest.json) ──► SegmentPlayer (2 <audio> alternos)
seg_NNN.json (spans, visemes) ──► Highlighter (rAF) ──► clase .hl en el fragmento ORIGINAL
                              └─► VisemeTrack ──► AvatarPanel (carga diferida de three + three-vrm)
eventos ──► IndexedDB ──► POST /api/events (por lotes, idempotente)
Service Worker: shell precargado · audio y tiempos en caché (206 a Range) · catálogo red primero
```

## Pantalla de traducción (entrada principal)

`#/` muestra `src/app/components/TranslatePanel.tsx`: texto en castellano, zona de resultado en
asháninka y la presentadora (el mismo `AvatarPanel` de C4, con `import()` diferido) al costado. La
lista de noticias pasó a `#/noticias` (el enlace «Volver a la lista» y la navegación apuntan ahí).

- **El traductor (tesis de una compañera) está pendiente de integración.** `src/app/translator.ts`
  define la interfaz `Translator`; la implementación por defecto `TRADUCTOR_PENDIENTE` no hace
  ninguna petición ni devuelve texto, y la pantalla lo declara. Estados: `inicial`, `cargando`,
  `resultado`, `error`, `pendiente` (reductor puro `reducir`, probado en `tests/translator.test.ts`).
- **Sin endpoint inventado.** Integrarlo exige acordar la API y exponerla en el mismo origen (la CSP
  solo permite `connect-src 'self'`). Los pasos están en el comentario de `translator.ts`.
- **El avatar queda en reposo:** sin audio no hay visemas. La voz y el avatar sincronizados solo
  existen para noticias guardadas; la vía prevista para el texto traducido es el contrato de
  `PLAN_DESARROLLO.md` §2 (`POST /api/news` → `process` → `batch` → C2–C4).
- La pantalla no emite eventos (llevarían la condición y la noticia de otra pantalla). Con una
  sesión experimental activa, la guardia de rutas la bloquea como a las demás.

## Condiciones

| Condición | Qué muestra | Qué NO carga |
|---|---|---|
| **C1 · solo texto** | Título y cuerpo por párrafos (`/api/catalog/{id}`) | Audio, manifiesto, three, VRM |
| **C2 · solo voz** | «Noticia N», controles, aviso de voz sintética y licencia. Los segmentos bloqueados se omiten con un aviso | Texto en asháninka, tiempos, avatar |
| **C3 · voz + texto** | Texto completo con resaltado sincronizado (fragmento original) y controles. Los bloqueados se ven como «solo texto» con su aviso, sin cortar la reproducción | Avatar |
| **C4 · voz + texto + avatar** | C3 + `AvatarPanel` con visemas del segmento activo. Degradación: `sin-webgl`, `fps-bajos` → imagen fija, con registro del evento | — |

Fuera del experimento, el investigador elige la condición en la lista o con `?c=` en la URL
(`#/noticia/3?c=C2`). Dentro de una sesión experimental la condición la fija el cuadrado de Williams del
participante y no se puede cambiar (ver «Experimento (Fase 5)» al final).

## Reproductor (`src/app/player.ts`, `queue.ts`)

- Dos `<audio>`: mientras suena uno, el otro tiene el siguiente cargado; al terminar, el otro arranca
  de inmediato (hueco medido: ver `resumen_fase4.md`). `prime()` precarga el primer segmento al abrir.
- Opus (principal) o MP3 (respaldo), según `canPlayType`. Velocidad 0,75× / 1× / 1,25× (`preservesPitch`).
- Repetir párrafo, párrafo siguiente, pausa. Teclado: **Espacio** (pausa/reanuda), **←** (repetir párrafo),
  **→** (párrafo siguiente); no actúan si el foco está en un botón, un selector o un enlace.
- Segmentos bloqueados (sin P2d): `url = null`; se avisan (`blocked-shown`) y se saltan sin parar.
- **Respaldo bajo demanda:** si no hay manifiesto (404), se lee el stream NDJSON de
  `/api/synthesize/{id}` y los segmentos se agregan al reproductor a medida que llegan (estado
  «preparando el siguiente audio» si se acaban antes de que llegue el siguiente).

## Resaltado (`src/app/highlight.ts`)

`seg_NNN.json` trae `spans`: fragmentos del texto **original** (`MINSA`, `2026`) con su intervalo de
audio, proyectado por el mapa de alineación de la Fase 1 (1.5c). Mientras suena la glosa o la forma
expandida, se resalta el fragmento original completo. El fragmento activo es el último resaltable
(con letras o dígitos y duración > 0) cuyo `t0` ya pasó según `AudioClock` (el mismo reloj de la Fase 3):
entre dos palabras se mantiene la anterior. Cada cambio queda en `Highlighter.log` (`clock_t`, `t0`)
para medir el desfase. Con `prefers-reduced-motion` el resaltado no anima (es un cambio de fondo).

## Service Worker (`src/sw.ts`, `src/sw-logic.ts`)

Escrito a mano (no `vite-plugin-pwa`) para controlar las peticiones `Range` de `<audio>`:

| Ruta | Estrategia |
|---|---|
| *shell* (HTML, JS, CSS iniciales, manifiesto web, íconos) | precarga; lista inyectada al compilar (`vite.config.ts`); **sin el avatar** |
| `/static/news/**`, `/static/audio/**` | caché primero; guarda el archivo **completo** y contesta **206** con `Content-Range` a las peticiones `Range` |
| `/api/catalog**` | red primero; sin conexión, la última respuesta guardada |
| `/assets/**`, `/models/**` (three, three-vrm, VRM) | se guardan al usarse por primera vez (C4 sin conexión) |
| `POST /api/events`, `/api/synthesize` | directo a la red |

«Guardar para escuchar sin conexión» (`src/app/offline.ts`) baja el manifiesto, los tiempos y el audio
de una noticia a la misma caché (`na-news-v1`).

## Eventos (`src/app/events.ts`, `backend/app/api/events.py`)

Cada acción (reproducir, pausar, velocidad, repetir, inicio/fin de segmento, bloqueado mostrado,
degradación, `avatar-ok`, cambio de tamaño o idioma, guardado sin conexión…) se guarda en IndexedDB con
un UUID y se envía por lotes a `POST /api/events` cuando hay red (al emitir, al volver la conexión y
al ocultar la página). El servidor ignora los duplicados (`event_id` único). **Privacidad:** solo un UUID
anónimo de sesión, la condición y la noticia; el `payload` admite únicamente una lista cerrada de claves
con valores escalares cortos (el servidor rechaza cualquier otra con 422). La Fase 5 añadió el orden, la
asignación y el cuestionario sobre esta base (lista de claves y tipos ampliada).

## Avisos éticos y accesibilidad

- Aviso permanente (C2–C4) de voz sintética, licencia de la voz (CC-BY-NC 4.0 si es MMS), aviso de
  avatar sintético (C4), **variante dialectal** y marca de pseudo-noticia del corpus (no apta para el experimento).
- 4 tamaños de texto (100, 125, 150 y 200 %), contraste AA en claro y oscuro, botones de al menos 44 px,
  foco visible, enlace «saltar al contenido», `lang="cni"` en el texto en asháninka, `aria-live` discreto,
  `prefers-reduced-motion`. axe-core (WCAG 2.1 A/AA) sin violaciones críticas ni graves en la lista, ajustes
  y C1–C4 (prueba E2E).
- **Interfaz en asháninka: pendiente de traducción por un hablante.** `src/app/i18n/cni.json` tiene las
  mismas claves con valor `null` (estado `PENDIENTE-TRADUCCION`); mientras tanto se muestra el castellano y
  Ajustes lo avisa. No se inventa ningún texto en asháninka.

## Servir y probar

```bash
cd frontend && npm run build                       # dist/ (index.html, sw.js, assets/)
uv run uvicorn app.main:app                        # sirve /, /api y /static en el mismo origen
npm run dev                                        # desarrollo: Vite en :5173 con proxy a :8000 (sin Service Worker)
npm test                                           # vitest (41)
npm run e2e                                        # compila y corre Playwright en Chromium real (18)
```

Las pruebas E2E levantan `scripts/e2e_server.py` (datos deterministas con el motor `fake`: una noticia
completa, una con un segmento bloqueado y una sin sintetizar para el respaldo NDJSON). La prueba del
avatar necesita el VRM provisional (`frontend/README.md`); si falta, se omite.

## Evaluación (tarea 4.7)

```bash
uv run python -m eval.fase4.prepare                # 30 pseudo-noticias de dev -> eval/fase4/out/ (mms_vits)
uv run python -m eval.fase4.serve &                # PWA + API + /static en :8766
node frontend/scripts/fase4_bench.mjs all          # carga, TTFA, reproducción, FPS, degradación, sin conexión, eventos
uv run python -m eval.fase4.run                    # -> eval/results/fase_4.json
```

Definiciones en `docs/metrics.md` (sección «Fase 4»), escritas antes de medir.

## Experimento (Fase 5)

Flujo guiado en `#/experimento` (`src/app/experiment.ts`, `components/ExperimentFlow.tsx`). Resumen del
diseño y del análisis en `docs/metrics.md` («Fase 5»); datos exportados en `data/DATA_DICTIONARY.md`.

```
#/experimento            consentimiento + código anónimo (P007)  ── POST /api/experiment/sessions
#/experimento/bloque/k   noticia k en la condición que fija Williams; «Continuar» al terminar
#/experimento/cuestionario/k   comprensión (marcada por un entrevistador) + esfuerzo + aceptabilidad
   … ×4 bloques …
#/experimento/final      covariables + ranking C1–C4 + comentario sin datos personales
#/experimento/fin        envía lo pendiente y cierra la sesión  ── POST /api/experiment/sessions/{code}/finish
```

- **Asignación.** El servidor devuelve la secuencia de 4 bloques (condición, noticia) a partir del código;
  el cliente la contrasta con su propia tabla de Williams (`secuenciaEsperada`) y rechaza una asignación
  que no coincida. Un vector común (`tests/fixtures/williams_vector.json`) lo prueban vitest y pytest.
- **Sin cambio libre de condición.** Con una sesión activa, la guardia de rutas (`guardia()` en `App.tsx`)
  redirige cualquier otra ruta (`#/`, `#/ajustes`, `#/noticia/..?c=`) a la de la fase actual, y se
  ocultan el selector y la navegación. Salir exige «Abandonar el estudio» con confirmación (evento
  `abandon`). Manipular la URL reinicia el bloque en curso.
- **Fin de bloque.** C2, C3 y C4: termina el audio (`onFinished`). C1 no tiene audio: botón «Terminé de leer»
  (`read-done`). Cada bloque emite `block-start` y `block-end` (`reason: completo`) con la condición y la
  noticia en el contexto del evento, y así los une la exportación.
- **Persistencia.** IndexedDB `na-events` v2 con los almacenes `events`, `experiment` (estado de la sesión,
  se reanuda tras recargar) y `responses` (cola de cuestionarios). La cola reenvía de forma idempotente
  (`response_id` UUID) cuando vuelve la red; una respuesta que el servidor rechaza (422) se aísla sin
  bloquear a las demás. El cierre de la sesión solo se acepta cuando están las 5 respuestas.
- **Pendientes (no se inventan).** El texto del consentimiento y su audio (`PENDIENTE-COMITE-ETICA`) y los
  ítems de comprensión (`PENDIENTE-HABLANTE`) son marcadores; `cni.json` conserva las claves nuevas en `null`.
- **Servidor.** `NA_EXPERIMENT_PILOTO=true` admite pseudo-noticias y marca todo como piloto. Sin ese modo
  el servidor exige 4 noticias revisadas por un hablante (P4). La exportación (`GET /api/experiment/export`)
  está cerrada salvo en modo piloto o con `NA_EXPORT_TOKEN` (cabecera `x-export-token`); la vía normal
  es la CLI: `uv run python -m app.cli experiment export --out DIR`.
- **Pruebas.** `tests/experiment.test.ts` (vitest) y `e2e/experiment.spec.ts` (Chromium real, servidor propio
  `scripts/e2e_server.py --experimento`, proyecto `experimento` de Playwright).

## Sistema visual (pulido UI/UX)

- Solo CSS propio en `frontend/src/app/styles.css`: sin librerías ni fuentes externas (pila `system-ui` y serif del sistema para titulares y lectura).
- Tokens de color en `:root`, redefinidos para modo oscuro con `prefers-color-scheme`; los pares texto/fondo cumplen WCAG 2.1 AA (axe-core, 0 violaciones en ambos modos) y los controles miden al menos 44 px.
- C4 en pantallas ≥ 960 px: dos columnas (avatar y reproductor fijos a un lado, lectura con resaltado al otro); en móvil se apila.
- Segmentos bloqueados como nota editorial, resaltado con borde suave, indicador de pasos del experimento (igual en las 4 condiciones; no revela la condición) y opciones de cuestionario como tarjetas.
