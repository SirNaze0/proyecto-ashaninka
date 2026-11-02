# Traducción castellano → asháninka (traductor BiTAM)

Este documento cubre la integración del traductor **BiTAM** (*Modelo de traducción automática
bidireccional con morfología adaptativa. Caso asháninka–español*, tesis de una compañera). Es el
primer eslabón del pipeline que prevé el contrato de datos de `PLAN_DESARROLLO.md` §2. El plan y
la historia completa están en `../../MejoraEIntegracion/`.

## Flujo

1. Quien redacta (cualquier persona: sin roles desde QuitarAdmin) escribe o pega una noticia en castellano en la **Sala de redacción**.
2. El servidor la traduce **una sola vez** con BiTAM y devuelve un **borrador**, sin guardar nada.
3. Quien redacta revisa el borrador (tabla de pares oración a oración), lo corrige si hace
   falta y lo publica con el flujo de siempre: `POST /api/news` → `process` → `build`.
4. El **ciudadano** solo ve, en el tablero, noticias ya traducidas (C1–C4). El público nunca usa
   la GPU ni la pantalla de traducción en vivo (`TranslatePanel` sigue sin traductor).

```
PWA (Redacción) ──────── POST /api/news/translate (sin token) ──────▶ backend (uv, transformers 5)
                       ── GET  /api/news/translate/status ─────────▶   │ segmenta, valida límites
                                                                         ▼ HTTP 127.0.0.1:8100
                                         traductor/servidor.py (entorno propio: torch 2.6 cu124,
                                         transformers 4.57.3, peft 0.17.1, bitam-infer), GPU fp16
                                                                         │ cni en minúsculas (MINEDU 2024)
                                                                         ▼
backend: restaurar_mayusculas → borrador {titulo_cni, paragraphs, oraciones, procedencia} → PWA
```

## Por qué es un servicio aparte

BiTAM fija `transformers==4.57.3`, `peft==0.17.1`, `torch==2.6.0` y `numpy==1.26.4`, y advierte
que con otras versiones «los pesos pueden cargar mal sin dar error». El backend usa
`transformers 5.x` y `torch 2.14` para la voz MMS. Las dos pilas no pueden compartir entorno.
Instalación, arranque y problemas frecuentes: [`../traductor/README.md`](../traductor/README.md).

## Configuración

| Variable | Dónde | Defecto | Uso |
|---|---|---|---|
| `NA_TRANSLATOR_ENGINE` | backend | `http` | `http` o `fake` (pruebas: no produce asháninka, marca `[fake-bitam]`) |
| `NA_TRANSLATOR_URL` | backend | vacío | Vacío = desactivado (la Redacción lo declara y el endpoint responde 503). Local: `http://127.0.0.1:8100` |
| `NA_TRANSLATOR_TIMEOUT` | backend | `120` | Segundos por petición |
| `BITAM_MODELS_DIR` | servicio | `../../../bitam_modelos_entrega/modelos` | Pesos de la entrega (**fuera del repositorio**) |
| `BITAM_DEVICE` | servicio | `auto` | `auto`, `cuda` o `cpu` |
| `BITAM_DTYPE` | servicio | `float16` en GPUs sin bf16 nativo | `config` = el bf16 de la entrega. Ver «dtype» en el README del servicio |

## API (pública desde QuitarAdmin; sin token)

| Ruta | Respuesta |
|---|---|
| `GET /api/news/translate/status` | `{disponible, motivo, modelo, version, dispositivo, fake}`. Nunca falla: si no está, `disponible: false` con el motivo |
| `POST /api/news/translate` `{titulo_es, cuerpo_es}` | `{titulo_cni, paragraphs, oraciones: [{parrafo, es, cni_modelo, cni}], procedencia, modelo, segundos, avisos}`. **No escribe en la base de datos** |

Códigos de error:

- **422**: título de más de 300 caracteres, cuerpo de más de 8.000, más de 80 oraciones o una oración de más de 1.000.
- **503**: el servicio no está configurado o no responde.
- **502**: el servicio respondió con un error.

## Qué hace el backend con la salida

- **Segmentación:** usa el `Segmenter` del pipeline, que ya trae abreviaturas castellanas. Envía
  **una oración por elemento**, porque BiTAM trunca a 128 tokens. El título y todas las oraciones
  van en **una sola llamada**, en lotes de 64.
- **Ortografía de salida (P7):** BiTAM normaliza a **MINEDU 2024**. La salida llega en
  minúsculas, sin tildes y con las vocales dobles colapsadas, salvo la lista blanca `piiri`,
  `iraaka` y `aari` (`bitam/resources/normalization.yaml`).
- **Restauración de mayúsculas** (`app.translation.service.restaurar_mayusculas`), determinista:
  - Si una palabra de la salida coincide, sin mayúsculas ni tildes, con una palabra de la fuente
    escrita con mayúscula **fuera del inicio** de la oración (o con una sigla), recupera la forma
    exacta de la fuente: `satipo` → `Satipo`, `peru` → `Perú`, `onu` → `ONU`.
  - La primera letra de la oración pasa a mayúscula si la fuente empieza con mayúscula.
  - **No inventa formas.** Por eso no recupera los nombres que BiTAM *adapta* a la morfología
    asháninka (p. ej. «Puerto Ocopa» → `portoki okopaji`).
- **Procedencia:** `traduccion_automatica`, `sistema = "BiTAM es2cni"`, `version` = el run
  entregado (`bitam_v5_seed13_20261018T230715Z_es2cni`) y `revisado_por_hablante = false`. La PWA
  nunca la marca como revisada: solo un hablante puede hacerlo, y solo las noticias revisadas
  entran al experimento (P4, regla 4 del contrato §2).

## Mediciones

| Qué | Archivo | Resumen |
|---|---|---|
| Latencia del servicio y bf16 frente a fp16 (Fase 1) | `eval/results/traductor_servicio*.json` | fp16: 2,21 s/oración (p95 4,26). Una noticia de 20 oraciones en lote tarda 16,1 s (bf16 emulado: 54,9 s) |
| Fidelidad del ajuste fp16 (Fase 1) | `eval/results/traductor_fidelidad_*.json` | chrF++ en dev (n=200): 26,37 (bf16) y 26,39 (fp16) |
| Compatibilidad con el pipeline (Fase 4) | `eval/results/traductor.json` | ver `MejoraEIntegracion/RESUMEN_FASE4.md` (métricas definidas antes en `docs/metrics.md`) |

La **calidad** de la traducción no se evalúa en esta tesis (contrato §2): pertenece a la tesis
BiTAM, que reporta un chrF++ de 24,50 es→cni en el test oficial de AmericasNLP. El resultado es un
**borrador** que debe revisar un hablante.

## Limitaciones

Ver `docs/limitations.md`, sección «Traductor BiTAM».

## Licencia y cita

- Pesos: **CC BY-NC 4.0** (derivados de NLLB-200), solo uso no comercial. El autor pide **no
  redistribuirlos**, así que no van en el repositorio ni en la imagen Docker.
- Código de inferencia `bitam`: MIT.
- Se cita la tesis BiTAM y NLLB Team (2022). Ver `CITATION.md` y `LICENSES.md`.
