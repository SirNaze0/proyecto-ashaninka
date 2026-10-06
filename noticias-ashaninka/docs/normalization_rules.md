# Reglas de normalización y recursos lingüísticos

> GENERADO por `uv run python -m app.cli build-docs`. No editar a mano: editar los YAML.

Estados: **validado** (aprobado por persona experta) · **candidato-corpus** (evidencia del
corpus AmericasNLP, sin validar) · **SUPUESTO-LING** / **SUPUESTO** (decisión provisional
o condición experimental, pendiente de validación).

## Resumen

| Estado | Entradas |
|---|---|
| SUPUESTO | 8 |
| SUPUESTO-LING | 4 |
| candidato-corpus | 20 |
| validado | 7 |

| Recurso | Archivo | SHA-256 | Entradas por estado |
|---|---|---|---|
| orthography_variants | `orthography_variants.yaml` | `0f4873afc328` | SUPUESTO-LING=4 |
| numerals_cni | `numerals_cni.yaml` | `9cf65682f71f` | vacío |
| acronyms | `acronyms.yaml` | `3467a8984828` | vacío |
| loanwords | `loanwords.yaml` | `056ea637e0c3` | vacío |
| es_to_cni_phonology | `es_to_cni_phonology.yaml` | `e153748cb35b` | vacío |
| neologisms | `neologisms.yaml` | `520ab95a6996` | vacío |
| proper_nouns | `proper_nouns.yaml` | `2fe2580bafba` | vacío |
| relative_dates | `relative_dates.yaml` | `56376d6f1315` | vacío |
| segmentation | `segmentation.yaml` | `59af92803b03` | vacío |
| g2p_inventory | `inventory.yaml` | `edf6ca3fda4d` | candidato-corpus=20 |
| g2p_cni_rules | `cni.yaml` | `bab12e52dc57` | vacío |
| mms_cni_adapter | `mms_cni.yaml` | `498fbc9edf0a` | SUPUESTO=8, validado=7 |

## orthography_variants

Unificación de variantes de escritura hacia la ortografía canónica (k, b, ts, ñ)

| id | Descripción | Patrón / forma | Reemplazo | Ejemplo | Fuente | Estado |
|---|---|---|---|---|---|---|
| ORT-001 | tz -> ts (ts es la forma mayoritaria) | `tz` | `ts` |  | Decisión del tesista 2026-10-05; frecuencias AmericasNLP2021@d3f519c (ver docs/corpus_report.md) | SUPUESTO-LING |
| ORT-002 | qu ante e/i -> k (k es la forma mayoritaria para la /k/) | `qu(?=[eiéí])` | `k` |  | Decisión del tesista 2026-10-05; frecuencias AmericasNLP2021@d3f519c | SUPUESTO-LING |
| ORT-003 | c no seguida de h -> k | `c(?!h)` | `k` |  | Decisión del tesista 2026-10-05; frecuencias AmericasNLP2021@d3f519c | SUPUESTO-LING |
| ORT-004 | v -> b (b es la forma mayoritaria) | `v` | `b` |  | Decisión del tesista 2026-10-05; frecuencias AmericasNLP2021@d3f519c | SUPUESTO-LING |

## numerals_cni

Numerales asháninka para números pequeños (política §3.1 del plan)

_Sin entradas._ Ver los comentarios `SUPUESTO-LING` del archivo.

## acronyms

Siglas: glosa en asháninka en la primera mención + sigla (política §3.1)

_Sin entradas._ Ver los comentarios `SUPUESTO-LING` del archivo.

## loanwords

Préstamos del castellano ya asentados, con su forma adaptada

_Sin entradas._ Ver los comentarios `SUPUESTO-LING` del archivo.

## es_to_cni_phonology

Reglas ordenadas de reescritura fonética castellano -> ortografía cni (P2d)

_Sin entradas._ Ver los comentarios `SUPUESTO-LING` del archivo.

## neologisms

Neologismos y perífrasis validados (solo referencia para el detector editorial)

_Sin entradas._ Ver los comentarios `SUPUESTO-LING` del archivo.

## proper_nouns

Nombres propios reconocidos y su reescritura fonética

_Sin entradas._ Ver los comentarios `SUPUESTO-LING` del archivo.

## relative_dates

Fechas relativas a marcar por el detector editorial

_Sin entradas._ Ver los comentarios `SUPUESTO-LING` del archivo.

## segmentation

Parámetros de segmentación en párrafos y oraciones

_Sin entradas._ Ver los comentarios `SUPUESTO-LING` del archivo.

## g2p_inventory

Inventario de grafemas canónicos y su fonema

| id | Descripción | Patrón / forma | Reemplazo | Ejemplo | Fuente | Estado |
|---|---|---|---|---|---|---|
| INV-CH | Dígrafo observado 1028 veces (train+dev) | `ch` | `` |  | AmericasNLP2021@d3f519c (data/candidates/graphemes.yaml) | candidato-corpus |
| INV-SH | Dígrafo observado 3100 veces (train+dev) | `sh` | `` |  | AmericasNLP2021@d3f519c (data/candidates/graphemes.yaml) | candidato-corpus |
| INV-TS | Dígrafo observado 5339 veces (train+dev) | `ts` | `` |  | AmericasNLP2021@d3f519c (data/candidates/graphemes.yaml) | candidato-corpus |
| INV-TY | Dígrafo observado 1136 veces (train+dev) | `ty` | `` |  | AmericasNLP2021@d3f519c (data/candidates/graphemes.yaml) | candidato-corpus |
| INV-A | Letra con frecuencia relativa 19.829 % | `a` | `` |  | AmericasNLP2021@d3f519c (data/candidates/graphemes.yaml) | candidato-corpus |
| INV-I | Letra con frecuencia relativa 16.57 % | `i` | `` |  | AmericasNLP2021@d3f519c (data/candidates/graphemes.yaml) | candidato-corpus |
| INV-T | Letra con frecuencia relativa 9.589 % | `t` | `` |  | AmericasNLP2021@d3f519c (data/candidates/graphemes.yaml) | candidato-corpus |
| INV-O | Letra con frecuencia relativa 8.272 % | `o` | `` |  | AmericasNLP2021@d3f519c (data/candidates/graphemes.yaml) | candidato-corpus |
| INV-R | Letra con frecuencia relativa 7.746 % | `r` | `` |  | AmericasNLP2021@d3f519c (data/candidates/graphemes.yaml) | candidato-corpus |
| INV-N | Letra con frecuencia relativa 7.342 % | `n` | `` |  | AmericasNLP2021@d3f519c (data/candidates/graphemes.yaml) | candidato-corpus |
| INV-K | Letra con frecuencia relativa 7.314 % | `k` | `` |  | AmericasNLP2021@d3f519c (data/candidates/graphemes.yaml) | candidato-corpus |
| INV-E | Letra con frecuencia relativa 6.05 % | `e` | `` |  | AmericasNLP2021@d3f519c (data/candidates/graphemes.yaml) | candidato-corpus |
| INV-S | Letra con frecuencia relativa 3.887 % | `s` | `` |  | AmericasNLP2021@d3f519c (data/candidates/graphemes.yaml) | candidato-corpus |
| INV-P | Letra con frecuencia relativa 2.717 % | `p` | `` |  | AmericasNLP2021@d3f519c (data/candidates/graphemes.yaml) | candidato-corpus |
| INV-M | Letra con frecuencia relativa 2.405 % | `m` | `` |  | AmericasNLP2021@d3f519c (data/candidates/graphemes.yaml) | candidato-corpus |
| INV-Y | Letra con frecuencia relativa 2.032 % | `y` | `` |  | AmericasNLP2021@d3f519c (data/candidates/graphemes.yaml) | candidato-corpus |
| INV-H | Letra con frecuencia relativa 1.596 % | `h` | `` |  | AmericasNLP2021@d3f519c (data/candidates/graphemes.yaml) | candidato-corpus |
| INV-J | Letra con frecuencia relativa 1.19 % | `j` | `` |  | AmericasNLP2021@d3f519c (data/candidates/graphemes.yaml) | candidato-corpus |
| INV-B | Letra con frecuencia relativa 0.992 % | `b` | `` |  | AmericasNLP2021@d3f519c (data/candidates/graphemes.yaml) | candidato-corpus |
| INV-Ñ | Letra con frecuencia relativa 0.583 % | `ñ` | `` |  | AmericasNLP2021@d3f519c (data/candidates/graphemes.yaml) | candidato-corpus |

## g2p_cni_rules

Reglas dependientes del contexto para la conversión grafema-fonema

_Sin entradas._ Ver los comentarios `SUPUESTO-LING` del archivo.

## mms_cni_adapter

Hipótesis de correspondencia canónica -> ortografía MMS

| id | Descripción | Patrón / forma | Reemplazo | Ejemplo | Fuente | Estado |
|---|---|---|---|---|---|---|
| TYP-001 | á -> a | `á` | `a` |  | tipográfica | validado |
| TYP-002 | é -> e | `é` | `e` |  | tipográfica | validado |
| TYP-003 | í -> i | `í` | `i` |  | tipográfica | validado |
| TYP-004 | ó -> o | `ó` | `o` |  | tipográfica | validado |
| TYP-005 | ú/ü -> u | `[úü]` | `u` |  | tipográfica | validado |
| TYP-006 | Puntuación y símbolos (con los espacios que los rodean) -> un espacio (MMS se entrenó sin puntuación, ver VitsTokenizer) | `(?:\s*(?:[^\w\s'-]\|[_ºª])+\s*)+` | ` ` |  | tipográfica; transformers VitsTokenizer.prepare_for_tokenization | validado |
| TYP-007 | Espacios múltiples -> uno | `\s{2,}` | ` ` |  | tipográfica | validado |
| H1-TZ | tz -> ts | `tz` | `ts` |  | Hipótesis H1 (tarea 1.9) | SUPUESTO |
| H1-Z | z -> s | `z` | `s` |  | Hipótesis H1 (tarea 1.9) | SUPUESTO |
| H1-KQU | k ante e/i -> qu | `k(?=[eiéí])` | `qu` |  | Hipótesis H1 (tarea 1.9) | SUPUESTO |
| H1-KC | k en los demás casos -> c | `k` | `c` |  | Hipótesis H1 (tarea 1.9) | SUPUESTO |
| H1-B | b -> v | `b` | `v` |  | Hipótesis H1 (tarea 1.9) | SUPUESTO |
| H1-NY | ñ -> ny | `ñ` | `ny` |  | Hipótesis H1 (tarea 1.9) | SUPUESTO |
| H2-Y | ñ -> y | `ñ` | `y` |  | Hipótesis H2 (tarea 1.9) | SUPUESTO |
| H3-N | ñ -> n | `ñ` | `n` |  | Hipótesis H3 (tarea 1.9) | SUPUESTO |
