# Tokenización de la entrada de mms-tts-cni (tarea 2.2b)

> GENERADO por `uv run python -m eval.fase2.tokenization.run`. No editar a mano.
> Fecha: 2026-10-06T03:30:46+00:00 · commit `fa86a5c` · adaptador `mms_cni/H1`.

## Hallazgo

El blanco de MMS es la letra `a` (id 0). `VitsTokenizer` (transformers 4.46 y 5.18) la trata como token especial y rompe el intercalado de blancos cuando hay `aa` o una `a` inicial o final: por ejemplo, `a` se tokeniza `[0]` en vez de `[0, 0, 0]`.
En la muestra, 48 de 100 oraciones están afectadas.

## Resultados

| Condición | Modo | CER canónico | IC 95 % | Precisión por palabra | Duración media (s) |
|---|---|---|---|---|---|
| T1 | hf | 0.0586 | [0.0509, 0.0664] | 0.6183 | 6.279 |
| T2 | manual | 0.0553 | [0.0479, 0.0632] | 0.6321 | 6.284 |

Diferencia pareada T2 − T1: -0.0034 (IC 95 % [-0.0065, -0.0001], p = 0.046).

## Decisión

Regla fijada antes de ejecutar: se adopta T2 salvo que T1 sea significativamente mejor.

**T2**: T2 reduce el CER de forma significativa.

Limitación: el TTS y el ASR de MMS comparten datos de entrenamiento (consistencia, no inteligibilidad humana).
