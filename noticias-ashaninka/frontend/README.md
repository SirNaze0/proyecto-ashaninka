# PWA de noticias en asháninka (Fase 4) y visor del avatar (Fase 3)

TypeScript + Vite + Preact. El avatar usa three.js y `@pixiv/three-vrm`, cargados de forma
**diferida** (fuera del paquete inicial). Documentación completa: `../docs/avatar.md`.

```bash
npm install
npm run dev          # http://localhost:5173 (reenvía /static y /api al backend en :8000)
npm run typecheck    # tsc --noEmit
npm test             # vitest: visemas, reloj, gestos, degradación, rutas, cola, reproductor, resaltado, eventos, SW
npm run build        # dist/ (index.html, sw.js, assets/) + dist/.vite/manifest.json (lo leen eval/fase3 y eval/fase4/bundle.py)
npm run e2e          # build + Playwright en Chromium real (3 perfiles: GPU, sin WebGL, SwiftShader)
npm run bench:size   # peso de las dos opciones de la tarea 3.1 (bench/)
```

## Modelo VRM provisional

El modelo de la presentadora final (VRoid Studio, pista paralela) aún no existe. Mientras tanto se
usa `VRM1_Constraint_Twist_Sample` (pixiv, VRM 1.0, redistribución permitida), reducido con
`scripts/optimize_vrm.py`. **No se versiona** (`public/models/*.vrm` está en `.gitignore`):

```bash
# desde noticias-ashaninka/
curl -sL -o /tmp/twist.vrm https://raw.githubusercontent.com/pixiv/three-vrm/dev/packages/three-vrm/examples/models/VRM1_Constraint_Twist_Sample.vrm
uv run python scripts/optimize_vrm.py /tmp/twist.vrm frontend/public/models/presentadora_provisional.vrm \
    --keep-expressions aa,ih,ou,ee,oh,blink
```

Para usar otro modelo: `/visor.html?vrm=/models/otro.vrm`.

## Visor

1. Sintetizar una noticia (`uv run python -m app.batch build --news 1`) y levantar el backend
   (`uv run uvicorn app.main:app`).
2. Abrir `http://localhost:5173/visor.html?news=1` (parámetros: `framing=rostro|busto`,
   `deterministic=1`, `size=360`, `vrm=…`).

## Scripts de Playwright (`scripts/`)

| Script | Para qué |
|---|---|
| `smoke.mjs` | Carga el visor en Chromium y guarda una captura |
| `capture.mjs` | Tareas 3.7 y 3.8: dibuja el avatar fotograma a fotograma (50 Hz), mide la boca renderizada y guarda JPEG a 25 fps. Reanudable |
| `realtime.mjs` | Reproducción real: FPS y error del reloj del cliente (con `gpu` o `swiftshader`, con o sin CPU limitada) |
| `degradation.mjs` | Tarea 3.6: sin WebGL, CPU muy lenta y condiciones normales |

`npx playwright install chromium` descarga el navegador la primera vez.

## Integración en la PWA (Fase 4)

```tsx
import { AvatarPanel } from "./avatar/AvatarPanel";
<AvatarPanel vrmUrl="/models/presentadora.vrm" fallbackImage="/presentadora_fija.svg"
  onReady={(h) => { h.viewer?.attachAudio(audioEl); h.viewer?.setTrack(new VisemeTrack(seg.visemes)); }}
  onEvent={registrarEventoDeDegradacion} />
```

Las condiciones C1–C3 no importan nada de `src/avatar/viewer.ts`, así que no descargan three.

## PWA (Fase 4)

Código en `src/app/` (ver `../docs/pwa.md`): `App.tsx` (rutas), `components/Presentation.tsx`
(C1–C4), `player.ts`, `highlight.ts`, `events.ts`, `offline.ts`, `i18n/`. El Service Worker es
`src/sw.ts` (sale como `dist/sw.js`). El avatar (three, three-vrm y el VRM) se importa de forma
diferida solo en C4. `public/icon-*.png` se generan con `uv run python scripts/make_icons.py`.
Banco de medición: `scripts/fase4_bench.mjs` (usa `eval/fase4/`).
