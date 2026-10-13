# Diccionario de datos de la exportación del experimento (Fase 5)

> **Archivo generado** por `uv run python -m app.cli experiment dictionary` a partir de
> `backend/app/experiment/export.py` (`COLUMNAS`). No lo edite a mano.

Todas las tablas se exportan en CSV (UTF-8, separador coma, vacío = sin dato) y JSON, y en
Parquet si `pyarrow` está instalado. El único identificador es el **código anónimo** del
participante (`participante`); no se exportan nombres, documentos, teléfonos, geolocalización,
edad exacta ni el identificador del dispositivo.

## `sesiones.csv`: una fila por participante

| Variable | Tipo | Unidad | Valores | Descripción |
|---|---|---|---|---|
| `participante` | texto | — | p. ej. P007 | Código anónimo del participante (sin datos personales) |
| `indice` | entero | — | 0, 1, 2… | Índice del participante (código − 1): decide fila y rotación |
| `fila_williams` | entero | — | 0–3 | Fila del cuadrado de Williams 4×4 (índice mod 4) |
| `desplazamiento_noticias` | entero | — | 0–3 | Rotación de noticias ((índice // 4) mod 4) |
| `piloto` | booleano | 0/1 | 0, 1 | 1 = sesión de prueba con pseudo-noticias; no entra en el análisis confirmatorio |
| `estado` | texto | — | activa, completa, abandonada | Estado de la sesión |
| `consent_version` | texto | — | versión | Versión del consentimiento informado aceptado |
| `bloques_completados` | entero | bloques | 0–4 | Bloques completados (fin de la noticia y cuestionario enviado) |
| `variante` | texto | — | asháninka, ashéninka, alto_perene, otra, no_sabe | Variante que habla (autodeclarada) |
| `edad_rango` | texto | años | 18-29, 30-44, 45-59, 60+ | Rango de edad (nunca la edad exacta) |
| `alfabetizacion` | texto | — | no_lee, lee_con_dificultad, lee_bien | Lectura en asháninka (autodeclarada) |
| `familiaridad_tec` | texto | — | ninguna, poca, media, alta | Familiaridad con el celular y las apps |
| `rank_C1` | entero | puesto | 1–4 | Puesto de preferencia de C1 (1 = la que más prefirió) |
| `rank_C2` | entero | puesto | 1–4 | Puesto de preferencia de C2 |
| `rank_C3` | entero | puesto | 1–4 | Puesto de preferencia de C3 |
| `rank_C4` | entero | puesto | 1–4 | Puesto de preferencia de C4 |

## `bloques.csv`: una fila por participante × posición (tabla del análisis)

| Variable | Tipo | Unidad | Valores | Descripción |
|---|---|---|---|---|
| `participante` | texto | — | p. ej. P007 | Código anónimo del participante (sin datos personales) |
| `piloto` | booleano | 0/1 | 0, 1 | 1 = sesión de prueba (ver sesiones.piloto) |
| `posicion` | entero | — | 0–3 | Posición del bloque en la sesión (0 = primero) |
| `condicion` | texto | — | C1, C2, C3, C4 | Condición: C1 texto, C2 voz, C3 voz + texto, C4 voz + texto + avatar |
| `news_id` | entero | — | id de noticia | Noticia presentada en el bloque |
| `slot_noticia` | entero | — | 0–3 | Índice de la noticia dentro del conjunto fijo de 4 |
| `fila_williams` | entero | — | 0–3 | Fila del cuadrado de Williams del participante |
| `bloqueados_prop` | decimal | proporción | 0–1 | Covariable: segmentos bloqueados (sin P2d) / segmentos de la noticia |
| `t_pantalla_ms` | entero | ms | ≥ 0 | Tiempo en pantalla: de block-start a block-end (o al último evento si no hubo fin) |
| `t_escucha_ms` | entero | ms | ≥ 0 | Tiempo de audio en reproducción (sin pausas); 0 en C1 |
| `repeticiones` | entero | conteo | ≥ 0 | Eventos repeat-paragraph del bloque |
| `pausas` | entero | conteo | ≥ 0 | Eventos pause del bloque |
| `cambios_velocidad` | entero | conteo | ≥ 0 | Eventos rate del bloque |
| `degradacion_avatar` | booleano | 0/1 | 0, 1 | 1 = el avatar se degradó (imagen fija) en un bloque C4 |
| `completado` | booleano | 0/1 | 0, 1 | 1 = terminó la noticia (block-end «completo») y envió el cuestionario |
| `comprension` | decimal | proporción | 0–1 | Aciertos de los 4 ítems de comprensión / 4 |
| `esfuerzo` | entero | escala | 1–9 | Esfuerzo mental (Paas) |
| `aceptabilidad` | decimal | escala | 1–5 | Media de facilidad, agrado y confianza |
| `variante` | texto | — | ver sesiones | Covariable del cuestionario final |
| `edad_rango` | texto | años | ver sesiones | Covariable del cuestionario final |
| `alfabetizacion` | texto | — | ver sesiones | Covariable del cuestionario final |
| `familiaridad_tec` | texto | — | ver sesiones | Covariable del cuestionario final |

## `respuestas.csv`: una fila por ítem respondido (formato largo)

| Variable | Tipo | Unidad | Valores | Descripción |
|---|---|---|---|---|
| `participante` | texto | — | p. ej. P007 | Código anónimo del participante (sin datos personales) |
| `cuestionario` | texto | — | post_noticia, final | Cuestionario al que pertenece el ítem |
| `posicion` | entero | — | 0–3 o vacío | Posición del bloque (vacío en el cuestionario final) |
| `condicion` | texto | — | C1–C4 o vacío | Condición del bloque (vacío en el final) |
| `news_id` | entero | — | id o vacío | Noticia del bloque (vacío en el final) |
| `item` | texto | — | id del ítem | Identificador del ítem (ver questionnaire.yaml) |
| `valor` | texto | según ítem | — | Respuesta (número u opción; en el comentario, el texto libre) |

## `eventos.csv`: una fila por evento del cliente

| Variable | Tipo | Unidad | Valores | Descripción |
|---|---|---|---|---|
| `participante` | texto | — | p. ej. P007 | Código anónimo del participante (sin datos personales) |
| `posicion` | entero | — | 0–3 o vacío | Bloque al que pertenece el evento (por condición y noticia) |
| `condicion` | texto | — | C1–C4 o vacío | Condición activa cuando ocurrió el evento |
| `news_id` | entero | — | id o vacío | Noticia activa cuando ocurrió el evento |
| `tipo` | texto | — | tipos de /api/events | Tipo de evento |
| `t_client` | fecha-hora | ISO 8601 | UTC | Instante en el dispositivo |
| `t_rel_ms` | entero | ms | ≥ 0 | Milisegundos desde el primer evento del participante |
| `payload` | json | — | claves cerradas | Datos del evento (sin user_agent ni message) |

## Ítems de los cuestionarios (`respuestas.item`)

| Cuestionario | Ítem | Tipo | Rango u opciones | Estado |
|---|---|---|---|---|
| post_noticia | `comp_1` | binario | 0/1 | PENDIENTE-HABLANTE |
| post_noticia | `comp_2` | binario | 0/1 | PENDIENTE-HABLANTE |
| post_noticia | `comp_3` | binario | 0/1 | PENDIENTE-HABLANTE |
| post_noticia | `comp_4` | binario | 0/1 | PENDIENTE-HABLANTE |
| post_noticia | `esfuerzo` | entero | 1–9 | estandar-Paas |
| post_noticia | `acep_facilidad` | entero | 1–5 | SUPUESTO |
| post_noticia | `acep_agrado` | entero | 1–5 | SUPUESTO |
| post_noticia | `acep_confianza` | entero | 1–5 | SUPUESTO |
| final | `variante` | opcion | asháninka, ashéninka, alto_perene, otra, no_sabe | SUPUESTO-LING |
| final | `edad_rango` | opcion | 18-29, 30-44, 45-59, 60+ | SUPUESTO |
| final | `alfabetizacion` | opcion | no_lee, lee_con_dificultad, lee_bien | SUPUESTO |
| final | `familiaridad_tec` | opcion | ninguna, poca, media, alta | SUPUESTO |
| final | `rank_C1` | entero | 1–4 | SUPUESTO |
| final | `rank_C2` | entero | 1–4 | SUPUESTO |
| final | `rank_C3` | entero | 1–4 | SUPUESTO |
| final | `rank_C4` | entero | 1–4 | SUPUESTO |
| final | `comentario` | texto | texto ≤ 500 | SUPUESTO |
