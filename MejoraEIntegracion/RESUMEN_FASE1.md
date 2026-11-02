# Resumen de la Fase 1: servicio BiTAM aparte

> **Estado:** culminada el 2026-11-02 · **Rama:** `mejora` (sin commit todavía)
> **Prompt:** `PROMPT_FASE1.md` · **Siguiente:** `PROMPT_FASE2.md` (backend)

## 1. Qué se hizo

- Se creó `noticias-ashaninka/traductor/`, un servicio HTTP local con **su propio entorno**
  (`torch 2.6.0+cu124`, `transformers 4.57.3`, `peft 0.17.1`, `numpy 1.26.4`). Es independiente del
  backend, que usa `transformers 5.18` y `torch 2.14`.
- El paquete `bitam-infer` se instala **desde la carpeta de la entrega** (ruta en
  `[tool.uv.sources]`). No se copió al repo ni el código ni los pesos de la compañera, y no se
  modificó ningún archivo de la entrega.
- El servicio carga **solo es2cni**, escucha en `127.0.0.1:8100` con un solo worker y expone:
  - `POST /traducir`, con 64 oraciones y 1.000 caracteres por oración como máximo (si no, 422);
  - `GET /salud`, que devuelve el run, el dispositivo y el dtype reales, las versiones, la carga y la VRAM.
- Se descargó el modelo base `facebook/nllb-200-distilled-1.3B` a `~/.cache/huggingface`, con la autorización del usuario.
- **Hallazgo del dtype y corrección:**
  - La config de la entrega pide `bfloat16`. `bitam` intenta pasar a `float16` en GPUs sin bf16,
    pero en torch 2.6 `torch.cuda.is_bf16_supported()` cuenta la **emulación** y devuelve `True`
    en la GTX 1060 (Pascal, sm_61). Por eso bf16 corría emulado y lento.
  - El servicio aplica la intención del código: `float16` si la capacidad es menor que 8.0. Lo hace
    como *override* de la config (`BITAM_DTYPE`; `config` fuerza el bf16 original).
  - Se comprobó con datos que **no degrada la traducción** (sección 4).
- Se añadieron dos herramientas de medición, solo con el split **dev** y sin guardar texto del corpus (solo hashes y números de línea):
  - `bench.py`: latencia;
  - `fidelidad.py`: chrF++ por dtype.

## 2. Archivos

| Archivo | Tipo |
|---|---|
| `noticias-ashaninka/traductor/pyproject.toml`, `uv.lock` | nuevo: entorno propio (índice cu124 y `bitam-infer` desde la ruta local) |
| `noticias-ashaninka/traductor/servidor.py` | nuevo: servicio FastAPI, motores `MotorBitam` y `MotorFalso`, y selección de dtype |
| `noticias-ashaninka/traductor/tests/test_servidor.py` | nuevo: 15 pruebas con el motor falso |
| `noticias-ashaninka/traductor/run.ps1`, `run.sh` | nuevo: arranque en 127.0.0.1 |
| `noticias-ashaninka/traductor/bench.py`, `fidelidad.py` | nuevo: mediciones |
| `noticias-ashaninka/traductor/README.md` | nuevo: instalación, API, dtype y problemas frecuentes |
| `noticias-ashaninka/eval/results/traductor_servicio.json` | nuevo: latencia fp16 (configuración final) |
| `noticias-ashaninka/eval/results/traductor_servicio_bf16.json` | nuevo: latencia bf16 (línea base de la entrega) |
| `noticias-ashaninka/eval/results/traductor_fidelidad_{float16,bfloat16}.json` | nuevo: chrF++ / chrF por dtype |

## 3. Pruebas obligatorias (salida real)

| # | Prueba | Resultado | Estado |
|---|---|---|---|
| 1 | `traducir.py --direction cni2es --text "nosabikashita texas."` | `Me mudé a Texas.` (exacto; 3 min 52 s, incluida la descarga del modelo base) | ✅ |
| 2 | `torch.cuda.is_available(), get_device_capability()` | `True (6, 1)`, `NVIDIA GeForce GTX 1060 6GB`. El riesgo T1 queda descartado | ✅ |
| 3 | `GET /salud` | `dispositivo: cuda:0`, `dtype: float16`, `carga_s: 14.1`, `version: bitam_v5_seed13_20261018T230715Z_es2cni` | ✅ |
| 4 | `POST /traducir` con 3 oraciones propias | `isaikayeti isha anampiki` / `osheki nijateniki omonkarata inkani` / `jananekipe ijatake obametantatsiri pichanaki`: 3 salidas no vacías y en minúsculas (`Pichanaki` → `pichanaki`) | ✅ |
| 5 | 65 oraciones · una oración de 1.001 caracteres | `422` · `422` | ✅ |
| 6 | `BITAM_FAKE=1 uv run pytest` (traductor) | `15 passed` | ✅ |
| 7 | Latencia con 20 oraciones del dev (semilla 13) | ver sección 4 → `eval/results/traductor_servicio.json` | ✅ |
| 8 | `git status` | Solo código, documentación y JSON de resultados. `traductor/.venv` ignorado (`.gitignore:2`). Ningún `.safetensors`, `.pt` ni `.bin` | ✅ |

Calidad del código: `ruff check` y `ruff format --check` (línea de 100, mismas reglas que el
backend) sin errores, y `shellcheck run.sh` limpio.

## 4. Mediciones (GTX 1060 6 GB, split dev de AmericasNLP)

**Latencia:** 20 oraciones, semilla 13, 11,05 palabras de media por oración, una oración por petición y calentamiento descartado.

| dtype | media | p50 | p95 | máx. | 20 oraciones en un lote | s/oración en lote |
|---|---|---|---|---|---|---|
| bf16 (entrega, emulado) | 5,39 s | 4,73 s | 11,13 s | 15,27 s | 54,87 s | 2,74 s |
| **fp16 (final)** | **2,21 s** | **2,10 s** | **4,26 s** | **4,64 s** | **16,14 s** | **0,81 s** |

Una primera tanda en bf16 dio una media de 4,76 s, con la misma muestra. Hay variabilidad entre ejecuciones.

**Fidelidad:** 200 oraciones del dev, semilla 13, lotes de 32. No es una evaluación de la calidad de BiTAM: solo comprueba que el cambio de dtype no la altera.

| dtype | chrF++ | chrF | tiempo total |
|---|---|---|---|
| bf16 (entrega) | 26,37 | 32,72 | 179 s |
| fp16 (final) | 26,39 | 32,68 | 147 s |

- Salidas idénticas entre los dos dtypes: **125 de 200** (62,5 %). Las demás difieren por la
  aritmética de la decodificación (beam 4), sin efecto en la métrica agregada (±0,04).
- **Memoria:** el pico de VRAM asignado por torch es de 5.152 MB en ambos dtypes (se da durante la carga).
  `nvidia-smi` llegó a mostrar 5.981 de 6.144 MiB ocupados, contando el escritorio. **Hay poco margen**:
  no conviene usar la GPU para otra cosa mientras el servicio está activo.
- **Carga:** 14,1 s en fp16 y 16,6 s en bf16, con el modelo base ya en caché.

**Implicación para la Fase 2:** una noticia de ~20 oraciones tarda unos 16 s si se envía en un solo
lote. El backend debe mandar las oraciones **en lote** (no una por una) y usar un timeout amplio (120 s, como estaba previsto).

## 5. Desviaciones respecto al plan

1. **dtype:** el plan suponía que `bitam` ya pasaba a fp16 solo. No lo hace en torch 2.6, así que
   se añadió la selección en el servicio (`dtype_por_defecto`) y se validó con chrF++.
2. **Herramientas extra:** `fidelidad.py` y la dependencia de desarrollo `sacrebleu==2.5.1`, para justificar el punto 1 con datos.
3. **Corpus:** este checkout no tiene `data/corpus/`. Se usó la copia descargada de
   `C:\Users\Marco\Downloads\Proyecto\noticias-ashaninka\data\corpus\americasnlp2021`, verificada
   con el mismo SHA-256 que `backend/app/corpus/loader.py`.
4. **Pruebas del servicio:** corren con el entorno del traductor y no con el del backend. Este
   checkout no tenía el `.venv` del backend instalado. Además, un `uv run --no-sync` creó un
   `noticias-ashaninka/.venv` **vacío**: git lo ignora, `uv sync` / `init.sh` lo reutilizarán y no
   causa problemas, pero se puede borrar.

## 6. Pendientes y notas para las fases siguientes

- **Fase 2:**
  - el backend debe segmentar en oraciones y enviar lotes de 64 como máximo;
  - la salida llega en minúsculas, así que hay que restaurar las mayúsculas (confirmado: `pichanaki`).
- **Windows:** al detener `run.ps1` / `run.sh`, `uv run` puede dejar `uvicorn` vivo en el puerto
  8100. Se documentó en el README cómo cerrarlo (`Get-NetTCPConnection` → `Stop-Process`).
- `traductor/` todavía no está en los hooks de pre-commit (ruff y shellcheck se ejecutaron a mano).
  Se incorporará en la Fase 4 junto con `scripts/verify.sh`.
- Docker sigue fuera del alcance, como estaba planeado.
