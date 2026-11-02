# Servicio de traducción BiTAM (castellano → asháninka)

Este es un servicio HTTP **local** que expone el modelo **BiTAM es2cni** (tesis de una compañera:
*Modelo de traducción automática bidireccional con morfología adaptativa (BiTAM). Caso
asháninka–español*) al backend de noticias. El administrador lo usa desde la Redacción para
obtener un **borrador** en asháninka. Ver `../../MejoraEIntegracion/PLAN_INTEGRACION.md`.

## Por qué va aparte

BiTAM exige versiones exactas: `transformers==4.57.3`, `peft==0.17.1`, `torch==2.6.0` y
`numpy==1.26.4`. Su README advierte que con otras versiones «los pesos pueden cargar mal sin dar
error». El backend usa `transformers 5.x` y `torch 2.14` para la voz MMS. Por eso este servicio
tiene **su propio entorno** (`traductor/.venv`) y el backend lo llama por HTTP.

## Requisitos

| Recurso | Detalle |
|---|---|
| Entrega de BiTAM | `bitam_modelos_entrega/` descomprimida. Por defecto en `../../../bitam_modelos_entrega` (junto a la carpeta del repositorio) |
| Modelo base | `facebook/nllb-200-distilled-1.3B` (~5,5 GB). Se descarga de Hugging Face la **primera vez** a `~/.cache/huggingface` |
| GPU | Recomendada: ~3 GB de VRAM en fp16 (la GTX 1060 no tiene bf16 y `bitam` pasa a fp16 solo). En CPU funciona, pero es más lento |
| Python | 3.11 (lo instala `uv`) |

Los pesos **no se versionan ni se meten en la imagen Docker**: son CC BY-NC 4.0 (derivados de NLLB-200),
y el autor pide no redistribuirlos.

## Instalación

```powershell
cd noticias-ashaninka\traductor
uv sync                      # torch 2.6.0+cu124, transformers 4.57.3, peft, bitam-infer (desde la entrega)
```

- Si la entrega está en otra ruta, cambia `bitam-infer = { path = ... }` en `pyproject.toml`.
- Si no hay GPU, cambia el índice de `torch` a `https://download.pytorch.org/whl/cpu`.

### Prueba de referencia de la instalación

La entrega trae una traducción de control que debe salir **exactamente** así (usa cni→es):

```powershell
$env:BITAM_MODELS_DIR = (Resolve-Path ..\..\..\bitam_modelos_entrega\modelos).Path
uv run python ..\..\..\bitam_modelos_entrega\traducir.py --direction cni2es --text "nosabikashita texas."
# -> Me mudé a Texas.
```

## Arranque

```powershell
.\run.ps1                    # http://127.0.0.1:8100, dispositivo auto
.\run.ps1 -Device cpu        # forzar CPU
```

```bash
./run.sh 8100 auto
```

La carga tarda entre 20 y 30 s. El servicio escucha **solo en 127.0.0.1**, con un worker: cada
proceso cargaría otra copia del modelo.

## API

| Método | Ruta | Entrada | Salida |
|---|---|---|---|
| `POST` | `/traducir` | `{"texts": ["oración 1", ...]}`: hasta 64 oraciones, 1.000 caracteres cada una (si no, 422) | `{"translations": [...], "modelo": "BiTAM es2cni", "version": "<run>"}` |
| `GET` | `/salud` | — | modelo, run, dispositivo y dtype reales, versiones, `carga_s`, `vram_max_mb` y límites |

Hay que enviar **una oración por elemento**, porque BiTAM trunca a 128 tokens. La segmentación la
hace el backend (Fase 2).

Variables de entorno:

| Variable | Defecto | Uso |
|---|---|---|
| `BITAM_MODELS_DIR` | `../../../bitam_modelos_entrega/modelos` (desde `run.*`) | carpeta con `v5_es2cni/` |
| `BITAM_DEVICE` | `auto` | `auto`, `cuda` o `cpu` |
| `BITAM_DTYPE` | `float16` en GPUs sin bf16 nativo | `float16`, `bfloat16`, `float32` o `config` (el de la entrega, bf16). Ver «dtype» abajo |
| `BITAM_FAKE` | — | `1` = motor falso para pruebas (no carga el modelo y no produce asháninka: marca el texto con `[fake-bitam]`) |

## Qué devuelve el modelo

- Ortografía **MINEDU 2024**, **en minúsculas**, sin tildes y con las vocales dobles colapsadas (salvo
  `piiri`, `iraaka` y `aari`). Esto responde a la pregunta P7 de `PLAN_DESARROLLO.md`.
- La calidad es de **borrador** (chrF++ 24,5 en el test de AmericasNLP): siempre necesita revisión de un hablante.

## dtype: por qué fp16 en la GTX 1060

La config entregada pide `bfloat16`. `bitam` pretende pasar a `float16` cuando la GPU no tiene
bf16, pero en torch 2.6 `torch.cuda.is_bf16_supported()` **cuenta la emulación** y devuelve `True`
en Pascal, así que bf16 corre emulado y es lento. El servicio aplica esa intención: si la capacidad
CUDA es menor que 8.0, usa fp16 (como *override* de la config, sin tocar el código de la entrega).
Lo medido el 2026-11-02 en la GTX 1060, con el split **dev**:

| dtype | s/oración (media · p95) | 20 oraciones en lote | chrF++ · chrF (n=200) |
|---|---|---|---|
| bf16 (entrega) | 5,39 · 11,13 | 54,9 s | 26,37 · 32,72 |
| **fp16** | **2,21 · 4,26** | **16,1 s** | **26,39 · 32,68** |

El 62,5 % de las salidas son idénticas y la métrica agregada no cambia. Datos en
`../eval/results/traductor_servicio*.json` y `traductor_fidelidad_*.json`.

## Pruebas y medición

```powershell
$env:BITAM_FAKE = "1"; uv run pytest; Remove-Item Env:BITAM_FAKE     # sin GPU ni pesos
# con el servicio real encendido (solo el split dev, nunca test):
uv run python bench.py --corpus <ruta>\data\corpus\americasnlp2021   # -> ../eval/results/traductor_servicio.json
uv run python fidelidad.py --corpus <ruta>\data\corpus\americasnlp2021 --n 200   # chrF++ del dtype activo
```

Los resultados **no guardan texto del corpus** (no se redistribuye): solo números de línea y hashes de las salidas.

## Problemas frecuentes

| Síntoma | Solución |
|---|---|
| `no se encuentra .../config.yaml` | Define `BITAM_MODELS_DIR` |
| `torch.cuda.is_available()` es `False` | Revisa el driver de NVIDIA, o arranca con `-Device cpu` |
| `CUDA out of memory` | Cierra otros procesos que usen la GPU. Este servicio solo carga es2cni |
| Tras cerrar la consola, el puerto 8100 sigue ocupado (Windows: `uv run` no reenvía la parada a uvicorn) | `Get-NetTCPConnection -LocalPort 8100` → `Stop-Process -Id <OwningProcess>` |
| Falla la descarga de Hugging Face | Descarga el modelo base una vez con conexión; luego usa `HF_HUB_OFFLINE=1` |
