# PROMPT: Fase 4 de la integración. Medición ortográfica, documentación y cierre

> Copia todo lo que está debajo de la línea en una sesión de Claude Code abierta en
> `C:\Users\Marco\Downloads\proyecto-ashaninka\proyecto-ashaninka`.
> Documentos que hay que leer antes: `MejoraEIntegracion/PLAN_INTEGRACION.md`, los
> `RESUMEN_FASE1..3.md`, `CLAUDE.md`, `PLAN_DESARROLLO.md` (§2, §3 P7 y §3.2) y
> `noticias-ashaninka/docs/metrics.md`.

---

# ROL

Actúa como ingeniero de investigación responsable de la reproducibilidad. Vas a **medir** cómo se
comporta el texto que produce BiTAM al pasar por el pipeline (normalización, adaptador MMS y TTS),
a documentar la integración para la tesis y a cerrar el trabajo con la verificación completa.

# CONTEXTO

- BiTAM devuelve texto en ortografía MINEDU 2024, en minúsculas, sin tildes y con las vocales dobles
  colapsadas. La Fase 2 restaura las mayúsculas de forma determinista.
- Regla del proyecto: **se definen las métricas antes de medir** (`docs/metrics.md`) y **nunca se
  usa el split test**. El test oficial de AmericasNLP es además el que usó BiTAM para evaluarse.
- La calidad de la traducción **no** se evalúa en esta tesis (contrato §2): solo se mide la
  compatibilidad con el pipeline.

# TAREAS

1. Escribir antes de ejecutar nada la sección «Integración BiTAM» en `docs/metrics.md`, con estas métricas:
   - porcentaje de segmentos bloqueados (sin `text_tts`);
   - porcentaje de palabras con letras ajenas al alfabeto nativo;
   - nombres propios detectados por `classify` antes y después de restaurar las mayúsculas;
   - número de vocales dobles en la salida frente a la referencia cni del **dev**;
   - latencia por oración (media, p50 y p95) y por noticia.
2. `eval/traductor/run.py` (módulo; el entorno del backend llama al servicio por HTTP):
   - toma N oraciones del split **dev** en castellano de `data/corpus/` (semilla fija, declarada en `docs/metrics.md`);
   - las traduce con el servicio de la Fase 1;
   - aplica `traducir_noticia` y `Pipeline.process_text`;
   - escribe `eval/results/traductor.json` con las métricas, las versiones (`/salud`), la semilla y la fecha.
3. Documentación:
   - `noticias-ashaninka/docs/translation.md` (nuevo): arquitectura, instalación del servicio,
     variables, límites, ortografía de salida, restauración de mayúsculas, limitaciones y cómo se cita BiTAM.
   - `PLAN_DESARROLLO.md` §3: P7 pasa a «Resuelto: MINEDU 2024, minúsculas, sin tildes, VV
     colapsadas (salvo la lista blanca)», con referencia a `traductor.json`.
   - `noticias-ashaninka/docs/limitations.md`: borrador automático (chrF++ ≈ 25), pérdida de
     mayúsculas, servicio local con GPU y Docker sin traductor.
   - `noticias-ashaninka/LICENSES.md`: NLLB-200 (CC BY-NC 4.0) y BiTAM (código MIT, pesos no redistribuibles).
   - `noticias-ashaninka/CITATION.md`: la tesis BiTAM y NLLB Team (2022).
   - `noticias-ashaninka/docs/pwa.md`: la Redacción con traducción.
   - `CLAUDE.md`: una línea en *Architecture* sobre `translation/` y el servicio `traductor/`.
   - `docker-compose.yml`: **no** se modifica. Solo se documenta por qué el traductor queda fuera.
4. Regenerar lo que es generado y no editar a mano: `uv run python -m eval.fase6.architecture` si
   aplica, y `build-docs`.

# PRUEBAS OBLIGATORIAS (criterio de cierre)

| # | Prueba | Resultado esperado |
|---|---|---|
| 1 | `uv run python -m eval.traductor.run` con el servicio encendido | `eval/results/traductor.json` creado, con todas las métricas declaradas |
| 2 | Comprobar que el script **rechaza** el split test (prueba unitaria) | Lanza un error si se le pide `test` |
| 3 | `scripts/verify.sh` (con E2E) | Todo en verde: ruff, pytest, vitest, tipos, build, E2E y `fase_6.json` |
| 4 | `uv run pytest traductor/tests` (servicio, con el traductor falso) | Verde |
| 5 | Recorrido completo real: Redacción → traducir una noticia de 3 párrafos → publicar → `build` → abrir en C1, C2, C3 y C4 | Funciona. Se anotan los segmentos bloqueados y la duración total |
| 6 | `git status` / `git diff --stat` | Sin pesos, `.venv` ni secretos. Solo los archivos previstos |

# RESTRICCIONES

- No ajustar nada para «mejorar» las métricas sobre el dev después de verlas. Lo que salga se
  reporta tal cual.
- Si el colapso de vocales dobles afecta a la pronunciación, se anota como pendiente lingüístico
  (P1) y no se corrige con reglas inventadas.
- Hacer commit solo si el usuario lo pide, en la rama `mejora`, con el mensaje en español.

# AL TERMINAR

Escribe `MejoraEIntegracion/RESUMEN_FASE4.md` con:

1. Qué se hizo.
2. Archivos.
3. La salida real de las pruebas.
4. La tabla de métricas de `traductor.json`.
5. El resultado del recorrido completo.
6. El estado final de P7.
7. Los pendientes para la tesis.

Después marca la Fase 4 y el plan completo como **Culminados** en el `README.md` de la carpeta.
