# Noticias automáticas de TV Perú (NoticiasTVPeru)

El tablón (`#/noticias`) se puede llenar solo con las últimas noticias de **TV Perú**. Cada X minutos, o al
pulsar «Refrescar ahora», el servidor:

1. descarga el RSS de TV Perú;
2. traduce un resumen al asháninka con **BiTAM**;
3. lo pasa por el pipeline y sintetiza la voz;
4. lo publica marcado como **«Traducción automática sin revisar»**, con un enlace a la noticia original.

Plan, prompts y resúmenes por fase: `../../NoticiasTVPeru/`.

## Flujo

```
https://www.tvperu.gob.pe/rss.xml ──(1 petición por ciclo, UA propio)──▶ app/feed/tvperu.py
   parsear_rss: <p> sin «Lee también», tuits, vídeos ni «TAMBIÉN TE PUEDE INTERESAR»
   recortar: ≤ 12 oraciones y ≤ 2.500 caracteres (oraciones completas)
        │
        ▼  FeedItem (guid único: nunca se duplica; texto es guardado para reintentar)
app/feed/servicio.py::ejecutar_ciclo   (un ciclo a la vez; hasta 3 noticias, las más recientes)
   traducir_noticia (BiTAM, servicio aparte) ─▶ NewsIn (traduccion_automatica, revisado_por_hablante=false,
                                                fuente_original = URL de TV Perú)
   import_payloads ─▶ process_news (normalización, adaptador MMS, G2P) ─▶ run_batch (voz por lotes)
        │
        ▼
/api/catalog?orden=recientes ──▶ tablón de la PWA (etiqueta + «Fuente: TV Perú»; enlace en la noticia)
```

Quién lo dispara:

- **El planificador** (`app/feed/planificador.py`): un hilo de fondo del backend que cada 30 s revisa si venció
  el intervalo guardado en la base (`FeedConfig`). Solo existe con `NA_FEED_ENABLED=true`.
- **«Refrescar ahora»** en el tablón (`POST /api/feed/run`).
- **La CLI**: `uv run python -m app.cli feed run`. Sirve también desde cron, aunque `NA_FEED_ENABLED` esté
  apagado.

## Configuración

| Variable | Defecto | Uso |
|---|---|---|
| `NA_FEED_ENABLED` | `false` (`true` en `.env.local.example`) | Arranca el planificador y habilita `POST /api/feed/run` (si no, responde 503) |
| `NA_FEED_URL` | `https://www.tvperu.gob.pe/rss.xml` | Feed RSS 2.0 |
| `NA_FEED_USER_AGENT` | vacío = `NoticiasAshaninka/1.0` (compatible) | Por si la fuente rechaza el UA por defecto |
| `NA_FEED_TIMEOUT` | `30` | Segundos de espera de la descarga |
| `NA_FEED_INTERVALO_MIN` | `0` | Intervalo inicial si la base aún no tiene uno |
| `NA_FEED_TRANSLATOR_TIMEOUT` | `900` | Espera del traductor dentro del ciclo (s). Es mayor que `NA_TRANSLATOR_TIMEOUT` (120 s, Redacción) porque el lote de una noticia superó los 120 s en la GTX 1060 (primer intento de medición) |
| `NA_TRANSLATOR_URL` | vacío | **Obligatoria para publicar**: sin BiTAM, las noticias quedan en cola (`pendiente`) |

El intervalo (apagado, 15 min, 30 min, 1 h, 3 h o 6 h) y las noticias por ciclo (de 1 a 5; 3 por defecto) se
cambian desde la PWA, o con `PUT /api/feed/config`, y se guardan en la base de datos.

## API (pública, como todo desde QuitarAdmin)

| Ruta | Respuesta |
|---|---|
| `GET /api/feed/status` | `habilitado`, `intervalo_min`, `ejecutando`, `ultima_ejecucion`, `proxima_ejecucion`, `ultimo_resultado` (nuevas, publicadas, errores, pendientes, `motivo`, duración) y conteo de ítems por estado |
| `PUT /api/feed/config` `{intervalo_min?, max_por_ciclo?}` | El estado actualizado; 422 si el valor no está permitido |
| `POST /api/feed/run` | 202 si arranca el ciclo; 409 si ya hay uno en curso; 503 si la función está apagada |
| `GET /api/catalog?orden=recientes` | El catálogo de siempre, ordenado de lo más reciente a lo más antiguo, con `traduccion_automatica`, `fuente_url` y `fuente_nombre` |

El castellano guardado (`titulo_es`, `cuerpo_es` y el texto de `FeedItem`) **nunca** sale por la API.

## Qué pasa cuando algo falla

| Situación | Comportamiento |
|---|---|
| TV Perú no responde, devuelve un error o cambia el formato | No se registra nada nuevo; en el estado queda «TV Perú: …». Se reintenta en el próximo ciclo |
| BiTAM apagado o sin `NA_TRANSLATOR_URL` | Las noticias quedan `pendiente` y no se publica nada (nunca se muestra castellano como si fuera asháninka). El estado dice «traductor no disponible» |
| Error de traducción o del pipeline | La noticia pasa a `error` y se reintenta; al tercer intento, a `descartada` |
| Noticia sin texto (solo vídeo o galería) | `descartada` al registrarla |
| Nombres propios en castellano en la salida | Esos segmentos quedan como «solo texto», sin audio (P2d), igual que en el resto del sistema |
| Dos peticiones de «Refrescar ahora» a la vez | La segunda responde 409 |

## Despliegue

- El traductor **no forma parte de Docker** (necesita GPU y sus pesos no son redistribuibles). En producción, sin
  `NA_TRANSLATOR_URL` apuntando a un servicio BiTAM accesible, los ciclos descargan las noticias pero no publican
  ninguna.
- Con varios procesos de uvicorn habría un planificador por proceso. El despliegue usa uno solo y, aunque hubiera
  varios, el candado evita los ciclos simultáneos solo dentro de cada proceso; la tabla `FeedItem` (con `guid`
  único) evita duplicados.
- `robots.txt` de TV Perú pide `Crawl-delay: 10`: el lector hace una sola petición por ciclo, y el intervalo
  mínimo es de 15 minutos.

## Medición

Definida antes de medir en `docs/metrics.md` (sección «Noticias automáticas de TV Perú») y ejecutada con
`uv run python -m eval.tvperu.run` → `eval/results/tvperu.json`. Resultados: ver «Resultados medidos» abajo.

## Limitaciones

Ver los puntos 78 a 81 de `docs/limitations.md`:

- 78: traducción sin revisar;
- 79: dependencia del formato del feed;
- 80: licencia de reutilización no verificada;
- 81: solo se traduce un resumen y se pierden nombres propios.

## Resultados medidos (2026-11-02, `eval/results/tvperu.json`)

Un ciclo real con BiTAM (GTX 1060, fp16), la voz `mms_vits` en CPU y sin otra carga, con lo definido en `docs/metrics.md`:

| Noticia (categoría) | Enviado a BiTAM | Traducción | s/oración | Síntesis | Segmentos (con audio / bloqueados) | Audio |
|---|---|---|---|---|---|---|
| cultural | 12 oraciones, 2.007 car. | 315 s | 24,3 | 41 s (carga en frío) | 9 (8 / 1) | 150 s |
| política | 12 oraciones, 1.776 car. | 198 s | 15,3 | 17 s | 9 (5 / 4) | 78 s |
| nacionales | 10 oraciones, 1.950 car. | 341 s | 31,0 | 19 s | 8 (4 / 4) | 84 s |

- **Ciclo completo: 933 s (≈ 15,5 min)** para 3 noticias. 15 nuevas en el feed: 3 publicadas y 12 en cola. Sin errores.
- **Audio:** 17 de 26 segmentos con voz (65 %); 9 bloqueados para TTS, que quedan como «solo texto».
- Hay menos segmentos que oraciones enviadas (26 frente a 34) porque BiTAM a veces pierde el punto final y une oraciones (limitación 73).
- **El cuello de botella es la traducción en lote:** de 15 a 31 s/oración, cuando una oración suelta tardó 6,4 s en la misma GPU justo antes de medir. La síntesis es mucho más rápida (17–41 s por noticia).
- **Primer intento** (`tvperu_intento1.json`): 0 publicadas, porque la primera traducción superó los 120 s de espera del cliente. Por eso existe `NA_FEED_TRANSLATOR_TIMEOUT` (900 s). Ver la revisión en `docs/metrics.md`.

**Consecuencia práctica:** con esta GPU, un ciclo de 3 noticias tarda unos 15 minutos, así que el intervalo de 15 min queda justo. Use 30 min o más, o baje a 1–2 noticias por ciclo. **Pendiente** (no se ajustó tras ver los datos): traducir en lotes pequeños dentro del ciclo y medirlo con otra ejecución.
