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
13. **Solo se probó H1 frente a H0, por decisión del tesista, y la `ñ` no quedó resuelta.** Con H1 (`ñ→ny`), la recuperación de la `ñ` fue **0 %**. El ASR transcribe sistemáticamente nuestro `ny` como `ne` + vocal (*nyaantsi* sale como *neantsi*, *oponya* como *oponea*). Es evidencia de que `ny` no es la escritura de la `ñ` en los datos de entrenamiento de MMS. Hay que probar otras hipótesis (por ejemplo, `ñ→y` o `ñ→n`) antes de la Fase 2.
14. **La recuperación por carácter es un proxy.** Se calcula por recuento, sin alineamiento carácter a carácter.

## Infraestructura

15. **El esquema de la base se aplica con `create_all`.** Las migraciones versionadas (Alembic) se incorporarán cuando el esquema se estabilice.
16. **`init.sh` solo se probó en Git Bash sobre Windows 11.** Las rutas para Linux, macOS y WSL existen en el código, pero no se ejecutaron en esta fase.
