# Resumen de la Fase 5: instrumentación del experimento intra-sujeto C1–C4

> **Proyecto:** Servicio web de noticias en lengua asháninka con síntesis de voz, texto y avatar
> **Fecha:** 2026-10-12 · **Repositorio:** `Proyecto` (código en `noticias-ashaninka/`) · **Rama:** `feat/fase5-experimento` · **Base:** Fase 4 (aprobada el 2026-10-12)
> **Estado:** implementada y verificada de punta a punta con una **simulación sintética**; **pendiente de aprobación**. Todo lo que requiere personas (consentimiento del comité, ítems de comprensión de un hablante, noticias revisadas, piloto con participantes, pruebas de escucha) sigue **pendiente** y no se inventó.

Las cifras vienen de ejecuciones reales (`eval/results/fase_5.json`, `eval/fase5/out/`). El diseño y el plan de análisis se escribieron **antes** de medir, en `docs/metrics.md` (sección «Fase 5» y su revisión fechada del 2026-10-12, también previa a la ejecución).

**Qué NO demuestra esta fase.** Los participantes son **sintéticos** y están marcados como piloto: la simulación prueba que la asignación, el registro, la exportación y el análisis son correctos (recuperan efectos verdaderos conocidos), **no** que C3 o C4 mejoren la comprensión. Hoy no hay ninguna noticia apta (todas son pseudo-noticias del corpus sin revisión de un hablante, P4).

---

## 1. Qué hace el sistema hoy

```
#/experimento ── código anónimo + consentimiento ── POST /api/experiment/sessions (Williams + noticias)
   ├─ bloque k (k = 0..3): la noticia en la condición asignada ── eventos block-start/block-end
   │     C1 «Terminé de leer» · C2/C3/C4 termina el audio · «Continuar»
   ├─ cuestionario k: comprensión (0/1, marcada por un entrevistador) + esfuerzo (Paas 1–9) + 3 ítems de aceptabilidad
   ├─ cuestionario final: variante, edad por rango, alfabetización, familiaridad, ranking C1–C4, comentario
   └─ fin: envía lo pendiente y cierra la sesión ── exportación CSV/JSON/Parquet ── análisis (eval/fase5)
```

- **Asignación.** Williams 4×4 (`C1 C2 C4 C3 / C2 C3 C1 C4 / C3 C4 C2 C1 / C4 C1 C3 C2`) con rotación de noticias, calculada del código (`P007` → participante 6). Cada transición ordenada A→B aparece una sola vez; en ciclos de 16 participantes, condición×posición, condición×noticia y noticia×posición aparecen 4 veces cada par (comprobado con 16, 32 y 48).
- **Sin cambio libre de condición.** Con la sesión activa solo existe la ruta de la fase actual: ni el selector, ni `?c=`, ni la lista, ni los ajustes permiten salir.
- **Material.** Las 4 noticias se fijan una vez y las comparten todos. Se prefieren las **sin segmentos bloqueados** (limitación 42); si faltan, se completan y se registra `bloqueados_prop` como covariable. En modo real exige noticias revisadas (P4); `NA_EXPERIMENT_PILOTO=true` admite pseudo-noticias y marca **todo** como piloto, y los datos piloto nunca entran en el análisis confirmatorio.
- **Persistencia e idempotencia.** Estado y respuestas en IndexedDB (la sesión se reanuda al recargar), envío por lotes con `response_id` UUID; reenviar no duplica. Una respuesta rechazada por el servidor se aísla sin bloquear las demás.
- **Privacidad.** Solo un código anónimo y el UUID del dispositivo (que **no** se exporta); edad por rangos; comentario rechazado si parece traer un correo, enlace, teléfono o documento; la exportación se verifica antes de escribirse.

## 2. Qué se implementó

| Tarea              | Componente                                                                                               | Dónde está                                                           |
| ------------------ | -------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- | ----------- |
| 5.1                | Pantalla de consentimiento con marcadores `PENDIENTE-COMITE-ETICA` (texto y audio en asháninka)          | `components/ExperimentFlow.tsx`                                      |
| 5.2                | Williams 4×4 + rotación, selector de las 4 noticias                                                      | `backend/app/experiment/latin.py`, `pool.py`                         |
| 5.3                | Sesiones, bloques, eventos nuevos, tiempos, repeticiones, pausas, abandono y degradación del avatar      | `api/experiment.py`, `api/events.py`, `export.py`                    |
| 5.4                | Cuestionarios (definidos en YAML con estado por ítem)                                                    | `resources/questionnaire.yaml`, `instrumentos.py`                    |
| 5.5                | Verificación de privacidad con control negativo                                                          | `privacy.py`                                                         |
| 5.6                | CSV + JSON + Parquet, `manifest.json` con hashes, `data/DATA_DICTIONARY.md` generado                     | `export.py`, CLI `experiment export                                  | dictionary` |
| 5.7 (análisis)     | Simulación por la API real, modelo mixto, no paramétricos, bootstrap, sensibilidad, potencia y cobertura | `eval/fase5/`                                                        |
| 5.7 (escucha), 5.8 | Inteligibilidad, MOS y piloto con personas                                                               | **Pendientes** (requieren personas)                                  |
| PWA                | IndexedDB v2, controlador, guardia de rutas, cola de respuestas                                          | `frontend/src/app/{db,experiment}.ts`                                |
| Pruebas            | 43 + 9 de Python, 24 de vitest, 3 E2E                                                                    | `backend/tests`, `frontend/tests`, `frontend/e2e/experiment.spec.ts` |

## 3. Resultados de la simulación (32 participantes sintéticos, semilla 20261012)

Todo pasó por los endpoints reales: 32 sesiones (31 completas, 1 abandono), 811 eventos y 155 respuestas, cada lote **reenviado una vez**.

| Criterio                          | Resultado                                                                                                                                      |
| --------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| Balance del cuadrado (16, 32, 48) | **Cumple** (los 4 balances exactos)                                                                                                            |
| Idempotencia                      | **Cumple**: 0 eventos y 0 respuestas nuevas al reenviar; crear la sesión dos veces devuelve la misma asignación                                |
| Exportación                       | **Cumple**: 32 sesiones, 128 bloques, 1 240 respuestas, 811 eventos; **0 de 124 bloques visitados** con valores distintos a la verdad simulada |
| Tiempos exportados                | **Cumple**: diferencia máxima de 3 ms en `t_escucha_ms` y 1 ms en `t_pantalla_ms` (tolerancia 5 ms)                                            |
| Privacidad                        | **Cumple**: 0 problemas; el verificador detecta un correo y un teléfono inyectados                                                             |
| Diccionario de datos              | **Cumple**: 53 de 53 columnas, y el archivo coincide con el generado                                                                           |
| Carga inicial de la PWA           | **Cumple**: 0,024 MB gzip (< 3 MB); el Service Worker no precarga el avatar                                                                    |

### Análisis (31 participantes analizados; P013 excluido por abandono)

Modelo mixto de la comprensión (REML, condición + posición + noticia + alfabetización, intercepto por participante), contrastes con Holm:

| Contraste | Verdadero | Estimado | IC 95 %         | p (Holm) |
| --------- | --------- | -------- | --------------- | -------- |
| C2 − C1   | 0,05      | 0,125    | [0,005; 0,245]  | 0,083    |
| C3 − C2   | 0,10      | 0,137    | [0,017; 0,257]  | 0,077    |
| C4 − C3   | 0,02      | −0,095   | [−0,215; 0,025] | 0,122    |

- **Recuperación:** los 3 efectos verdaderos caen dentro del IC 95 % del ajuste único (sin reajustar la semilla). Con **200 réplicas** de 32 participantes la cobertura del IC 95 % es de **0,945, 0,945 y 0,955** (nominal 0,95) y el sesgo medio es de −0,002, 0,001 y −0,001: el método es insesgado, pero **una sola muestra de 32 es ruidosa** (el C4 − C3 salió con signo contrario al verdadero y aun así dentro del IC).
- **No paramétricos** (Friedman, 4 condiciones): comprensión p = 0,0013, esfuerzo p = 0,0019, aceptabilidad p < 0,001. Wilcoxon por pares con Holm: solo C3 − C2 en aceptabilidad (p = 0,006, r = 0,55) es significativo.
- **Bootstrap** (B = 2 000, participantes): C3 − C2 en comprensión 0,137 [0,024; 0,250]; C2 − C1 en esfuerzo −0,58 [−1,03; −0,13].
- **Sensibilidad:** sin el único bloque C4 degradado y con la noticia como componente de varianza los contrastes cambian menos de 0,005.
- **Potencia** (d = 0,5 de C3 sobre C1, SD de un bloque 0,262, diferencia 0,131; 200 réplicas por N): 0,415 con 16, 0,575 con 32, 0,69 con 48, **0,865 con 64** y 0,935 con 96. **N mínimo para 0,80: 64 participantes.** Con los 32 de una primera tanda la potencia es de apenas 0,575 (limitación 57).

### Pruebas y calidad

| Comprobación                          | Resultado                                                                                                                                                  |
| ------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `uv run pytest`                       | **191 pasaron**, 1 omitida por diseño, 0 fallos                                                                                                            |
| `ruff check` y `ruff format --check`  | **0 errores**                                                                                                                                              |
| `npm test` (vitest)                   | **65 de 65** (24 nuevas)                                                                                                                                   |
| `npm run typecheck` / `npm run build` | **0 errores**                                                                                                                                              |
| `npm run e2e` (Chromium real)         | **21 de 21** (3 nuevas: sesión completa con exportación y sin conexión, abandono, consentimiento y código ya usado; axe sin violaciones críticas o graves) |

## 4. Cómo se usa

Comandos en Git Bash dentro de `Proyecto/noticias-ashaninka`.

```bash
(cd frontend && npm install && npm run build)
NA_EXPERIMENT_PILOTO=true uv run uvicorn app.main:app      # abrir http://127.0.0.1:8000/#/experimento
uv run python -m app.cli experiment export --out data/export [--incluir-piloto] [--format csv,json,parquet]
uv run python -m app.cli experiment dictionary             # regenera data/DATA_DICTIONARY.md
uv run python -m eval.fase5.analysis data/export           # análisis con datos reales (no incluye el piloto)
uv run python -m eval.fase5.run                            # simulación + análisis + criterios (~4 min) -> fase_5.json
(cd frontend && npm test && npm run e2e)                   # E2E con servidor propio --experimento
```

## 5. Criterios de cierre

| Criterio                                                            | Estado                                                                                      |
| ------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| El piloto completo se exporta a CSV sin errores                     | **Cumple con la simulación sintética**; el piloto con 2–3 personas (5.8) está **pendiente** |
| El diccionario de datos cubre el 100 % de las columnas              | **Cumple** (53 de 53)                                                                       |
| La prueba de privacidad pasa                                        | **Cumple** (con control negativo)                                                           |
| Cuadrado de Williams balanceado y asignación determinista           | **Cumple**                                                                                  |
| Flujo completo C1–C4 + cuestionarios + exportación en Chromium real | **Cumple** (E2E)                                                                            |
| Pipeline de análisis reproducible que recupera efectos conocidos    | **Cumple** (cobertura 0,945–0,955)                                                          |
| Carga inicial < 3 MB                                                | **Cumple** (0,024 MB)                                                                       |
| Consentimiento aprobado por el comité, con audio en asháninka (5.1) | **Pendiente** (marcador)                                                                    |
| Ítems de comprensión redactados por un hablante, oral (5.4)         | **Pendiente** (marcador)                                                                    |
| ≥ 8 noticias revisadas por un hablante (P4)                         | **Pendiente**: sin ellas el modo real no inicia                                             |
| Guiones de escucha: inteligibilidad y MOS (5.7)                     | **Pendiente** (requiere personas)                                                           |

## 6. Pendientes que se arrastran

| Pendiente                                                    | Impacto                                                   | Acción                                        |
| ------------------------------------------------------------ | --------------------------------------------------------- | --------------------------------------------- |
| **Texto del consentimiento y su audio**                      | La pantalla muestra un marcador                           | Comité de ética + hablante que grabe el audio |
| **Ítems de comprensión y sus claves**                        | Sin ellos no hay variable de comprensión real             | Hablante, con modalidad oral                  |
| **Noticias revisadas (P4)**                                  | El experimento real no puede arrancar                     | ≥ 8 noticias, revisadas por un hablante       |
| **Piloto con 2–3 personas (5.8)** y **escucha (5.7)**        | No hay datos reales ni de MOS                             | Reclutar participantes y un hablante          |
| **Interfaz en asháninka**, **Android físico**, **VRM final** | Heredados de la Fase 4                                    | Hablante, dispositivo, pista de VRoid         |
| **P1, P2a–P2d, P5, Praat**                                   | Heredados de las Fases 1 a 3                              | Lingüista, hablantes, compañera               |
| **Fase 6**                                                   | Despliegue: Docker, HTTPS, proteger `/api/events/summary` | Pendiente de iniciar                          |

Las limitaciones completas están en `docs/limitations.md` (puntos 46 a 58, nuevos en esta fase).
