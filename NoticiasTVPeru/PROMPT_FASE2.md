# PROMPT: Fase 2. PWA: controles en el tablón y aviso de la fuente

> Copia todo lo que está debajo de la línea en una sesión de Claude Code abierta en
> `C:\Users\Marco\Downloads\proyecto-ashaninka\proyecto-ashaninka`.
> Antes, lee `NoticiasTVPeru/PLAN_TVPERU.md`, `CLAUDE.md`, `NoticiasTVPeru/RESUMEN_FASE1.md` y `noticias-ashaninka/docs/pwa.md`.

---

# ROL

Actúa como ingeniero frontend senior (Preact, TypeScript, Vitest y Playwright). Vas a añadir al tablón los controles de actualización automática y la etiqueta de traducción automática con un enlace a la fuente.

# CONTEXTO

- API de la Fase 1: `GET /api/feed/status`, `PUT /api/feed/config` y `POST /api/feed/run`.
- `GET /api/catalog?orden=recientes` devuelve `fuente_url` y `traduccion_automatica`.
- `components/NewsList.tsx` carga el catálogo solo al montar; la primera tarjeta es la destacada.
- `cni.json` lleva `null` en toda clave nueva.

# TAREAS

1. `src/app/feed.ts`: cliente y funciones puras de formato.
2. `NewsList.tsx`:
   - orden reciente;
   - barra «Noticias de TV Perú» con el selector «Actualizar cada», el botón «Refrescar ahora» y el estado;
   - recarga al terminar un ciclo y cada 60 s.
3. Etiqueta «Traducción automática sin revisar» y «Fuente: TV Perú», en las tarjetas y en `Presentation.tsx`.
4. i18n y estilos (contraste AA en claro y en oscuro).

# PRUEBAS OBLIGATORIAS (criterio de cierre)

| # | Prueba | Resultado esperado |
|---|---|---|
| 1 | `npm test` (incluye `tests/feed.test.ts`) | Verde |
| 2 | `npm run typecheck` y `npm run build` (carga inicial < 3 MB) | Correcto |
| 3 | `npm run e2e` (nuevo `e2e/tvperu.spec.ts` con `page.route`; axe en claro y en oscuro) | Verde |

# RESTRICCIONES

- No se inventa texto en asháninka en la interfaz.
- three y three-vrm siguen cargándose con `import()` dinámico.
- Comentarios, documentos y commits en español.

# AL TERMINAR

Escribe `NoticiasTVPeru/RESUMEN_FASE2.md` con:

1. Qué se hizo.
2. Los archivos.
3. La salida real de las pruebas.
4. Desviaciones y pendientes.

Después marca la fase como **Culminada** en `PLAN_TVPERU.md` y haz un commit en español.
