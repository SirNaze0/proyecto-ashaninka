# Registro de licencias

| Recurso | Versión | Licencia | Restricción | Uso en el proyecto |
|---|---|---|---|---|
| `facebook/mms-tts-cni` (Meta MMS) | revisión `a744890` | CC-BY-NC 4.0 | **No comercial.** Un servicio público con fines comerciales no puede usarlo | Voz principal (Fase 2). Su `vocab.json` está en `backend/tests/fixtures/` |
| `facebook/mms-1b-all` (Meta MMS) | revisión `3d33597` | CC-BY-NC 4.0 | **No comercial** | Solo para evaluación (experimento 1.9, prueba de ida y vuelta) |
| Corpus AmericasNLP 2021 asháninka–castellano | commit `d3f519c` | El repositorio no declara una licencia explícita | Uso académico con las citas obligatorias. **No se redistribuye en este repositorio**: lo descarga `init.sh` | Evidencia ortográfica, candidatos léxicos y corpus de prueba |
| Corpus monolingüe iapucp (opcional) | `main` | Ver su repositorio | Cita obligatoria | Opcional (`--with-monolingual`) |
| eSpeak-NG (Fase 2) | — | GPL-3.0 | Sin restricción comercial | Línea base y alternativa sin restricción comercial |
| num2words | ≥ 0.5.13 | LGPL-2.1 | — | Verbalización castellana |
| FastAPI, SQLModel, Pydantic, PyYAML, uv, ruff | — | MIT / BSD | — | Infraestructura |
| PyTorch, transformers | — | BSD-3 / Apache-2.0 | — | Solo en evaluación (grupo `eval`) |

## Advertencias

- La voz sintética representa la variante dialectal de los datos de entrenamiento de MMS, que no está documentada. Se declarará en la interfaz y en los metadatos de cada audio (Fase 2).
- Los textos derivados del corpus en `data/candidates/` son extractos breves con su referencia de línea, para fines de investigación.
