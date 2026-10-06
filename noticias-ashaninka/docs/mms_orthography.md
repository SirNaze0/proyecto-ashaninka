# Experimento de ortografía MMS (tarea 1.9, P6)

> GENERADO por `uv run python -m eval.fase1.mms_orthography.run`. No editar a mano.
> Fecha: 2026-10-06T02:23:48+00:00 · commit `949d031` · semilla 20261005 · bootstrap 1000.

## Método

Texto canónico (normalizador, sin candidatos) → adaptador de la hipótesis → `mms-tts-cni` → `mms-1b-all` (adaptador `cni`) → inversa MMS→canónica → CER contra la entrada. H0 no adapta: `VitsTokenizer` elimina en silencio los caracteres desconocidos.

## Muestra

| Medida | Valor |
|---|---|
| dev_total | 883 |
| bloqueadas_sin_p2d | 149 |
| fuera_de_rango_longitud | 13 |
| elegibles | 721 |
| muestra | 4 |

## Resultados

| Hipótesis | CER canónico | IC 95 % | CER espacio MMS | Precisión por palabra |
|---|---|---|---|---|
| H0 | 0.1152 | [0.0836, 0.1768] | 0.1383 | 0.3404 |
| H1 | 0.0782 | [0.0492, 0.1446] | 0.0741 | 0.4681 |
| H2 | 0.0658 | [0.0369, 0.124] | 0.0566 | 0.4894 |
| H3 | 0.0761 | [0.0346, 0.1488] | 0.0667 | 0.4681 |

### Recuperación por carácter conflictivo (proxy por recuento)

| Hipótesis | k | b | ñ | ts |
|---|---|---|---|---|
| H0 | 0.0 | 0.0 | 0.0 | 1.0 |
| H1 | 0.9091 | 1.0 | 0.0 | 1.0 |
| H2 | 0.9545 | 1.0 | 0.0 | 1.0 |
| H3 | 0.9091 | 1.0 | 0.0 | 1.0 |

### Consistencia en palabras con ñ (espacio MMS de cada hipótesis)

| Hipótesis | Palabras con ñ | Consistencia |
|---|---|---|
| H0 | 4 | 0.0 |
| H1 | 4 | 0.0 |
| H2 | 4 | 0.25 |
| H3 | 4 | 0.5 |

### Comparación pareada frente a la hipótesis activa (H1)

| Hipótesis | Diferencia de CER | IC 95 % | p |
|---|---|---|---|
| H2 | -0.0122 | [-0.0183, -0.0043] | 0.008 |
| H3 | 0.0012 | [-0.0135, 0.026] | 1.0 |

## Decisión

Regla (fijada antes de ejecutar): cambiar la hipótesis activa solo si el IC 95 % pareado frente a la activa excluye 0 a favor de la candidata Y la candidata tiene mayor consistencia en palabras con ñ.

Hipótesis con menor CER canónico: H2. Hipótesis elegida: **H2**.
Diferencia pareada de CER (H2 − H0): -0.0491 (IC 95 % [-0.061, -0.0346], p < 0.001 (ningún remuestreo cruza 0)).

Escucha A/B con hablante: pendiente_hablante.

## Limitación

TTS y ASR de MMS comparten datos de entrenamiento: la prueba mide consistencia, no inteligibilidad humana.
