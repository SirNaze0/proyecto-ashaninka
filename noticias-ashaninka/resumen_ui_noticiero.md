# Resumen de la integración UI/UX: diseño de noticiero, roles y Sala de Redacción

> **Proyecto:** Servicio web de noticias en lengua asháninka con síntesis de voz, texto y avatar
> **Fecha:** 2026-10-20 · **Rama:** `style/super-ui-noticiero` · **Base:** Fase 6 (aprobada el 2026-10-13) y diseño de noticiero v0 (`b8953`)
> **Estado:** implementada y verificada con las pruebas automáticas de la máquina de desarrollo. Una prueba E2E (`avatar.spec.ts`, proyecto `gpu`) **falla también sin estos cambios** (ver sección 4).

Las cifras vienen de ejecuciones reales (`npm test`, `npm run e2e`, `eval.fase4.bundle`). El texto de la interfaz en asháninka sigue **pendiente de un hablante** (`cni.json` vacío a propósito): no se inventó ninguna cadena.

## 1. Propósito de la integración UI/UX

- **Ciudadano:** portada con noticia destacada y tarjetas, estudio de TV con la presentadora al centro y lectura paralela alternativa, sin pasos de configuración.
- **Administrador:** acceso a la Sala de Redacción para cargar noticias por archivo o texto y publicarlas con audio por lotes.
- **Ligereza:** todo es CSS y Preact sin librerías nuevas. La carga inicial es de **37 120 bytes gzip (0,035 MB)** frente al presupuesto de 3 MB; three/three-vrm y el VRM siguen tras `import()`.
- **Pulido (esta rama):** micro-interacciones (elevación de tarjetas, subrayado animado en la navegación, botones), marco de monitor y rótulo «EN AIRE» en C4, teleprompter con iluminación sobre la palabra activa y zona de arrastre con estados claros.

## 2. Arquitectura de vistas y roles

| Vista | Acceso | Contenido |
| --- | --- | --- |
| Ciudadano | público | traducción (entrada), portada, noticia en C1–C4, ajustes |
| Administrador | `x-admin-token` verificado | todo lo anterior + Sala de Redacción |

- `role.ts`: el rol «Administrador» **no protege nada por sí mismo**. Pide el token, lo comprueba con `GET /api/news` y lo guarda **solo en memoria** (nunca en `localStorage` ni IndexedDB); al cerrar la pestaña se pierde.
- La protección real es `require_admin` en el backend (cerrado por defecto, 403 sin token válido). La redacción solo aparece con `role === "admin"` y token verificado (`puedeVerRedaccion`).
- La publicación usa `/api/news` → process → build, todos protegidos.

## 3. Estudio TV centrado (C4) y Sala de Redacción

**Estudio C4** (`Presentation.tsx`, `noticiero.css`)
- Presentadora (avatar) al centro, con *lower-third* (etiqueta + variante dialectal) y ondas de voz.
- Marco de monitor con borde degradado **estático** y rótulo «EN AIRE»: el punto rojo parpadea solo mientras se reproduce (animación de opacidad, sin coste de composición).
- Teleprompter: el propio texto resaltado (`highlight.ts`, sincronizado con el audio) como barra oscura flotante; la palabra activa lleva un halo suave.
- El fondo del escenario sigue **sólido y sin sombras exteriores sobre el canvas**: un degradado con sombra grande bajaba el WebGL a < 10 FPS (nota en el CSS). Por eso el efecto cinematográfico se logró con borde, línea de luz y sombra del teleprompter.

**Sala de Redacción** (`Newsroom.tsx`)
- Ingesta por archivo `.txt`, `.csv` o `.json` (arrastrar o elegir), por texto pegado o con plantilla CSV; los lotes se revisan noticia por noticia.
- La zona de arrastre tiene borde punteado, icono y un estado «Suelta el archivo» al arrastrar.
- Durante la publicación se muestra una barra **indeterminada** (`role="progressbar"` sin valor). No se inventó un porcentaje: el servidor no informa progreso, así que no se simula uno falso.
- La procedencia sigue siendo obligatoria; el texto debe venir ya en asháninka (la traducción es→cni sigue pendiente de integración).

**Decisión sobre el cambio de tema.** No se aplicaron transiciones de color/fondo al alternar claro/oscuro: dejaban colores intermedios que `axe-core` medía a mitad de camino y reportaba como fallo de contraste. Las transiciones de 0,2 s se limitaron a transformación, sombra y borde. Todo se desactiva con `prefers-reduced-motion`.

## 4. Resultados de calidad y pruebas

| Comprobación | Resultado |
| --- | --- |
| `npm test` (vitest) | **90 de 90** |
| `npm run typecheck` / `npm run build` | **0 errores** |
| `npm run e2e` (Chromium real) | **35 de 36** |
| `axe-core` (portada, estudio y redacción, claro y oscuro) | **0 violaciones serias** (prueba `noticiero`, pasa) |
| Carga inicial (`eval.fase4.bundle`) | **37 120 B gzip (0,035 MB)** < 3 MB |

**Prueba que falla:** `avatar.spec.ts` (proyecto `gpu`, «C4: el avatar se carga de forma diferida…») queda en modo `fijo` en lugar de `avatar`. Se reprodujo **igual con los cambios guardados en el stash** (código previo), así que no la causan estos cambios; apunta a que Chromium de esta máquina no inicia WebGL. No se ejecutó la medición de 60 FPS ni de desfase tras el pulido: **queda pendiente repetirla en una máquina con GPU** (`eval.fase4.run`) para confirmar que el marco y el halo no cuestan FPS.
