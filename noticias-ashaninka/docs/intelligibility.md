# Inteligibilidad objetiva por motor (tarea 2.10)

> GENERADO por `uv run python -m eval.fase2.intelligibility.run`. No editar a mano.
> Fecha: 2026-10-13T00:10:17+00:00 · commit `965c822` · adaptador `mms_cni/H1` · tokenización MMS `manual`.

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
| espeak_ng | 0.2291 | [0.2203, 0.2382] | 0.0511 |

Diferencia pareada mms_vits − espeak_ng: -0.1779 (IC 95 % [-0.1888, -0.167], p = 0.0).

## Sesgo y limitaciones

El ASR de MMS comparte datos con el TTS de MMS: la comparación favorece a mms_vits.
La línea base eSpeak lee la ortografía asháninka con la voz castellana: es una referencia ingenua, no un TTS asháninka. Su audio se remuestrea a 16 kHz por interpolación lineal.
