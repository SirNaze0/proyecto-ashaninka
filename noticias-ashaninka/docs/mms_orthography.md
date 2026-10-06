# Experimento de ortografía MMS (tarea 1.9, P6)

> GENERADO por `uv run python -m eval.fase1.mms_orthography.run`. No editar a mano.
> Fecha: 2026-10-06T02:45:51+00:00 · commit `eadad12` · semilla 20261005 · bootstrap 1000.

## Método

Texto canónico (normalizador, sin candidatos) → adaptador de la hipótesis → `mms-tts-cni` → `mms-1b-all` (adaptador `cni`) → inversa MMS→canónica → CER contra la entrada. H0 no adapta: `VitsTokenizer` elimina en silencio los caracteres desconocidos.

## Muestra

| Medida | Valor |
|---|---|
| dev_total | 883 |
| bloqueadas_sin_p2d | 149 |
| fuera_de_rango_longitud | 13 |
| elegibles | 721 |
| muestra | 100 |

## Resultados

| Hipótesis | CER canónico | IC 95 % | CER espacio MMS | Precisión por palabra |
|---|---|---|---|---|
| H0 | 0.1499 | [0.1381, 0.1621] | 0.1734 | 0.2918 |
| H1 | 0.0586 | [0.0509, 0.0664] | 0.0555 | 0.6183 |
| H2 | 0.0579 | [0.0502, 0.0659] | 0.0534 | 0.6252 |
| H3 | 0.057 | [0.0492, 0.0658] | 0.0519 | 0.6238 |

### Recuperación por carácter conflictivo (proxy por recuento)

| Hipótesis | k | b | ñ | ts |
|---|---|---|---|---|
| H0 | 0.0483 | 0.1429 | 0.0 | 1.0 |
| H1 | 0.9796 | 0.8182 | 0.0 | 0.994 |
| H2 | 0.9771 | 0.8312 | 0.0 | 0.982 |
| H3 | 0.9796 | 0.8182 | 0.0 | 0.994 |

### Consistencia en palabras con ñ (espacio MMS de cada hipótesis)

| Hipótesis | Palabras con ñ | Consistencia |
|---|---|---|
| H0 | 26 | 0.0 |
| H1 | 26 | 0.0 |
| H2 | 26 | 0.1923 |
| H3 | 26 | 0.4615 |

### Comparación pareada frente a la hipótesis activa (H1)

| Hipótesis | Diferencia de CER | IC 95 % | p |
|---|---|---|---|
| H2 | -0.0008 | [-0.0034, 0.0025] | 0.606 |
| H3 | -0.0016 | [-0.0046, 0.0013] | 0.272 |

## Decisión

Regla (fijada antes de ejecutar): cambiar la hipótesis activa solo si el IC 95 % pareado frente a la activa excluye 0 a favor de la candidata Y la candidata tiene mayor consistencia en palabras con ñ.

Hipótesis con menor CER canónico: H3. Hipótesis elegida: **H1**.
Diferencia pareada de CER (H1 − H0): -0.0915 (IC 95 % [-0.102, -0.0806], p < 0.001 (ningún remuestreo cruza 0)).

Escucha A/B con hablante: pendiente_hablante.

## Limitación

TTS y ASR de MMS comparten datos de entrenamiento: la prueba mide consistencia, no inteligibilidad humana.
