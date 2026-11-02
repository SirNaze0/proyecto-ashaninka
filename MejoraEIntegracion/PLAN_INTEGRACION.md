# Plan de integración del traductor BiTAM (es→cni)

> **Versión:** 1.0 · **Fecha:** 2026-11-02 · **Rama de trabajo:** `mejora`
> **Entrega analizada:** `C:\Users\Marco\Downloads\proyecto-ashaninka\bitam_modelos_entrega` (zip
> `bitam_modelos_entrega.zip`, 2,09 GB, compartido por Drive)

## 1. Contexto

Según `PLAN_DESARROLLO.md` §1 y §2, las noticias llegan en asháninka desde el **sistema de
traducción español→asháninka de la tesis de una compañera**. Hasta ahora ese traductor no estaba
integrado: `frontend/src/app/translator.ts` usa `TRADUCTOR_PENDIENTE` y la Redacción exige pegar el
texto ya traducido. La compañera entregó sus modelos entrenados y el código de inferencia, así que
ahora se puede cerrar ese eslabón.

### 1.1 Qué contiene la entrega

| Elemento | Detalle |
|---|---|
| Código | Paquete `bitam` (inferencia, MIT): `api.py` (`BitamTranslator`), ortografía, morfología, tokenizador y recursos YAML |
| Modelo base | `facebook/nllb-200-distilled-1.3B`, congelado. **No viene en el zip**: se descarga de Hugging Face (~5,5 GB) |
| es→cni | `modelos/v5_es2cni/peft/`: LoRA r=16 (`adapter_model.safetensors`, ~1,1 GB), 2 adapters bottleneck y `new_token_embeddings.pt`. chrF++ **24,50** en el test oficial de AmericasNLP |
| cni→es | `modelos/v3_cni2es/peft/`: LoRA r=8 y 1 adapter. chrF++ **26,25** |
| Ejemplos | `traducir.py` (CLI) y `ejemplos/servidor_fastapi.py` (HTTP sin autenticación) |
| Licencia | Código MIT. Pesos CC BY-NC 4.0 (derivados de NLLB-200), «no redistribuir sin consultar al autor» |

### 1.2 Veredicto: **sí se puede usar**, con estas condiciones

1. **Entorno separado (obligatorio).** BiTAM fija `transformers==4.57.3`, `peft==0.17.1`,
   `torch==2.6.0`, `numpy==1.26.4` y `huggingface-hub==0.36.0`. Su README avisa de que con otras
   versiones «los pesos pueden cargar mal sin dar error». El `uv.lock` del proyecto tiene
   `transformers 5.18.0`, `torch 2.14.1+cpu`, `numpy 2.4.6` y `huggingface-hub 1.33.0`, y los
   necesita la voz MMS. Por eso BiTAM corre como **servicio HTTP aparte** con su propio entorno, y el
   backend lo llama.
2. **Hardware disponible:** GTX 1060 de 6 GB, 24 GB de RAM y Ryzen 7 5700X.
   - La arquitectura Pascal no tiene bf16. ~~`bitam/model.py` ya cambia a fp16 por su cuenta~~ →
     **corregido en la Fase 1:** en torch 2.6 no lo hace, porque cuenta la emulación. El servicio
     fuerza fp16, validado con chrF++ en el dev.
   - **Medido en la Fase 1:** 2,21 s por oración de media en fp16, y una noticia de 20 oraciones
     en un lote tarda 16,1 s. El pico de VRAM es de 5,15 GB (ver `RESUMEN_FASE1.md`).
   - Se carga solo es2cni; cni2es se usa una vez para comprobar la instalación.
3. **Encaje con el flujo:** se traduce una sola vez, en la Redacción, y el ciudadano consume la
   noticia ya publicada. El endpoint de traducción va dentro del router `/api/news`, que ya exige
   `require_admin`. No se abre ningún endpoint público ni se gasta GPU por cada visitante.
4. **Ortografía de salida (resuelve P7).** BiTAM normaliza a **MINEDU 2024**: minúsculas, sin tildes
   y con las vocales dobles colapsadas (solo conserva `piiri`, `iraaka` y `aari`). Esto tiene
   consecuencias:
   - **Se pierden las mayúsculas.** `pipeline/normalize/classify.py:152` detecta los nombres
     propios por la mayúscula, así que hay que restaurarlas de forma determinista (Fase 2).
   - Las grafías `k/b/ts/ñ` coinciden con la ortografía canónica del sistema.
   - Falta **medir** cómo se comporta el colapso de vocales dobles en `unify` y en el TTS (Fase 4).
5. **Licencia compatible.** NLLB-200 es CC BY-NC 4.0, igual que la voz MMS, y la tesis no es
   comercial. Los pesos **no entran en git ni en la imagen Docker**: se indican con `BITAM_MODELS_DIR`.
6. **Calidad.** Con un chrF++ de ~25 el resultado es un **borrador**. Se guarda con
   `procedencia.tipo = "traduccion_automatica"` y `revisado_por_hablante = false`. Solo entran al
   experimento las noticias revisadas por un hablante (P4, regla 4 del contrato §2).
7. **Seguridad de los pesos.** Los `.pt` se cargan con `torch.load`; en torch 2.6 el valor por
   defecto es `weights_only=True`. No se usa `trust_remote_code`. El servicio escucha solo en
   `127.0.0.1`.

## 2. Arquitectura

```
PWA (Redacción, admin) ──POST /api/news/translate (x-admin-token)──▶ Backend FastAPI (uv, transformers 5)
                                                                        │ segmenta en oraciones
                                                                        │ HTTP 127.0.0.1:8100
                                                                        ▼
                                                     Servicio BiTAM (entorno propio, torch 2.6 cu124, GPU)
                                                        POST /traducir · GET /salud
                                                                        │ cni (MINEDU, minúsculas)
                                                                        ▼
Backend: restaura mayúsculas → borrador {titulo_cni, paragraphs, oraciones, procedencia} → PWA
Admin revisa/edita → publicar(): POST /api/news → /process → /build (voz) → tablero del Ciudadano (C1–C4)
```

## 3. Fases

| Fase | Objetivo | Prompt | Pruebas obligatorias (criterio de cierre) |
|---|---|---|---|
| 1 | Servicio BiTAM aparte: `noticias-ashaninka/traductor/` | `PROMPT_FASE1.md` | La referencia cni2es da exactamente `Me mudé a Texas.` · `/salud` responde con `cuda` y `float16` · límites (64 oraciones / 1.000 caracteres → 422) · pytest del servicio con un traductor falso · latencia medida en `eval/results/traductor_servicio.json` |
| 2 | Backend: `backend/app/translation/` y `POST /api/news/translate` | `PROMPT_FASE2.md` | pytest: segmentación, restauración de mayúsculas, cliente (servidor falso, timeout), endpoint 403/200/422/503 · `test_docs_fase6.py` en verde · `.env.example` completo · `ruff check` y `ruff format --check` · `pytest -m smoke` |
| 3 | PWA: tarjeta «Traducir desde castellano» en la Redacción | `PROMPT_FASE3.md` | `npm test` (vitest) · `npm run typecheck` · `npm run build` y presupuesto < 3 MB · E2E Playwright con `page.route` (éxito, 503, 403) · axe sin violaciones |
| 4 | Medición ortográfica real, documentación, licencias y cierre | `PROMPT_FASE4.md` | `eval/results/traductor.json` generado con el split **dev** · `scripts/verify.sh` en verde · recorrido completo real (traducir → publicar → C4) · documentos actualizados |

Al cerrar cada fase se escribe `RESUMEN_FASEn.md` en esta carpeta con:

- lo que se hizo;
- los archivos tocados;
- la salida real de las pruebas;
- las desviaciones respecto al plan;
- los pendientes.

## 4. Decisiones de diseño

| Decisión | Motivo |
|---|---|
| Servicio aparte y no una dependencia del backend | Conflicto de versiones de `transformers`, `torch` y `numpy` (§1.2.1) |
| El endpoint vive en `/api/news/translate` | Hereda `require_admin`. La regla de Fase 6 («todo endpoint de escritura nuevo usa `require_admin`») se cumple sin excepciones nuevas |
| El endpoint **no guarda** nada | El administrador revisa antes de publicar. Se reutiliza `publicar()` tal cual |
| Restauración de mayúsculas determinista | Primera letra de cada oración + tokens que coinciden con un token capitalizado de la fuente. No inventa formas asháninka |
| Solo es2cni en memoria | VRAM de 6 GB y el flujo solo necesita es→cni |
| La pantalla pública `TranslatePanel` sigue sin traducción en vivo | El ciudadano consume noticias ya traducidas, y así no se expone la GPU al público |
| Docker del traductor fuera del alcance | GPU en Docker sobre Windows exige WSL2 y NVIDIA Container Toolkit. Se documenta y no se afirma que funcione sin probarlo |

## 5. Variables de entorno nuevas

| Variable | Dónde | Defecto | Uso |
|---|---|---|---|
| `NA_TRANSLATOR_ENGINE` | backend | `http` | `http` o `fake` (pruebas) |
| `NA_TRANSLATOR_URL` | backend | vacío (desactivado) | p. ej. `http://127.0.0.1:8100` |
| `NA_TRANSLATOR_TIMEOUT` | backend | `120` | segundos por petición al servicio |
| `BITAM_MODELS_DIR` | servicio | — | carpeta `modelos/` de la entrega (fuera del repo) |
| `BITAM_DEVICE` | servicio | `auto` | `auto`, `cuda` o `cpu` |

Las `NA_*` se documentan en `.env.example` y `.env.production.example`, porque hay una prueba que lo exige.

## 6. Riesgos

| Id | Riesgo | Mitigación |
|---|---|---|
| T1 | torch 2.6 cu124 no soporta la GTX 1060 (sm_61) | Se comprueba en la Fase 1 con `torch.cuda.get_device_capability()`. Si falla, se usa `BITAM_DEVICE=cpu` y se mide |
| T2 | Faltan las mayúsculas y los nombres propios no se reconocen | Restauración determinista (Fase 2) y medición antes/después (Fase 4) |
| T3 | Las vocales colapsadas cambian la pronunciación del TTS | Se mide en la Fase 4 y queda como pendiente lingüístico (P1) si aparece. No se «corrige» a mano |
| T4 | Una traducción de baja calidad se publica como definitiva | Procedencia obligatoria, `revisado_por_hablante=false` y aviso fijo en la Redacción. El experimento solo admite noticias revisadas |
| T5 | Peticiones largas bloquean el worker | Límites de tamaño, timeout, candado interno de BiTAM y un solo servicio |
| T6 | Redistribuir los pesos sin permiso | Fuera de git (`.gitignore`) y fuera de la imagen. Solo se usa la ruta local |
| T7 | Evaluar sobre el test de AmericasNLP (es el de BiTAM) | La Fase 4 usa solo el split **dev** |

## 7. Fuera de alcance

- Volver a entrenar o ajustar BiTAM.
- Evaluar la calidad de la traducción. Según el contrato §2 «la calidad de su traducción **no** se
  evalúa aquí; solo se controla su procedencia».
- Traducir la interfaz al asháninka (`cni.json` sigue vacío).
- Servir el traductor dentro de Docker.
