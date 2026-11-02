# Resumen de la Fase 4: verificación integral y README

**Estado: Culminada (2026-11-02).**

## 1. Qué se hizo

- Se ejecutaron todos los pasos de `scripts/verify.sh`: ruff, pytest, el traductor con motor falso, vitest, tipos,
  build, E2E en Chromium real y la consolidación de `eval/results/fase_6.json`. BiTAM estuvo encendido todo el
  tiempo.
- **Prueba manual de punta a punta con BiTAM real**, en Chromium (Playwright con un script temporal, ya
  borrado). Uvicorn corría con `NA_FEED_ENABLED=true`, la voz `mms_vits` y una base temporal, con 1 noticia por
  ciclo para acortar la prueba.
- Comprobación de un segundo ciclo (sin duplicados) y de dos «Refrescar» seguidos (409).
- Se escribió `NoticiasTVPeru/README.md`.
- **Arreglo encontrado al verificar:** `scripts/e2e_server.py` fija ahora `NA_TRANSLATOR_URL=""` y
  `NA_FEED_ENABLED=false`. Con BiTAM encendido y el `.env` local apuntando a `:8100`, el servidor E2E veía el
  traductor disponible, y la prueba axe del noticiero (que espera el aviso «pendiente» en la Redacción) fallaba.
  Las E2E ya no dependen del `.env` de cada máquina.

## 2. Salida real

```
== ruff                       All checks passed! · 173 files already formatted
== pytest                     1 failed, 362 passed, 8 skipped   (fallo previo del VRM)
== traductor (fake)           15 passed
== PWA                        Tests 117 passed (117) · typecheck ok · index 89,06 kB (gzip 27,38 kB)
== E2E (tras el arreglo)      4 skipped · 44 passed (1.9m)
== fase_6.json
OK pruebas_seguridad: 36/36
NO pruebas_despliegue: 29/31          (fallo previo del VRM + 1 omitida: no hay Caddy)
OK pruebas_escucha: 22/22
OK pruebas_documentacion: 13/13
-- docker_build_y_arranque: pendiente
OK carga_inicial: 0.0381
OK regresion_fase5: {'cumplidos': 13, 'en_fallo': {}}
NO pruebas_pytest: 362/371            (el mismo fallo previo; el resto son omitidas)
OK pruebas_vitest: 117/117
OK pruebas_e2e: 44/48                 (4 omitidas, las de siempre)
```

**Prueba manual** (BiTAM real en la GTX 1060, Chromium):

```
21:30:53 barra: Aún no se ha actualizado
21:31:08 tras elegir 30 min: … · próxima ahora mismo
21:31:08 refrescar ahora: en curso
21:36:33 terminado: Última actualización ahora mismo · 1 publicadas, 14 en cola · próxima en 30 min
21:36:35 tarjetas con etiqueta: 1 | tarjetas: 1
21:36:35 aviso: Traducción automática de una noticia de TV Perú, sin revisar por un hablante. Ver la noticia original en TV Perú
21:36:35 enlace: https://www.tvperu.gob.pe/noticias/nacionales/ucayali-despliegan-maquinaria-para-restablecer-el-transito-en-carretera-federico-basadre-tras-huaico
21:36:35 botón de reproducción: habilitado
estado: ciclo 318,8 s · 15 nuevas · 1 publicada · audio 4 segmentos con voz y 5 bloqueados · intervalo 30 · próxima 22:06 UTC
```

**Segundo ciclo** (por la API):

```
POST run -> 202
POST run otra vez -> 409
nuevas 0 · publicadas [2] · items {pendiente: 13, publicada: 2} · 515,9 s
catálogo «recientes»: [(2, …huanuco-y-ucayali-tras-deslizamiento), (1, …federico-basadre-tras-huaico)] · URL distintas: True
```

## 3. Desviaciones y pendientes

- **Dependencia circular entre `fase_6.json` y `test_docs_fase6.py`:** la prueba exige que el resumen de la Fase 6
  nombre cada criterio incumplido de `fase_6.json`. Un `fase_6.json` intermedio, con el E2E en «NO» por el
  problema del `.env`, hizo fallar esa prueba, y ese fallo volvió a quedar como «NO» al consolidar. Para salir del
  ciclo se restauró el `fase_6.json` del commit, se repitió pytest y se consolidó de nuevo. Al final la
  documentación queda en 13/13.
- La prueba manual usó 1 noticia por ciclo, para no tardar 15 min por ciclo. Con 3 por ciclo, la medición de la
  Fase 3 dio 933 s.
- **No se comprobó:** que el **planificador** dispare solo al vencer el intervalo de 30 min con el servidor real
  (habría que esperar media hora; sí lo cubren las pruebas de `toca_ejecutar`), ni la voz al reproducirse de
  oído. El botón se habilita y el manifiesto existe.
- **Sigue pendiente (Fase 3):** traducir en lotes pequeños dentro del ciclo, para acortarlo.
- BiTAM sigue encendido en el puerto 8100 (ocupa unos 5 GB de VRAM). Se apaga cerrando su proceso.
