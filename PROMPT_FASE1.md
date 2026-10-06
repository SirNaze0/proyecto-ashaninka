# PROMPT — Fase 1: Pipeline de texto (corpus, ingesta, normalización, adaptador ortográfico y G2P)

> Copia todo lo que está debajo de la línea en una sesión nueva de Claude Code. Antes, completa los parámetros entre `[corchetes]` y adjunta el archivo `PLAN_DESARROLLO.md` (**v1.2**).

---

# ROL

Actúa como ingeniero de software senior especializado en procesamiento de texto y habla para lenguas de bajos recursos. Vas a implementar la **Fase 1** del artefacto de una tesis de Ingeniería de Sistemas: "Servicio web de noticias en lengua asháninka para mejorar el acceso a información mediante síntesis de voz, texto y avatar". El artefacto será la base experimental de un artículo para una revista Q1. La reproducibilidad y la trazabilidad valen más que la sofisticación.

# DOCUMENTO RECTOR

`PLAN_DESARROLLO.md` (v1.2) es la especificación. Léelo completo antes de escribir código, en especial:

- §2: contrato de ingesta con la tesis de traducción.
- §3: pendientes P1, P2a–P2e, P5, **P6 y P7**.
- §3.1: política de normalización, separación entre la etapa editorial y la automática, sub-etapas **2-0 a 2f**, las dos ortografías internas y los mapas de alineación.
- **§3.2: corpus AmericasNLP 2021, el hallazgo de la ortografía de MMS y qué usos están permitidos y cuáles no.**
- §5 Fase 1: tareas **1.0 a 1.9** y criterios de cierre.
- §8: riesgos R13–R15.

Si este prompt y el plan se contradicen, **manda el plan**: señala la contradicción y pregunta.

# CONTEXTO CRÍTICO (ya medido; vuelve a medirlo en la tarea 1.0)

Análisis exploratorio del 2026-10-05:

- El vocabulario de `facebook/mms-tts-cni` tiene 31 símbolos. Sus letras son `a c e h i j m n o p q r s t u v y` (más los dígitos, `'`, `-` y el espacio). **No incluye `k`, `b`, `ñ`, `z`, `g`, `l`, `d` ni `f`.** El reconocedor de voz `mms-1b-all` (adaptador `cni`) tiene las mismas letras.
- El corpus AmericasNLP usa la ortografía moderna. Entre el **53 % y el 60 % de las palabras** (según el split) tiene al menos un carácter fuera de ese vocabulario. La letra fuera del vocabulario más frecuente es `k` (16 185 apariciones en train).
- `VitsTokenizer` (con `normalize=True`) **elimina en silencio** los caracteres que no están en su vocabulario: *kipatsi* llega al modelo como *ipatsi*. Este es el problema central que la Fase 1 debe resolver (R13).
- El corpus mezcla ortografías (`b`/`v`, `ts`/`tz`) y variantes dialectales.
- Los dígitos se conservan al traducir: 337 de las 340 líneas de train con dígitos en castellano también los tienen en asháninka.

# PARÁMETROS

**Por completar:**
- RUTA_PROYECTO: `[C:\Users\Marco\Downloads\noticias-ashaninka\]`
- NOTICIAS_DE_PRUEBA: `[ruta a los archivos de noticias en asháninka, y su formato: txt / docx / json / csv]`
- RECURSO_P1 (alfabeto, inventario fonémico y ortografía canónica): `[ruta o "no disponible"]`
- RECURSO_P2a (numerales nativos validados): `[ruta o "no disponible"]`
- RECURSO_P2d (adaptación fonológica castellano→asháninka): `[ruta o "no disponible"]`
- RECURSOS_P2b/P2c/P2e (siglas, préstamos, neologismos): `[ruta o "empezar con candidatos del corpus"]`
- RECURSO_P5 (conjunto de referencia de unas 200 palabras con su transcripción fonémica): `[ruta o "no disponible"]`
- RESPUESTA_P7 (corpus y ortografía del traductor de la compañera): `[descripción o "desconocida"]`
- VARIANTE_DIALECTAL de las noticias de prueba: `[variante o "desconocida"]`
- HABLANTE_BILINGÜE disponible para las tareas 1.8 y 1.9: `[sí / no]`
- USAR_CORPUS_MONOLINGÜE (`iapucp/multilingual-data-peru`, carpeta `cni`): `[sí / no]`

**Ya fijados (no cambiar sin justificar):**

| Recurso | Versión fijada | SHA-256 |
|---|---|---|
| Repositorio `AmericasNLP/americasnlp2021` | commit `d3f519c6b38299d8149311e65a369047350e6849` | — |
| `data/ashaninka-spanish/train.cni` | — | `dd528a5b61284dde62d1c957a8e7bdbad296f40cb9ed128b592e5aaa9bdf6d84` |
| `data/ashaninka-spanish/train.es` | — | `d86a5aecc2b9ea0e1ac684cb1984d8fb6420482c8d750d3ed58d04739348002e` |
| `data/ashaninka-spanish/dev.cni` | — | `90c85ba9bee92e3ff871e3128a6d2f376387978d108538f552d87874b9f35161` |
| `data/ashaninka-spanish/dev.es` | — | `5ea9455bee5e67f56db261a7969cf410a8f833305afc669cc6d5ee39ef7b10d3` |
| `test_data/test.cni` | — | `9927b2daa5a4d607945cfed06bfd83a83517fa455af31d0753e911d9a0a1e004` |
| `data/ashaninka-spanish/test.es` | — | `a30e58fe429dcaeaf17699e38e2e23ffc13722ae530c4c724f9855d26c73aa8f` |
| `facebook/mms-tts-cni` | revisión `a744890bf8b52fd17ed322d8d995dec6cf77809b` | `vocab.json`: `e1c795b28e1077be9a9baf60d2399639ed698774014bbc930de601f8dd4fa62b` |
| `facebook/mms-1b-all` (solo para la tarea 1.9, unos 3,9 GB) | revisión `3d33597edbdaaba14a8e858e2c8caa76e3cec0cd` | — |

Los hashes se calcularon el 2026-10-05 sobre archivos descargados por `raw.githubusercontent.com` y `huggingface.co`. Si al descargar no coinciden, `init.sh` se detiene y lo informa; no continúa con otra versión.

# ENTORNO (confirmado)

- Windows 11, sin GPU, desarrollo local. **Sin Docker en esta fase** (se agrega en la Fase 6).
- Python 3.11 con `uv`. FastAPI, SQLModel + SQLite, Pydantic v2, PyYAML, `num2words` (lang `es`), `pytest`, `pytest-cov`, `ruff`, `pre-commit`.
- Solo para las tareas 1.8 y 1.9 (dependencias opcionales, grupo `eval`): `torch` (CPU), `transformers`, `soundfile`, `jiwer`.
- Repositorio git inicializado desde el primer commit. Un commit por tarea, con mensajes descriptivos.
- Convención de idioma: identificadores del código en inglés; comentarios, docstrings y documentación en castellano.

# REGLAS INNEGOCIABLES

1. **No inventes datos lingüísticos del asháninka.** Esto incluye grafemas, dígrafos, fonemas, numerales, adaptaciones fonológicas, glosas, préstamos y correspondencias ortográficas. Si un recurso no está disponible:
   - El motor se implementa y se prueba igual, con **reglas de prueba ficticias** en `tests/fixtures/` (por ejemplo, un alfabeto inventado "xyz"). Esas reglas nunca se presentan como asháninka.
   - Los archivos de recursos reales quedan creados con su esquema, vacíos o con entradas marcadas con un `status` distinto de `validado`, y con un comentario `# SUPUESTO-LING: <qué falta y quién debe validarlo>`.
   - Cualquier línea de código que dependa de un supuesto lingüístico lleva el marcador `# SUPUESTO-LING`.
2. **Lo que sale del corpus es candidato, no un hecho.** Toda entrada extraída del corpus lleva `status: candidato-corpus`, su frecuencia y ejemplos con número de línea. Solo una persona experta la pasa a `validado`.
3. **Disciplina de splits:** las reglas y los extractores se construyen y depuran con **train**; los ajustes se hacen con **dev**; **test** se usa solo en la medición final y nunca para decidir reglas. Un test automático verifica que ningún recurso YAML cite líneas de test como ejemplo.
4. **El corpus no se redistribuye:** va en `data/corpus/` (en `.gitignore`), lo descarga `init.sh` y se verifica por hash.
5. **Nunca dependas de que el tokenizador elimine caracteres.** El texto que llega a `mms-tts-cni` ya debe estar 100 % dentro de su vocabulario. La validación 2f **lanza un error** si no lo está; no basta con un aviso.
6. **Todo número reportado proviene de una ejecución real.** Si algo no se pudo medir, se escribe `"no_medido"` con el motivo.
7. **El normalizador no aplica decisiones editoriales**: no redondea cifras, no pasa fechas a relativo y no crea neologismos. Solo las **detecta y marca** (§3.1).
8. **Nada se descarta en silencio.** Todo token sin regla queda en `unresolved` con su posición.
9. Si un requisito es ambiguo, **pregunta antes de asumir** (máximo cinco preguntas, agrupadas al inicio).
10. Fuera de alcance en esta fase: la interfaz `TTSEngine` de producción, el hook de duraciones, los visemas, el frontend y Docker. Las excepciones son los **scripts de evaluación** de las tareas 1.8 y 1.9 y el **adaptador ortográfico** de MMS, que sí se implementa en esta fase.

# ALCANCE: TAREAS

## 1.1 Esqueleto del repositorio

Estructura según el plan (crea solo lo necesario para esta fase):

```
noticias-ashaninka/
├── init.sh                       # inicializa el proyecto en cualquier máquina (ver 1.1b)
├── .env.example                  # variables de configuración documentadas
├── .gitattributes                # fuerza LF en *.sh (evita que Windows rompa init.sh con CRLF)
├── .gitignore                    # incluye data/corpus/, modelos descargados, .env
├── README.md                     # instalación (vía init.sh) y uso de la Fase 1
├── LICENSES.md                   # registro: num2words, MMS (CC-BY-NC 4.0), corpus (sin licencia explícita: uso académico con citas)
├── CITATION.md                   # referencias obligatorias del corpus y de MMS (§9 del plan)
├── CHANGELOG.md
├── pyproject.toml                # grupos: dev, eval
├── .pre-commit-config.yaml       # ruff, shellcheck
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── cli.py
│   │   ├── config.py
│   │   ├── api/news.py
│   │   ├── db/{models.py, session.py}
│   │   ├── metrics/timing.py
│   │   ├── corpus/                # tarea 1.0
│   │   │   ├── loader.py          # lee los splits y verifica hashes
│   │   │   ├── report.py          # informe que reproduce §3.2
│   │   │   └── extract.py         # candidatos: numerales, siglas, préstamos, nombres propios, variantes
│   │   └── pipeline/
│   │       ├── types.py          # dataclasses compartidas (ver "Interfaces")
│   │       ├── segment.py
│   │       ├── normalize/
│   │       │   ├── engine.py      # orquesta 2-0 a 2d
│   │       │   ├── unify.py       # 2-0 unificación ortográfica
│   │       │   ├── classify.py    # 2a
│   │       │   ├── verbalize.py   # 2b
│   │       │   ├── acronyms.py    # 2c
│   │       │   ├── rewrite.py     # 2d
│   │       │   ├── editorial.py   # detector editorial (1.5b)
│   │       │   └── resources/
│   │       │       ├── orthography_variants.yaml  # 2-0 (P1, P7)
│   │       │       ├── numerals_cni.yaml          # P2a
│   │       │       ├── acronyms.yaml              # P2b
│   │       │       ├── loanwords.yaml             # P2c
│   │       │       ├── es_to_cni_phonology.yaml   # P2d
│   │       │       ├── neologisms.yaml            # P2e
│   │       │       └── proper_nouns.yaml          # gazetteer de nombres propios
│   │       ├── g2p/
│   │       │   ├── engine.py
│   │       │   └── rules/{inventory.yaml, cni.yaml}   # P1, sobre la ortografía CANÓNICA
│   │       └── tts/adapters/      # específico de cada motor, NO es una regla lingüística
│   │           ├── base.py        # OrthographyAdapter
│   │           ├── mms_cni.py     # 2e: canónica → ortografía MMS + mapa de caracteres
│   │           ├── mms_cni.yaml   # hipótesis H1..Hn y la elegida (P6)
│   │           └── validate.py    # 2f: validación estricta contra el vocabulario
│   └── tests/
│       ├── fixtures/              # reglas ficticias, noticias sintéticas, mms_cni_vocab.json
│       ├── unit/
│       └── integration/
├── data/
│   ├── news/                      # noticias de prueba convertidas al contrato del §2
│   ├── corpus/                    # (gitignored) AmericasNLP descargado por init.sh
│   └── candidates/                # salidas de los extractores (sí se versionan; son derivadas y citan líneas)
├── docs/
│   ├── normalization_rules.md     # GENERADO, no se edita a mano
│   ├── corpus_report.md           # GENERADO por la tarea 1.0
│   ├── mms_orthography.md         # GENERADO por la tarea 1.9: hipótesis, CER y decisión
│   ├── g2p.md
│   └── limitations.md
├── eval/
│   ├── fase1/                     # scripts de medición
│   │   └── mms_orthography/       # tarea 1.9
│   ├── listening/rewrite_check/   # tarea 1.8
│   └── results/fase_1.json
└── scripts/convert_test_news.py   # convierte NOTICIAS_DE_PRUEBA al contrato
```

## 1.1b `init.sh`: inicialización en cualquier máquina

Un solo script en la raíz deja el proyecto listo para trabajar en una máquina limpia. Es el **único** paso de instalación del README.

**Compatibilidad:**
- Bash ≥ 4 en Linux, macOS, WSL y Git Bash (Windows).
- Detecta el sistema operativo con `uname` y adapta rutas y comandos. Por ejemplo, en Git Bash el entorno virtual vive en `.venv/Scripts`, no en `.venv/bin`. Para los hashes usa `sha256sum` o `shasum -a 256`, según cuál exista.
- Empieza con `#!/usr/bin/env bash` y `set -euo pipefail`.
- `.gitattributes` con `*.sh text eol=lf`, para que un clon en Windows no lo rompa con CRLF.

**Comportamiento:**
- **Idempotente:** ejecutarlo dos veces no rompe nada, no duplica datos y no vuelve a descargar archivos cuyo hash ya coincide.
- **No usa `sudo` ni instala paquetes del sistema por su cuenta.** Si falta una herramienta del sistema, muestra el comando de instalación según el sistema operativo y termina con un código de error claro.
- Mensajes con prefijo `[init]` y resumen final de lo que hizo o se saltó.
- Códigos de salida: `0` ok, `1` falta un requisito del sistema, `2` falló una etapa, `3` un hash no coincide.

**Etapas, en orden:**
1. Verificar requisitos: `git`, `curl` y conexión a internet (solo si hay algo que descargar).
2. Instalar `uv` con su instalador oficial si no está (en el directorio del usuario, sin `sudo`) y comprobar su versión.
3. `uv python install 3.11` y `uv sync` (dependencias de producción y desarrollo fijadas en `uv.lock`; el grupo `eval` solo con las opciones de evaluación).
4. Crear `.env` a partir de `.env.example` **solo si no existe**. Nunca sobrescribe uno existente.
5. Crear la base SQLite y aplicar las migraciones.
6. **Descargar el corpus AmericasNLP** en el commit fijado → `data/corpus/americasnlp2021/` y verificar los 6 hashes. Antes, muestra la cita obligatoria y la condición de uso académico.
7. Descargar `vocab.json` de `facebook/mms-tts-cni` en la revisión fijada → `tests/fixtures/mms_cni_vocab.json` y verificar su hash. Muestra el aviso de la licencia CC-BY-NC 4.0. **No hace falta `transformers` para este paso**: se descarga el archivo directamente.
8. `pre-commit install`, solo si existe `.git`.
9. Validar los recursos YAML contra su esquema e informar cuántas entradas hay en cada estado (`validado`, `candidato-corpus`, `SUPUESTO-LING`).
10. Prueba rápida: `pytest -q -m smoke` (un subconjunto de menos de 30 s).

**Opciones:**

| Opción | Efecto |
|---|---|
| (sin opciones) | Etapas 1–10 |
| `--with-data` | Además, convierte e importa las noticias de prueba, genera el informe y los candidatos del corpus (1.0) y ejecuta `process --all` |
| `--with-monolingual` | Además, descarga el corpus monolingüe `iapucp/multilingual-data-peru` (carpeta `cni`), con su cita |
| `--with-audio-eval` | Además, instala el grupo `eval` y descarga `mms-tts-cni` completo (tarea 1.8). Pide confirmación por el tamaño y la licencia |
| `--with-asr-eval` | Además, descarga `mms-1b-all` (**unos 3,9 GB**) para la tarea 1.9. Pide confirmación mostrando el tamaño, la licencia y el espacio libre en disco |
| `--check` | Solo verifica el entorno, los hashes y el estado de cada etapa, sin modificar nada |
| `--reset-db` | Borra y recrea la base de datos. Pide confirmación interactiva salvo que se pase `--yes` |
| `--help` | Ayuda con ejemplos |

**Pruebas del script:**
- Se ejecuta con `shellcheck` sin errores (agregado a `pre-commit`).
- En el informe final se indica **en qué sistemas operativos se probó realmente**. Como mínimo Git Bash en Windows 11 (la máquina del tesista). Si se probó en WSL o Linux, también. No se declara compatible un sistema donde no se ejecutó.

## 1.0 Corpus AmericasNLP: informe y extracción de candidatos

Va después de 1.1b porque depende de la descarga.

- **`corpus/loader.py`:** lee los splits paralelos (train, dev, test), verifica los hashes y expone pares (línea, cni, es).
- **`corpus/report.py` → `docs/corpus_report.md` + bloque `corpus` en `fase_1.json`:** reproduce **todas** las mediciones del §3.2 del plan (oraciones, tokens, tipos, % de caracteres y de palabras fuera del vocabulario de MMS, líneas con dígitos, frecuencia de cada letra, pares de variantes `b`/`v` y `ts`/`tz`). **Compara tus valores con los del plan y explica cualquier diferencia** (por ejemplo, otra forma de tokenizar). Agrega el inventario de grafemas y dígrafos observado, con frecuencias.
- **`corpus/extract.py` → `data/candidates/*.yaml`**, todo con `status: candidato-corpus`, frecuencia y hasta 3 ejemplos (split y línea, **solo de train o dev**):
  - **Numerales (P2a):** patrones "palabra (dígito)" y alineaciones de números entre cni y es. El plan ya registra *aparoni* (1), *apite* (2), *maba* (3) y *apapakoroni* (5). Marca como ruido lo que sea inconsistente, como *apapakoroni* (0,5).
  - **Siglas (P2b):** tokens en mayúsculas o con puntos, con su frecuencia y su contexto en castellano.
  - **Préstamos (P2c):** tokens que aparecen idénticos (o casi, por distancia de edición) en la línea cni y en su par es, sin contar nombres propios.
  - **Nombres propios (gazetteer):** tokens con mayúscula inicial compartidos entre cni y es que no empiezan oración.
  - **Variantes ortográficas (2-0):** pares de palabras que difieren solo en `b`↔`v`, `ts`↔`tz` u otras sustituciones frecuentes que detectes, con el recuento de cada forma.
- Un subcomando de la CLI (`corpus report`, `corpus extract`) y una prueba de que la extracción es determinista (dos ejecuciones dan el mismo resultado).

## 1.2 Modelo de datos (SQLModel + SQLite)

- `News`: id, título y cuerpo en cni, título y cuerpo en es (opcionales; **nunca** se exponen en los endpoints que use el experimento), variante_dialectal, fecha_publicacion, fuente_original, estado (`ingested | processed | error`), timestamps.
- `Provenance` (1:1 con `News`, **obligatoria**): tipo (`traduccion_humana | traduccion_automatica | automatica_revisada`), sistema, versión, revisado_por_hablante, revisor_id.
- `Segment`: news_id, idx, paragraph_idx, text_orig, **text_canonical**, **text_tts** (ortografía MMS), alignment_map (JSON, original↔canónico), **tts_char_map** (JSON, canónico↔MMS), phonemes (JSON), editorial_flags (JSON), unresolved (JSON), resources_hash, **adapter_id** (hipótesis de adaptador usada).
- `ResourceVersion`: hash SHA-256 de cada YAML de recursos usado al procesar. Así cada segmento sabe con qué versión de las reglas se generó.
- Restricción probada con un test: una `News` sin `Provenance` no se guarda.

## 1.3 Ingesta

- API REST: `POST/GET/PUT/DELETE /api/news`, `POST /api/news/import`, `POST /api/news/{id}/process`, `GET /api/news/{id}/segments`, `GET /api/news/{id}/editorial-report`.
- Validación con Pydantic exactamente según el contrato del §2 del plan.
- CLI: `uv run python -m app.cli import data/news/`, `process --all`, `report --news <id>`, `build-docs`, `corpus report`, `corpus extract`.
- `scripts/convert_test_news.py` convierte NOTICIAS_DE_PRUEBA al contrato. Si falta un metadato, se usa un valor explícito `"desconocido"`, nunca uno inventado.
- Además, un modo `import --from-corpus dev --limit N` que trata oraciones del corpus como pseudo-noticias **solo para pruebas de carga y de integración**, con procedencia `tipo: corpus_americasnlp`. Nunca se marcan como aptas para el experimento.

## 1.4 Segmentación

- Primero párrafos, luego oraciones, a partir de la puntuación. Las reglas son configurables, con excepciones para abreviaturas y números con punto o con el símbolo de ordinal (`1°`, `5º`, `Nº 29338`), que aparecen en el corpus.
- Los offsets de caracteres se conservan respecto al texto original.

## 1.5 Normalizador (sub-etapas 2-0 a 2d del §3.1)

Se procesa **por documento** (necesario para la regla de la primera mención de siglas) y se emite el resultado **por segmento**. Su salida es el **texto canónico**.

- **2-0 Unificación ortográfica:** las variantes de escritura se llevan a la ortografía canónica según `orthography_variants.yaml`. Si P1 y P7 no están resueltos, la ortografía canónica queda como `SUPUESTO-LING` y la dirección de cada unificación (por ejemplo, `v`→`b` o `b`→`v`) **no se decide por frecuencia**: se deja configurable y se pregunta. Cada cambio entra al mapa de alineación.
- **2a Clasificación:** número pequeño, número grande, porcentaje, dinero, año, fecha, ordinal, sigla, nombre propio, préstamo o desconocido.
  - El límite entre número pequeño y grande se lee de `numerals_cni.yaml` (P2a). Nunca va fijo en el código.
  - Convenciones peruanas (por ejemplo `S/ 1 500`, `S/. 20`, `30 %`, `05/10/2026`, "5 de octubre de 2026") y las del corpus (`10,000`, `0,5`, `1°`, `Nº 29338`). Si un separador decimal o de miles es ambiguo, se marca en `unresolved`; no se adivina.
  - Nombre propio = está en el gazetteer **o** contiene grafemas ajenos al inventario canónico **o** es una palabra con mayúscula inicial que no empieza oración. Esta heurística lleva el marcador `SUPUESTO-LING` y se documenta.
- **2b Verbalización:** números pequeños → numeral cni (solo con entradas `validado` de P2a; si solo hay candidatos, se usan **detrás de una opción explícita** `--allow-candidates` y el segmento queda marcado). Números grandes, porcentajes, dinero y fechas → palabras en castellano con `num2words` (lang `es`) más plantillas para día, mes y año.
- **2c Siglas:** en la primera mención del documento, glosa cni + sigla; en las siguientes, solo la sigla. La lectura (como palabra o deletreada) sale de `acronyms.yaml`. Una sigla que no está en el glosario va a `unresolved` y se reporta.
- **2d Reescritura fonética castellano→ortografía canónica cni:** primero el léxico (P2c, P2b y el gazetteer con su forma reescrita), después las reglas de `es_to_cni_phonology.yaml` (P2d), ordenadas y con coincidencia más larga. Cada aplicación registra los `rule_ids` usados.

**Esquema de cada regla en YAML** (aplica a todos los recursos):

```yaml
- id: P2D-001
  description: "…"
  pattern: "…"          # o "source" para entradas de léxico
  replacement: "…"
  examples: [{input: "…", output: "…", ref: "train:782"}]   # nunca test
  frequency: 12          # si viene del corpus
  source: "referencia bibliográfica, persona validadora o 'AmericasNLP2021@d3f519c'"
  status: validado | candidato-corpus | SUPUESTO-LING
```

`build-docs` genera `docs/normalization_rules.md` a partir de los YAML: una tabla por recurso con id, descripción, ejemplo, fuente y estado, más un resumen de cuántas entradas hay en cada estado.

## 1.5b Detector editorial

Marca sin modificar el texto:

- Números grandes candidatos a redondeo.
- Fechas completas que podrían pasarse a relativo.
- Términos ausentes del glosario P2e (palabras de origen castellano que no están en P2c ni en el gazetteer).
- Fechas relativas ya presentes en el texto (riesgo R10).

Salida: `editorial_flags` por segmento + `GET /api/news/{id}/editorial-report` (JSON) + `report --news <id>` (texto legible para el revisor o la compañera).

## 1.5c Mapas de alineación

Hay dos mapas por segmento:

1. **Original ↔ canónico** (`alignment_map`): lista de `NormalizedSpan`.
2. **Canónico ↔ MMS** (`tts_char_map`): lo produce el adaptador 2e, carácter por carácter. Una correspondencia puede ser 1→N (por ejemplo, un carácter canónico que se escribe con dos en MMS) o N→1.

Propiedades verificadas con tests, para ambos mapas:

- Cubren el 100 % del texto de origen, sin huecos ni solapamientos.
- Concatenar los destinos reproduce exactamente el texto de destino.
- Los fragmentos sin cambios también figuran, con la categoría `identity`.
- Componer los dos mapas permite ir de cualquier carácter MMS a su fragmento original. La Fase 3 lo necesita para pasar las duraciones de VITS al resaltado.

## 1.6 G2P basado en reglas

- Trabaja sobre la ortografía **canónica**, nunca sobre la de MMS.
- Monolingüe: la reescritura de los fragmentos en castellano ya ocurrió en 2d.
- `inventory.yaml` (grafema → fonema, clases de fonemas) y `cni.yaml` (reglas de contexto, coincidencia más larga, en orden). El inventario observado en el informe del corpus (1.0) sirve de **punto de partida documentado**, pero cada grafema queda `candidato-corpus` hasta validarse con P1.
- Salida por palabra: la palabra, su lista de fonemas, los `rule_ids` y los `char_spans`, que indican qué caracteres canónicos produjeron cada fonema.
- Un grafema desconocido va a `unknown`, no se lanza excepción.
- Justifica en `docs/g2p.md` por qué se eligieron reglas y no un modelo neuronal (ver §3 del plan).
- PER contra P5 si existe. Si P5 no existe, genera la **lista de muestreo** para P5: 200 palabras de train, estratificadas por frecuencia y por grafemas cubiertos, lista para que una persona experta la transcriba.

## 1.9 Adaptador ortográfico MMS y experimento de ortografía (P6)

Se implementa después del G2P y antes de cerrar el normalizador, porque la validación 2f depende de él.

**Implementación (producción):**
- **`tts/adapters/base.py`:** interfaz `OrthographyAdapter` con `adapt(text_canonical) -> (text_tts, char_map)`, `vocab()`, `id`.
- **`tts/adapters/mms_cni.py`:** reglas dependientes del contexto leídas de `mms_cni.yaml`. La hipótesis activa se elige por configuración.
- **`tts/adapters/validate.py` (2f):** comprueba que el 100 % de `text_tts` esté en `mms_cni_vocab.json`. Si no, **lanza `OutOfVocabularyError`** con los caracteres y su posición.
- **Prueba de regresión clave:** para todo `text_tts`, la salida normalizada de `VitsTokenizer` (sin el entrelazado de blancos) debe ser **idéntica** a `text_tts`. Esto demuestra que el tokenizador ya no descarta nada. La prueba se omite (skip, con motivo) si no está instalado el grupo `eval`.

**Hipótesis (archivo `mms_cni.yaml`, todas con `status: SUPUESTO`):** son condiciones experimentales, no afirmaciones lingüísticas.
- **H0, sin adaptar:** el texto canónico pasa tal cual y el tokenizador elimina lo que no conoce. Es la línea base que reproduce el defecto actual.
- **H1…Hn:** familias de correspondencias para los caracteres fuera del vocabulario que reporte la tarea 1.0, como mínimo `k`, `b`, `ñ` y `z`/`tz`. Por ejemplo: `k`→`c` antes de a/o/u y de consonante y `k`→`qu` antes de e/i; `b`→`v`; para `ñ` se prueban varias alternativas. **Propón el conjunto de hipótesis en tus preguntas iniciales y espera confirmación**: no lo decidas en silencio.

**Experimento (`eval/fase1/mms_orthography/`, requiere `--with-asr-eval`):**
1. Muestra fija de **100 oraciones de dev** (semilla fija), estratificada para que contenga los caracteres conflictivos.
2. Para cada hipótesis: texto canónico → adaptador → `mms-tts-cni` (semilla fija) → WAV → `mms-1b-all` con el adaptador `cni` → transcripción.
3. **Métrica principal:** CER en el espacio **canónico**. La transcripción se devuelve a la ortografía canónica con la inversa documentada de la hipótesis (identidad para H0) y se compara con el texto canónico de entrada. **Secundarias:** CER en el espacio MMS, precisión por palabra y CER desglosado por cada carácter conflictivo.
4. Intervalos de confianza con bootstrap (1 000 remuestreos) y prueba de diferencia pareada entre la mejor hipótesis y H0.
5. Si `HABLANTE_BILINGÜE = sí`: hoja CSV de escucha A/B (H0 frente a la mejor hipótesis, 20 oraciones, orden aleatorizado y a ciegas).
6. `docs/mms_orthography.md` (generado): tabla de resultados, la hipótesis elegida y **la limitación**: el TTS y el reconocedor comparten datos de entrenamiento, así que la prueba mide consistencia, no inteligibilidad humana.

Si no hay recursos para ejecutar el experimento, el adaptador queda implementado con las hipótesis y el resultado se declara `"no_medido"`. **La fase no se cierra sin este experimento.**

## 1.7 Pruebas

- Unitarias por cada regla y por cada categoría de la política, usando **reglas ficticias** si faltan los recursos reales.
- Primera mención de siglas: aparece la glosa la primera vez y no las siguientes.
- Propiedades de los dos mapas de alineación y de su composición (ver 1.5c).
- 2f: el 100 % del `text_tts` pertenece al vocabulario de MMS. Prueba de regresión con el tokenizador (ver 1.9).
- Unificación 2-0: probada con los pares de variantes extraídos en 1.0 (por ejemplo, *maba*/*mava* deben quedar en una sola forma canónica, sea cual sea la elegida).
- Integración: el 100 % de las noticias de prueba **y de las 883 oraciones de dev** se procesa sin excepciones.
- Disciplina de splits: ningún YAML cita líneas de test.
- PER contra P5, si está disponible; si no, `"no_medido"`.
- Cobertura ≥ 90 % en `backend/app/pipeline/` y `backend/app/corpus/`.

## 1.8 Validación auditiva de la reescritura (script, no producción)

- `eval/listening/rewrite_check/` genera una lista de unos 50 ítems (nombres propios, fechas, siglas y números grandes, tomados de las noticias de prueba y de los candidatos del corpus), cada uno con su original, su forma canónica, su `text_tts` y su audio sintetizado **con el adaptador elegido en 1.9**.
- El audio sale de un **script independiente** que usa `transformers.VitsModel` con `facebook/mms-tts-cni` en la revisión fijada. Es solo una herramienta de evaluación: **no** es la interfaz `TTSEngine` de la Fase 2. Semilla fija.
- Una hoja CSV recoge el juicio del hablante: `aceptable | no_aceptable | comentario`.
- Si `HABLANTE_BILINGÜE = no`, se genera el material y la métrica queda `"pendiente_hablante"`.

# INTERFACES (`pipeline/types.py`)

```python
@dataclass(frozen=True)
class NormalizedSpan:
    orig_start: int; orig_end: int; orig_text: str
    norm_text: str; category: str; rule_ids: tuple[str, ...]

@dataclass(frozen=True)
class CharMapEntry:              # canónico ↔ MMS (adaptador 2e)
    src_start: int; src_end: int     # en text_canonical
    dst_start: int; dst_end: int     # en text_tts
    rule_id: str | None

@dataclass
class EditorialFlag:
    kind: str            # big_number | full_date | missing_neologism | relative_date
    orig_start: int; orig_end: int; note: str

@dataclass
class Unresolved:
    orig_start: int; orig_end: int; text: str; reason: str

@dataclass
class NormalizationResult:
    text_canonical: str
    spans: list[NormalizedSpan]
    editorial_flags: list[EditorialFlag]
    unresolved: list[Unresolved]
    resources_hash: str

@dataclass
class AdaptedText:
    text_tts: str
    char_map: list[CharMapEntry]
    adapter_id: str                  # p. ej. "mms_cni/H2"

@dataclass
class PhonemizedWord:
    word: str; phonemes: list[str]
    char_spans: list[tuple[int, int]]; rule_ids: list[str]

@dataclass
class G2PResult:
    words: list[PhonemizedWord]; unknown: list[Unresolved]
```

Puedes ajustar los nombres si lo justificas, pero se mantiene la información.

# MÉTRICAS: `eval/results/fase_1.json`

Generadas con `uv run python -m eval.fase1.run`, nunca escritas a mano:

```json
{
  "fase": 1,
  "commit": "<hash>",
  "fecha": "<ISO-8601>",
  "hardware": {"cpu": "...", "ram_gb": 0, "os": "..."},
  "versiones_fijadas": {"americasnlp2021": "d3f519c…", "mms-tts-cni": "a744890…", "mms-1b-all": "3d33597…"},
  "resources_hash": {"numerals_cni.yaml": "...", "...": "..."},
  "corpus": {
    "train": {"oraciones": 0, "tokens": 0, "tipos": 0, "chars_fuera_vocab_pct": 0, "palabras_fuera_vocab_pct": 0, "lineas_con_digitos": 0},
    "dev":   {"...": 0},
    "test":  {"...": 0},
    "diferencias_con_plan": "explicación o 'ninguna'"
  },
  "candidatos": {"numerales": 0, "siglas": 0, "prestamos": 0, "nombres_propios": 0, "pares_variantes": 0},
  "noticias_prueba": {"noticias": 0, "segmentos": 0, "tokens": 0, "variante": "..."},
  "categorias_pct": {"numero_pequeno": 0, "numero_grande": 0, "...": 0},
  "unresolved_pct": {"noticias_prueba": 0, "dev": 0},
  "editorial_flags_por_noticia": {"media": 0, "por_tipo": {}},
  "vocab_mms": {
    "palabras_fuera_vocab_antes_del_adaptador_pct": {"dev": 0},
    "palabras_fuera_vocab_despues_del_adaptador_pct": {"dev": 0}
  },
  "ortografia_mms": {
    "hipotesis": {"H0": {"cer_canonico": 0, "ic95": [0, 0]}, "H1": {"...": 0}},
    "elegida": "Hx | no_medido",
    "p_valor_vs_H0": "valor | no_medido",
    "escucha_ab": "pendiente_hablante | resultado"
  },
  "reglas": {"total": 0, "validadas": 0, "candidato_corpus": 0, "supuesto_ling": 0},
  "g2p_per": "no_medido | valor",
  "reescritura_aceptada_pct": "pendiente_hablante | valor",
  "latencia_ms": {
    "segmentacion": {"p50": 0, "p95": 0},
    "normalizacion": {"p50": 0, "p95": 0},
    "adaptador_mms": {"p50": 0, "p95": 0},
    "g2p": {"p50": 0, "p95": 0}
  },
  "cobertura_tests_pct": 0
}
```

La latencia se mide con `metrics/timing.py` sobre N ≥ 100 ejecuciones por noticia y sobre las oraciones de dev.

# CRITERIOS DE CIERRE (del plan v1.2)

- [ ] Informe del corpus reproducible, comparado con el §3.2 del plan y con las diferencias explicadas.
- [ ] Candidatos extraídos de forma determinista, todos con `status: candidato-corpus` y sin ejemplos de test.
- [ ] Cobertura de pruebas ≥ 90 %.
- [ ] El 100 % de las noticias de prueba y de las oraciones de dev se procesa sin excepciones.
- [ ] El 100 % del `text_tts` está en el vocabulario de `mms-tts-cni`, y la prueba de regresión con el tokenizador pasa (no se elimina ningún carácter).
- [ ] Adaptador elegido **con evidencia** (CER de ida y vuelta por hipótesis, con intervalos de confianza), o declarado `"no_medido"` con el motivo. En ese caso la fase **no** se cierra.
- [ ] Se reportan el % de elementos sin normalizar y el % de elementos marcados por el detector editorial.
- [ ] PER del G2P medida, o declarada `"no_medido"` con la lista de muestreo para P5 ya generada.
- [ ] P1, P2a, P2d y la decisión de ortografía canónica (2-0) validados por una persona experta. **Si no lo están, la fase se entrega como "implementada, pendiente de validación lingüística"; no como cerrada.**
- [ ] `docs/normalization_rules.md`, `docs/corpus_report.md` y `docs/mms_orthography.md` generados.
- [ ] En una máquina limpia, `./init.sh` deja el entorno listo (con el corpus verificado por hash) y `./init.sh --check` termina con código 0. Se informa en qué sistemas operativos se probó.
- [ ] `shellcheck init.sh` sin errores.
- [ ] El README permite a un tercero ejecutar `./init.sh --with-data` y luego `import → process → report` desde cero.

# FORMA DE TRABAJO

1. **Antes de programar:** lee el plan y los recursos disponibles, y responde con:
   - (a) tus preguntas bloqueantes (máximo cinco). Una de ellas debe ser la **propuesta del conjunto de hipótesis H1…Hn** para el adaptador MMS.
   - (b) el orden de implementación.

   **Espera mi confirmación.**
2. Implementa en este orden: 1.1 → 1.1b (versión inicial de `init.sh`, que se amplía a medida que se agregan etapas) → **1.0** → 1.2 → 1.3 → 1.4 → 1.6 → **1.9 (adaptador + validación 2f; el experimento puede correr en segundo plano)** → 1.5 → 1.5b → 1.5c → 1.7 → 1.8 → métricas.
   - El G2P va antes que el normalizador porque 2a necesita el inventario de grafemas.
   - El adaptador va antes que el normalizador porque cada segmento procesado debe salir ya validado contra el vocabulario de MMS.
3. Al terminar cada tarea: corre `ruff` y `pytest` y haz el commit. Si una prueba falla, repórtala con su salida; no la desactives.
4. Registra todo supuesto y toda limitación en `docs/limitations.md` a medida que aparezcan. Como mínimo: la mezcla de ortografías y variantes del corpus; que el corpus no es de noticias; que la prueba de ida y vuelta mide consistencia y no inteligibilidad humana; y la licencia no comercial de MMS.

# ENTREGABLE FINAL

1. `fase1_entrega.zip` con **solo los archivos nuevos o modificados**, conservando la estructura de carpetas. **No incluye el corpus ni los modelos.**
2. Un resumen breve con:
   - Qué se implementó.
   - Salida de `./init.sh --check` y los sistemas operativos donde se probó `init.sh`.
   - Las métricas de `fase_1.json` (valores reales), destacando el % de palabras fuera del vocabulario **antes y después** del adaptador y el CER por hipótesis.
   - La lista de entradas `SUPUESTO-LING` y `candidato-corpus` pendientes, con quién debe validarlas.
   - Las limitaciones encontradas.
   - El estado de la fase: **cerrada** o **implementada, pendiente de validación lingüística**.
3. Después, detente y espera aprobación antes de pasar a la Fase 2.
