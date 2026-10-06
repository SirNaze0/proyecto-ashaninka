# Manifiesto por noticia y archivos de audio (Fase 2)

El JSON Schema del manifiesto se genera desde el modelo Pydantic
(`backend/app/batch/manifest.py`) con:

```bash
uv run python -m app.batch schema    # -> docs/manifest.schema.json
```

Las pruebas validan cada manifiesto generado contra ese modelo
(`backend/tests/integration/test_synthesis.py`).

## Ubicación de los archivos (carpeta `static/`, servida en `/static` con soporte de `Range`)

| Archivo | Contenido |
|---|---|
| `static/audio/<k[:2]>/<k>.opus` | Audio en OGG/Opus (principal) |
| `static/audio/<k[:2]>/<k>.mp3` | Audio MP3 (respaldo) |
| `static/audio/<k[:2]>/<k>.json` | `meta`: motor, modelo, revisión, licencia, uso comercial, variante, adaptador, semilla, texto, duración, `synth_ms`, RTF, kbps reales, sha256 y `"sintetico": true`. `durations`: las duraciones del motor, si las expone |
| `static/news/<id>/manifest.json` | Manifiesto de la noticia (esquema abajo) |
| `static/news/<id>/seg_NNN.json` | Tiempos del segmento: duraciones, tiempos por carácter canónico y por fragmento original |

`k` es la **clave de caché por contenido**: el sha256 de un JSON con el texto que recibe el
motor, el motor, el modelo, la revisión, el `adapter_id`, los parámetros que afectan al audio
(velocidad, ruido, tokenización…) y la tasa de Opus. Si el mismo texto se pide con la misma
configuración, se reutiliza el audio; si cambia cualquiera de esos campos, por ejemplo la
hipótesis del adaptador, la clave cambia.

## Esquema del manifiesto (versión 1.0)

| Campo | Tipo | Descripción |
|---|---|---|
| `schema_version` | texto | `"1.0"` |
| `news_id`, `titulo_cni`, `fecha_publicacion` | | Datos de la noticia (nunca el texto castellano) |
| `generated_at` | ISO-8601 | Momento de generación |
| `engine` | objeto | `engine`, `model`, `revision`, `adapter_id`, `params` |
| `notices` | objeto | `synthetic_voice` (aviso de voz sintética), `license`, `commercial_use`, `non_commercial_warning` (texto o `null`), `dialect` |
| `segments[]` | lista | Uno por oración, en orden (ver abajo) |
| `total_duration_s`, `segments_with_audio`, `segments_blocked` | | Resumen |

Cada elemento de `segments[]`:

| Campo | Descripción |
|---|---|
| `idx`, `paragraph_idx`, `text_orig` | Posición y texto original de la oración |
| `tts_ready` | `false` si el segmento quedó bloqueado (letras fuera del vocabulario del motor) |
| `audio` | `{opus, mp3, opus_kbps, mp3_kbps}` o `null` si está bloqueado |
| `duration_s` | Duración del audio (`null` si está bloqueado) |
| `timings` | URL de `seg_NNN.json` (`null` si está bloqueado) |
| `blocked_reason` | Motivo del bloqueo; el cliente muestra solo el texto (modo degradado) |

## Tiempos (`seg_NNN.json`)

- `durations`: `tokens`, `frames`, `hop_samples`, `sample_rate`, `char_times` por carácter del texto que recibió el motor, y `blank_rule`.
- `canonical_times`: (inicio, fin) por carácter del texto canónico, proyectados con `tts_char_map`.
  - Un tramo canónico que produjo varios caracteres de audio recibe su intervalo completo, repartido en partes iguales.
  - Un tramo que no produjo audio, como la puntuación eliminada, recibe un intervalo de duración 0 en el instante en que terminó lo anterior.
- `spans`: un objeto por fragmento original (`orig_start`, `orig_end`, `orig_text`, `category`, `t0`, `t1`), proyectado con `alignment_map`. Es la entrada del resaltado sincronizado de la Fase 4.

Estos tiempos se derivan de las duraciones que el modelo usó realmente, verificadas en cada
síntesis (`sum(frames) × hop == len(audio)`). Si coinciden con los sonidos reales se valida en la
Fase 3.

## Streaming bajo demanda (`GET /api/synthesize/{news_id}`)

Respuesta `application/x-ndjson`, un objeto por línea, en este orden:

1. `{"event": "meta", "t_ms", "news_id", "segments", "engine", "notices"}`
2. Por cada oración, en orden:
   - `{"event": "segment", "t_ms", "reused", …campos de segments[]}`, o
   - `{"event": "blocked", "t_ms", …}`.
3. `{"event": "done", "t_ms", "manifest"}`

`t_ms` son los milisegundos desde que llegó la solicitud. El `t_ms` del primer evento `segment`
es el TTFA del servidor (ver `docs/metrics.md`). Si se supera el límite de síntesis simultáneas
(`NA_MAX_CONCURRENT_SYNTH`), la respuesta es 503 con `Retry-After`. Si la noticia supera
`NA_MAX_NEWS_CHARS`, la respuesta es 413.
