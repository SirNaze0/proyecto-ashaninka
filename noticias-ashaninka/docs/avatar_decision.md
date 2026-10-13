# Decisión de la tecnología del avatar (tarea 3.1)

> **Decisión (2026-10-12): three.js + `@pixiv/three-vrm`.** Se descarta TalkingHead.
> Tomada de forma automática, con las mediciones de abajo, según lo acordado para esta fase.

## Criterios

Los de la tarea 3.1 y los del experimento: peso del paquete (< 3 MB), desfase labial (≤ 80 ms),
60 FPS y compatibilidad con Preact. Se añaden dos que el plan menciona sin cifrarlos:
compatibilidad con el modelo que sale de VRoid Studio y control del reloj de reproducción.

## Comparativa

| Criterio | three + three-vrm | TalkingHead 1.7.0 | Cómo se midió |
|---|---|---|---|
| Peso del bundle (minificado) | 887 KB | 1 026 KB | `vite build` de un punto de entrada mínimo (`frontend/bench/`, `npm run bench:size`) |
| Peso del bundle (gzip) | **196 KB** | 226 KB | ídem; `eval/fase3/bundle.py` |
| Compatibilidad con Preact | Sí (probado) | Probable (no probado) | Ambas son agnósticas del framework y trabajan sobre un nodo del DOM. three-vrm se probó con `AvatarPanel.tsx`; TalkingHead no se integró |
| Modelo de VRoid (VRM) | **Nativo**: expresiones `aa ih ou ee oh blink` | **No**: exige morph targets ARKit y visemas Oculus (`viseme_aa`…) | Lectura del VRM de ejemplo (sus morph targets son `Fcl_MTH_A/I/U/E/O`) y del código de TalkingHead |
| Control del reloj | Total: se evalúa la pista en `audio.currentTime` o en un instante dado (`renderAt`) | Cola de habla y bucle de animación propios (a juzgar por su README y sus imports); no se probó si admite dibujar un instante dado | Lectura de la documentación; no probado en ejecución |
| Visemas de la lengua | Los genera este proyecto (`seg_NNN.json`) | Módulos de labios para en, fi, de, fr y lt; ninguno para asháninka | README y `modules/` |
| Dependencias | Una versión de `three` | Trae su propia copia de `three` 0.180 (el proyecto usa 0.186): dos copias si se mezclan | `node_modules` |
| Licencia | MIT | MIT | `package.json` |
| **FPS medidos** | **60** (GPU), 17–18 (sin GPU) | no medido | `frontend/scripts/realtime.mjs` (ver `docs/avatar.md`) |
| **Desfase labial** | **sistemático −10,8 ms [IC 95 %: −18,5; −2,1]** | no medido | `eval/fase3/lipsync.py` |

## Por qué TalkingHead no se pudo medir en desfase ni en FPS

Esos dos criterios requieren cargar el avatar de la presentadora. TalkingHead no puede cargar el
modelo VRM de VRoid sin convertirlo (añadir los morph targets ARKit y los visemas Oculus en
Blender), y el plan ya lo anticipaba en §1: sus modelos de referencia venían de Ready Player Me,
que ya no opera. Medirlo habría exigido modelar un avatar distinto, que es justo el costo que se
quería evitar. La decisión se apoya entonces en la compatibilidad, el control del reloj y el peso;
**no** en una comparación de FPS y desfase entre las dos, y así queda dicho.

No se cronometró el tiempo de integración de cada una, así que el criterio «rapidez de
desarrollo» del plan no tiene cifra: lo que sí consta es que el visor completo (carga diferida,
visemas, parpadeo, mirada, gestos, degradación, medición y captura) está construido sobre
three-vrm y ocupa 28,6 KB (11,9 KB gzip, Preact incluido) de código propio.

## Qué se pierde al elegir three-vrm

- Los gestos y el habla no vienen hechos: la coarticulación, el parpadeo y los gestos son código de este
  proyecto (`backend/app/pipeline/viseme/`, `frontend/src/avatar/`).
- Las animaciones de Mixamo no se pudieron automatizar (exigen cuenta de Adobe y aceptar sus
  términos en cada descarga). Los cuatro gestos son procedurales (rotaciones de huesos
  normalizados); `Gestures.register()` admite clips retargeteados cuando existan.
