# Plan de desarrollo — Servicio web de noticias en asháninka con voz sintética, texto y avatar

> **Tesis:** "Servicio web de noticias en lengua asháninka para mejorar el acceso a información mediante síntesis de voz, texto y avatar"
> **Documento:** Plan de desarrollo (cierre de la Fase 0, versión 1.2)
> **Fecha:** 2026-10-05
> **Cambios en v1.2:** se incorpora el corpus AmericasNLP 2021 asháninka–castellano (§3.2). Hallazgo crítico: la ortografía del corpus no coincide con la del modelo de voz `mms-tts-cni`. Se agregan la sub-etapa 2e (adaptador ortográfico), el pendiente P6, la prueba de ida y vuelta TTS→ASR y los riesgos R13–R15
> **Cambios en v1.1:** P2 (política de normalización) resuelto a nivel de política. Se añaden §3.1, nuevos pendientes P2a–P2e, rediseño de la tarea 1.5 y riesgos R10–R12
> **Estado:** Fases 1, 2 y 3 aprobadas (2026-10-12). Fase 2 con la línea base eSpeak-NG cerrada (tareas 2.3, 2.8 y 2.10 al 100 %). Fase 4 en ejecución (2026-10-12)

Todas las cifras de latencia, rendimiento y calidad de este documento son **metas o estimaciones**. Ninguna ha sido medida aún. Los valores reales se registrarán en `eval/results/` al cerrar cada fase.

---

## 1. Decisiones confirmadas

| Tema | Decisión | Origen |
|---|---|---|
| Backend | Python 3.11 + FastAPI + SQLite (SQLModel) | Confirmado por el tesista |
| Frontend | TypeScript + Vite + Preact, como PWA | Confirmado por el tesista |
| Infraestructura | Primero **local** (Windows, sin GPU). Luego se migra a un servidor dimensionado con las mediciones de la Fase 2 | Confirmado por el tesista |
| Fuente de las noticias | Las noticias ya llegan **en asháninka**, generadas por el **sistema de traducción español→asháninka de la tesis de una compañera**. Este proyecto empieza en el texto asháninka | Confirmado por el tesista |
| Corpus actual | Hay noticias de prueba en asháninka. No hay traductores humanos disponibles por ahora | Confirmado por el tesista |
| Corpus lingüístico | **AmericasNLP 2021, asháninka–castellano** (texto paralelo, sin audio). Se usa como evidencia empírica y como corpus de prueba del pipeline de texto, **no** como autoridad lingüística ni como noticias del experimento (§3.2) | Confirmado por el tesista (v1.2) |
| Dispositivos del experimento | Celulares Android de gama media con 4G | Confirmado por el tesista |
| Avatar | Libertad de tecnología; el criterio es **rapidez de desarrollo con calidad**. El diseño de la presentadora es propio | Confirmado por el tesista |
| TTS principal | `facebook/mms-tts-cni` (VITS, **CC-BY-NC 4.0**) | Heredado del proyecto Unity anterior |
| TTS de línea base | G2P propio + eSpeak-NG (GPL-3.0) | Fase 0 |
| Política de normalización | Política por categoría + **reescritura fonética previa** a la ortografía asháninka: una sola voz y un solo flujo de visemas (ver §3.1) | Confirmado por el tesista (v1.1) |
| Avatar (tecnología) | **Three.js + `@pixiv/three-vrm`**, con un modelo VRM diseñado en **VRoid Studio** | Fase 0, ratificado por la pregunta 5 |

### Por qué no se usa Unity

Del proyecto anterior se reutiliza el conocimiento, no el motor:

- La integración con `mms-tts-cni`.
- La lógica de lectura de WAV (`AvatarVoz.cs`, adaptada a Python o TypeScript).
- El patrón de gestos disparados por eventos (`AvatarGestos.cs`).
- La experiencia con uLipSync.

Unity WebGL queda descartado por cuatro motivos:

1. Su compilación mínima excede el límite de 3 MB de carga inicial.
2. Compila lento, lo que alarga cada ciclo de prueba.
3. Su servidor `HttpListener` no funciona en el navegador.
4. El modelo actual es masculino, y aquí se necesita una presentadora.

Three.js + VRM resuelve los cuatro puntos:

- Se descarga en unos cientos de KB, más el modelo comprimido.
- VRoid Studio permite diseñar la presentadora en horas, sin saber modelado 3D.
- El formato VRM ya trae formas de boca vocálicas (A, I, U, E, O) y parpadeo.
- Las animaciones de Mixamo se pueden adaptar (retargeting) al esqueleto VRM.

**Alternativa evaluada:** la librería [TalkingHead](https://github.com/met4citizen/TalkingHead) (MIT). Pide avatares con los 15 visemas de Oculus, que VRoid no genera; sus modelos de referencia venían de Ready Player Me, que ya no opera. Se hará una prueba de 1 día al inicio de la Fase 3. Si resulta más rápida, se adopta y se documenta el cambio.

---

## 2. Integración con la tesis de traducción

La tesis de la compañera es el **primer eslabón** del pipeline. Para que ambas tesis sean independientes y citables, la integración se define con un contrato de datos versionado:

```json
POST /api/news
{
  "titulo_cni": "…",
  "cuerpo_cni": "…",
  "titulo_es": "…",
  "cuerpo_es": "…",
  "variante_dialectal": "SUPUESTO: por definir",
  "fecha_publicacion": "2026-10-04",
  "fuente_original": "nombre del medio o URL",
  "procedencia": {
    "tipo": "traduccion_automatica",
    "sistema": "nombre del traductor de la compañera",
    "version": "x.y.z",
    "revisado_por_hablante": false,
    "revisor_id": null
  }
}
```

**Reglas del contrato**

1. Hay dos modos de ingesta:
   - **Archivo** (JSON o CSV en `data/news/`) desde el día 1. Así este proyecto no depende de que el traductor esté desplegado.
   - **API**, cuando el traductor esté disponible.
2. El campo `procedencia` es **obligatorio**.
3. El texto en castellano (`*_es`) se guarda como referencia, pero **nunca se muestra durante el experimento**. Si se mostrara, contaminaría la medición de comprensión en asháninka.
4. **Solo pueden entrar al experimento noticias con `revisado_por_hablante: true`.** Si no hay ninguna revisada, el experimento no puede ejecutarse (ver el riesgo R2).
5. Las **decisiones editoriales** de la política de normalización (redondear cifras, pasar fechas a relativo, neologismos de P2e) deben venir **ya aplicadas** en el texto que entrega el traductor o la revisión (§3.1). Este sistema solo las detecta y las reporta; no las aplica.

**Para la tesis:** se cita el trabajo de la compañera en los antecedentes y en la arquitectura, como el componente de traducción. La calidad de su traducción **no** se evalúa aquí; solo se controla su procedencia como variable.

---

## 3. Pendientes bloqueantes

El desarrollo avanza con supuestos marcados como `# SUPUESTO-LING` en el código, pero **la Fase 1 no se cierra** sin resolver P1, P2a y P2d.

| ID | Pendiente | Estado | Lo bloquea | Quién podría resolverlo |
|---|---|---|---|---|
| **P1** | Alfabeto oficial e inventario fonémico del asháninka (grafemas, dígrafos, vocales largas, nasalización) **y la ortografía canónica del sistema** | Abierto, **con evidencia del corpus (v1.2)**: inventario de grafemas observado y variación ortográfica medida (§3.2). La evidencia orienta, pero no reemplaza la validación | G2P, visemas, reescritura fonética (P2d depende de P1) y unificación ortográfica | Norma del MINEDU, la tesis de la compañera, docentes EIB, Ortega et al. (2020) |
| ~~**P2**~~ | ~~Política de normalización~~ | **Resuelto como política (v1.1)**, ver §3.1. Queda abierto el contenido lingüístico concreto, en P2a–P2e | — | — |
| **P2a** | **Sistema numeral nativo:** límite superior de los "números pequeños" y forma escrita de cada número | Abierto, **con candidatos del corpus (v1.2)**: pares del tipo "palabra (dígito)" en el texto paralelo (§3.2) | Verbalización de números | Hablantes, docentes EIB, la compañera |
| **P2b** | **Glosario de siglas:** sigla → glosa en asháninka validada + modo de lectura (como palabra o deletreada) + reescritura fonética | Abierto, crece con el uso | Expansión de siglas | Traductores, la compañera |
| **P2c** | **Léxico de préstamos asentados:** forma castellana → forma adaptada que usa la comunidad | Abierto, crece con el uso | Reescritura de préstamos | Hablantes |
| **P2d** | **Tabla de adaptación fonológica castellano→asháninka:** qué fonemas castellanos no existen (por ejemplo /l/, señalado por el tesista) y por cuál se sustituye cada uno | Abierto | Reescritura de lo que no está en P2b ni P2c (nombres propios, números y fechas en castellano) | Lingüista o docente EIB. **No se inventa** |
| **P2e** | **Glosario de neologismos y perífrasis** (vacuna, elecciones, inflación…) | Abierto | Etapa editorial (no la normalización automática, ver §3.1) | Traductores + glosarios de EIB del Minedu |
| **P3** | Variante dialectal de las noticias de prueba y de los futuros participantes | Metadatos, interfaz, análisis por variante | Fuente de las noticias y contacto comunitario |
| **P4** | Al menos **8 noticias revisadas por un hablante**, equivalentes en longitud | Experimento (Fase 5) | Hablante colaborador (aunque sea uno solo) |
| **P5** | Conjunto de referencia de **unas 200 palabras con su transcripción fonémica** | Medir la tasa de error del G2P | Lingüista o docente EIB. Las palabras se pueden muestrear del corpus por frecuencia |
| **P6** | **Ortografía con la que se entrenó `mms-tts-cni`** y su correspondencia con la ortografía canónica del sistema (por ejemplo, ¿la /k/ se escribe "c" o "qu"? ¿cómo se escribe la "ñ"?) | **Nuevo (v1.2), crítico** | Adaptador ortográfico 2e. Sin él, el TTS pronuncia mal más de la mitad de las palabras (§3.2) | Experimento propio de la Fase 1 (tarea 1.9): prueba de ida y vuelta TTS→ASR con hipótesis alternativas + escucha de un hablante. Se puede complementar con el texto de la Biblia asháninka en la ortografía antigua del ILV/SIL |
| **P7** | **Ortografía de salida del traductor de la compañera**: ¿con qué corpus se entrenó? Si fue con AmericasNLP, hereda su variación ortográfica | Nuevo (v1.2) | Unificación ortográfica 2-0 | La compañera |

> **Recomendación:** pedir a la compañera las fuentes lingüísticas que ya usa. Probablemente resuelve P1 y parte de P2a–P2e sin costo adicional.

### 3.1 Política de normalización (aprobada en v1.1)

#### Política por categoría

| Categoría | Cómo se lee | Justificación | Dónde se aplica |
|---|---|---|---|
| Números pequeños (cantidades bajas) | En asháninka | El sistema numeral nativo cubre cantidades bajas y es de uso cotidiano | Normalización automática (requiere P2a) |
| Números grandes, porcentajes, dinero | En castellano, o reformulados ("más de mil personas", "la mitad") | Es el uso real; cuando el número no es esencial, redondear reduce la carga cognitiva | Lectura en castellano: **automática**. Reformulación: **editorial** (ver abajo) |
| Años y fechas completas | Día, mes y año en castellano | No hay nombres nativos de meses de uso extendido | Automática |
| Fechas relativas ("ayer", "la próxima semana") | En asháninka | Más comprensible que una fecha completa | **Editorial**, con salvaguarda (ver R10) |
| Siglas | Primera mención: glosa en asháninka + sigla en castellano. Después, solo la sigla | La sigla es opaca aunque se pronuncie bien; la glosa es lo que da comprensión | Automática por documento (requiere P2b) |
| Nombres propios (personas, lugares mestizos, instituciones) | Castellano | No se traducen | Automática (reescritura fonética, P2d) |
| Préstamos asentados | Forma adaptada a la fonología asháninka | Así los pronuncia la comunidad | Automática (léxico P2c) |
| Conceptos nuevos | Neologismo o perífrasis validada con traductores y glosarios de EIB | Evita inventar términos sin aval comunitario | **Editorial** (P2e). El normalizador solo detecta y marca |

#### Decisión técnica: reescritura fonética previa

Todo lo que se lee en castellano (números grandes, fechas, siglas, nombres propios) se **reescribe con la ortografía asháninka, tal como lo diría un hablante bilingüe**, antes de llegar al TTS. Por ejemplo, "2026", "MINSA" o "Satipo" se convierten en su pronunciación escrita en ortografía asháninka.

- **Ventajas:**
  - Una sola voz (`mms-tts-cni`).
  - Un solo G2P monolingüe.
  - Un solo flujo de visemas.
  - Ningún cambio de voz a mitad de una oración.
  - Es la opción más defendible para un servicio de bajos recursos.
- **Alternativas descartadas:**
  - **Cambiar a una voz castellana** para los fragmentos en castellano: hay dos voces y un cambio de timbre a mitad de oración, se necesitan dos G2P y dos mapas de visemas, y la sincronización se complica.
  - **Pasar el castellano tal cual** al TTS asháninka: el modelo pronuncia mal los fonemas que no existen en la lengua, como /l/.
- **Contribución citable:** la tabla P2d, el glosario P2b y el léxico P2c, versionados y documentados regla por regla en `docs/normalization_rules.md`.

#### Separación entre la etapa editorial y la normalización automática

La política mezcla dos tipos de operaciones, y el sistema las trata por separado:

- **Transformaciones deterministas**, que conservan el contenido: verbalizar, expandir siglas y reescribir fonéticamente. Las hace el **normalizador** (etapa 2) de forma automática y reproducible.
- **Decisiones editoriales**, que cambian el contenido: redondear cifras, pasar fechas a relativo y crear neologismos. **No** las hace el normalizador. Corresponden al texto que llega del traductor o de la revisión humana. El normalizador solo las **detecta y marca** (por ejemplo, "número grande no esencial: candidato a redondeo" o "término sin entrada en el glosario"). Si las hiciera solo, el sistema estaría editando la noticia sin aval humano.

#### Sub-etapas del normalizador

```
texto cni (con fragmentos en castellano y ortografía variable)
  2-0 Unificación ortográfica → variantes de escritura (p. ej. b/v, ts/tz) → ortografía CANÓNICA del sistema (P1, P7)  [v1.2]
  2a Clasificación de tokens → número_pequeño | número_grande | porcentaje | dinero |
                               año | fecha | sigla | nombre_propio | préstamo | desconocido
  2b Verbalización           → números pequeños en cni (P2a). Números, fechas y dinero en palabras castellanas
  2c Siglas                  → glosa cni + sigla en la 1.ª mención del documento, solo sigla después (P2b)
  2d Reescritura fonética    → castellano → ortografía canónica cni: primero el léxico (P2c, P2b), luego la tabla de reglas (P2d)
        │
        ├──► texto canónico ──► G2P (etapa 3), visemas, resaltado
        ▼
  2e Adaptador ortográfico   → ortografía canónica → ortografía de entrenamiento de MMS (P6)  [v1.2]
  2f Validación              → cada carácter de salida debe existir en el vocabulario de mms-tts-cni
texto en ortografía MMS (solo para el TTS)  +  mapas de alineación original↔canónico↔MMS
```

**Por qué hay dos ortografías internas.** El G2P, los visemas y la documentación trabajan sobre la ortografía **canónica**, la oficial y validada por personas expertas. El adaptador 2e es un detalle de implementación del motor MMS: convierte a la ortografía con la que ese modelo fue entrenado. Si mañana se cambia de motor TTS, solo cambia el adaptador. Por eso vive en `pipeline/tts/adapters/` y no en las reglas lingüísticas. El adaptador también produce un mapa de caracteres: las duraciones que devuelve VITS (Fase 3) están en caracteres de la ortografía MMS y hay que devolverlas a la canónica.

#### Implicación técnica: lo que se muestra difiere de lo que se pronuncia

En pantalla se muestra el texto **original** ("MINSA", "2026"), pero el audio pronuncia la forma **expandida y reescrita**. Por eso el normalizador produce un **mapa de alineación** entre cada fragmento original y sus tokens normalizados. El resaltado sincronizado usa ese mapa: mientras suena la glosa y la sigla expandida, se resalta "MINSA" completo. Sin ese mapa, el resaltado y el audio se desincronizan justo en los números, fechas y siglas.

### 3.2 Corpus AmericasNLP 2021 asháninka–castellano (v1.2)

**Fuente:** <https://github.com/AmericasNLP/americasnlp2021/tree/main/data/ashaninka-spanish> (paralelo) y `test_data/test.cni`. Lo extrajo y preprocesó Richard Castro (proyecto AshaninkaMT), a partir de diccionarios, textos de Mihas (2011, alto Perené) y traducciones propias.

**Citas obligatorias** (según el README del corpus): Ortega, Castro-Mamani y Montoya Samame (2020), *Overcoming Resistance: The Normalization of an Amazonian Tribal Language*, LoResMT; Cushimariano Romano y Sebastián Q. (2008), diccionario asháninka–castellano; Mihas (2011). Si se usa el corpus monolingüe complementario (`iapucp/multilingual-data-peru`, carpeta `cni`): Bustamante, Oncevay y Zariquiey (2020), LREC.

**Licencia:** el repositorio no declara una licencia explícita. Se usa con fines académicos, citando, y esa condición queda registrada en `LICENSES.md`. **No se redistribuye el corpus dentro del repositorio del proyecto**: `init.sh` lo descarga.

#### Mediciones iniciales

Análisis exploratorio ejecutado el 2026-10-05 sobre los archivos descargados del repositorio y el vocabulario publicado de `facebook/mms-tts-cni`. Se repetirá de forma reproducible en la Fase 1 (tarea 1.0).

| Medida | train | dev | test |
|---|---|---|---|
| Oraciones (líneas paralelas) | 3 883 | 883 | 1 003 |
| Tokens en asháninka | 26 145 | 6 086 | 6 453 |
| Tipos (palabras distintas, en minúsculas) | 10 231 | 2 686 | 2 899 |
| Caracteres (sin espacios) fuera del vocabulario de MMS | 13,46 % | 10,87 % | 11,20 % |
| **Palabras con al menos un carácter fuera del vocabulario de MMS** | **60,3 %** | **53,0 %** | **53,7 %** |
| Líneas con dígitos | 338 | 94 | 71 |

#### Hallazgo crítico: el corpus y el modelo de voz usan ortografías distintas

- **Vocabulario de `mms-tts-cni`:** 31 símbolos, todos en minúscula. Las letras son `a c e h i j m n o p q r s t u v y`, más los dígitos, `'`, `-` y el espacio. **No incluye `k`, `b`, `ñ`, `z`, `g`, `l`, `d` ni `f`.** El modelo de reconocimiento de voz MMS (`mms-1b-all`, adaptador `cni`) tiene exactamente las mismas letras. Esto sugiere que ambos se entrenaron con textos en la ortografía antigua, que escribe la /k/ con "c" y "qu".
- **El corpus usa la ortografía moderna:** `k` es la letra fuera del vocabulario más frecuente (16 185 apariciones en train), seguida de `b` (2 237), `z` (1 851) y `ñ` (1 495).
- **Consecuencia verificada en el código fuente de `transformers`:** `VitsTokenizer`, con `normalize=True`, **elimina en silencio** todo carácter que no está en el vocabulario. Por ejemplo, *kipatsi* llegaría al modelo como *ipatsi*. Así, más de la mitad de las palabras de un texto en ortografía moderna se pronunciaría incompleta, sin ningún error ni aviso. Este defecto probablemente también afecte al proyecto Unity anterior, aunque no se ha verificado porque no se ha visto su backend.
- **El corpus mezcla ortografías:** `b` (2 237) junto a `v` (1 897), con la misma palabra escrita de ambas formas (*maba* 16 y *mava* 13); `tz` (1 819) junto a `ts` (4 133). También mezcla variantes (asháninka, ashéninka, alto Perené). De ahí salen la sub-etapa 2-0 y el pendiente P7.

#### Otras evidencias

- **Los dígitos se conservan al traducir:** 337 de las 340 líneas de train con dígitos en castellano también los tienen en asháninka. Un traductor entrenado con este corpus producirá dígitos, así que la normalización de números es imprescindible.
- **Candidatos para P2a** (aparecen en el corpus como "palabra (dígito)"): *aparoni* (1) ×12, *apite* (2) ×5, *apapakoroni* (5) ×4, *maba* (3) ×1. Uno es ruido: *apapakoroni* (0,5). Los números grandes aparecen en castellano, como "diez mil (10,000)", lo que coincide con la política del §3.1. **Estado: candidato del corpus, pendiente de validación. No es un dato confirmado.**
- **Siglas y nombres propios:** VIII, FOSPA, UIT, I.U., CIA, U2, Kennedy, Washington… son el material inicial para P2b y para el gazetteer.

#### Qué uso se le da y qué uso no

| Uso | Sí / No | Detalle |
|---|---|---|
| Evidencia para P1 (grafemas, dígrafos, variación) | **Sí** | Informe de frecuencias. La decisión final la valida una persona experta |
| Candidatos para P2a, P2b, P2c y el gazetteer | **Sí** | Extracción automática con estado `candidato-corpus` |
| Corpus de prueba del pipeline de texto | **Sí** | **train** para construir y depurar reglas; **dev** para ajustar; **test** solo para la medición final. Las reglas no se ajustan mirando test |
| Material de la prueba de ida y vuelta TTS→ASR (P6) y de escucha | **Sí** | Oraciones de dev |
| Entrenar o ajustar el TTS | **No** | No tiene audio |
| Noticias del experimento | **No** | No son noticias (textos legales, cartas, oraciones traducidas) y no están revisadas para este fin |
| Autoridad lingüística | **No** | Mezcla ortografías y variantes |

---

## 4. Arquitectura (resumen)

```
 Tesis de traducción (es→cni)
            │  JSON con contrato
            ▼
┌──────────────────────────── BACKEND (FastAPI) ───────────────────────────┐
│ [1] Ingesta → [2] Normalización → [3] G2P → [4] TTSEngine → [5] Alineación│
│                                              ├ MmsVits       ├ duraciones │
│                                              └ ESpeak (base) │ VITS / MMS │
│                                                              ▼     FA     │
│                                          [6] Fonema→Visema               │
│   Modo por lotes: static/news/{id}/manifest.json + seg_NNN.{opus,mp3,json}│
│   Modo bajo demanda: /api/synthesize (streaming por oración)              │
│   [M] Métricas por etapa         [X] Experimento + exportación CSV        │
└──────────────────────────────────────────────────────────────────────────┘
            │ HTTP con Range
            ▼
┌──────────────────────── PWA (< 3 MB de carga inicial) ───────────────────┐
│ [7] Reproductor por segmentos · resaltado de texto · avatar VRM (carga    │
│     diferida, con degradación) · condiciones C1–C4 · cola de eventos      │
│     offline · interfaz en cni/es                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

**Unidad de entrega:** el **segmento**, es decir, una oración con su audio y su JSON de tiempos (palabras, fonemas, visemas). Esto permite:

- Un TTFA bajo en el modo bajo demanda.
- Reanudar descargas.
- Cachear noticias.
- Repetir por párrafo.
- Comparar con justicia el modo por lotes y el bajo demanda, porque usan el mismo formato.

### Detalle técnico clave: alineación sin un alineador externo

`mms-tts-cni` es un modelo VITS: recibe **caracteres** y decide internamente cuánto dura cada uno. Se instala un *forward hook* sobre `duration_predictor` del `VitsModel` de Hugging Face para capturar esas duraciones. Luego se repite la misma operación que hace el modelo (`ceil(exp(log_dur) · mask · length_scale)`) y se convierte de frames a segundos.

Hay que tener en cuenta dos detalles:

1. El tokenizador de MMS intercala tokens en blanco entre los caracteres (`add_blank`). Su duración se reparte entre los caracteres vecinos.
2. Como la ortografía es transparente, los caracteres se agrupan en grafemas y fonemas con el G2P (por ejemplo, un dígrafo suma las duraciones de sus dos caracteres).

El resultado son **tiempos exactos para el audio sintetizado, sin costo adicional**. El alineador forzado de MMS (torchaudio) sirve para validar los tiempos y para la línea base eSpeak.

---

## 5. Plan por fases

**Convenciones para todas las fases**

- Cada fase termina con un zip que contiene **solo los archivos nuevos o modificados**, un `CHANGELOG` de la fase y `eval/results/fase_N.json` con métricas reales, el hash del commit y los datos del hardware.
- Cronograma estimado: unas 15,5 semanas de desarrollo más el trabajo de campo. La pista paralela (§6) reduce el camino crítico.

### Fase 1 — Pipeline de texto (2,5 semanas; +0,5 por las tareas 1.0 y 1.9 de v1.2)

**Objetivo:** que una noticia en asháninka entre al sistema, se normalice y produzca fonemas, todo con trazabilidad.

| Tarea | Detalle |
|---|---|
| 1.0 Corpus AmericasNLP | `init.sh` lo descarga (no se versiona en el repositorio) y verifica sus hashes. Script de **informe del corpus** que reproduce las mediciones del §3.2. **Extractores de candidatos**: numerales (P2a), siglas (P2b), préstamos castellanos dentro de oraciones asháninka (P2c), nombres propios (gazetteer) y variantes ortográficas (2-0). Todo sale con `status: candidato-corpus` y su frecuencia |
| 1.1 Esqueleto del repositorio | `uv` (entorno Python), `ruff`, `pytest`, `pre-commit`, estructura de carpetas, README mínimo |
| 1.2 Modelo de datos | `News`, `Provenance`, `Segment`, con migraciones. Restricción: una noticia sin procedencia no se guarda |
| 1.3 Ingesta | CRUD con FastAPI + carga masiva desde `data/news/*.json`. Se validan contra el contrato del §2 |
| 1.4 Segmentación | Oraciones y párrafos (reglas de puntuación, configurables) |
| 1.5 Normalización | Implementar las sub-etapas 2-0 a 2f de §3.1. El adaptador 2e es el de la tarea 1.9. Recursos en YAML versionados: `numerals_cni.yaml` (P2a), `acronyms.yaml` (P2b), `loanwords.yaml` (P2c), `es_to_cni_phonology.yaml` (P2d). Verbalización castellana con `num2words` (lang `es`). **Cada regla lleva id, descripción, ejemplo y fuente.** Lo que no tiene regla se marca, nunca se descarta. Se genera automáticamente `docs/normalization_rules.md` (contribución citable) |
| 1.5b Detector editorial | Marca sin modificar: números grandes candidatos a redondeo, fechas que podrían pasarse a relativo, términos sin entrada en P2e. Genera un reporte por noticia para el revisor o la compañera |
| 1.5c Mapa de alineación | Fragmento original ↔ tokens normalizados, guardado por segmento. Lo usa el resaltado (Fase 4) |
| 1.6 G2P basado en reglas | Inventario en `inventory.yaml` y reglas de coincidencia más larga en `cni.yaml`. Es **monolingüe**: gracias a la reescritura previa, solo recibe ortografía asháninka. Todo marcado como `SUPUESTO-LING` hasta resolver P1 |
| 1.7 Pruebas | Unitarias por regla y por categoría de la política. Prueba de "primera mención" de siglas. Prueba de que el 100 % de los caracteres de salida está en el vocabulario de `mms-tts-cni`. Prueba con todas las noticias de prueba. Tasa de error del G2P contra el conjunto de referencia (si P5 ya está disponible) |
| 1.8 Validación auditiva de la reescritura | Sintetizar con MMS una lista de nombres propios, fechas y siglas reescritos, y que un hablante bilingüe juzgue si "suena como lo diría un bilingüe". Se reporta el % aceptado |
| 1.9 Experimento de ortografía MMS (P6) | **Hipótesis** de correspondencia canónica→MMS (p. ej. k→c/qu, b→v, ñ→?) escritas en YAML como `SUPUESTO`. **Prueba de ida y vuelta**: oraciones de dev en cada hipótesis → `mms-tts-cni` → reconocimiento de voz `mms-1b-all` (adaptador `cni`) → tasa de error de caracteres (CER) contra la entrada. Se compara contra la **condición sin adaptar** (caracteres eliminados en silencio). Gana la hipótesis con menor CER y se confirma con la escucha de un hablante (1.8). Limitación declarada: el TTS y el reconocedor comparten datos de entrenamiento, así que la prueba mide consistencia, no inteligibilidad humana |

**Criterios de cierre**

- Cobertura de pruebas del pipeline de texto ≥ 90 %.
- El 100 % de las noticias de prueba y del split dev del corpus se procesa sin excepciones.
- El 100 % de la salida está en el vocabulario del TTS, **sin depender de que el tokenizador elimine caracteres**.
- Informe del corpus y candidatos generados de forma reproducible.
- Adaptador 2e elegido con evidencia (CER de ida y vuelta por hipótesis).
- Se reporta el porcentaje de elementos sin normalizar y el de elementos marcados por el detector editorial.
- La tasa de error del G2P se mide si existe P5; si no, queda declarada como pendiente.
- P1, P2a y P2d validados por una persona experta. P2b, P2c y P2e pueden cerrar con una versión inicial que crece con el uso.

### Fase 2 — Síntesis de voz y medición de RTF/TTFA (2 semanas)

| Tarea | Detalle |
|---|---|
| 2.1 Interfaz `TTSEngine` | `synthesize(text|phonemes) -> AudioResult(wav, sr, durations?, meta)` y `info() -> {modelo, versión, licencia, variante}` |
| 2.2 `MmsVitsEngine` | Modelo cargado una sola vez en memoria, CPU, semilla fija (reproducibilidad), hook de duraciones (§4) |
| 2.3 `ESpeakEngine` | Recibe los fonemas del G2P en notación `[[…]]` de eSpeak-NG. Línea base sin restricción comercial |
| 2.4 Registro de licencias | `LICENSES.md` + campo de licencia en los metadatos de cada audio. Aviso automático si el modelo es no comercial |
| 2.5 Codificación | Opus (meta: 24–32 kbps) + respaldo MP3. Manifiesto por noticia |
| 2.6 Modo por lotes | CLI `python -m app.batch build --all` → `static/news/{id}/` |
| 2.7 Modo bajo demanda | `/api/synthesize/{id}` con streaming por oración (NDJSON con metadatos + URLs de los segmentos a medida que se generan) |
| 2.8 Banco de pruebas | `eval/rtf_ttfa/`: N ≥ 100 síntesis por motor, noticias de hasta 500 caracteres. Se reporta RTF (media y desviación) y TTFA (p50, p95, p99), en modo por lotes y bajo demanda, y con 1, 4 y 8 clientes concurrentes |
| 2.9 Dimensionamiento | Con los datos de 2.8 se calcula la CPU y RAM del servidor (§7) |
| 2.10 Inteligibilidad objetiva (v1.2) | CER de ida y vuelta TTS→ASR (método de la tarea 1.9) sobre el split **test** del corpus, para ambos motores. Es una medida automática y reproducible que complementa, sin reemplazar, la prueba con hablantes de la Fase 5 |

### Estado de la Fase 2: APROBADA (2026-10-12)

- **Modo principal de entrega: por lotes** (TTFA p95 de 44 ms, cumple < 2 s). **Bajo demanda: solo respaldo** (TTFA p95 de 2357 ms con 1 cliente; no cumple y no se usa en el experimento).
- RTF de `mms_vits`: 0,19 (AMD de 16 núcleos) y 0,2546 (Intel de 12, reejecución final). CER de ida y vuelta sobre test: 0,0516.
- **Línea base eSpeak-NG: CERRADA (2026-10-12).** Las tareas **2.3, 2.8 y 2.10 quedaron al 100 %**. eSpeak-NG 1.52.0: RTF 0,0105 (DE 0,005); CER de ida y vuelta sobre test 0,2291 [0,2203; 0,2382], precisión por palabra 0,0511 (frente a 0,0516 y 0,647 de `mms_vits`). La reejecución se hizo en un Intel de 12 núcleos: el RTF de `mms_vits` allí es 0,2546 (0,19 en el AMD original). Detalle en `resumen_fase2.md` §7.

**Criterios de cierre**

- RTF < 1.0 y TTFA p95 < 2 s **medidos** en local. Si no se cumplen, se reportan igual y se documenta la causa.
- CER de ida y vuelta reportado por motor.
- Ambos motores son intercambiables con un solo parámetro de configuración.

### Fase 3 — Alineación, visemas y avatar (3 semanas)

| Tarea | Detalle |
|---|---|
| 3.1 Prueba de 1 día | Comparar TalkingHead con three-vrm y elegir (§1) |
| 3.2 Alineación | Duraciones de VITS → tiempos por fonema y palabra. Validación contra el alineador de MMS y contra **20 oraciones anotadas a mano** en Praat (error medio de los límites en ms) |
| 3.3 Mapa fonema→visema | `viseme/map.yaml`: fonemas → {A, I, U, E, O, cerrado, neutro} con pesos. `SUPUESTO-LING` hasta resolver P1 |
| 3.4 Pista de visemas | Coarticulación con suavizado (transiciones de 40–60 ms, parámetro configurable). Se exporta en el JSON del segmento |
| 3.5 Avatar en el cliente | Carga diferida de `three-vrm`, controlador de visemas sincronizado con `audio.currentTime`, parpadeo y mirada sutil, 3–4 animaciones de Mixamo adaptadas (reposo hablando, saludo de apertura, asentir, despedida) |
| 3.6 Degradación | Sondeo de FPS durante 2 s. Si los FPS son menores a 20, o no hay WebGL, se pasa a audio + texto con una imagen fija, y se **registra el evento** |
| 3.7 Captura para métricas | Playwright graba el canvas → ≥ 30 clips MP4 |
| 3.8 Métricas de sincronía labial | LSE-D y LSE-C con SyncNet (`eval/lipsync/`) + **desfase directo**: correlación cruzada entre la energía del audio y la apertura de la boca renderizada. Criterio: ≤ 80 ms |

### Estado de la Fase 3: APROBADA (2026-10-12)

- **3.1:** se adopta **three + `@pixiv/three-vrm`**; TalkingHead descartado (exige morph targets ARKit/Oculus que VRoid no genera). `docs/avatar_decision.md`.
- **3.2–3.4:** alineación por palabra y fonema, mapa grafema → visema (`SUPUESTO-LING`) y pista con coarticulación en cada `seg_NNN.json`; manifiesto 1.1. Error del centro de palabra frente al alineador CTC: 63,9 ms de media (34 ms de mediana). **Pendiente:** las 20 oraciones anotadas en Praat (requiere a una persona).
- **3.5–3.6:** visor en `frontend/` (carga diferida, degradación probada). Paquete inicial de 11,7 KB gzip; avatar diferido de 224,5 KB; 60 FPS con GPU, 17–18 sin GPU. Modelo VRM **provisional** (2,41 MB); gestos procedurales (Mixamo no es automatizable).
- **3.7–3.8:** 40 clips. Desfase sistemático −10,8 ms (IC 95 %: −18,5 a −2,1), total estimado 26–55 ms; el desfase **por clip** no es verificable con el método (calibrado con desplazamientos conocidos). SyncNet **no discrimina** con este avatar (control negativo idéntico).
- Resumen y detalle: `resumen_fase3.md`, `docs/avatar.md`, `eval/results/fase_3.json`.

**Criterios de cierre**

- LSE-D y LSE-C reportados sobre ≥ 30 clips.
- Desfase máximo medido ≤ 80 ms.
- La limitación de usar SyncNet con un avatar estilizado queda documentada en `docs/limitations.md`.

### Fase 4 — Interfaz web completa (3 semanas)

| Tarea | Detalle |
|---|---|
| 4.1 Base de la PWA | Vite + Preact, rutas, i18n (`cni.json`, `es.json`) con selector de idioma. Los textos de la interfaz en asháninka quedan **pendientes de traducción por un hablante** |
| 4.2 Reproductor | Reproducción por segmentos, sin cortes entre ellos (precarga del siguiente), velocidad de 0.75× a 1.25×, repetir párrafo, pausa |
| 4.3 Resaltado | Palabra activa sincronizada con los tiempos. Usa el mapa de alineación de 1.5c para resaltar el fragmento **original** ("MINSA", "2026") mientras suena su forma expandida. Tamaño de texto ajustable (3 niveles o más) |
| 4.4 Service Worker | Caché de noticias ya reproducidas, descargas con `Range` para reanudar, cola de eventos en IndexedDB que se sincroniza al volver la conexión |
| 4.5 Avisos éticos | Aviso visible de que la voz y el avatar son sintéticos. Etiqueta de la variante dialectal en cada noticia |
| 4.6 Condiciones experimentales | Un único componente de presentación con 4 modos: C1 solo texto, C2 solo voz, C3 voz + texto, C4 voz + texto + avatar |
| 4.7 Rendimiento del cliente | Presupuesto: carga inicial < 3 MB (shell + primer segmento). El avatar va **fuera** del presupuesto inicial, en carga diferida. Se mide con Playwright + CDP, con la CPU 4× más lenta y una red 4G simulada |

**Criterios de cierre**

- Peso inicial medido < 3 MB.
- Las 4 condiciones funcionan.
- La degradación está probada.
- Se verifica en **un Android de gama media real** y en simulación con la CPU 4× más lenta.

### Fase 5 — Instrumentación experimental (2 semanas)

| Tarea | Detalle |
|---|---|
| 5.1 Consentimiento | Pantalla de consentimiento informado (texto aprobado por el comité de ética de la universidad), con audio en asháninka |
| 5.2 Asignación | Cuadrado latino de Williams 4×4 para el orden de las condiciones + rotación de la asignación noticia↔condición (requiere **P4**: ≥ 8 noticias revisadas) |
| 5.3 Registro por sesión | ID anónimo (UUID generado en el dispositivo), condición, orden, noticia, tiempo en pantalla, repeticiones, pausas, cambios de velocidad, abandono, **degradación del avatar** |
| 5.4 Cuestionario | Ítems por noticia en asháninka. **Modalidad oral recomendada** (audio grabado por un hablante, no TTS) para no confundir comprensión con alfabetización. Covariables: variante, rango de edad, alfabetización autodeclarada, familiaridad con tecnología |
| 5.5 Privacidad | No se guardan nombres, documentos, teléfonos ni geolocalización precisa. La edad se registra por rangos. Una prueba automática verifica que el CSV no contenga identificadores personales |
| 5.6 Exportación | CSV + `data/DATA_DICTIONARY.md` (variable, tipo, unidad, valores, descripción) |
| 5.7 Guiones de evaluación | `eval/listening/`: inteligibilidad (transcripción de palabras clave → tasa de acierto) y MOS de naturalidad de 1 a 5, MMS frente a eSpeak, resultados por variante. Incluye el **análisis de potencia** para estimar el tamaño de muestra y el plan de análisis (modelo mixto: condición + orden + covariables, con participante y noticia como efectos aleatorios) |
| 5.8 Piloto | Prueba completa del flujo con 2–3 personas antes del campo |

**Criterios de cierre**

- El piloto completo se exporta a CSV sin errores.
- El diccionario de datos cubre el 100 % de las columnas.
- La prueba de privacidad pasa.

### Fase 6 — Despliegue, reproducibilidad y banco de pruebas (2 semanas)

| Tarea | Detalle |
|---|---|
| 6.1 Contenedores | `Dockerfile` para el backend, compilación estática del frontend, `docker-compose.yml` con un solo comando |
| 6.2 Servidor | VPS dimensionado con las mediciones de la Fase 2. Caddy como proxy con HTTPS automático (necesario para la PWA y el Service Worker) |
| 6.3 Banco de pruebas final | Se repiten las mediciones de las Fases 2, 3 y 4 en el servidor: local frente a servidor, por lotes frente a bajo demanda |
| 6.4 Reproducibilidad | README de "cero a funcionando" probado por **una persona ajena** al proyecto. Versiones fijadas, semillas y hashes de los modelos |
| 6.5 Documentación | `docs/architecture.md` (diagrama + tabla por etapa con **latencias medidas**), `docs/limitations.md`, `LICENSES.md` |

**Criterios de cierre:** una persona revisora reproduce el sistema y el banco de pruebas solo con el README.

---

## 6. Cronograma

```
Semana:            1  2  3  4  5  6  7  8  9 10 11 12 13 14 15 16
F1 Texto + corpus  ██ ██ ▌
F2 TTS                   ▐█ ██ ▌
F3 Avatar                       ▐█ ██ ██ ▌
F4 Web                                   ▐█ ██ ██ ▌
F5 Experimento                                    ▐█ ██ ▌
F6 Despliegue                                           ▐█ ██ ▌
─────────────────────────────────────────────────────────────────────
Pista paralela:
  Diseño de la presentadora (VRoid) ██ ██ ██ ██ ██
  Resolver P1–P7 (lingüístico)      ██ ██ ██ ██ ██ ██ ██ ██ ██ ██
  Comité de ética (consentimiento)           ██ ██ ██ ██ ██ ██
```

**Diseño de la presentadora (pista paralela, semanas 1 a 5)**

1. Definir su identidad visual en equipo: rasgos, vestimenta (por ejemplo, la cushma) y fondo del estudio. Idealmente se valida con al menos una persona asháninka.
2. Modelarla en VRoid Studio y exportar a VRM 1.0.
3. Comprimir el modelo (texturas a 1K o menos, meshopt). **Meta:** ≤ 2 MB.
4. Adaptar al esqueleto VRM 3 o 4 animaciones de Mixamo.

El trámite ante el comité de ética conviene iniciarlo temprano porque suele demorar.

---

## 7. Recursos para desarrollo local y servidor

**Local (ya disponible)**
- Windows 11, Python 3.11 con `uv`, Node 20 o superior, eSpeak-NG (instalador de Windows), ffmpeg y Praat.
- Docker Desktop solo se necesita desde la Fase 6. Antes basta un entorno virtual, que es más rápido para iterar.
- No hace falta GPU.

**Servidor (estimación preliminar, a confirmar con la Fase 2)**
- MMS-VITS es un modelo pequeño (decenas de millones de parámetros) y corre en CPU.
- Punto de partida: **2–4 vCPU, 4–8 GB de RAM, 20 GB de disco**, sin GPU.
- El modo por lotes reduce mucho la carga: solo se sintetiza una vez por noticia.
- Esta estimación **se reemplaza** por el dimensionamiento medido en la tarea 2.9.

---

## 8. Riesgos actualizados

| ID | Riesgo | Probabilidad / impacto | Mitigación |
|---|---|---|---|
| R1 | Los recursos lingüísticos (P1, P2a–P2e, P5) no llegan a tiempo | Alta / Alto | Supuestos marcados en el código, pedir las fuentes a la compañera, cierre de la Fase 1 condicionado |
| R2 | **No hay hablantes revisores**: las noticias del experimento serían solo traducción automática | Alta / **Crítico** | Conseguir al menos 1 hablante para revisar 8 noticias (P4). Si no es posible, declarar la traducción automática como condición fija y limitación del estudio |
| R3 | Licencia no comercial de MMS | Segura / Medio | Advertencia en la interfaz y en los metadatos. eSpeak-NG como alternativa |
| R4 | `mms-tts-cni` fue entrenado con textos bíblicos: vocabulario distinto al de noticias y variante dialectal desconocida | Alta / Medio | Normalización robusta, MOS e inteligibilidad por variante, declarado en las limitaciones |
| R5 | La traducción automática de la compañera produce construcciones poco naturales que el TTS lee mal | Media / Medio | Registro de procedencia. Separar en el análisis los errores de traducción de los de síntesis |
| R6 | La alfabetización confunde la condición C1 | Alta / Alto | Cuestionario oral, covariable, interacción en el modelo de análisis |
| R7 | El avatar se degrada en C4 durante el campo | Baja con gama media / Alto | Registro del evento, exclusión o marcado en el análisis, preselección de los celulares |
| R8 | SyncNet no es válido para un avatar estilizado | Media / Medio | El desfase directo es el criterio principal. Declarado como limitación |
| R9 | Tamaño de muestra insuficiente para una revista Q1 | Media / Alto | Análisis de potencia en la Fase 5. El diseño intra-sujeto maximiza la potencia por participante |
| R10 | **Las fechas relativas caducan.** El audio se genera una vez y se sirve como archivo estático; "ayer" deja de ser verdad al día siguiente | Alta / Medio | Las fechas relativas solo se usan respecto a la **fecha de publicación**, que se muestra siempre y se lee al inicio de la noticia. Si una noticia se escucha mucho después, se puede regenerar el audio. Las noticias del experimento se escriben sin fechas relativas |
| R11 | **Nombres propios fuera del léxico:** cada noticia trae nombres nuevos (personas, distritos) | Segura / Medio | Para lo que no está en el léxico se aplican las reglas de P2d de forma automática. Se reporta la cobertura del léxico frente a las reglas. La validación auditiva (1.8) da la tasa de aceptación |
| R12 | La reescritura fonética **se aleja de la forma escrita**, por ejemplo una forma reescrita que no coincide visualmente con "Satipo" | Media / Bajo | El usuario ve el texto original y el mapa de alineación mantiene el resaltado correcto (§3.1). La reescritura solo existe internamente, en la entrada del TTS |
| R13 | **La ortografía de entrada no coincide con la del modelo de voz** (§3.2): el tokenizador elimina en silencio `k`, `b`, `ñ`, `z`…, y más de la mitad de las palabras se pronuncia incompleta | **Medida / Crítico** | Adaptador 2e elegido con el experimento 1.9. Validación 2f que **falla** (no avisa: falla) si queda un carácter fuera del vocabulario. Prueba de regresión que compara la entrada del tokenizador con su salida normalizada: deben ser idénticas |
| R14 | La correspondencia canónica→MMS no es 1 a 1 (por ejemplo, la /k/ se escribe "c" o "qu" según la vocal que sigue, y la "ñ" no tiene un equivalente evidente) | Alta / Alto | Reglas dependientes del contexto en el adaptador. Comparación de hipótesis con CER de ida y vuelta. Lo que no se resuelva se declara como limitación |
| R15 | El corpus mezcla ortografías y variantes: las reglas aprendidas de él pueden ser inconsistentes | Alta / Medio | Unificación ortográfica 2-0, estado `candidato-corpus` hasta validar, disciplina train/dev/test |

---

## 9. Reutilización y citas obligatorias

| Trabajo | Qué se reutiliza | Cómo se cita |
|---|---|---|
| Tesis "Avatar en asháninka para la enseñanza de la lengua" | Integración con MMS-TTS, lógica de WAV, patrón de gestos por eventos, experiencia con sincronía labial | Antecedentes + metodología (componentes adaptados). Pedir autorización escrita |
| Tesis de traducción español→asháninka (compañera) | Fuente de las noticias en asháninka | Antecedentes + arquitectura (componente externo). Acordar el contrato de datos |
| Meta MMS (Pratap et al., 2023) | `mms-tts-cni`, `mms-1b-all` (reconocimiento de voz para la prueba de ida y vuelta), alineador forzado de MMS. Todos con licencia CC-BY-NC 4.0 | Referencia bibliográfica + `LICENSES.md` |
| Corpus AmericasNLP 2021 asháninka–castellano | Evidencia ortográfica, candidatos léxicos, corpus de prueba (§3.2) | Ortega et al. (2020); Cushimariano Romano y Sebastián Q. (2008); Mihas (2011); Mager et al. (2021), tarea compartida AmericasNLP. Si se usa el monolingüe: Bustamante et al. (2020) |
| eSpeak-NG, three-vrm, VRoid, Mixamo | Línea base, avatar, animaciones | `LICENSES.md` + mención en la metodología |

---

## 10. Próximo paso

Al aprobar este plan se inicia la **Fase 1**. Para empezar necesito:

1. Las **noticias de prueba en asháninka**, en cualquier formato (las convierto al contrato del §2).
2. Lo que tengas o puedas pedirle a la compañera sobre **P1** (alfabeto), **P2a** (números nativos), **P2d** (adaptación de fonemas castellanos) y **P7** (con qué corpus entrenó su traductor y en qué ortografía escribe). El corpus AmericasNLP ya da candidatos para P1, P2a, P2b y P2c, pero no reemplaza la validación. Los glosarios P2b, P2c y P2e pueden empezar con los candidatos del corpus y de las noticias de prueba.
3. Confirmar dónde vivirá el proyecto. Propuesta: `C:\Users\Marco\Downloads\noticias-ashaninka\`, separado del proyecto Unity de la otra tesis, y con un repositorio git desde el inicio.
