# PROMPT: Fase 1 de la integración. Servicio BiTAM aparte

> Copia todo lo que está debajo de la línea en una sesión de Claude Code abierta en
> `C:\Users\Marco\Downloads\proyecto-ashaninka\proyecto-ashaninka`.
> Documentos que hay que leer antes: `MejoraEIntegracion/PLAN_INTEGRACION.md`, `CLAUDE.md` y el
> `README.md` de la entrega (`..\bitam_modelos_entrega\README.md`).

---

# ROL

Actúa como ingeniero de ML/infraestructura. Vas a levantar el traductor **BiTAM es→cni** (tesis de
una compañera) como **servicio local aparte**, con su propio entorno de Python, para que el backend
del servicio de noticias pueda llamarlo por HTTP en la Fase 2. La honestidad de las mediciones vale
más que la velocidad.

# CONTEXTO

- Entrega: `C:\Users\Marco\Downloads\proyecto-ashaninka\bitam_modelos_entrega`, con `bitam/`,
  `modelos/v5_es2cni`, `modelos/v3_cni2es`, `requirements.txt`, `pyproject.toml` (`bitam-infer`) y
  `ejemplos/servidor_fastapi.py`.
- BiTAM necesita versiones exactas: `torch==2.6.0`, `transformers==4.57.3`, `peft==0.17.1`,
  `numpy==1.26.4`, etc. Esas versiones **chocan** con el `uv.lock` del backend
  (`transformers 5.18.0`, `torch 2.14.1+cpu`), así que BiTAM **no se instala** en el entorno de
  `noticias-ashaninka/`.
- Máquina: Windows 11, GTX 1060 de 6 GB (Pascal, sin bf16), 24 GB de RAM y Ryzen 7 5700X.
- El modelo base `facebook/nllb-200-distilled-1.3B` se descarga de Hugging Face la primera vez (~5,5 GB).

# TAREAS

1. Crear `noticias-ashaninka/traductor/`:
   - `pyproject.toml` propio (Python 3.11) con las versiones exactas de `requirements.txt` de
     BiTAM, más `fastapi` y `uvicorn`. `torch==2.6.0` sale del índice
     `https://download.pytorch.org/whl/cu124` (como `explicit`). `bitam-infer` se instala desde la
     ruta local de la entrega, indicada en el README; **no se copia el código ni los pesos al repo**.
   - `servidor.py`, basado en `ejemplos/servidor_fastapi.py`:
     - en el `lifespan` carga **solo** `BitamTranslator.load("es2cni", device=BITAM_DEVICE)`
       (`auto` por defecto);
     - `POST /traducir` recibe `{"texts": [...]}`: como máximo 64 oraciones y 1.000 caracteres por
       oración (si se pasa, responde 422). Devuelve `{"translations": [...], "modelo": "BiTAM es2cni",
       "version": <run>}`; el run se lee del comentario o la cabecera de `modelos/v5_es2cni/config.yaml`
       (`bitam_v5_seed13_20261018T230715Z_es2cni`);
     - `GET /salud` devuelve el modelo, el run, el dispositivo real, el dtype real y las versiones de
       torch, transformers y peft;
     - se arranca **solo en `127.0.0.1:8100`**;
     - permite inyectar un traductor falso (variable `BITAM_FAKE=1`) para probarlo sin GPU.
   - `run.ps1` y `run.sh`: arrancan uvicorn con un solo worker.
   - `README.md`: instalación (`uv venv`, `uv pip install`, `BITAM_MODELS_DIR`), arranque, prueba
     de referencia y problemas frecuentes.
   - `tests/test_servidor.py`: pytest con `BITAM_FAKE=1` (salud, traducción, límites → 422 y
     cadenas vacías).
2. Agregar al `.gitignore` todo lo que no debe versionarse: `traductor/.venv/` y cualquier ruta de pesos.
3. Instalar el entorno y descargar el modelo base (pedir confirmación antes de descargar ~5,5 GB).

# PRUEBAS OBLIGATORIAS (criterio de cierre)

| # | Prueba | Resultado esperado |
|---|---|---|
| 1 | `python traducir.py --direction cni2es --text "nosabikashita texas."` (CLI de la entrega, con el entorno del traductor) | Exactamente `Me mudé a Texas.` |
| 2 | `python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_capability())"` | `True (6, 1)`. Si da `False`, documentarlo y seguir con `BITAM_DEVICE=cpu` (riesgo T1) |
| 3 | `GET http://127.0.0.1:8100/salud` | 200, con dispositivo `cuda` (o `cpu` justificado) y dtype `float16` en GPU |
| 4 | `POST /traducir` con 3 oraciones reales en castellano | 200, 3 traducciones no vacías, en minúsculas |
| 5 | `POST /traducir` con 65 oraciones, o con una de 1.001 caracteres | 422 |
| 6 | `uv run pytest traductor/tests` (con `BITAM_FAKE=1`) | Todo verde |
| 7 | Latencia: 20 oraciones del split **dev** de AmericasNLP, sin usar el test | Media, p50 y p95 por oración, tiempo de carga y VRAM máxima, en `eval/results/traductor_servicio.json` |
| 8 | `git status` | Ningún archivo de pesos ni `.venv` en el índice |

# RESTRICCIONES

- No modificar el código de la entrega, que es de la compañera. Si algo falla, se documenta.
- No exponer el servicio fuera de `127.0.0.1`.
- No publicar cifras que no se hayan medido.
- Comentarios y documentación en español.

# AL TERMINAR

Escribe `MejoraEIntegracion/RESUMEN_FASE1.md` con:

1. Qué se hizo.
2. Archivos creados o modificados.
3. La salida real de cada prueba de la tabla.
4. Las mediciones de `traductor_servicio.json`.
5. Desviaciones y pendientes.

Después marca la Fase 1 como **Culminada** en `MejoraEIntegracion/README.md`.
