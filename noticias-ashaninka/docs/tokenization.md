# Tokenización de la entrada de mms-tts-cni (tarea 2.2b)

> GENERADO por `uv run python -m eval.fase2.tokenization.run`. No editar a mano.
> Fecha: 2026-10-06T03:19:22+00:00 · commit `27a76f6` · adaptador `mms_cni/H1`.

## Hallazgo

El blanco de MMS es la letra `a` (id 0). `VitsTokenizer` (transformers 4.46 y 5.18) la trata como token especial y rompe el intercalado de blancos cuando hay `aa` o una `a` inicial o final: por ejemplo, `a` se tokeniza `[0]` en vez de `[0, 0, 0]`.
En la muestra, 3 de 3 oraciones están afectadas.

## Resultados

| Condición | Modo | CER canónico | IC 95 % | Precisión por palabra | Duración media (s) |
|---|---|---|---|---|---|
| T1 | hf | 0.1184 | [0.0938, 0.1795] | 0.3704 | 6.928 |
| T2 | manual | 0.1096 | [0.0781, 0.1538] | 0.4815 | 7.008 |

Diferencia pareada T2 − T1: -0.0109 (IC 95 % [-0.0256, 0.0], p = 0.076).

## Decisión

Regla fijada antes de ejecutar: se adopta T2 salvo que T1 sea significativamente mejor.

**T2**: sin diferencia significativa; T2 da correspondencia exacta token-carácter.

Limitación: el TTS y el ASR de MMS comparten datos de entrenamiento (consistencia, no inteligibilidad humana).
