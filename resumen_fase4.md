# Resumen de la Fase 4: Interfaz web (PWA) y condiciones experimentales C1–C4

> **Proyecto:** Servicio web de noticias en lengua asháninka con síntesis de voz, texto y avatar
> **Fecha:** 2026-10-12 · **Repositorio:** `Proyecto` (código en `noticias-ashaninka/`) · **Rama:** `feat/fase4-pwa` · **Base:** Fase 3 (`fc8b9`)
> **Estado:** implementada y medida; **pendiente de aprobación**. Cumplen todos los criterios medibles en simulación. **No se verificó en un Android de gama media real** (requiere el dispositivo) y la interfaz en asháninka sigue **pendiente de traducción por un hablante**.

Todas las cifras vienen de ejecuciones reales (`eval/results/fase_4.json` y `eval/fase4/out/*.json`). Las definiciones de las métricas se escribieron **antes** de medir, en `docs/metrics.md` (sección «Fase 4»); la única revisión (el material de 30 pseudo-noticias de 3 líneas) se fechó antes de la primera medición.

**Cierre previo (eSpeak-NG).** La línea base quedó cerrada el 2026-10-12: RTF de eSpeak 0,0105; CER sobre test 0,2291 [0,2203; 0,2382]; tareas 2.3, 2.8 y 2.10 al 100 %. La reejecución en el equipo Intel de 12 núcleos cambió el RTF de `mms_vits` a 0,2546 (antes 0,19). Con eSpeak instalado hay 139 pruebas de Python pasando y 1 omitida por diseño (la que solo corre sin eSpeak).

---

## 1. Qué hace el sistema hoy

Una PWA en Preact que presenta cada noticia en una de las 4 condiciones del experimento y funciona sin conexión:

| Condición | Qué ve y oye el participante |
|---|---|
| **C1 · solo texto** | El título y el cuerpo. No se descarga audio, manifiesto, three ni el modelo del avatar |
| **C2 · solo voz** | «Noticia N», controles y el aviso de voz sintética. Sin texto en asháninka ni avatar. Los segmentos bloqueados se omiten con un aviso |
| **C3 · voz + texto** | Texto con la palabra o fragmento original resaltado mientras suena (MINSA o 2026 se resaltan enteros). Los segmentos bloqueados (sin P2d) se ven como «solo texto» y la reproducción continúa |
| **C4 · voz + texto + avatar** | C3 + la presentadora (three-vrm, carga diferida) con visemas sincronizados. Si no hay WebGL o los FPS < 20, imagen fija y se registra el evento |

```
catálogo ─► lista ─► #/noticia/{id}?c=C1..C4
manifiesto 1.1 ─► SegmentPlayer (2 <audio>, precarga) ─► Highlighter (AudioClock) ─► texto original
seg_NNN.json ─► VisemeTrack ─► AvatarPanel (import() diferido)
eventos ─► IndexedDB ─► POST /api/events (por lotes, idempotente) · Service Worker: shell + audio en caché (206 a Range)
```

---

## 2. Qué se implementó

| Tarea | Componente | Dónde está |
|---|---|---|
| 4.1 | Rutas por hash, lista, ajustes, i18n (`es.json` completo; `cni.json` con las mismas claves en `null`, **pendiente de traducción**), Web App Manifest e íconos | `frontend/src/app/`, `public/manifest.webmanifest` |
| 4.2 | Reproductor por segmentos: 2 `<audio>`, precarga, Opus con respaldo MP3, 0,75–1,25×, repetir párrafo, pausa, teclado, respaldo NDJSON bajo demanda | `player.ts`, `queue.ts`, `data.ts` |
| 4.3 | Resaltado del fragmento **original** con `spans` y `AudioClock`; 4 tamaños de texto | `highlight.ts`, `Presentation.tsx` |
| 4.4 | Service Worker propio (206 a `Range`), «guardar para escuchar sin conexión», cola de eventos en IndexedDB | `sw.ts`, `sw-logic.ts`, `offline.ts`, `events.ts` |
| 4.5 | Avisos de voz y avatar sintéticos, licencia, variante dialectal, marca de pseudo-noticia | `components/Notices.tsx` |
| 4.6 | Un componente con las 4 condiciones | `components/Presentation.tsx` |
| 4.7 | Banco de pruebas en Chromium real con CDP; consolidación | `frontend/scripts/fase4_bench.mjs`, `eval/fase4/` |
| API | `/api/catalog` (lista, detalle, meta; nunca el castellano), `/api/events` (lote ≤ 500, idempotente, lista cerrada de claves), gzip solo para texto, sirve `frontend/dist` | `backend/app/api/{catalog,events}.py`, `main.py` |
| Pruebas | 41 de vitest (24 nuevas), 18 E2E de Playwright (con axe-core), 17 nuevas de Python (API 8 + evaluación 9) | `frontend/tests`, `frontend/e2e`, `backend/tests` |

---

## 3. Resultados

**Material:** 30 pseudo-noticias de 3 líneas consecutivas del split **dev** (69 segmentos con audio, 21 bloqueados = 23 %, hasta 25,7 s de audio), sintetizadas con `mms_vits` (`eval/fase4/prepare.py`). **Perfil móvil simulado:** CPU 4× más lenta + 4G (9 Mbps, 150 ms). Chromium 156 con una RTX 3060 Ti. **No son noticias reales ni un teléfono real.**

### Carga inicial (MB transferidos hasta el primer audio listo, primera visita, gzip)

| Condición | Máximo | Meta |
|---|---|---|
| C1 | 0,021 | < 3 MB |
| C2 | 0,039 | < 3 MB |
| C3 | 0,099 | < 3 MB |
| C4 (sin el avatar diferido) | 0,048 | < 3 MB |
| C4 total (con three, three-vrm y el VRM) | 2,81 | referencia |

Paquete inicial por `vite build`: 18,7 KB gzip; el avatar diferido, 234 KB gzip; el VRM provisional, 2,53 MB (**supera la meta de 2 MB del modelo final**). El Service Worker precarga 20,4 KB y **no incluye el avatar**.

### TTFA del cliente por lotes (clic → primer audio; 30 noticias × 3 repeticiones)

| Perfil | Caché | p50 | p95 | p99 |
|---|---|---|---|---|
| Sin límite | fría | 13,6 ms | **15,3 ms** | 17,5 ms |
| Sin límite | caliente | 14,0 ms | 17,1 ms | 18,3 ms |
| **Móvil 4× + 4G** | **fría** | 87,5 ms | **113 ms** ✓ (< 2 s) | 148,6 ms |
| Móvil 4× + 4G | caliente | 11,3 ms | 14,2 ms | 24,4 ms |
| C4, móvil 4× + 4G (10 noticias) | fría | 77,9 ms | 87,1 ms | |

*Arranque completo* (navegación → primer audio), móvil 4× + 4G en frío: p50 892 ms, **p95 948 ms**; sin límite, p95 147 ms. El TTFA «clic → audio» es corto porque el primer segmento se precarga al abrir la noticia (ver `docs/limitations.md`, 40); por eso se reporta también el arranque completo, que también cumple < 2 s.

### Reproducción continua y resaltado (reproducción completa)

| Caso | Noticias completas | Hueco entre segmentos (mediana / p95) | Desfase del resaltado \|p95\| / máx. | Cobertura |
|---|---|---|---|---|
| C3, sin límite | 30/30 | 1,3 / 6,1 ms | 15,4 / 18,5 ms | 100 % (383 fragmentos) |
| C3, móvil 4× | 30/30 | 4,4 / 9,0 ms | 15,8 / 17,9 ms | 100 % |
| C4, sin límite | 10/10 | 0,8 / 6,3 ms | 15,7 / 17,7 ms | 100 % (127) |
| C4, móvil 4× | 10/10 | 3,5 / 9,9 ms | 15,2 / 17,9 ms | 100 % |

Meta del desfase: |p95| ≤ 80 ms → **cumple** (≈ un cuadro de pantalla). Es el error del resaltado frente al reloj estimado del audio; **no incluye la latencia de salida del dispositivo** (limitación 39). Los segmentos bloqueados se mostraron como solo texto en todas las reproducciones (21 en C3, 5 en C4) sin cortarlas.

### FPS y degradación en C4 (dentro de la PWA)

| Caso | Modo | FPS (5 s) | Evento |
|---|---|---|---|
| GPU del equipo | avatar | **60** (dibujo p95 2,2 ms) | `avatar-ok` |
| GPU + CPU 4× más lenta | avatar | **60** (p95 4,7 ms) | `avatar-ok` |
| Software (SwiftShader) | avatar | 15,9 | `avatar-ok` |
| Software + CPU 4× | imagen fija | n/a (sin avatar) | `fps-bajos` |
| Sin WebGL | imagen fija | — | `sin-webgl` |
| CPU 20× + software | imagen fija | — | `fps-bajos` (0,3 FPS) |

Con SwiftShader sin limitar la CPU, el sondeo de 2 s dejó pasar el avatar (≥ 20 FPS) y luego sostuvo solo 15,9: el sondeo es de una sola vez (limitación de la Fase 3, 31). La degradación se probó también con audio y texto funcionando.

### Sin conexión, eventos y accesibilidad

| Medida | Resultado |
|---|---|
| Sin conexión (C1, C2, C3 × 3 noticias, una con bloqueado) | 9/9 abren y se reproducen completas desde la caché; el Service Worker contesta **206** a `Range` |
| Cola de eventos | 25 eventos sin red → 25 pendientes → 100 % entregados al volver (26 en el servidor con el `view-start`), 0 pendientes, 0 duplicados al reenviar |
| axe-core (WCAG 2.1 A/AA) en lista, ajustes y C1–C4 | **0 violaciones críticas o graves** (se corrigió un `aria-prohibited-attr` real del avatar) |

---

## 4. Cómo se usa

Comandos en Git Bash dentro de `Proyecto/noticias-ashaninka`.

```bash
(cd frontend && npm install && npm run build)            # PWA -> frontend/dist
uv run uvicorn app.main:app                               # http://127.0.0.1:8000  (PWA + /api + /static)
# abrir:  http://127.0.0.1:8000/#/noticia/1?c=C3          (C1, C2, C3 o C4)
(cd frontend && npm test && npm run typecheck && npm run e2e)

# evaluación (tarea 4.7)
uv run python -m eval.fase4.prepare                       # 30 pseudo-noticias dev -> eval/fase4/out/
uv run python -m eval.fase4.serve &                       # :8766
node frontend/scripts/fase4_bench.mjs all                 # ~35 min
uv run python -m eval.fase4.bundle && uv run python -m eval.fase4.run   # -> eval/results/fase_4.json
```

Detalle de la arquitectura en `docs/pwa.md`.

---

## 5. Criterios de cierre

| Criterio | Estado |
|---|---|
| Carga inicial < 3 MB | **Cumple** (máx. 0,099 MB; C4 con avatar y VRM: 2,81 MB) |
| TTFA p95 < 2 s por lotes | **Cumple** (113 ms con CPU 4× + 4G en frío; arranque completo 948 ms) |
| Desfase del resaltado ≤ 80 ms | **Cumple** (\|p95\| 15,8 ms; máx. 18,5 ms; sin latencia de salida) |
| 60 FPS | **Cumple con GPU** (60, también con CPU 4×). **No sin GPU** (15,9). No verificado en un Android real |
| Las 4 condiciones funcionan | **Cumple** (E2E y 80 reproducciones completas) |
| Segmentos bloqueados sin romper la reproducción | **Cumple** |
| Degradación probada y registrada | **Cumple** (3 casos) |
| Sin conexión, cola de eventos | **Cumple** |
| Accesibilidad (axe-core) | **Cumple** (0 críticas o graves) |
| Avisos éticos (voz/avatar sintéticos, licencia, variante) | **Cumple** |
| Verificación en un **Android de gama media real** | **Pendiente** (requiere el dispositivo) |
| Pruebas y lint | **Cumple**: 139 de Python (1 omitida por diseño), cobertura 97,6 %; 41 de vitest; 18 E2E; `ruff`, `ruff format --check` y `tsc` sin errores |

## 6. Pendientes que se arrastran

| Pendiente | Impacto | Acción |
|---|---|---|
| **Android de gama media real** | CPU 4× y 4G son simuladas; FPS y TTFA reales pueden ser peores | Medir con `fase4_bench.mjs` apuntando `BASE` al servidor desde el teléfono (Chrome remoto) |
| **Interfaz en asháninka** | `cni.json` vacío (`PENDIENTE-TRADUCCION`) | Lo traduce un hablante; no se inventa |
| **Noticias reales revisadas (P4)** | Se midió con pseudo-noticias del corpus | ≥ 8 noticias revisadas por un hablante |
| **C2 omite los bloqueados** | Amenaza a la validez entre condiciones (23 % de la muestra) | En el experimento usar noticias sin bloqueados o tratarlo como covariable |
| **VRM final de la presentadora** | El provisional pesa 2,53 MB (meta ≤ 2 MB) | Pista paralela (VRoid) |
| **Praat (20 oraciones), P1, P2d, P2a–P2c, P5** | Pendientes de la Fase 3 | Lingüista, hablantes, compañera |
| **Fase 5** | Consentimiento, cuadrado latino, cuestionario, exportación CSV | La cola de eventos y su privacidad ya están |

Las limitaciones completas están en `docs/limitations.md` (puntos 36 a 45, nuevos en esta fase).
