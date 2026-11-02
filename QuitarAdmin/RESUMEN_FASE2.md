# Resumen de la Fase 2: PWA sin selector de rol

**Estado: Culminada (2026-11-02).**

## 1. Qué se hizo

- Se quitaron de la cabecera el selector «Ciudadano / Administrador», el formulario del token, el aviso de
  «Token verificado» y el botón «Salir de administración». La franja superior solo muestra «Acceso
  público al noticiero comunitario».
- El enlace **Sala de redacción** se ve siempre en la navegación (salvo durante una sesión experimental
  activa, cuando la cabecera solo muestra la marca, igual que antes). `#/redaccion` ya no redirige a la portada.
- La Redacción publica (`news → process → build → segments`), traduce con BiTAM y consulta el estado del traductor
  **sin cabecera de token**.
- Se borró `frontend/src/app/role.ts`; `role` y `token` salen del contexto de la app.
- i18n: se borraron `role.*` (11 claves), `masthead.access.admin`, `newsroom.guard` y
  `newsroom.error.forbidden` de `es.json` y `cni.json` (en `cni.json` eran `null`; no se inventó texto).
- CSS: se quitaron `.roles`, `.role*` y `.token-form`. `.token-msg` se queda porque la Redacción lo usa para los errores.

## 2. Archivos

| Archivo | Cambio |
|---|---|
| `src/app/role.ts` | **Borrado** |
| `src/app/App.tsx` | Sin estado de rol ni token; sin redirección de la Redacción |
| `src/app/ctx.ts` | Sin `role` ni `token` |
| `src/app/components/Masthead.tsx` | Sin selector ni formulario; enlace a la Redacción siempre visible |
| `src/app/newsroom.ts` | `publicar(d, f)`, `traducir(d, signal, f)` y `estadoTraductor(f)` sin token |
| `src/app/components/Newsroom.tsx` | Sin guardas `if (!token)` ni mensajes 403 |
| `src/app/router.ts`, `translator.ts` | Comentarios |
| `src/app/i18n/es.json`, `cni.json` | Claves borradas |
| `src/app/noticiero.css` | Estilos del rol borrados |
| `tests/newsroom.test.ts`, `tests/newsroom-translate.test.ts` | Sin token; comprueban que NO se envía `x-admin-token`; se quitó la prueba de `verificarToken` y `puedeVerRedaccion` |
| `e2e/noticiero.spec.ts` | Las pruebas «Ciudadano» y «Administrador» pasan a ser una sola: «Sin roles: cualquiera ve la sala de redacción» |
| `e2e/newsroom-translate.spec.ts` | Entra sin token; la petición de traducción no lleva token; se quitó el caso 403 |
| `e2e/helpers.ts` | Borrada la constante `ADMIN` |
| `e2e/experiment.spec.ts`, `offline-a11y.spec.ts`, `avatar-sin-webgl.spec.ts` | Sin cabeceras; la exportación sin token da **200** |
| `scripts/fase4_bench.mjs` | `/api/events/summary` sin cabecera |

## 3. Salida real de las pruebas

```
$ npm test
 Test Files  9 passed (9)
      Tests  102 passed (102)

$ npm run typecheck
> tsc --noEmit            (sin errores)

$ npm run build
dist/assets/index-BeW8-kWH.js              83.20 kB │ gzip:  25.53 kB
dist/assets/three.module-C8enonVg.js      736.44 kB │ gzip: 186.85 kB   (carga diferida con import())
✓ built in 747ms

$ npm run e2e        (dos ejecuciones completas seguidas)
  4 skipped
  39 passed (1.8m)

$ uv run pytest -q
1 failed, 337 passed, 9 skipped     (el mismo fallo previo de .dockerignore/VRM, ver RESUMEN_FASE1)
```

Las 4 pruebas E2E omitidas (`sin-webgl` y `software`) ya se omitían antes en esta máquina.

## 4. Desviaciones y pendientes

- **Intermitencia de accesibilidad que ya existía.** En las dos primeras ejecuciones completas falló de forma
  alternada `color-contrast: .primary` en el estudio C4 (una vez en `offline-a11y`, otra en `noticiero`).
  En aislado, las mismas pruebas pasaron 4 de 4. La causa es que `.btn` anima `opacity` durante
  0,2 s (`noticiero.css`) y axe medía el botón Reproducir a mitad del paso de deshabilitado a
  habilitado. El rol no tiene nada que ver. **Arreglo:** las dos pruebas axe emulan
  `prefers-reduced-motion: reduce` (`styles.css` anula todas las transiciones con esa preferencia).
  Después hubo dos ejecuciones completas seguidas en verde.
- La documentación todavía describe el token: se resuelve en la Fase 3.
