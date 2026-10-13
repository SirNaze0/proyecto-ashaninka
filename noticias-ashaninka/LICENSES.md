# Registro de licencias

| Recurso | Versión | Licencia | Restricción | Uso en el proyecto |
|---|---|---|---|---|
| `facebook/mms-tts-cni` (Meta MMS) | revisión `a744890` | CC-BY-NC 4.0 | **No comercial.** Un servicio público con fines comerciales no puede usarlo | Voz principal (Fase 2). Su `vocab.json` está en `backend/tests/fixtures/` |
| `facebook/mms-1b-all` (Meta MMS) | revisión `3d33597` | CC-BY-NC 4.0 | **No comercial** | Solo para evaluación (experimento 1.9, prueba de ida y vuelta) |
| Corpus AmericasNLP 2021 asháninka–castellano | commit `d3f519c` | El repositorio no declara una licencia explícita | Uso académico con las citas obligatorias. **No se redistribuye en este repositorio**: lo descarga `init.sh` | Evidencia ortográfica, candidatos léxicos y corpus de prueba |
| Corpus monolingüe iapucp (opcional) | `main` | Ver su repositorio | Cita obligatoria | Opcional (`--with-monolingual`) |
| eSpeak-NG (Fase 2) | versión detectada en tiempo de ejecución (en los metadatos de cada audio) | GPL-3.0 | Sin restricción comercial. Se invoca como programa externo, no se enlaza | Línea base (`NA_TTS_ENGINE=espeak_ng`) y alternativa sin restricción comercial. Se instala aparte |
| num2words | ≥ 0.5.13 | LGPL-2.1 | — | Verbalización castellana |
| FastAPI, SQLModel, Pydantic, PyYAML, uv, ruff | — | MIT / BSD | — | Infraestructura |
| PyTorch, transformers | — | BSD-3 / Apache-2.0 | — | Solo en evaluación (grupo `eval`) |
| three.js, `@pixiv/three-vrm`, Preact, Vite | three 0.186, three-vrm 3.5 | MIT | — | Avatar y visor (Fase 3), cliente |
| TalkingHead (`@met4citizen/talkinghead`) | 1.7.0 | MIT | — | Solo en la comparativa de la tarea 3.1 (`frontend/bench/`); no se usa en producción |
| `VRM1_Constraint_Twist_Sample` (pixiv Inc.) | v1.0.1 | Licencia VRM 1.0 (https://vrm.dev/licenses/1.0/): redistribución y modificación permitidas | Es un modelo de ejemplo, **provisional**; no es la presentadora final | Avatar de pruebas (`frontend/public/models/`, no versionado; se reduce con `scripts/optimize_vrm.py`) |
| SyncNet (Chung y Zisserman, `joonson/syncnet_python` @ `907c0b5`) | `syncnet_v2` | Código MIT. Los pesos los publica el VGG de Oxford sin una licencia explícita | Solo evaluación académica; **no se redistribuyen**: se descargan a `models/syncnet/` | LSE-D y LSE-C (tarea 3.8) |
| Playwright, imageio-ffmpeg, scipy, python-speech-features | — | Apache-2.0 / BSD / MIT | ffmpeg de imageio-ffmpeg se distribuye con licencia GPL; se usa como programa externo | Captura y evaluación (grupo `eval`) |

## Advertencias

- Desde la Fase 2, cada audio guarda en su JSON de metadatos el modelo, la revisión, la licencia, si permite uso comercial, la variante y el aviso de voz sintética. Si el motor es no comercial, el manifiesto incluye la advertencia `non_commercial_warning` y el servidor la escribe en el log al iniciar.

- La voz sintética representa la variante dialectal de los datos de entrenamiento de MMS, que no está documentada. Se declarará en la interfaz y en los metadatos de cada audio (Fase 2).
- Los textos derivados del corpus en `data/candidates/` son extractos breves con su referencia de línea, para fines de investigación.
