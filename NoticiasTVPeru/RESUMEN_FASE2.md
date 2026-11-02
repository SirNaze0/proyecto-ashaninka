# Resumen de la Fase 2: PWA (controles en el tablón y aviso de la fuente)

**Estado: Culminada (2026-11-02).**

## 1. Qué se hizo

- **Barra «Noticias de TV Perú»** (`components/FeedBar.tsx`), arriba del tablón:
  - selector **«Actualizar cada»**: apagado, 15 min, 30 min, 1 h, 3 h o 6 h (`PUT /api/feed/config`);
  - botón **«Refrescar ahora»** (`POST /api/feed/run`), que se desactiva mientras corre un ciclo;
  - estado: «Última actualización hace 5 min · 3 publicadas, 12 en cola · próxima en 25 min», o el motivo del
    fallo, por ejemplo «sin publicar: traductor no disponible»;
  - si el servidor tiene la función apagada, lo dice y desactiva los controles.
  - Consulta el estado cada 60 s, o cada 5 s mientras hay un ciclo en marcha. **Al terminar un ciclo
    recarga el tablón.**
- **Tablón** (`NewsList.tsx`): pide `/api/catalog?orden=recientes`, así que la «Destacada» es la noticia más
  reciente, y se recarga cada 60 s con la pestaña visible.
- **Aviso en cada noticia automática:**
  - en la tarjeta, las etiquetas «Traducción automática sin revisar» y «Fuente: TV Perú»;
  - al abrirla (`Presentation.tsx`, fuera del experimento), «Traducción automática de una noticia de TV Perú,
    sin revisar por un hablante» con el enlace «Ver la noticia original en TV Perú» (`target=_blank`,
    `rel=noopener noreferrer`).
- Cliente puro `src/app/feed.ts`, con funciones de formato que se pueden probar.
- i18n: 29 claves nuevas en `es.json` y las mismas con `null` en `cni.json` (no se inventó texto).
- **Corrección del modo sin conexión** (regresión que encontró la E2E):
  - «Guardar para uso sin conexión» guarda también `/api/catalog?orden=recientes`;
  - si no la encuentra, el Service Worker recurre a la misma ruta sin parámetros (`ignoreSearch`).

## 2. Archivos

| Archivo | Cambio |
|---|---|
| `src/app/feed.ts`, `src/app/components/FeedBar.tsx` | **Nuevos** |
| `src/app/components/NewsList.tsx` | Orden reciente, barra, recarga y etiquetas |
| `src/app/components/Presentation.tsx` | Aviso y enlace a la fuente |
| `src/app/data.ts`, `src/app/types.ts` | `fetchCatalog(orden)` y campos de fuente |
| `src/app/offline.ts`, `src/sw.ts` | Catálogo «recientes» disponible sin conexión |
| `src/app/i18n/es.json`, `cni.json` | Claves `feed.*`, `list.autoTranslation`, `list.source` y `news.auto*` |
| `src/app/noticiero.css` | Estilos de la barra |
| `tests/feed.test.ts` | **Nuevo**: 15 pruebas |
| `e2e/tvperu.spec.ts` | **Nuevo**: 5 pruebas |
| `e2e/conditions.spec.ts`, `e2e/offline-a11y.spec.ts` | Ya no suponen que la noticia 1 va primera |

## 3. Salida real de las pruebas

```
$ npm test
      Tests  117 passed (117)          (antes 102; +15 de feed.test.ts)
$ npm run typecheck                    (sin errores)
$ npm run build
dist/assets/index-CoCRMYOc.js   89.06 kB │ gzip: 27.38 kB   (antes 83,20 kB; three sigue diferido)
$ npm run e2e
  4 skipped
  44 passed (1.9m)                     (antes 39; +5 de tvperu.spec.ts)
$ uv run pytest -q
1 failed, 360 passed, 9 skipped        (el fallo previo del VRM)
```

La E2E de TV Perú simula `/api/feed/*` con `page.route`, porque el servidor E2E tiene la función apagada y no
contacta a TV Perú. Comprueba:

- la barra apagada, con el servidor real;
- el cambio de intervalo (`PUT {intervalo_min: 15}`);
- «Refrescar ahora», el paso a «Actualizando» y la recarga del tablón al terminar;
- el motivo «traductor no disponible»;
- la etiqueta y el enlace a la fuente;
- axe en claro y en oscuro, sin violaciones graves.

## 4. Desviaciones y pendientes

- **Una ejecución de la E2E tardó 1,6 h** y falló `csp.spec.ts › C2` porque el audio se quedó en «Oración 1 de 3».
  Esa prueba no toca nada de esta fase. Repetida sola, pasó 6 de 6, y la suite completa repetida pasó 44 de 44 en
  1,9 min. Lo más probable es que el equipo estuviera suspendido o con mucha carga durante esa ejecución.
- El enlace a la fuente se muestra en la vista de la noticia y no en la tarjeta, porque la tarjeta entera ya es un
  enlace y HTML no admite enlaces anidados. En la tarjeta solo se ve el texto «Fuente: TV Perú».
- El aviso no se muestra dentro del experimento. Las noticias automáticas no son aptas para el experimento real,
  y en el piloto no se ofrece un enlace externo que saque al participante del flujo.
