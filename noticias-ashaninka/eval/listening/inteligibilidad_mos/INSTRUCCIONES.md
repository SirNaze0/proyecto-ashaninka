# Escucha de voces sintéticas: instrucciones

Gracias por ayudarnos. Vas a escuchar oraciones en asháninka dichas por **voces sintéticas**
(generadas por computadora, no por una persona). Hay dos voces distintas mezcladas; no se te dice
cuál es cuál. Queremos saber **cuánto se entiende** y **qué tan natural suena**.

## Para la persona que escucha

1. Descomprime la carpeta y abre **`hoja_escucha.html`** con Chrome, Firefox o Edge. Funciona sin
   internet.
2. Escribe el **identificador** que te dieron (letras y números; **no tu nombre**) y elige la
   **variante** que hablas.
3. En cada bloque:
   - Pulsa el audio y escúchalo las veces que quieras.
   - En **«Escriba lo que entiende»** escribe las palabras que reconozcas, como puedas. No hace
     falta escribir la oración completa ni acertar la ortografía. Si no entiendes nada, déjalo vacío.
   - Marca la **naturalidad de la voz** de 1 (muy artificial) a 5 (muy natural).
   - Si quieres, añade un comentario corto.
4. Al terminar, pulsa **Descargar respuestas** y envía el archivo `respuestas_<tu identificador>.csv`.

Son unos 50 audios y toma unos 25 a 30 minutos. Usa audífonos y un lugar tranquilo. Puedes hacer
pausas, pero **no cierres la página antes de descargar las respuestas**.

Algunos audios se repiten a propósito, con otro nombre: es normal. No hay respuestas correctas ni
incorrectas para la naturalidad, nos interesa tu oído.

## Para la persona que aplica la prueba

- **Entrega solo el contenido de `kit_escucha.zip`.** El archivo `clave.csv` (qué voz es cada audio y
  las palabras que se cuentan) **no debe llegar a quien escucha**: queda con quien aplica la prueba.
- Si la persona prefiere no escribir, puede dictar y quien aplica escribe en su lugar en la hoja
  (anótalo en el comentario del primer audio). No corrijas ni completes lo que dice.
- Se recomienda que escuchen **al menos 3 personas por variante** (con menos, el informe marca la
  variante como «insuficiente») y **al menos 2 en total** (con una sola, el informe no calcula
  intervalos ni acuerdo).
- No se registra nombre, edad, documento, teléfono ni ubicación: solo el identificador y la variante.
- Para puntuar: `uv run python -m eval.listening.inteligibilidad_mos.score respuestas_*.csv`
  (usa `out/clave.csv`). Resultado en `eval/results/escucha_inteligibilidad_mos.json`.

## Cómo se cuenta (definido antes de medir, en `docs/metrics.md`)

- Por oración se toman como **palabras clave** las 3 primeras palabras de 5 o más letras. Una palabra
  clave **acierta** si aparece entre las palabras que escribió la persona (sin importar mayúsculas,
  tildes ni signos; la ñ sí cuenta).
- El **CER por palabra** mide cuánto se parece lo escrito a la palabra clave cuando no acierta.
- El **MOS** es la media de las puntuaciones de naturalidad de 1 a 5.
- Se compara **MMS frente a eSpeak-NG** sobre las mismas oraciones del conjunto de prueba (*test*).
