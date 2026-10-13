# Limitaciones y supuestos (Fase 1)

Las limitaciones valen tanto como los logros. Este archivo se actualiza a medida que aparecen.

## Datos y lingüística

1. **No hay datos lingüísticos validados todavía.** P1 (alfabeto e inventario), P2a (numerales), P2d (adaptación fonológica castellano→asháninka) y P5 (conjunto de referencia) siguen pendientes. Todo lo que depende de ellos está marcado como `SUPUESTO-LING` o `candidato-corpus`.
2. **El corpus mezcla ortografías y variantes.** AmericasNLP 2021 combina `b`/`v`, `ts`/`tz` y `k`/`c`/`qu`, además de variantes dialectales (asháninka, ashéninka, alto Perené). Las reglas derivadas de él pueden ser inconsistentes (R15).
3. **La ortografía canónica es una decisión provisional.** Se eligió la mayoritaria del corpus (`k`, `b`, `ts`, `ñ`), según la decisión del tesista del 2026-10-05. A nivel de palabra no siempre coincide: por ejemplo, *ikantzi* (98) aparece más que *ikantsi* (30), aunque en el corpus completo `ts` (5339) supera a `tz` (1773). Debe validarse con P1 y P7.
4. **El corpus no es de noticias.** Contiene textos legales, cartas y oraciones traducidas. No sirve como noticias del experimento ni como muestra representativa del vocabulario periodístico.
5. **Los candidatos extraídos tienen ruido.** Por ejemplo, *apapakoroni* (0,5), o "préstamos" que en realidad son palabras asháninka sin traducir en la línea castellana (*nija*). Por eso todo sale como `candidato-corpus`.

## Heurísticas del normalizador (SUPUESTO-LING)

6. **Detección de castellano.** Una palabra se considera castellana si tiene una letra fuera del inventario candidato o una vocal con tilde. Así quedan falsos negativos: palabras castellanas escritas solo con letras "nativas" y sin tilde (*como*, *pero*, *octavo*) se tratan como asháninka.
7. **Nombre propio.** Se considera nombre propio toda palabra con mayúscula inicial fuera del inicio de oración. Esto falla en títulos y en palabras capitalizadas por estilo (*Ñaantsi* en textos legales).
8. **Siglas.** Una secuencia en mayúsculas de 6 caracteres o menos se trata como sigla si no está en un título. Las palabras en mayúsculas dentro de una oración pueden confundirse con siglas.
9. **Números.** Los separadores ambiguos (`10,000`, `2.500`) no se interpretan: quedan en `unresolved`. Las fechas `dd/mm/aaaa` siguen la convención peruana, y los años de 2 dígitos se consideran ambiguos.
10. **Sin P2d no se puede reescribir el castellano.** Mientras P2d esté vacía, ningún fragmento castellano se reescribe como lo diría un hablante bilingüe. Los que contienen `d`, `l`, `g`, `f`, `x` o `w` (letras ausentes del vocabulario de MMS) dejan el segmento **bloqueado para el TTS**. Los demás se marcan como "no normalizado según la política". El porcentaje de segmentos bloqueados se reporta en `fase_1.json`.

## Adaptador ortográfico y experimento 1.9

11. **El TTS y el ASR de MMS comparten datos de entrenamiento.** La prueba de ida y vuelta mide la consistencia del par de modelos, no la inteligibilidad humana. La escucha A/B con un hablante sigue pendiente.
12. **La inversa del adaptador no es exacta.** `tz→ts` y `z→s` no se pueden revertir. Para H0, el CER canónico usa la inversa de la hipótesis activa (H1), porque la transcripción siempre sale en la ortografía de MMS.
13. **La escritura de la `ñ` para MMS sigue sin resolverse.** Con H1 (`ñ→ny`), el ASR transcribe nuestro `ny` como `ne` + vocal (*nyaantsi* sale como *neantsi*). La consistencia en palabras con `ñ` fue 0 %. Se probaron además H2 (`ñ→y`) y H3 (`ñ→n`) con una regla de decisión fijada antes de ejecutar:
    - Ninguna mejora el CER global frente a H1 de forma significativa: H2 −0,0008 (IC 95 % [−0,0034; 0,0025]); H3 −0,0016 (IC 95 % [−0,0046; 0,0013]). Por eso **se mantiene H1**.
    - La consistencia en palabras con `ñ` sube con H3 (46 %) y con H2 (19 %), pero eso **no prueba** que suenen como /ɲ/: la `n` y la `y` son sonidos frecuentes que los modelos reproducen bien con cualquier escritura.
    - La muestra tiene solo 26 palabras con `ñ`, demasiado pocas para que la `ñ` mueva el CER de oraciones completas.
    - Siguiente paso: la escucha A/B dirigida ya está preparada (`eval/listening/enye_ab/`). Son 20 palabras (10 con `ñ` inicial y 10 con `ñ` interna) sintetizadas con la misma semilla en H1, H2 y H3, comparadas a ciegas en 60 pares, más 4 controles con audios idénticos. Falta aplicarla a un hablante.
14. **La recuperación por carácter es un proxy.** Se calcula por recuento, sin alineamiento carácter a carácter.

## Infraestructura

15. **El esquema de la base se aplica con `create_all`.** Las migraciones versionadas (Alembic) se incorporarán cuando el esquema se estabilice.
16. **`init.sh` solo se probó en Git Bash sobre Windows 11.** Las rutas para Linux, macOS y WSL existen en el código, pero no se ejecutaron en esta fase.

## Síntesis de voz (Fase 2)

17. **El tokenizador de Hugging Face no intercala bien los blancos.** En MMS, el token de relleno y blanco es la letra `a` (id 0). `VitsTokenizer` (transformers 4.46 y 5.18) la trata como token especial y rompe el intercalado cuando hay `aa` o una `a` al inicio o al final; esto afectó a 48 de las 100 oraciones de la muestra. Se adoptó el intercalado manual de VITS (T2) por una mejora pequeña y apenas significativa en el CER (−0,0034, IC 95 % [−0,0065; −0,0001], p = 0,046). Las cifras de la Fase 1 se midieron con el tokenizador de Hugging Face (T1) y siguen siendo válidas para esa condición: T1 reproduce exactamente el CER de H1 (0,0586). No sabemos cómo se preprocesó el texto al entrenar MMS. Ver `docs/tokenization.md`.
18. **La variante dialectal de la voz no está documentada.** Es la de los datos de entrenamiento de MMS. Se declara en los metadatos de cada audio y en el manifiesto.
19. **La línea base eSpeak-NG es ingenua.** Lee la ortografía asháninka con la voz castellana. No es un TTS asháninka; sirve como referencia sin restricción comercial. El modo por fonemas queda deshabilitado hasta validar P1.
20. **El CER de ida y vuelta favorece a MMS.** El ASR (`mms-1b-all`) y el TTS de MMS comparten datos de entrenamiento, así que la comparación entre motores está sesgada a favor de `mms_vits`. Para eSpeak, además, el audio se remuestrea de 22 050 a 16 000 Hz por interpolación lineal.
21. **Las duraciones de VITS están verificadas, pero su exactitud fonética no.** La suma de frames reproduce exactamente la longitud del audio. Los tiempos por carácter, en cambio, reparten los blancos mitad y mitad, que es una regla convencional. Si esos tiempos coinciden con los sonidos reales se valida en la Fase 3 (tarea 3.2).
22. **Los segmentos sin P2d no tienen audio.** Mientras P2d no exista, los segmentos con letras castellanas fuera del vocabulario de MMS se entregan solo como texto (modo degradado).
23. **El rendimiento se midió con pseudo-noticias**, es decir, oraciones de dev concatenadas, no con noticias reales. El dimensionamiento asume que la capacidad bajo demanda escala linealmente con los núcleos.
24. **La tasa de Opus no se fija directamente.** libsndfile solo permite un nivel de compresión; la tasa real de cada archivo se mide y se reporta.
25. **`init.sh` sin opciones desinstala el grupo `eval`** (jiwer, matplotlib), porque `uv sync` deja el entorno igual al lockfile. Para las evaluaciones hay que usar `./init.sh --with-tts` o `--with-asr-eval`.

## Alineación, visemas y avatar (Fase 3)

26. **El mapa grafema → visema es una hipótesis, no un dato lingüístico.** Todo `map.yaml` es `SUPUESTO-LING` (P1 abierto): los pesos son una articulación genérica (vocales abiertas/cerradas/redondeadas, cierre labial de `p m b`, coarticulación de las demás consonantes). El "fonema" que usa la alineación es el grafema segmentado por el G2P. Mientras no se valide P1, que la boca coincida con el audio no prueba que los visemas sean los del asháninka.
27. **La alineación de VITS se validó contra otro modelo, no contra una persona.** El error del centro de palabra frente al alineador CTC es de 63,9 ms de media (34 ms de mediana); 11 de 40 oraciones superan los 80 ms. CTC emite picos de ~20 ms, por lo que sesga inicio y fin (+109 ms y −93 ms) y solo el centro es fiable. **Las 20 oraciones anotadas a mano en Praat no se hicieron**: requieren a una persona (kit en `eval/fase3/praat/`).
28. **El desfase por clip no se puede medir con este método.** La correlación entre la envolvente del audio y la boca es baja (r ≈ 0,3) y ambigua por el periodo silábico: con desplazamientos conocidos el estimador por clip se equivoca 30–60 ms de media y hasta 680 ms. Solo el desfase **sistemático** (curvas promediadas de 40 clips: −10,8 ms, IC 95 % −18,5 a −2,1) es fiable. El método se revisó **después** de la primera medición y así queda declarado en `docs/metrics.md`. Una verificación clip a clip necesita anotación manual o captura de pantalla con audio real.
29. **SyncNet no discrimina con este avatar.** LSE-D y LSE-C con el audio correcto (11,78 y 0,76) son iguales a los del control negativo con audio de otro clip (11,77 y 0,76). Los valores de un vídeo real rondan 7 de LSE-C; aquí no son evidencia de sincronía (riesgo R8, confirmado). No se usó detector de caras: el recorte de 224×224 es la cámara fija del avatar.
30. **El desfase medido no incluye la latencia de salida de audio del dispositivo.** El navegador no la expone para un `<audio>` y no se midió con hardware (micrófono o fotodiodo). Se incluye un parámetro de compensación (`latencyMs` de `AudioClock`) para cuando se mida en un dispositivo.
31. **Los FPS son del equipo de desarrollo, no de un Android de gama media.** Con GPU (RTX 3060 Ti) y con la CPU 4× más lenta: 60 FPS. Sin aceleración gráfica (SwiftShader): 17–18 FPS, por debajo del umbral de 20, de modo que el avatar se degrada a imagen fija. La verificación en un dispositivo real queda para la Fase 4.
32. **El modelo VRM es provisional y pesa más que la meta.** `VRM1_Constraint_Twist_Sample` de pixiv (VRM 1.0, redistribución permitida), reducido de 10,8 a 2,41 MB con `scripts/optimize_vrm.py` (texturas a 1024 px y solo las 6 expresiones que usa el visor). La meta del modelo final es ≤ 2 MB. No se versiona (`frontend/public/models/*.vrm`).
33. **Los gestos son procedurales, no de Mixamo.** Mixamo exige cuenta de Adobe y términos por descarga: no se puede automatizar ni versionar. Hay 4 gestos (reposo hablando, saludo, asentir, despedida) como rotaciones de huesos normalizados; `Gestures.register()` admite clips retargeteados.
34. **TalkingHead se descartó sin medir su FPS ni su desfase.** No carga el VRM de VRoid sin convertirlo (ver `docs/avatar_decision.md`). La decisión se apoya en compatibilidad, control del reloj y peso del bundle.
35. **Las clips y mediciones usan renderizado fotograma a fotograma, no grabación en tiempo real.** Los 40 MP4 salen de `renderAt(t)` (determinista); el reloj en tiempo real se mide aparte con 8 oraciones por configuración. Las capturas del plan («Playwright graba el canvas») se adaptaron así porque la grabación en tiempo real depende de la velocidad del equipo.
