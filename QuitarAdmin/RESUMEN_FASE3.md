# Resumen de la Fase 3: evaluación y documentación

**Estado: Culminada (2026-11-02).**

## 1. Qué se hizo

- **Evaluación de la Fase 6** (`eval/fase6/`):
  - El criterio de seguridad pasa de «endpoints administrativos cerrados por defecto» a «sin rol
    administrativo (ninguna ruta da 403), cabeceras, CSP, límite de tasa y salud».
  - El diagrama de `architecture.py` dice ahora «Sala de redacción de la PWA (API /api/news: pública)» y
    «sin roles (QuitarAdmin)».
  - Se regeneraron `eval/results/fase_6.json` (`--sin-build`) y `docs/architecture.md`.
- **Documentación que está viva:**
  - `docs/deployment.md`: sin `NA_ADMIN_TOKEN` en el primer despliegue; la sección «Sin roles: toda la API
    es pública» sustituye a «Endpoints administrativos»; recomienda `basicauth` de Caddy si se expone
    fuera de una red de confianza; se quitó la fila del 403 en solución de problemas.
  - `docs/pwa.md`: la sección «Roles» pasa a ser «Sin roles»; la Redacción y la exportación son públicas.
  - `docs/translation.md`: el flujo y la API, sin token; se quitó el código 403.
  - `docs/metrics.md`: el criterio verificable de seguridad pasa a ser «sin rol administrativo».
  - `docs/limitations.md`: se actualizaron la 55 (la exportación es pública) y la 67 (sin usuarios ni
    token), y hay una **nueva 77: «La API no tiene autenticación»**.
  - `README.md`, `traductor/README.md`, `CHANGELOG.md` (entrada «QuitarAdmin») y `CLAUDE.md` (raíz).
- **Documentos históricos:** `resumen_fase6.md` y `resumen_ui_noticiero.md` (en la raíz y en
  `noticias-ashaninka/`) **no se reescribieron**; se les añadió una «Nota posterior (QuitarAdmin)».

## 2. Archivos

`eval/fase6/run.py`, `eval/fase6/architecture.py`, `eval/results/fase_6.json`, `docs/architecture.md`
(generado), `docs/deployment.md`, `docs/pwa.md`, `docs/translation.md`, `docs/metrics.md`,
`docs/limitations.md`, `README.md`, `traductor/README.md`, `CHANGELOG.md`, `../CLAUDE.md`,
`resumen_fase6.md` (×2) y `resumen_ui_noticiero.md` (×2).

## 3. Salida real de las pruebas

```
$ uv run python -m eval.fase6.run --sin-build
OK pruebas_seguridad: 59/59          (antes 55/55: se añadieron las pruebas de acceso abierto)
NO pruebas_despliegue: 30/32         (1 fallo previo ajeno al rol + 1 omitida: no hay binario de caddy)
OK pruebas_escucha: 22/22
OK pruebas_documentacion: 15/15
OK docker_compose_config: True
OK solo_caddy_publica_puertos: {'caddy': ['80', '443', '443']}
-- docker_build_y_arranque: pendiente
OK carga_inicial: 0.0363
OK regresion_fase5: {'cumplidos': 13, 'en_fallo': {}}
NO pruebas_pytest: 363/373

$ uv run ruff check backend eval scripts        All checks passed!
$ uv run ruff format --check backend eval scripts   159 files already formatted
$ uv run pytest -q
1 failed, 337 passed, 9 skipped
```

El único fallo de pytest, que es también el que deja `pruebas_despliegue` y `pruebas_pytest` en «NO», es
`test_dockerignore_deja_pasar_lo_que_el_runtime_necesita_y_excluye_lo_sensible`. Esa prueba exige
`frontend/public/models/presentadora_provisional.vrm`, un archivo que no está en git ni en esta máquina. **Se
comprobó** que, al crear ese archivo temporalmente, la prueba pasa (`2 passed`), y después se borró. El
`fase_6.json` del 2026-10-13 tenía 31/32 porque entonces el archivo sí estaba presente.

## 4. Desviaciones y pendientes

- `pruebas_pytest` cuenta 363/373 porque incluye las omitidas (corpus, eSpeak-NG, Caddy y BiTAM) y el fallo del VRM.
- La limitación nueva es la **77**, no la 70 que se pensó al principio: la 70 ya existía (el traductor).
- `docs/metrics.md` describe métricas definidas antes de medir. Se cambió solo la fila de seguridad,
  porque su criterio dejó de existir. Las métricas lingüísticas y de experimento no se tocaron.
