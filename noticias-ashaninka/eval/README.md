# Evaluación (Fase 1)

Todos los números de `eval/results/` provienen de ejecuciones reales de estos scripts.

| Script | Qué mide | Salida |
|---|---|---|
| `eval/fase1/run.py` | Categorías, % sin resolver, marcas editoriales, palabras fuera del vocabulario MMS antes y después del adaptador, latencia por etapa, estado de las reglas | `eval/results/fase_1.json` |
| `eval/fase1/mms_orthography/run.py` | Experimento 1.9: CER de ida y vuelta TTS→ASR por hipótesis del adaptador | `eval/results/mms_orthography.json`, `docs/mms_orthography.md` |
| `eval/listening/rewrite_check/build.py` | Material de la escucha 1.8 | `eval/listening/rewrite_check/hoja_escucha.csv` (+ `audio/`) |
| `eval/listening/enye_ab/build.py` | Escucha A/B a ciegas de palabras con ñ (H1 `ny`, H2 `y`, H3 `n`): 20 palabras, 60 pares y 4 controles | `eval/listening/enye_ab/out/kit_escucha_enye.zip` (para la persona oyente, sin la clave) |
| `eval/listening/enye_ab/score.py` | Puntúa esa escucha: controles, victorias por par, prueba binomial exacta y tasa de victoria por posición de la ñ | `eval/results/escucha_enye_<oyente>.json` |
| `eval/fase2/tokenization/run.py` | Tokenización de la entrada de MMS: T1 (VitsTokenizer) frente a T2 (intercalado manual) | `eval/results/fase_2_tokenizacion.json`, `docs/tokenization.md` |
| `eval/rtf_ttfa/bench.py` | RTF, carga en frío, barrido hilos × trabajadores, TTFA HTTP (servidor, cliente y por lotes) con 1/4/8 clientes, rendimiento y RAM | `eval/results/fase_2_rendimiento.json`, `docs/figures/` |
| `eval/fase2/sizing.py` | Dimensionamiento del servidor | `docs/sizing.md` |
| `eval/fase2/intelligibility/run.py` | CER de ida y vuelta por motor sobre el split test | `eval/results/fase_2_inteligibilidad.json`, `docs/intelligibility.md` |
| `eval/fase2/run.py` | Reúne las métricas de la Fase 2 | `eval/results/fase_2.json` |
| `eval/fase1/p5_sample.py` | Lista de 200 palabras para el conjunto de referencia P5 | `eval/fase1/p5_sample.csv` |

## Guía para la persona hablante

1. **Escucha de la reescritura (1.8):** abre `rewrite_check/hoja_escucha.csv`. En cada fila marcada como `listo`, escucha el audio de la columna `audio` y escribe `aceptable` o `no_aceptable` según si suena como lo diría un hablante bilingüe. Las filas `bloqueado (P2d)` no tienen audio todavía.
2. **Escucha A/B (1.9):** abre `fase1/mms_orthography/out/escucha_ab.csv`. En cada fila escucha `audio_A` y `audio_B` (sin saber cuál es cuál) y escribe `A`, `B` o `igual` según cuál se entiende mejor. La clave está en `escucha_ab_clave.csv`: no la abras antes de terminar.
3. **Escucha de la ñ:** envía `enye_ab/out/kit_escucha_enye.zip`; las instrucciones van dentro (`INSTRUCCIONES.md`). Con el archivo devuelto: `uv run python -m eval.listening.enye_ab.score respuestas_escucha_enye.csv --oyente O1`.
4. **Transcripción P5:** en `fase1/p5_sample.csv`, completa la columna `transcripcion_fonemica` (IPA) de cada palabra.

Las carpetas de audio no se versionan: se regeneran con los scripts, que usan semillas fijas.
