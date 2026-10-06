# G2P basado en reglas: justificación

## Decisión

La conversión grafema-fonema (etapa 3) usa **reglas ordenadas** sobre la ortografía canónica:
primero las reglas de contexto (`cni.yaml`) y después el inventario, donde gana la coincidencia
más larga (`inventory.yaml`). Se descartó un G2P neuronal por cuatro razones:

1. **Ortografía transparente.** La ortografía asháninka es relativamente transparente: la correspondencia grafema-fonema es casi biunívoca, salvo los dígrafos. Un modelo neuronal no aporta capacidad útil donde las reglas bastan.
2. **No hay datos de entrenamiento.** No existe un diccionario de pronunciación asháninka disponible. Un G2P neuronal necesita miles de pares palabra–transcripción.
3. **Interpretabilidad y trazabilidad.** Cada fonema emitido guarda el id de la regla y el tramo de caracteres que lo produjo (`char_spans`). Las reglas son citables en el artículo y las puede auditar una persona lingüista.
4. **Reproducibilidad.** Las reglas son deterministas y versionadas por hash (`ResourceVersion`).

El modelo neuronal solo se reconsideraría si la tasa de error por fonema (PER) contra el
conjunto de referencia P5 resultara alta. Esa medición está pendiente: falta P5. La lista de
muestreo ya está en `eval/fase1/p5_sample.csv`.

## Estado actual: segmentación grafémica, no transcripción fonémica

Sin P1 (alfabeto oficial e inventario fonémico) **no se asigna ningún fonema**. El inventario
(`inventory.yaml`) se generó a partir de la evidencia del corpus (`data/candidates/graphemes.yaml`)
con dos criterios documentados:

- **Letras:** frecuencia relativa ≥ 0,5 % en palabras que no aparecen en la oración castellana paralela.
- **Dígrafos:** secuencias observadas ≥ 1000 veces que la ortografía canónica conserva (`ch`, `sh`, `ts`, `ty`).

Todas las entradas tienen `status: candidato-corpus` y `phoneme: null`. Mientras sea así, el G2P
emite etiquetas `<grafema>`, por ejemplo `tsimatsi → <ts> <i> <m> <a> <ts> <i>`. Esto ya sirve en
la Fase 3 para agrupar las duraciones de VITS por unidad. El mapa a visemas, en cambio, requiere
P1 validado.

Que `ts`, `sh`, `ch` o `ty` sean un único fonema es una **hipótesis** que debe confirmar P1. El
inventario lo marca como `SUPUESTO-LING`.

## Cómo validar

1. Una persona experta completa `phoneme` (IPA) en cada entrada de `inventory.yaml` y cambia el `status` a `validado`.
2. Agrega reglas de contexto en `cni.yaml` si hay alófonos.
3. Transcribe la columna `transcripcion_fonemica` de `eval/fase1/p5_sample.csv`.
4. Con eso se calcula la PER y se reporta en `fase_1.json`.
