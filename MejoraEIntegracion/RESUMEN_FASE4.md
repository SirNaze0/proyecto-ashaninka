# Resumen de la Fase 4: medición ortográfica, documentación y cierre

> **Estado:** culminada el 2026-11-02 · **Rama:** `mejora`
> **Prompt:** `PROMPT_FASE4.md` · Con esta fase **se completa el plan de integración** (4 de 4).

## 1. Qué se hizo

- **Métricas definidas antes de medir** en `docs/metrics.md` (sección «Integración del traductor
  BiTAM»):
  - muestra: N = 100 del **dev**, semilla 13;
  - métricas: latencia, segmentos bloqueados, letras ajenas, nombres propios (candidatos, copiados,
    detectados por `classify` antes y después) y vocales dobles;
  - reglas: una sola ejecución, nada se ajusta después y sin otra carga;
  - limitaciones declaradas de antemano.
- **`eval/traductor/run.py`** (`uv run python -m eval.traductor.run --corpus DIR`):
  - rechaza cualquier split que no sea `dev` y verifica el SHA-256 del corpus;
  - no guarda texto del corpus, solo números de línea, recuentos y hashes;
  - escribe `eval/results/traductor.json`;
  - tiene 7 pruebas unitarias (`test_traductor_eval.py`, marcadas `smoke`).
- **Recorrido completo real** en Chromium (Playwright) sobre la interfaz: Redacción → traducir
  con BiTAM en GPU → revisar → publicar con la **voz MMS real** → C1, C2, C3 y C4 hasta «Fin de la noticia».
- Se descargó la voz `mms-tts-cni` con `scripts/verify_models.py --descargar --solo-servicio`
  (145 MB, revisión fijada, **SHA-256 OK** contra `models.lock.json`). Es el paso estándar de `init.sh --with-tts`.
- **Documentación:**
  - `docs/translation.md` (nuevo): flujo, arquitectura, configuración, API, P7, restauración de mayúsculas, mediciones, licencia y cita.
  - `docs/limitations.md`: limitaciones 70 a 76.
  - `docs/pwa.md`: la Redacción con traducción y el diagrama de rutas.
  - `LICENSES.md`: BiTAM, NLLB-200 y el entorno del traductor.
  - `CITATION.md`: NLLB Team (2022) y la tesis BiTAM.
  - `PLAN_DESARROLLO.md`: **P7 resuelto**.
  - `CLAUDE.md`: comandos y arquitectura.
- **Calidad:**
  - `traductor/` entra en los hooks de pre-commit (ruff y ruff format) y `traductor/run.sh` en shellcheck;
  - `scripts/verify.sh` ejecuta ruff sobre `traductor/` y sus pruebas (motor falso) si el entorno está instalado.
- `docker-compose.yml` **no se modificó**, como estaba planeado. Por qué el traductor queda fuera de Docker se explica en `docs/translation.md`, `docs/deployment.md` y `.env.production.example`.

## 2. Archivos

| Archivo | Tipo |
|---|---|
| `eval/traductor/__init__.py`, `run.py` | nuevo |
| `eval/results/traductor.json` | nuevo: resultados (sin texto del corpus) |
| `backend/tests/unit/test_traductor_eval.py` | nuevo: 7 pruebas (split, hash, auxiliares) |
| `docs/translation.md` | nuevo |
| `docs/metrics.md`, `docs/limitations.md`, `docs/pwa.md` | modificado |
| `LICENSES.md`, `CITATION.md` | modificado |
| `scripts/verify.sh`, `.pre-commit-config.yaml` (raíz) | modificado: `traductor/` en lint, shellcheck y pruebas |
| `PLAN_DESARROLLO.md`, `CLAUDE.md` (raíz) | modificado: P7 resuelto, comandos y arquitectura |

## 3. Pruebas obligatorias (salida real)

| # | Prueba | Resultado | Estado |
|---|---|---|---|
| 1 | `uv run python -m eval.traductor.run` con el servicio encendido | `eval/results/traductor.json` con todas las métricas declaradas (§4) | ✅ |
| 2 | El script rechaza el split test | `test_rechaza_cualquier_split_que_no_sea_dev[test/train/TEST]` y hash distinto → error: `7 passed` | ✅ |
| 3 | `scripts/verify.sh` | Ruff y formato OK (164 archivos). pytest: **363 passed, 9 skipped, 1 failed**. El fallo es el de siempre, **anterior y ajeno**: `test_dockerignore_deja_pasar…` exige el VRM ausente. Como `verify.sh` usa `set -e`, se detuvo ahí, así que el resto de sus pasos se ejecutó a mano con los mismos comandos: traductor `15 passed`, vitest `105 passed (9 archivos)`, `tsc` limpio, `npm run e2e` **`41 passed, 4 skipped`** (avatar, VRM ausente). `eval.fase6.run` **no** se ejecutó a propósito: reescribiría `fase_6.json`, que es el registro de la Fase 6 | ⚠️ (solo por el VRM) |
| 4 | `uv run pytest traductor/tests` (motor falso) | `15 passed` | ✅ |
| 5 | Recorrido completo real (§5) | Funciona de punta a punta. 0 segmentos bloqueados | ✅ |
| 6 | `git status` | Solo código, documentación y `traductor.json`. `models/`, pesos, `.venv` y BD **ignorados**. El recorrido usó una BD y un `static/` en el scratchpad | ✅ |

## 4. Mediciones (`eval/results/traductor.json`)

Muestra: 100 oraciones del **dev** de AmericasNLP (semilla 13), servicio BiTAM es2cni en fp16 sobre la GTX 1060.

| Métrica | Resultado |
|---|---|
| Salidas vacías · en minúsculas | 0 · 100 de 100 |
| Segmentos bloqueados para TTS (salida restaurada) | **4 de 102 (3,9 %)**: letras `d` y `l` de nombres castellanos sin reescritura P2d |
| Palabras con letras ajenas al inventario nativo | **2 de 709 (0,3 %)** |
| Nombres propios: candidatos en la fuente | 36 |
| … copiados por BiTAM | **3 (8,3 %)**. El resto los adapta («Puerto Ocopa» → `portoki okopaji`) o los omite |
| … detectados por `classify` | **0** en la salida cruda → **2** tras restaurar mayúsculas |
| Vocales dobles por 100 palabras | **0,00** en la salida de BiTAM frente a **20,67** en la referencia `dev.cni` |
| Latencia (s/oración, una por petición) | media 6,16 · p50 5,29 · p95 12,97 · máx 17,44 |
| Lote de 100 oraciones | 1.850 s (18,5 s/oración) |

**Sobre la latencia:** estas cifras **no cumplen** la regla «sin otra carga» que fijé en `docs/metrics.md`.
- Durante la medición la GPU estaba compartida con aplicaciones del escritorio: en reposo marcaba
  un 32 % de uso con Wallpaper Engine, Opera GX, Discord y Epic Games abiertos, y la VRAM estaba
  casi llena (5.938 de 6.144 MiB).
- La carga del modelo tardó 28 s, frente a 14 s en la Fase 1.
- No se cerraron aplicaciones del usuario sin permiso, así que la latencia se informa como **medida
  con carga de escritorio**.
- La latencia limpia de referencia sigue siendo la de la Fase 1: 2,21 s/oración y 16,1 s para 20 oraciones en lote.
- Las métricas de compatibilidad no dependen del tiempo y son válidas.

**Lectura de los resultados** (sin ajustar nada, como fijaban las reglas):
- Casi todo lo que produce BiTAM es sintetizable: 96 % de segmentos listos y apenas 0,3 % de palabras con letras ajenas.
- La restauración de mayúsculas funciona, pero tiene **poco material**: BiTAM copia muy pocos nombres propios.
- BiTAM **elimina todas las vocales largas**. Es la consecuencia más importante para la voz y queda como pendiente lingüístico (P1).

## 5. Recorrido completo real (prueba 5)

Noticia de 3 párrafos en castellano («Lluvias afectan a comunidades de Satipo»), escrita para la
prueba. Backend con voz MMS real y traductor BiTAM en GPU; navegador Chromium manejado con Playwright.

| Paso | Resultado |
|---|---|
| Estado en la Redacción | «Traductor disponible: BiTAM es2cni (bitam_v5_seed13_20261018T230715Z_es2cni, cuda:0)» |
| Traducir | **18,5 s** para 7 oraciones (título + 6). Borrador con 3 párrafos, procedencia «Traducción automática», sin marcar como revisada. Título: `Ompoña ompoña oshiyakantari anampiki Satipo` (`Satipo` restaurado) |
| Publicar y sintetizar (MMS, CPU) | **43,3 s** → «Noticia 1 publicada: **4 fragmentos con audio, 0 solo texto**» |
| C1 | texto visible, sin reproductor |
| C2 | voz sin texto. Reproduce hasta «Fin de la noticia» (32,1 s) |
| C3 | voz y texto con resaltado (`.hl`) hasta «Fin de la noticia» (32,1 s) |
| C4 | voz, texto y presentadora. Llega al final (32,1 s). El avatar 3D cae a **imagen fija** (evento `degradacion`) porque falta el VRM |
| CSP | **0 violaciones**. Solo hay dos 404 en consola, ambos de `/models/presentadora_provisional.vrm` |
| Audio | Opus servido con `206 Partial Content` (`Range`) |

Capturas (fuera del repositorio):
- `C:\Users\Marco\AppData\Local\Temp\claude\C--Users-Marco-Downloads-proyecto-ashaninka-proyecto-ashaninka\db02c095-bdf7-4752-a4cb-1a5ecd06cbae\scratchpad\recorrido\1_redaccion_borrador.png`
- `C:\Users\Marco\AppData\Local\Temp\claude\C--Users-Marco-Downloads-proyecto-ashaninka-proyecto-ashaninka\db02c095-bdf7-4752-a4cb-1a5ecd06cbae\scratchpad\recorrido\2_estudio_C4.png`

**Hallazgo del recorrido (limitación 73):**
- BiTAM a veces omite el punto final («…obametantatsiri ishaninkape»). Por eso las 7 oraciones
  dieron 4 fragmentos, y la mayúscula inicial de la oración siguiente quedó en mitad del segmento («… nija **Meka** …»).
- No se corrigió, para respetar la regla de no ajustar después de ver resultados.
- Propuesta: copiar el signo final de la fuente cuando falte, y medirlo con **otra** muestra.

## 6. Estado final de P7

**Resuelto.** La salida de BiTAM está en **ortografía MINEDU 2024**:
- minúsculas, sin tildes y con las vocales dobles colapsadas (lista blanca: `piiri`, `iraaka` y `aari`);
- grafías `k/b/ts/ñ`, que coinciden con la forma canónica del sistema.

Las mayúsculas se restauran en el backend. El efecto de perder las vocales largas pasa a **P1**
(validación lingüística). Registrado en `PLAN_DESARROLLO.md` §3.

## 7. Pendientes para la tesis

1. **VRM de la presentadora:** copiar `presentadora_provisional.vrm` a `frontend/public/models/`
   (o regenerarlo con `scripts/optimize_vrm.py`). Con eso, `verify.sh` debería quedar en verde de
   punta a punta y las 4 E2E del avatar dejarían de saltarse.
2. **Latencia sin carga:** repetir solo la latencia de `eval.traductor.run` con el escritorio en
   reposo (cerrando Wallpaper Engine y otros programas que usan la GPU), o en el servidor definitivo.
3. **Puntuación final (limitación 73):** proponer y medir, con otra muestra del dev, que se copie el signo final de la fuente.
4. **Vocales largas (P1):** consultar con un hablante o lingüista si la pérdida de vocales dobles
   afecta a la comprensión o la pronunciación de la voz MMS.
5. **Revisión por un hablante:** toda noticia traducida debe revisarla un hablante (y marcarse «automática revisada») antes de entrar al experimento (P4).
6. **Cita de BiTAM:** completar con la compañera la autoría y los datos de publicación en `CITATION.md` (la entrega los deja «por completar»).
7. **Despliegue:** el traductor necesita una máquina con GPU y los pesos (no redistribuibles); no está en `docker compose`.
