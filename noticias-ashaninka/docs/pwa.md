# PWA y condiciones experimentales (Fase 4)

Cliente en `frontend/` (Preact + TypeScript + Vite). Sirve las 4 condiciones intra-sujeto del
experimento con un único componente (`src/app/components/Presentation.tsx`) y funciona sin conexión.

```
catálogo (/api/catalog) ──► lista ──► #/noticia/{id}?c=C1..C4
manifiesto 1.1 (/static/news/{id}/manifest.json) ──► SegmentPlayer (2 <audio> alternos)
seg_NNN.json (spans, visemes) ──► Highlighter (rAF) ──► clase .hl en el fragmento ORIGINAL
                              └─► VisemeTrack ──► AvatarPanel (carga diferida de three + three-vrm)
eventos ──► IndexedDB ──► POST /api/events (por lotes, idempotente)
Service Worker: shell precargado · audio y tiempos en caché (206 a Range) · catálogo red primero
```

## Condiciones

| Condición | Qué muestra | Qué NO carga |
|---|---|---|
| **C1 · solo texto** | Título y cuerpo por párrafos (`/api/catalog/{id}`) | Audio, manifiesto, three, VRM |
| **C2 · solo voz** | «Noticia N», controles, aviso de voz sintética y licencia. Los segmentos bloqueados se omiten con un aviso | Texto en asháninka, tiempos, avatar |
| **C3 · voz + texto** | Texto completo con resaltado sincronizado (fragmento original) y controles. Los bloqueados se ven como «solo texto» con su aviso, sin cortar la reproducción | Avatar |
| **C4 · voz + texto + avatar** | C3 + `AvatarPanel` con visemas del segmento activo. Degradación: `sin-webgl`, `fps-bajos` → imagen fija, con registro del evento | — |

El orden de las condiciones por participante (cuadrado latino de Williams) es de la Fase 5: aquí el
investigador la elige en la lista o con `?c=` en la URL (`#/noticia/3?c=C2`).

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
con valores escalares cortos (el servidor rechaza cualquier otra con 422). La Fase 5 añadirá el orden, la
asignación y el cuestionario sobre esta base.

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
