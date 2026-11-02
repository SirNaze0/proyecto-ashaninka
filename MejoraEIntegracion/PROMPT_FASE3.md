# PROMPT: Fase 3 de la integración. Redacción en la PWA

> Copia todo lo que está debajo de la línea en una sesión de Claude Code abierta en
> `C:\Users\Marco\Downloads\proyecto-ashaninka\proyecto-ashaninka`.
> Documentos que hay que leer antes: `MejoraEIntegracion/PLAN_INTEGRACION.md`,
> `MejoraEIntegracion/RESUMEN_FASE2.md`, `CLAUDE.md`, `.claude/rules/frontend-pwa.md` y
> `noticias-ashaninka/docs/pwa.md`.

---

# ROL

Actúa como ingeniero frontend senior (Preact, TypeScript, accesibilidad y Playwright). Vas a añadir
a la **Sala de redacción** (solo administrador) la traducción automática castellano→asháninka con
BiTAM, usando `POST /api/news/translate` (Fase 2).

# CONTEXTO

- `frontend/src/app/components/Newsroom.tsx` ya tiene estos elementos:
  - los campos `titulo_es` y `cuerpo_es`, ocultos dentro de un `<details>`;
  - la procedencia (`tipo`, `sistema`, `version`, `revisado_por_hablante`);
  - la publicación real con `publicar()` de `newsroom.ts`;
  - el banner `newsroom.translatorPending`.
- El token de administración está en `useApp().token` y se envía como `x-admin-token`.
- La CSP permite `connect-src 'self'`, y la ruta es del mismo origen.
- `cni.json` está vacío **a propósito**: las claves nuevas solo van en `es.json`.
- La pantalla pública `TranslatePanel` y `TRADUCTOR_PENDIENTE` se quedan como están: el ciudadano
  solo consume noticias ya traducidas. Como mucho se ajusta su texto para decirlo.

# TAREAS

1. `newsroom.ts`:
   - `traducir(draft, token, signal)`: hace un POST a `/api/news/translate` y lanza `TranslateError`
     con el estado HTTP (403, 422 o 503).
   - `aplicarTraduccion(draft, respuesta)`, función **pura**: rellena `titulo_cni`, `paragraphs` y
     `procedencia` (`traduccion_automatica`, `sistema` y `version` de la respuesta,
     `revisado_por_hablante=false`) y conserva `titulo_es`, `cuerpo_es`, la fecha, la fuente y la variante.
2. `Newsroom.tsx`: nueva tarjeta **«Traducir desde castellano»** como primera opción:
   - Saca los campos `titulo_es` y `cuerpo_es` del `<details>` y los pone en esta tarjeta.
   - Botón «Traducir con BiTAM» (`data-testid="room-translate"`) con estado ocupado, barra de
     progreso accesible y cancelación con `AbortController`.
   - Cuando la traducción sale bien:
     - rellena el borrador (editable);
     - muestra una tabla plegable de pares oración es/cni para revisar;
     - muestra el aviso fijo de borrador automático (chrF++ ≈ 25, revisar con un hablante).
   - Mensajes según el error: 403 → `newsroom.error.forbidden`; 503 → «traductor no disponible»;
     422 → «texto demasiado largo».
   - El banner `translatorPending` se sustituye por el estado real.
   - Si se edita el castellano después de traducir, se avisa de que el borrador ya no le corresponde.
     No se borra nada sin preguntar.
3. `i18n/es.json`: claves nuevas `newsroom.translate.*`. No se toca `cni.json`.
4. Estilos en `noticiero.css`, con los tokens existentes, legibles en tema claro y oscuro.

# PRUEBAS OBLIGATORIAS (criterio de cierre)

| # | Prueba | Resultado esperado |
|---|---|---|
| 1 | Vitest `tests/newsroom-translate.test.ts`: `aplicarTraduccion` (campos, procedencia, conserva el castellano) y `traducir` (éxito, 403, 422, 503 y abort, con `fetch` simulado) | Verde |
| 2 | `npm test` (toda la suite) | Verde |
| 3 | `npm run typecheck` | Sin errores |
| 4 | `npm run build` y presupuesto inicial < 3 MB (`uv run python -m eval.fase4.run` o `eval/fase4/bundle.py`) | Se cumple, y three/VRM siguen con `import()` |
| 5 | E2E `e2e/newsroom-translate.spec.ts` con `page.route("**/api/news/translate")`: éxito → título y párrafos rellenados y procedencia `traduccion_automatica`; 503 → mensaje; 403 → mensaje | Verde en Chromium |
| 6 | axe en la Redacción con la tarjeta nueva | 0 violaciones |
| 7 | `npm run e2e` completo (incluye `csp.spec.ts`, `noticiero.spec.ts` y `translate.spec.ts`) | Verde |
| 8 | Prueba manual con el servicio de la Fase 1 y el backend: traducir → revisar → Publicar → abrir en C4 | La noticia se reproduce con voz y avatar. Captura o descripción en el resumen |

# RESTRICCIONES

- Ningún texto asháninka inventado en la interfaz.
- Siempre visible el aviso de voz sintética CC-BY-NC 4.0 en C2–C4 (ya existe, no debe romperse).
- Los segmentos bloqueados siguen mostrándose solo como texto, con su aviso.
- Comentarios en español.

# AL TERMINAR

Escribe `MejoraEIntegracion/RESUMEN_FASE3.md` con:

1. Qué se hizo.
2. Archivos.
3. La salida real de las pruebas.
4. El tamaño del paquete inicial.
5. El resultado de la prueba manual.
6. Desviaciones y pendientes.

Después marca la Fase 3 como **Culminada** en el `README.md` de la carpeta.
