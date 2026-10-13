# Avatar, alineación y visemas (Fase 3)

Resultados reales en `eval/results/fase_3.json` (y `fase_3_*.json`). Definiciones de las métricas
en `docs/metrics.md`; decisión de la librería en `docs/avatar_decision.md`; formato de los datos en
`docs/manifest_schema.md`.

```
duraciones de VITS ─► canonical_times ─► alignment (palabras y fonemas, G2P) ─► visemes (eventos y keyframes)
        seg_NNN.json ──────────────────────────────────────────────────────────────┐
        audio.currentTime ─► AudioClock ─► VisemeTrack.sample(t) ─► expresiones VRM ─► canvas
```

## Backend (`backend/app/pipeline/viseme/`)

| Módulo | Qué hace | Tarea |
|---|---|---|
| `align.py` | Agrupa los tiempos por carácter canónico en palabras y fonemas (la segmentación grafémica es la del G2P) | 3.2 |
| `resources/map.yaml` | Mapa grafema → visema con pesos, **todo `SUPUESTO-LING`** (pendiente de P1). Versionado por hash: el sha256 viaja en cada pista y en el manifiesto | 3.3 |
| `track.py` | Eventos contiguos, coarticulación anticipatoria, transiciones de `smooth_ms` con `lead` y `keyframes` lineales | 3.4 |

Canales: `A I U E O` (vocales) y `C` (cierre labial de `p m b`); las demás consonantes son neutras con
una fracción de la vocal siguiente (coarticulación). Parámetros: `NA_VISEME_SMOOTH_MS` (50 por
defecto, el plan pide 40–60) y `NA_VISEME_LEAD` (0,5). El mapa no tiene datos validados de
asháninka: es una hipótesis articulatoria genérica, y cada entrada lo dice.

`app.batch build` escribe `alignment` y `visemes` en cada `seg_NNN.json`; el manifiesto sube a la versión
1.1 (campo `visemes` con la trazabilidad; los manifiestos 1.0 siguen siendo válidos). Una pista
típica pesa 8 KB (99 keyframes, 51 eventos, 47 fonemas) y el `seg_NNN.json` completo, 17 KB.

## Cliente (`frontend/src/avatar/`)

| Módulo | Qué hace |
|---|---|
| `viseme-track.ts` | Evalúa los keyframes (misma regla que `track.sample` de Python) y traduce canales a expresiones VRM |
| `clock.ts` | `AudioClock`: estima la posición del audio entre los saltos de `currentTime` con un filtro de máximo; monótono; no extrapola antes de que el audio arranque |
| `idle.ts` | Parpadeo (2–6 s), mirada sutil y 4 gestos procedurales (reposo hablando, saludo de apertura, asentir y despedida) como deltas acotados sobre la pose de reposo (`POSE_LIMITS`/`limitPose`): brazos siempre abajo (≤ 0,06 rad) y cabeza/torso sutiles, nunca hacia atrás |
| `viewer.ts` | `AvatarViewer`: three y three-vrm con **carga diferida**, encuadre, `renderAt(t)` determinista |
| `degradation.ts`, `create-avatar.ts` | Sondeo de FPS de 2 s y detección de WebGL; si FPS < 20 o no hay WebGL se muestra una imagen fija y se **registra el evento** (`window.__avatarEvents`) |
| `AvatarPanel.tsx` | Componente Preact listo para la condición C4 de la Fase 4 |
| `measure.ts` | Apertura de la boca renderizada a partir de los píxeles (para 3.8) |

Cómo ejecutarlo: `frontend/README.md`.

## Resultados (dev, 40 oraciones de 2–12 s, `mms_vits` H1; equipo de desarrollo)

### Alineación contra el alineador forzado (3.2)

Referencia: alineación CTC de `mms-1b-all` (adaptador `cni`) sobre el mismo Opus. 211 palabras.

| Error (VITS − CTC) | Sesgo | MAE | Mediana | Dentro de 50 ms | Dentro de 80 ms |
|---|---|---|---|---|---|
| **Centro de palabra** | +8,3 ms | **63,9 ms** (IC 95 %: 57,4–71,1) | 34,0 ms | 64 % | 74 % |
| Inicio de palabra | +109,4 ms | 110,1 ms | 44,0 ms | 56 % | 74 % |
| Fin de palabra | −92,8 ms | 99,2 ms | 72,0 ms | 37 % | 55 % |

El sesgo de inicio y fin es el esperado de CTC (intervalos interiores al sonido, ver
`eval/fase3/ctc.py`); el **centro** es la medida fiable: la mitad de las palabras queda a menos de 34 ms.
El p90 es de 180 ms: hay oraciones con error alto (11 de 40 superan los 80 ms de MAE del centro,
con un máximo de 142 ms) que no se investigaron una a una; no se sabe cuánto de ese error es de CTC
y cuánto de las duraciones de VITS. **La anotación manual en Praat (20 oraciones) está pendiente**: hace falta una
persona. El kit está listo en `eval/fase3/praat/` y `python -m eval.fase3.praat comparar` calcula el
error cuando existan los TextGrid anotados.

### Sincronía labial (3.8)

- **Desfase sistemático audio-boca renderizada: −10,8 ms** (IC 95 %: −18,5 a −2,1; negativo = la boca va
  un poco *antes* que el audio, como corresponde a la anticipación visual), con 40 clips y el estimador
  agrupado de plantilla CTC. El estimador agrupado de energía lo confirma: −3,3 ms (−7,5 a +0,9).
  Ambos siguen desplazamientos conocidos de ±40 y ±80 ms con un error de 1,7 ms (plantilla) y 0,4 ms (energía).
- **Por clip no se puede concluir.** Los estimadores por clip fallan al seguir los desplazamientos
  conocidos (MAE de 30 y 60 ms, hasta 680 ms), y 19 de 40 clips (energía) o 27 de 40 (plantilla) dan
  |lag| > 80 ms. Eso es ruido del método (correlación baja, ambigüedad del periodo silábico), no
  un desfase demostrado: el motivo y la calibración están en `docs/metrics.md`. Cumplir el criterio «máximo
  por clip ≤ 80 ms» **no es verificable** con este método.
- **Error del reloj del cliente** (Chromium con GPU, CPU normal y 4× más lenta): **≤ 3,4 ms y ≤ 7,5 ms en
  régimen**; 36,6 ms como máximo en el arranque del audio (primeros 0,5 s, cuando `currentTime` aún avanza
  a saltos irregulares).
- **Desfase total estimado:** 18,5 ms (peor cota del IC) + 7,5 ms = **26 ms en régimen**, 55 ms contando
  el arranque. Cumple ≤ 80 ms. **No incluye la latencia de salida de audio del dispositivo.**
- **SyncNet (LSE-D / LSE-C), 40 clips:** LSE-D 11,78 y LSE-C 0,76 de media. El **control negativo** (audio de otro clip) da
  11,77 y 0,76: **idéntico**. SyncNet **no discrimina** entre el audio correcto y uno ajeno con este avatar
  estilizado (riesgo R8 del plan, confirmado). Los valores se reportan por exigencia del criterio de
  cierre, pero no son evidencia de sincronía. Detalle en `docs/limitations.md`.

### FPS y peso (3.5, 3.6)

| Configuración | FPS medios | Observación |
|---|---|---|
| Chromium + GPU (RTX 3060 Ti, ANGLE/D3D11), 360 px | **60** | 8 clips; dibujo p95 de 2,7 ms |
| ídem con CPU 4× más lenta | **60** (59,9 mín.) | dibujo p95 de 5,2 ms |
| Sin GPU (SwiftShader), CPU normal | 18,2 | por debajo del umbral de 20: el avatar se degrada |
| Sin GPU, CPU 4× más lenta | 16,6 | ídem; error del reloj de hasta 104 ms |

**No es un Android de gama media.** Son las cifras del equipo de desarrollo; la verificación en un
dispositivo real sigue pendiente (criterio de cierre de la Fase 4). Con GPU hay holgura de sobra para
60 FPS; sin aceleración gráfica la degradación a imagen fija entra, como está diseñado.

| Peso | Valor |
|---|---|
| Paquete inicial del visor (gzip) | **11,7 KB** (< 3 MB) |
| Avatar diferido: three + GLTFLoader + three-vrm (gzip) | 224,5 KB |
| Modelo VRM provisional | 2,41 MB (meta del modelo final: ≤ 2 MB, **no cumplida** por el provisional) |
| Todo junto (inicial + avatar + VRM) | < 3 MB |

### Degradación (3.6)

Probada en Chromium real (`frontend/scripts/degradation.mjs`): **sin WebGL** → imagen fija, evento
`sin-webgl`, audio y texto disponibles; **CPU 20× más lenta** → evento `fps-bajos` (0,4 FPS) e imagen
fija; **condiciones normales** → avatar y evento `avatar-ok`. El sondeo de 2 s es conservador: mide
también la carga inicial (38,7 FPS en el equipo de desarrollo, que luego da 60).

## Qué NO hace esta fase (y por qué)

- **Mixamo:** no se descargaron clips (cuenta de Adobe y términos por descarga); hay 4 gestos procedurales.
- **Presentadora final:** el modelo es provisional (VRM1 de ejemplo de pixiv, redistribución permitida,
  reducido de 10,8 a 2,4 MB con `scripts/optimize_vrm.py`). El diseño propio con VRoid sigue en la pista paralela.
- **Visemas validados:** el mapa es `SUPUESTO-LING` hasta resolver P1.
- **Praat:** solo el kit; las 20 anotaciones las tiene que hacer una persona.
- **eSpeak-NG:** sigue sin instalar (requiere confirmación de administrador); no afecta a esta fase.
