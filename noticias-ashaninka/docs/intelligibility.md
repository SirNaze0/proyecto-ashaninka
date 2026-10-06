# Inteligibilidad objetiva por motor (tarea 2.10)

> GENERADO por `uv run python -m eval.fase2.intelligibility.run`. No editar a mano.
> Fecha: 2026-10-06T04:56:12+00:00 · commit `cb42a79` · adaptador `mms_cni/H1` · tokenización MMS `manual`.

Método: TTS → `mms-1b-all` (adaptador `cni`) → CER en el espacio canónico. Muestra fija del split **test** (primera vez que se usa).

| Medida | Valor |
|---|---|
| test_total | 1003 |
| elegibles | 725 |
| muestra | 200 |
| semilla | 20261007 |

| Motor | CER | IC 95 % | Precisión por palabra |
|---|---|---|---|
| mms_vits | 0.0516 | [0.0459, 0.0573] | 0.6474 |
| espeak_ng | no_medido (eSpeak-NG no instalado) | | |

## Sesgo y limitaciones

El ASR de MMS comparte datos con el TTS de MMS: la comparación favorece a mms_vits.
La línea base eSpeak lee la ortografía asháninka con la voz castellana: es una referencia ingenua, no un TTS asháninka. Su audio se remuestrea a 16 kHz por interpolación lineal.
