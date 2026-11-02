# PROMPT: Fase 4. Verificación integral y README

> Copia todo lo que está debajo de la línea en una sesión de Claude Code abierta en
> `C:\Users\Marco\Downloads\proyecto-ashaninka\proyecto-ashaninka`.
> Antes, lee `NoticiasTVPeru/PLAN_TVPERU.md`, `CLAUDE.md` y todo `NoticiasTVPeru/`.

---

# ROL

Actúa como responsable de QA. Debes comprobar la función de punta a punta y dejar el README.

# CONTEXTO

- `scripts/verify.sh` se detiene en pytest si falta el VRM provisional (fallo previo conocido).

# TAREAS

1. Ejecutar `scripts/verify.sh` (o sus pasos a mano).
2. Prueba manual:
   - traductor encendido y `NA_FEED_ENABLED=true`;
   - «Refrescar ahora» en el tablón;
   - intervalo de 15 min;
   - un segundo ciclo no duplica noticias.
3. Escribir `NoticiasTVPeru/README.md`.

# PRUEBAS OBLIGATORIAS (criterio de cierre)

| # | Prueba | Resultado esperado |
|---|---|---|
| 1 | Verificación completa | Verde, salvo el fallo previo del VRM |
| 2 | Prueba manual | Noticias publicadas con voz, etiqueta y fuente |

# RESTRICCIONES

- Declarar lo que no se pudo comprobar.
- Comentarios, documentos y commits en español.

# AL TERMINAR

Escribe `NoticiasTVPeru/RESUMEN_FASE4.md` con:

1. Qué se hizo.
2. Los archivos.
3. La salida real de las pruebas.
4. Desviaciones y pendientes.

Después marca la fase como **Culminada** en `PLAN_TVPERU.md` y haz un commit en español.
