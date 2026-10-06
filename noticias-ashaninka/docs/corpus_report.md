# Informe del corpus AmericasNLP 2021 asháninka–castellano

> GENERADO por `uv run python -m app.cli corpus report`. No editar a mano.
> Corpus: commit `d3f519c` (hashes verificados). Vocabulario: `facebook/mms-tts-cni@a744890`.

## Medidas por split

| Medida | train | dev | test |
|---|---|---|---|
| Oraciones | 3883 | 883 | 1003 |
| Caracteres (sin espacios) | 232494 | 53401 | 55113 |
| Tokens (`\w+`) | 26145 | 6086 | 6453 |
| Tipos (minúsculas) | 10231 | 2686 | 2899 |
| % caracteres fuera del vocabulario MMS | 13.46 | 10.87 | 11.2 |
| % palabras con ≥1 carácter fuera del vocabulario MMS | 60.3 | 53.0 | 53.7 |
| Líneas con dígitos | 338 | 94 | 71 |

## Vocabulario de mms-tts-cni

`␠ ' - 0 1 2 3 4 5 6 7 8 9 a c e h i j m n o p q r s t u v y |`

## Caracteres fuera del vocabulario más frecuentes (train)

| Carácter | Apariciones |
|---|---|
| `k` | 16185 |
| `.` | 3554 |
| `,` | 3453 |
| `b` | 2237 |
| `z` | 1851 |
| `ñ` | 1495 |
| `”` | 442 |
| `“` | 440 |
| `:` | 439 |
| `;` | 202 |
| `°` | 128 |
| `?` | 125 |
| `)` | 114 |
| `(` | 101 |
| `l` | 100 |
| `!` | 66 |
| `d` | 58 |
| `ó` | 37 |
| `g` | 28 |
| `f` | 27 |

## Variación ortográfica (recuentos en el texto en minúsculas)

| Par | train | dev | test |
|---|---|---|---|
| `b/v` | 2237 / 1897 | 620 / 30 | 519 / 44 |
| `ts/tz` | 4133 / 1819 | 1339 / 0 | 1172 / 0 |
| `k/c(?!h)` | 16185 / 122 | 3479 / 59 | 3484 / 172 |
| `k/qu` | 16185 / 11 | 3479 / 1 | 3484 / 5 |
| `ñ/ny` | 1495 / 3 | 51 / 4 | 157 / 0 |

## Conservación de dígitos al traducir (train)

337 de 340 líneas castellanas con dígitos también tienen dígitos en asháninka.

## Frecuencia de letras (train)

`a` 44749, `i` 37495, `t` 20482, `o` 18460, `r` 17438, `n` 16604, `k` 16185, `e` 11737, `s` 8295, `p` 5763, `m` 5084, `y` 4889, `h` 3791, `j` 2719, `b` 2237, `v` 1897, `z` 1851, `ñ` 1495, `c` 1033, `u` 144, `l` 100, `d` 58, `ó` 37, `g` 28, `f` 27, `á` 22, `í` 13, `q` 11, `º` 9, `ú` 6, `w` 6, `é` 5, `x` 4, `à` 1

## Comparación con PLAN_DESARROLLO.md v1.2 §3.2

Ninguna diferencia: las mediciones coinciden con las publicadas en el plan.
