# Resumen de la Fase 2: Síntesis de voz, interfaz intercambiable y medición de RTF/TTFA

> **Proyecto:** Servicio web de noticias en lengua asháninka con síntesis de voz, texto y avatar
> **Fecha:** 2026-10-06 · **Repositorio:** `Proyecto` (código en `noticias-ashaninka/`) · **Base:** etiqueta `fase1`
> **Estado:** implementada, **pendiente de aprobación**. La meta de TTFA bajo demanda **no se cumple** con la configuración principal (ver §3).

Todas las cifras de este documento vienen de ejecuciones reales. Están en `eval/results/fase_2.json`
y en los archivos `fase_2_*.json` de esa carpeta. Las definiciones de las métricas se escribieron
antes de medir, en `docs/metrics.md`.

---

## 1. Qué hace el sistema hoy

Además de normalizar la noticia (Fase 1), el sistema **la convierte en voz**:

1. Cada oración lista para el TTS se sintetiza con el motor elegido. Las oraciones bloqueadas (sin P2d) **no se sintetizan** y se entregan solo como texto.
2. El audio se codifica en **Opus** (principal) y **MP3** (respaldo) y se guarda en una **caché por contenido**: el mismo texto no se vuelve a sintetizar.
3. Cada audio lleva sus metadatos: modelo, revisión, licencia, uso comercial, variante, aviso de voz sintética, semilla y RTF.
4. Se guardan las **duraciones reales** que usó el modelo y se proyectan sobre el texto original. Son la base del resaltado sincronizado y de la sincronía labial.
5. Se entrega de dos maneras:
   - **por lotes:** un manifiesto por noticia y archivos estáticos;
   - **bajo demanda:** un stream NDJSON que envía cada oración en cuanto está lista.

```
segmento listo ─► motor TTS (mms_vits | espeak_ng | fake) ─► WAV + duraciones verificadas
               ─► Opus/MP3 + metadatos en caché (static/audio/…) ─► manifiesto + tiempos por fragmento
               ─► /static (por lotes)  ·  /api/synthesize/{id} (streaming NDJSON)
```

---

## 2. Qué se implementó

| Tarea | Componente | Dónde está |
|---|---|---|
| 2.0 | Etiqueta `fase1`; `pre-commit` desde la raíz de `Proyecto`; `init.sh` detecta el repositorio y eSpeak-NG; opción `--with-tts` | `.pre-commit-config.yaml`, `init.sh`, `scripts/venv_exec.sh` |
| 2.1 | Interfaz `TTSEngine`, `FakeEngine` y registro de motores con un solo parámetro (`NA_TTS_ENGINE`), con un pool de instancias | `backend/app/pipeline/tts/` |
| 2.2 | `MmsVitsEngine` con hook de duraciones verificado en cada síntesis | `pipeline/tts/mms_vits.py` |
| 2.2b | Experimento de tokenización (hallazgo nuevo, ver §3) | `eval/fase2/tokenization/`, `docs/tokenization.md` |
| 2.3 | `ESpeakEngine`: línea base GPL en modo `texto-es`; el modo por fonemas queda deshabilitado sin P1 | `pipeline/tts/espeak.py` |
| 2.4–2.5 | Metadatos, Opus/MP3, caché por contenido, manifiesto con JSON Schema, tiempos por fragmento | `backend/app/audio.py`, `backend/app/batch/`, `docs/manifest_schema.md` |
| 2.6 | Modo por lotes idempotente; tablas `AudioAsset` y `SynthesisRun` | `python -m app.batch` |
| 2.7 | Streaming NDJSON, `/static` con soporte de `Range`, límites 413 y 503, precarga opcional | `backend/app/api/synthesize.py` |
| 2.8 | Banco de pruebas: RTF, barrido, TTFA HTTP, rendimiento, RAM y figuras | `eval/rtf_ttfa/`, `docs/figures/` |
| 2.9 | Dimensionamiento del servidor | `eval/fase2/sizing.py`, `docs/sizing.md` |
| 2.10 | CER de ida y vuelta sobre el split **test** | `eval/fase2/intelligibility/`, `docs/intelligibility.md` |
| 2.11 | Pruebas: contrato de motores, hook, caché, manifiesto, streaming y límites. 89 pasan, 1 se omite (eSpeak no instalado); cobertura 96,5 % | `backend/tests/` |

---

## 3. Resultados

### Hallazgo: el tokenizador de Hugging Face rompe la entrada de MMS

En MMS, el token blanco es la **letra `a`** (id 0). `VitsTokenizer` (igual en transformers 4.46 y
5.18) la trata como token especial y rompe el intercalado de blancos cuando hay `aa` (frecuente en
asháninka) o una `a` al inicio o al final. Afectaba a **48 de 100** oraciones. Experimento con una
regla fijada antes de ejecutar:

| Condición | CER | IC 95 % |
|---|---|---|
| T1: VitsTokenizer (lo usado en la Fase 1) | 0,0586 | [0,0509; 0,0664] |
| T2: intercalado manual de VITS | **0,0553** | [0,0479; 0,0632] |

La diferencia es −0,0034 (IC 95 % [−0,0065; −0,0001], p = 0,046). **Se adoptó T2.** El efecto es
pequeño y está al borde de la significancia. T1 reproduce exactamente el CER de la Fase 1.

### Velocidad de síntesis (RTF, `mms_vits`, CPU AMD de 16 núcleos)

| Medida | Valor |
|---|---|
| RTF (100 segmentos, en caliente) | **0,19** (DE 0,007; p95 0,20) → meta RTF < 1 **cumplida** |
| Carga del modelo en frío | 7,7 s |
| Duraciones verificadas | 50 de 50 oraciones con desfase de 0 frames |

### Barrido de configuración (segundos de audio por segundo)

| Hilos \ Trabajadores | 1 | 2 | 4 |
|---|---|---|---|
| 1 | 2,00 | 2,68 | 4,70 |
| 4 | 3,82 | 6,32 | **8,68** |
| 8 | 5,27 | 6,56 | 6,82 |
| 16 | 5,09 | 5,54 | 6,50 (RTF p95 1,05) |

Configuración por defecto, elegida con la regla fijada antes de medir (mayor rendimiento con RTF p95 < 1): **4 hilos × 4 trabajadores**.

### Tiempo hasta el primer audio (TTFA del cliente, p95; 100 pseudo-noticias de 300–500 caracteres)

| Modo | 1 cliente | 4 clientes | 8 clientes |
|---|---|---|---|
| Bajo demanda, configuración principal (4 × 4) | **2357 ms** ✗ | 5067 ms | 8559 ms |
| Bajo demanda, configuración de latencia (8 × 1), análisis secundario | 1875 ms ✓ | 5947 ms | 10391 ms |
| **Por lotes** (noticia ya sintetizada) | **44 ms** ✓ | 49 ms ✓ | 66 ms ✓ |

- **La meta TTFA p95 < 2 s no se cumple bajo demanda con la configuración principal.** Causa: el TTFA depende casi por completo de la duración de la **primera oración**, que mide entre 5,5 s de media y 15,5 s en el p99. Con 1 cliente, el 90 % de las solicitudes queda por debajo de 2 s, y si la primera oración dura 5 s o menos el p95 baja a 1064 ms.
- **La configuración de latencia sí cumple con 1 cliente**, pero rinde menos con carga.
- **Con 4 u 8 clientes simultáneos no se cumple en ninguna configuración.**
- **El modo por lotes cumple holgadamente.** Es el modo principal que prevé el plan.
- **Rendimiento máximo:** 9,5 s de audio por segundo. **RAM pico:** 1,06 GB con 1 trabajador y 2,16 GB con 4.

### Inteligibilidad objetiva (CER de ida y vuelta, split **test**, 200 oraciones)

| Motor | CER | IC 95 % | Precisión por palabra |
|---|---|---|---|
| `mms_vits` (H1 + T2) | **0,0516** | [0,0459; 0,0573] | 0,647 |
| `espeak_ng` | no medido (eSpeak-NG no instalado) | | |

### Otros resultados

| Medida | Valor |
|---|---|
| Opus (objetivo 24 kbps) | 25,8 kbps reales (3,2 KB por segundo de audio) |
| MP3 | 33,4 kbps reales |
| Segmentos de dev con audio | 83,4 % (el resto queda bloqueado por falta de P2d) |
| Noticias completas (todas sus oraciones con audio) | 83,1 % |

### Dimensionamiento (propuesta para el §7 del plan)

**Piloto por lotes:** con hasta 50 noticias por día servidas como archivos estáticos, bastan
**2 vCPU y 2 GB de RAM, sin GPU**, con `NA_TTS_WORKERS=1`. Con 500 noticias por día harían falta
7 vCPU para terminar la síntesis en menos de 1 hora. El modo bajo demanda queda como respaldo para
noticias aún no sintetizadas. Detalle en `docs/sizing.md`.

---

## 4. Cómo se usa

Comandos en Git Bash dentro de `Proyecto/noticias-ashaninka`.

### Instalar o actualizar

```bash
./init.sh --with-tts      # dependencias, modelo de voz y verificación de eSpeak-NG
./init.sh --check         # verifica todo (código 0)
```

eSpeak-NG se instala aparte, con el MSI oficial en Windows. Hoy no está instalado.

### Elegir el motor y la configuración (`.env`)

| Variable | Valores | Por defecto |
|---|---|---|
| `NA_TTS_ENGINE` | `mms_vits` (principal, **no comercial**) · `espeak_ng` (línea base GPL) · `fake` (pruebas) | `mms_vits` |
| `NA_TORCH_THREADS` / `NA_TTS_WORKERS` | hilos de torch / síntesis simultáneas | 4 / 4 (servidor pequeño: workers = 1; menor TTFA: 8 / 1) |
| `NA_MMS_TOKENIZATION` | `manual` (T2) · `hf` | `manual` |
| `NA_MMS_ADAPTER` | `H1`, `H2`, `H3`… | `H1` |
| `NA_OPUS_KBPS` | tasa objetivo de Opus | 24 |
| `NA_TTS_PRELOAD` | cargar el modelo al iniciar el servidor | `false` (en producción, `true`) |

### Modo por lotes

```bash
uv run python -m app.cli import data/news/          # o: import --from-corpus dev --limit 20
uv run python -m app.batch build --all              # sintetiza o reutiliza y escribe los manifiestos
uv run python -m app.batch build --news 3 --engine espeak_ng
```

Volver a ejecutarlo no repite trabajo: reutiliza la caché e informa cuántos segmentos sintetizó y
cuántos reutilizó.

### Servidor y modo bajo demanda

```bash
NA_TTS_PRELOAD=true uv run uvicorn app.main:app
```

| Ruta | Para qué |
|---|---|
| `GET /api/synthesize/{id}` | Stream NDJSON: `meta` → un `segment` o `blocked` por oración → `done` |
| `GET /static/news/{id}/manifest.json` | Manifiesto de la noticia: audios, duraciones, avisos y licencia |
| `GET /static/audio/…/<clave>.opus` · `.mp3` | Audio, con soporte de `Range` para descargas reanudables |
| `GET /static/news/{id}/seg_NNN.json` | Tiempos de cada fragmento original, para el resaltado |

### Evaluación

```bash
uv run python -m eval.fase2.tokenization.run        # T1 frente a T2
uv run python -m eval.rtf_ttfa.bench all            # rendimiento (~1 h, en segundo plano)
uv run python -m eval.fase2.sizing                  # dimensionamiento
uv run python -m eval.fase2.intelligibility.run     # CER sobre test
uv run python -m eval.fase2.run                     # -> eval/results/fase_2.json
```

---

## 5. Criterios de cierre

| Criterio | Estado |
|---|---|
| RTF < 1 y TTFA p95 < 2 s medidos | RTF **cumple** (0,19). TTFA bajo demanda **no cumple** con la configuración principal (2357 ms); sí con la de latencia (1875 ms) y en modo por lotes (44 ms). Reportado con su causa |
| Motores intercambiables con un parámetro y pruebas de contrato | **Cumple** (`NA_TTS_ENGINE`). eSpeak queda `no_medido` porque no está instalado |
| CER de ida y vuelta por motor sobre test | `mms_vits` **cumple** (0,0516). eSpeak pendiente de instalación |
| Hook de duraciones verificado en ≥ 50 oraciones | **Cumple** (50/50, desfase 0) |
| Modo por lotes idempotente y streaming con caché compartida | **Cumple** |
| Manifiestos válidos con avisos | **Cumple** (JSON Schema + pruebas) |
| Ningún segmento bloqueado se sintetiza; disponibilidad reportada | **Cumple** (83,4 %) |
| Documentación (`metrics`, `sizing`, `manifest_schema`, `intelligibility`, `limitations`, `LICENSES`) | **Cumple** |
| `pre-commit` activo desde la raíz y `init.sh --check` con código 0 | **Cumple** |

## 6. Pendientes que se arrastran

| Pendiente | Impacto | Acción |
|---|---|---|
| **eSpeak-NG sin instalar** | Falta la línea base (RTF y CER de eSpeak) | Instalar el MSI y ejecutar `bench rtf` y `intelligibility.run` (unos 15 min) |
| **TTFA bajo demanda > 2 s** | La meta solo se cumple en modo por lotes o con 1 usuario en la configuración de latencia | Decidir si el bajo demanda es solo respaldo, o probar a sintetizar la primera oración por cláusulas (afecta la prosodia; habría que medirlo) |
| **Escritura de la `ñ`** | Pendiente de la escucha A/B con un hablante | Aplicar `kit_escucha_enye.zip` |
| **P1, P2d, P2a–P2c, P5** | Sin fonemas reales (visemas de la Fase 3) y el 16,6 % de los segmentos sin audio | Lingüista, hablantes, compañera |
| **Variante dialectal de la voz** | No documentada | Declarada en los metadatos; confirmar con hablantes |

Las limitaciones completas están en `noticias-ashaninka/docs/limitations.md` (puntos 17 a 25, nuevos en esta fase).
