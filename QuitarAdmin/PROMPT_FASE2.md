# PROMPT: Fase 2. PWA sin selector de rol

> Copia todo lo que está debajo de la línea en una sesión de Claude Code abierta en
> `C:\Users\Marco\Downloads\proyecto-ashaninka\proyecto-ashaninka`.
> Antes, lee `QuitarAdmin/PLAN_QUITAR_ADMIN.md`, `QuitarAdmin/RESUMEN_FASE1.md` y
> `noticias-ashaninka/docs/pwa.md`.

---

# ROL

Actúa como ingeniero frontend senior (Preact, TypeScript, Vitest y Playwright). Vas a quitar de la
PWA el selector «Ciudadano / Administrador» y el token, para que la Sala de redacción quede abierta.

# CONTEXTO

- `frontend/src/app/role.ts`: `Role`, `adminHeaders`, `verificarToken` y `puedeVerRedaccion`.
- `App.tsx:47-49,101-105,113-143`: estado `role`/`token`, redirección de `#/redaccion` y propiedades del `Masthead`.
- `ctx.ts:7,18-20`: `role` y `token` en el contexto.
- `components/Masthead.tsx`: radiogroup de roles (líneas 66-91), formulario del token (94-117) y enlace a la
  Redacción condicionado (160).
- `newsroom.ts:240-362`: `call`, `publicar`, `traducir` y `estadoTraductor` reciben `token`.
- `components/Newsroom.tsx:36-152`: `useApp().token` y las guardas `if (!token) return`.
- Pruebas: `tests/newsroom.test.ts`, `tests/newsroom-translate.test.ts`, `e2e/noticiero.spec.ts`,
  `e2e/newsroom-translate.spec.ts`, `e2e/helpers.ts`, `scripts/e2e_server.py` y `frontend/scripts/fase4_bench.mjs`.

# TAREAS

1. Borrar `role.ts` y todo uso de `role`/`token`.
2. La Redacción se ve siempre (el enlace se oculta durante una sesión experimental activa, como el resto).
3. Borrar las claves i18n y las reglas CSS que queden sin uso (`cni.json` sigue con `null`; no inventar texto).
4. Adaptar las pruebas unitarias y E2E.

# PRUEBAS OBLIGATORIAS (criterio de cierre)

| # | Prueba | Resultado esperado |
|---|---|---|
| 1 | `npm test` | Verde |
| 2 | `npm run typecheck` | Sin errores |
| 3 | `npm run build` | Correcto; presupuesto inicial < 3 MB |
| 4 | `npm run e2e` | Verde |
| 5 | `uv run pytest` (prueba de i18n y del servidor E2E) | Verde |

# RESTRICCIONES

- three y three-vrm se siguen cargando con `import()` dinámico.
- Se mantiene el aviso de voz sintética CC-BY-NC 4.0.

# AL TERMINAR

Escribe `QuitarAdmin/RESUMEN_FASE2.md` y haz un commit en español.
