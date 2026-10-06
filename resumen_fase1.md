# Resumen de la Fase 1: Pipeline de texto

> **Proyecto:** Servicio web de noticias en lengua asháninka con síntesis de voz, texto y avatar
> **Fecha:** 2026-10-05 · **Commit de entrega:** `c62e8c6` · **Entrega:** `fase1_entrega.zip`
> **Estado:** implementada, **pendiente de validación lingüística** (no cerrada)

Todas las cifras de este documento vienen de ejecuciones reales. Están en
`eval/results/fase_1.json` y `eval/results/mms_orthography.json`.

---

## 1. Qué hace el sistema hoy

Recibe una noticia escrita en asháninka (la que entrega el traductor de la tesis compañera) y la
deja **lista para ser leída por la voz sintética**:

1. La guarda con sus metadatos y su procedencia.
2. La divide en párrafos y oraciones.
3. Normaliza el texto:
   - unifica las variantes de escritura;
   - escribe números, fechas y dinero en palabras;
   - expande las siglas;
   - marca lo que está en castellano.
4. Convierte el texto a la ortografía que entiende el modelo de voz `mms-tts-cni`, y verifica que no quede ningún carácter que el modelo vaya a ignorar.
5. Segmenta cada palabra en sus unidades de escritura (G2P), dato que necesitará la sincronía labial del avatar en la Fase 3.
6. Genera un reporte editorial con lo que una persona debe revisar.

La Fase 1 **todavía no produce audio para el servicio**: el audio llega en la Fase 2. Solo se
sintetiza voz dentro de los scripts de evaluación.

```
noticia en asháninka
  └─► segmentación ─► normalización ─► TEXTO CANÓNICO ─┬─► G2P (unidades por palabra)
                                                       └─► adaptador MMS ─► validación ─► TEXTO PARA LA VOZ
```

---

## 2. Qué se implementó

| Tarea | Componente | Dónde está |
|---|---|---|
| 1.0 | Descarga del corpus AmericasNLP 2021, verificado por hash. Informe del corpus y extracción de candidatos (numerales, siglas, préstamos, nombres propios, variantes ortográficas, letras) | `backend/app/corpus/`, `docs/corpus_report.md`, `data/candidates/` |
| 1.1 | Estructura del proyecto, dependencias fijadas, `ruff`, `pytest`, `pre-commit` | raíz del repositorio |
| 1.1b | `init.sh`: instala y verifica todo en cualquier máquina | `init.sh` |
| 1.2 | Base de datos: noticias, procedencia obligatoria, segmentos y versión de las reglas usadas | `backend/app/db/` |
| 1.3 | API REST y línea de comandos para importar, procesar y consultar noticias | `backend/app/api/`, `backend/app/cli.py` |
| 1.4 | Segmentación en párrafos y oraciones (respeta abreviaturas y enumeraciones) | `backend/app/pipeline/segment.py` |
| 1.5 | Normalizador: unificación ortográfica, clasificación, verbalización, siglas y reescritura del castellano | `backend/app/pipeline/normalize/` |
| 1.5b | Detector editorial: marca números grandes, fechas, fechas relativas y términos sin glosario. **No modifica nada** | `normalize/editorial.py` |
| 1.5c | Mapa de alineación entre el texto original y el normalizado, para el resaltado sincronizado | dentro de cada segmento |
| 1.6 | G2P por reglas, con inventario sacado del corpus | `backend/app/pipeline/g2p/`, `docs/g2p.md` |
| 1.7 | 68 pruebas automáticas (98,7 % de cobertura) | `backend/tests/` |
| 1.8 | Hoja de escucha para validar la reescritura, con audios | `eval/listening/rewrite_check/` |
| 1.9 | Adaptador ortográfico para MMS y experimento que lo justifica | `backend/app/pipeline/tts/adapters/`, `eval/fase1/mms_orthography/`, `docs/mms_orthography.md` |
| — | Lista de 205 palabras para que un lingüista las transcriba (P5) | `eval/fase1/p5_sample.csv` |
| — | Documentación: README, licencias, citas, limitaciones | `README.md`, `LICENSES.md`, `CITATION.md`, `docs/limitations.md` |

### Dos ortografías internas

- **Ortografía canónica.** Es la del sistema: la mayoritaria del corpus (`k`, `b`, `ts`, `ñ`), según tu decisión del 2026-10-05. La usan el G2P y la documentación.
- **Ortografía MMS.** Es la que conoce el modelo de voz: no tiene `k`, `b`, `ñ` ni `z`. El adaptador convierte de una a otra. Si mañana se cambia de modelo de voz, solo cambia el adaptador.

---

## 3. Resultados

### El hallazgo central y su solución

El tokenizador de `mms-tts-cni` **borra en silencio** las letras que no conoce: *kipatsi* llega
al modelo como *ipatsi*. Con el texto tal como viene del corpus, el 53 % de las palabras se
pronunciaría incompleto.

| Medida (100 oraciones de dev) | Sin adaptador (H0) | Con adaptador (H1) |
|---|---|---|
| Error de caracteres, ida y vuelta voz→reconocedor (CER) | 0,150 | **0,059** |
| Intervalo de confianza 95 % | 0,138–0,162 | 0,051–0,066 |
| Palabras reconocidas correctamente | 29 % | 62 % |
| `k` recuperada | 5 % | 98 % |
| `b` recuperada | 14 % | 82 % |
| `ñ` recuperada | 0 % | **0 %** |

La diferencia es significativa (p < 0,001). Queda pendiente la `ñ`: el reconocedor transcribe
nuestro `ny` como `ne` + vocal, señal de que esa no es la escritura con la que se entrenó MMS.

### Otras medidas (883 oraciones de dev)

| Medida | Valor |
|---|---|
| Oraciones procesadas sin errores | 883 de 883 (906 segmentos) |
| Segmentos listos para la voz | 83,4 % |
| Palabras ilegibles para MMS, antes → después del adaptador | 53,0 % → 3,8 % |
| Caracteres que aún bloquean | `d`, `l`, `g`, `w`, `f`, `x` (castellano sin la tabla P2d) |
| Elementos sin normalizar | 5,6 % |
| Latencia p95 por segmento: normalización / adaptador / G2P | 0,38 ms / 0,51 ms / 0,10 ms |
| Informe del corpus comparado con el plan | sin diferencias |

---

## 4. Cómo se usa

Todos los comandos se ejecutan en una terminal **Git Bash** dentro de la carpeta del proyecto
(`C:\Users\Marco\Downloads\noticias-ashaninka`).

### 4.1 Instalar (una sola vez, o en una máquina nueva)

```bash
./init.sh
```

Instala `uv` y Python 3.11, las dependencias, la base de datos, el corpus y el vocabulario de
MMS, y al final ejecuta una prueba rápida.

```bash
./init.sh --check                          # solo verifica que todo esté bien (no cambia nada)
./init.sh --with-data                      # además genera el informe del corpus y procesa datos de prueba
./init.sh --with-audio-eval --with-asr-eval --yes   # descarga los modelos de voz (~4 GB) para evaluar
```

Si al abrir una terminal nueva el comando `uv` no existe:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

### 4.2 Cargar noticias

**Opción A: noticias propias.** Si tienes noticias en `.txt`, `.docx`, `.json` o `.csv`, primero
conviértelas al formato del sistema. En los `.txt` y `.docx`, la primera línea es el título:

```bash
uv run python scripts/convert_test_news.py ruta/a/mis_noticias --tipo traduccion_automatica --sistema "traductor-companera"
uv run python -m app.cli import data/news/
```

Importar dos veces la misma carpeta no duplica noticias.

**Opción B: oraciones del corpus como noticias de prueba.**

```bash
uv run python -m app.cli import --from-corpus dev --limit 20
```

Estas pseudo-noticias quedan marcadas como `corpus_americasnlp` y **nunca** son aptas para el experimento.

### 4.3 Procesar y revisar

```bash
uv run python -m app.cli process --all          # procesa todas las noticias
uv run python -m app.cli process --news 3       # solo la noticia 3
uv run python -m app.cli report --news 3        # reporte editorial legible
```

Ejemplo de reporte:

```
[0] (BLOQUEADO para TTS) Otimimotake amitakoteneri ashi Rudolph Anderson otsipatearo U2.
    · sin resolver: 'Rudolph' — nombre propio sin reescritura (gazetteer/P2d)
    · sin resolver: 'U2' — sigla sin entrada usable en el glosario (P2b)
    · sin resolver: '…' — bloqueado para TTS: fuera del vocabulario 'dl'
```

- **"Listo para TTS":** la voz puede leer ese segmento completo.
- **"Bloqueado":** contiene letras que el modelo borraría; falta una regla (normalmente P2d).
- **"Sin resolver":** algo que el sistema no supo normalizar. Nunca se descarta en silencio.
- **"Editorial":** sugerencias para una persona (redondear una cifra, revisar una fecha relativa…). El sistema no las aplica solo.

### 4.4 Usar la API web

```bash
uv run uvicorn app.main:app --reload
```

Abre <http://127.0.0.1:8000/docs> para probar los endpoints desde el navegador:

| Método | Ruta | Para qué |
|---|---|---|
| `POST` | `/api/news` | Crear una noticia (la procedencia es obligatoria) |
| `POST` | `/api/news/import` | Crear varias noticias |
| `GET` | `/api/news` · `/api/news/{id}` | Consultar noticias (nunca devuelve el texto en castellano) |
| `PUT` · `DELETE` | `/api/news/{id}` | Editar o borrar una noticia |
| `POST` | `/api/news/{id}/process` | Procesar una noticia |
| `GET` | `/api/news/{id}/segments` | Ver los segmentos: texto canónico, texto para la voz, mapas y unidades G2P |
| `GET` | `/api/news/{id}/editorial-report` | Ver el reporte editorial en JSON |

Formato mínimo de una noticia:

```json
{
  "titulo_cni": "…",
  "cuerpo_cni": "…",
  "variante_dialectal": "desconocida",
  "fecha_publicacion": "2026-10-05",
  "fuente_original": "…",
  "procedencia": {
    "tipo": "traduccion_automatica",
    "sistema": "traductor-companera",
    "version": "1.0",
    "revisado_por_hablante": false
  }
}
```

Una noticia solo es **apta para el experimento** si `revisado_por_hablante` es `true`.

### 4.5 Corpus, documentación y evaluación

```bash
uv run python -m app.cli corpus report       # -> docs/corpus_report.md
uv run python -m app.cli corpus extract      # -> data/candidates/*.yaml
uv run python -m app.cli build-docs          # -> docs/normalization_rules.md
uv run python -m app.cli validate-resources  # revisa que los YAML estén bien escritos

uv run pytest --cov --cov-report=json                      # pruebas y cobertura
uv run python -m eval.fase1.mms_orthography.run --n 100    # experimento del adaptador (~25 min en CPU)
uv run python -m eval.listening.rewrite_check.build        # hoja de escucha con audios
uv run python -m eval.fase1.p5_sample                      # lista de palabras para el lingüista
uv run python -m eval.fase1.run                            # métricas -> eval/results/fase_1.json
```

### 4.6 Cómo se incorpora un dato lingüístico validado

Las reglas viven en archivos YAML. Cada entrada tiene un **estado**:

- `validado`: aprobado por una persona experta; se usa.
- `candidato-corpus`: evidencia del corpus; **no** se usa salvo `NA_ALLOW_CANDIDATES=true` en `.env`, y el segmento queda marcado.
- `SUPUESTO-LING`: decisión provisional pendiente de validar.

Por ejemplo, para validar el numeral "1", agrega en
`backend/app/pipeline/normalize/resources/numerals_cni.yaml`:

```yaml
entries:
  - id: P2A-001
    description: "Numeral 1"
    replacement: "aparoni"
    value: 1
    source: "Nombre de la persona validadora, fecha"
    status: validado
```

Después ejecuta `build-docs` y `process --all`. Cada segmento guarda el hash de las reglas con que
se procesó, así que siempre se sabe qué versión generó cada resultado.

| Archivo | Para qué |
|---|---|
| `normalize/resources/numerals_cni.yaml` | Numerales nativos y el límite de "número pequeño" (P2a) |
| `normalize/resources/acronyms.yaml` | Siglas con su glosa en asháninka (P2b) |
| `normalize/resources/loanwords.yaml` | Préstamos asentados (P2c) |
| `normalize/resources/es_to_cni_phonology.yaml` | Reescritura del castellano como lo diría un bilingüe (P2d) |
| `normalize/resources/neologisms.yaml` | Neologismos validados (P2e) |
| `normalize/resources/proper_nouns.yaml` | Nombres propios y su pronunciación |
| `normalize/resources/orthography_variants.yaml` | Unificación hacia la ortografía canónica |
| `g2p/rules/inventory.yaml` | Letras y su fonema (P1) |
| `tts/adapters/mms_cni.yaml` | Hipótesis del adaptador para MMS |

---

## 5. Pendientes para cerrar la fase

| Pendiente | Impacto | Quién |
|---|---|---|
| **P2d**: tabla castellano→asháninka | Bloquea el 16,6 % de los segmentos | Lingüista o docente EIB |
| **Escritura de la `ñ` para MMS** | Hoy se pierde en el 100 % de los casos | Repetir el experimento con `ñ→y` y `ñ→n` (requiere tu aprobación) |
| **P1**: alfabeto e inventario fonémico | Sin él no hay fonemas reales ni visemas | Lingüista; fuentes de tu compañera |
| **P7**: ortografía del traductor de tu compañera | Confirma o cambia la ortografía canónica | Tu compañera |
| **P2a, P2b, P2c**: numerales, siglas, préstamos | Hoy los números se leen en castellano y las siglas quedan sin glosa | Hablantes y traductores |
| **P5**: 205 palabras transcritas | Permite medir el error del G2P | Lingüista |
| **Escuchas con hablante** (1.8 y A/B) | Confirman la inteligibilidad humana | Hablante bilingüe |

Las limitaciones completas están en `docs/limitations.md`. Las más importantes son estas:

- El corpus mezcla ortografías y variantes, y no es de noticias.
- La detección de castellano es heurística.
- El experimento mide la consistencia entre los modelos de MMS, no la comprensión humana.
- `init.sh` solo se probó en Git Bash sobre Windows 11.
