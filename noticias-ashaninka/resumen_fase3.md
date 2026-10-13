# Resumen de la Fase 3: Alineación, visemas y avatar

> **Proyecto:** Servicio web de noticias en lengua asháninka con síntesis de voz, texto y avatar
> **Fecha:** 2026-10-12 · **Repositorio:** `Proyecto` (código en `noticias-ashaninka/`) · **Base:** commit `965c822` (Fase 2)
> **Estado:** implementada, **APROBADA el 2026-10-12**. Cumple los criterios medibles con matices (ver §5): el desfase **por clip** no es verificable con el método disponible, SyncNet no discrimina con este avatar, y quedan tareas que requieren a una persona o un dispositivo (Praat, Android real).

Todas las cifras de este documento vienen de ejecuciones reales. Están en `eval/results/fase_3.json` y en
los archivos `fase_3_alineacion.json` y `fase_3_lipsync.json` de esa carpeta. Las definiciones de las métricas
se escribieron antes de medir, en `docs/metrics.md`; la única revisión posterior (el estimador del desfase)
está fechada y explicada en ese mismo archivo.

**Cierre de la Fase 2.** Aprobada el 2026-10-12: el modo por lotes (TTFA 44 ms) es el principal y el
bajo demanda (2357 ms) queda solo como respaldo. La línea base eSpeak-NG quedó **cerrada** el 2026-10-12 (RTF 0,0105; CER sobre test 0,2291): las tareas 2.3, 2.8 y 2.10 están al 100 %.

---

## 1. Qué hace el sistema hoy

Además de voz, cada oración sintetizada trae **los tiempos de cada palabra y fonema y una pista de visemas**, y existe un **visor** que mueve la boca de una presentadora VRM sincronizada con el audio:

1. Las duraciones reales de VITS (Fase 2) se agrupan en palabras y grafemas (segmentados por el G2P).
2. Un mapa grafema → visema (`SUPUESTO-LING`, versionado por hash) y una coarticulación anticipatoria producen una curva lineal por tramos (`keyframes`) en cada `seg_NNN.json`.
3. El cliente evalúa esa curva en la posición estimada del audio y mueve las expresiones VRM `aa ih ou ee oh`; añade parpadeo, mirada y gestos.
4. Si no hay WebGL o los FPS son menores a 20, pasa a imagen fija con audio y texto y **registra el evento**.

```
duraciones VITS ─► tiempos por carácter canónico ─► palabras y fonemas ─► eventos ─► keyframes (seg_NNN.json)
audio.currentTime ─► AudioClock ─► VisemeTrack.sample ─► expresiones VRM ─► canvas (three-vrm, carga diferida)
```

---

## 2. Qué se implementó

| Tarea   | Componente                                                                                     | Dónde está                                                                    |
| ------- | ---------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| 3.1     | Comparativa y decisión: **three + three-vrm** (TalkingHead descartado)                         | `docs/avatar_decision.md`, `frontend/bench/`                                  |
| 3.2     | Alineación por palabra y fonema; validación contra CTC; kit de Praat                           | `backend/app/pipeline/viseme/align.py`, `eval/fase3/{alignment,ctc,praat}.py` |
| 3.3     | Mapa grafema → visema (`SUPUESTO-LING`, sha256 en cada pista)                                  | `backend/app/pipeline/viseme/resources/map.yaml`                              |
| 3.4     | Pista con coarticulación y suavizado (`NA_VISEME_SMOOTH_MS`, `NA_VISEME_LEAD`); manifiesto 1.1 | `backend/app/pipeline/viseme/track.py`, `backend/app/batch/`                  |
| 3.5     | Visor y `AvatarPanel` (Preact), reloj, parpadeo, mirada, 4 gestos, optimizador de VRM          | `frontend/src/avatar/`, `scripts/optimize_vrm.py`                             |
| 3.6     | Degradación (WebGL + sondeo de 2 s) con registro                                               | `frontend/src/avatar/{degradation,create-avatar}.ts`                          |
| 3.7     | 40 clips MP4 del avatar (split dev)                                                            | `frontend/scripts/capture.mjs`, `eval/fase3/lipsync.py`                       |
| 3.8     | Desfase directo, LSE-D/LSE-C, control negativo, peso, FPS                                      | `eval/fase3/`, `frontend/scripts/realtime.mjs`                                |
| Pruebas | 17 de visemas, 14 de evaluación, 2 de integración; 17 del cliente (vitest)                     | `backend/tests/`, `frontend/tests/`                                           |

---

## 3. Resultados

### Alineación contra el alineador forzado (3.2) — 40 oraciones de dev, 211 palabras

| Error (VITS − CTC)    | Sesgo     | MAE                              | Mediana | Dentro de 80 ms |
| --------------------- | --------- | -------------------------------- | ------- | --------------- |
| **Centro de palabra** | +8,3 ms   | **63,9 ms** (IC 95 %: 57,4–71,1) | 34 ms   | 74 %            |
| Inicio de palabra     | +109,4 ms | 110,1 ms                         | 44 ms   | 74 %            |
| Fin de palabra        | −92,8 ms  | 99,2 ms                          | 72 ms   | 55 %            |

CTC subestima el intervalo de cada sonido (sesgo de inicio y fin esperado); el centro es la medida fiable.
11 de 40 oraciones superan los 80 ms de error del centro. **Las 20 oraciones anotadas en Praat quedan pendientes** (kit listo).

### Sincronía labial (3.8) — 40 clips

| Medida                                                                             | Valor                                                                                                                                       |
| ---------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- | --- | ---------------------------- |
| **Desfase sistemático** audio-boca renderizada (estimador agrupado, plantilla CTC) | **−10,8 ms** (IC 95 %: −18,5 a −2,1; negativo = la boca va antes)                                                                           |
| Ídem, estimador agrupado de energía (comprobación)                                 | −3,3 ms (−7,5 a +0,9)                                                                                                                       |
| Precisión de esos estimadores con desplazamientos conocidos (±40, ±80 ms)          | 1,7 ms y 0,4 ms de error medio                                                                                                              |
| Desfase **por clip**                                                               | **No concluyente**: los estimadores por clip fallan 30–60 ms de media (hasta 680 ms); 19 y 27 de 40 clips dan                               | lag | > 80 ms por ruido del método |
| Error del reloj del cliente                                                        | ≤ 3,4 ms (≤ 7,5 ms con CPU 4× más lenta) en régimen; 36,6 ms en el arranque del audio                                                       |
| **Desfase total estimado**                                                         | **26 ms en régimen, 55 ms con el arranque** (peor cota del IC + error del reloj). No incluye la latencia de salida de audio del dispositivo |
| LSE-D / LSE-C (SyncNet)                                                            | 11,78 / 0,76                                                                                                                                |
| Control negativo (audio de otro clip)                                              | 11,77 / 0,76 → **SyncNet no discrimina** con este avatar                                                                                    |

### Rendimiento y peso del cliente

| Medida                                                          | Valor                                                              |
| --------------------------------------------------------------- | ------------------------------------------------------------------ |
| FPS, Chromium con GPU (RTX 3060 Ti), 360 px                     | **60** (dibujo p95 2,7 ms)                                         |
| FPS con la CPU 4× más lenta (misma GPU)                         | **60** (dibujo p95 5,2 ms)                                         |
| FPS sin GPU (SwiftShader)                                       | 18,2; con CPU 4× más lenta, 16,6 → se degrada a imagen fija (< 20) |
| Paquete inicial del visor (gzip)                                | **11,7 KB** (< 3 MB)                                               |
| Avatar de carga diferida: three + GLTFLoader + three-vrm (gzip) | 224,5 KB                                                           |
| Modelo VRM provisional                                          | 2,41 MB (la meta del modelo final es ≤ 2 MB)                       |
| Inicial + avatar + VRM                                          | < 3 MB                                                             |
| Pista de visemas por oración                                    | 8 KB (99 keyframes, 51 eventos); `seg_NNN.json` completo: 17 KB    |

### Degradación (3.6) — Chromium real

| Caso                 | Resultado                                                  |
| -------------------- | ---------------------------------------------------------- |
| Sin WebGL            | imagen fija, evento `sin-webgl`, audio y texto disponibles |
| CPU 20× más lenta    | imagen fija, evento `fps-bajos` (0,4 FPS)                  |
| Condiciones normales | avatar, evento `avatar-ok`                                 |

### Decisión de la librería (3.1)

three + three-vrm: bundle de 196 KB gzip (TalkingHead, 226 KB), compatible de forma nativa con el VRM de VRoid
(TalkingHead exige morph targets ARKit/Oculus) y con control total del reloj. **No se midieron los FPS ni el
desfase de TalkingHead**: no carga el modelo sin convertirlo. Detalle en `docs/avatar_decision.md`.

---

## 4. Cómo se usa

Comandos en Git Bash dentro de `Proyecto/noticias-ashaninka`.

```bash
uv run python -m app.batch build --news 1        # regenera seg_NNN.json con alignment y visemes
uv run uvicorn app.main:app                      # backend en :8000
cd frontend && npm install && npm run dev        # visor: http://localhost:5173/visor.html?news=1
npm test && npm run typecheck && npm run build
```

Modelo VRM provisional: ver `frontend/README.md` (no se versiona). Evaluación completa:

```bash
uv run python -m eval.fase3.prepare              # 150 oraciones de dev -> 40 elegidas (eval/fase3/out/)
uv run python -m eval.fase3.alignment            # 3.2
node frontend/scripts/capture.mjs eval/fase3/out/selection.json eval/fase3/out/capture
uv run python -m eval.fase3.lipsync              # 3.7-3.8
node frontend/scripts/realtime.mjs eval/fase3/out/selection.json eval/fase3/out/cliente_gpu_x1.json gpu 1 8
node frontend/scripts/degradation.mjs eval/fase3/out/degradacion.json
uv run python -m eval.fase3.run                  # -> eval/results/fase_3.json
```

---

## 5. Criterios de cierre

| Criterio                                                                | Estado                                                                                                                                                                       |
| ----------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| LSE-D y LSE-C reportados sobre ≥ 30 clips                               | **Cumple** (40 clips). Con la salvedad de que el control negativo muestra que no discriminan                                                                                 |
| Desfase máximo medido ≤ 80 ms                                           | **Cumple en el sistemático** (peor cota 18,5 ms; total 26–55 ms con el reloj). **Por clip: no verificable** con este método (ver §3)                                         |
| Limitación de SyncNet con un avatar estilizado en `docs/limitations.md` | **Cumple** (punto 29)                                                                                                                                                        |
| Paquete inicial < 3 MB                                                  | **Cumple** (11,7 KB gzip; con el avatar y el VRM, < 3 MB)                                                                                                                    |
| 60 FPS                                                                  | **Cumple con GPU** (60, también con la CPU 4× más lenta). **No sin GPU** (17–18). No verificado en un Android de gama media                                                  |
| Alineación validada contra el alineador de MMS                          | **Cumple** (centro de palabra: 63,9 ms de error medio)                                                                                                                       |
| Alineación validada contra 20 oraciones anotadas a mano en Praat        | **Pendiente** (requiere a una persona; kit listo)                                                                                                                            |
| Degradación probada y con registro del evento                           | **Cumple**                                                                                                                                                                   |
| Pruebas y lint                                                          | **Cumple**: 122 pruebas de Python pasan y 1 se omite por diseño (solo corre sin eSpeak-NG instalado), cobertura 97 %; 17 pruebas de vitest; `ruff check`, `ruff format --check` y `tsc` sin errores |

## 6. Pendientes que se arrastran

| Pendiente                              | Impacto                                                                       | Acción                                                                                    |
| -------------------------------------- | ----------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| **Anotación en Praat de 20 oraciones** | Sin referencia humana de la alineación                                        | Una persona anota `eval/fase3/praat/` y se ejecuta `python -m eval.fase3.praat comparar`  |
| **P1** (alfabeto/fonemas)              | El mapa de visemas es una hipótesis (`SUPUESTO-LING`)                         | Lingüista o docente EIB; validar o corregir `map.yaml`                                    |
| **Presentadora final** (VRoid)         | El modelo es provisional y pesa 2,41 MB (meta ≤ 2 MB); no hay clips de Mixamo | Pista paralela de diseño; `Gestures.register()` admite clips retargeteados                |
| **Dispositivo Android de gama media**  | Los FPS y el reloj son del equipo de desarrollo                               | Medir en la Fase 4 (criterio de cierre)                                                   |
| **Latencia de salida de audio**        | El desfase total no la incluye                                                | Medir con hardware; usar `AudioClock.latencyMs`                                           |
| **Verificación del desfase por clip**  | El método de correlación no la permite                                        | Anotación manual o captura de pantalla con audio real                                     |

Las limitaciones completas están en `docs/limitations.md` (puntos 26 a 35, nuevos en esta fase).
