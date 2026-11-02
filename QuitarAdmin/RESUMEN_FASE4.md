# Resumen de la Fase 4: verificación integral

**Estado: Culminada (2026-11-02).**

## 1. Qué se hizo

- Se ejecutó `scripts/verify.sh`. El script se detiene en el paso de pytest por el fallo previo del VRM
  (ver §3), así que los pasos siguientes se ejecutaron **a mano, con los mismos comandos del script**:
  pruebas del traductor con el motor falso, vitest con reporte JSON, `npm test`, `typecheck`, `build`, Playwright con
  reporte JSON y `eval.fase6.run` (consolidación sin `--sin-build`; Docker queda «pendiente» porque el demonio
  está apagado).
- Prueba manual con uvicorn real, sin `NA_ADMIN_TOKEN` y con el piloto apagado.
- Búsqueda de restos (`git grep`). Aparecieron 3 restos en código de evaluación y una instrucción operativa
  vieja, y se corrigieron:
  - `eval/fase4/prepare.py`: ya no fija `NA_ADMIN_TOKEN`;
  - `eval/fase5/simulate.py`: ya no guarda ni borra `NA_EXPORT_TOKEN`;
  - `MejoraEIntegracion/README.md`: el paso 5 y la sección `.env` ya no piden token.
- Se escribió `QuitarAdmin/README.md`.

## 2. Salida real

```
== Python: lint y formato
All checks passed!
164 files already formatted
== Python: pruebas
1 failed, 337 passed, 9 skipped           (el fallo previo del VRM)
== Traductor BiTAM: pruebas del servicio (motor falso)
15 passed
== PWA
 Test Files  9 passed (9)
      Tests  102 passed (102)
typecheck ok
✓ built in 252ms
== PWA: E2E en Chromium real
  4 skipped
  39 passed (1.8m)
== Consolidación (eval/results/fase_6.json)
OK pruebas_seguridad: 36/36
NO pruebas_despliegue: 29/31             (fallo previo del VRM; 1 omitida: no hay Caddy)
OK pruebas_escucha: 22/22
OK pruebas_documentacion: 13/13
OK docker_compose_config: True
-- docker_build_y_arranque: pendiente
OK carga_inicial: 0.0363
OK regresion_fase5: {'cumplidos': 13, 'en_fallo': {}}
NO pruebas_pytest: 337/347
OK pruebas_vitest: 102/102
OK pruebas_e2e: 39/43
```

(Los totales por área difieren de los de la Fase 3 porque aquí `eval.fase6.run` lee el `pytest.xml` de la
ejecución completa en lugar de lanzar su propia ejecución por área; los parametrizados se cuentan de otra forma.)

Prueba manual (uvicorn real, puerto 8765, base de datos temporal):

```
POST   /api/news                  -> 201
GET    /api/news                   -> 200
DELETE /api/news/1                 -> 204
GET    /api/news/1                 -> 404
GET    /api/experiment/export      -> 200
GET    /api/events/summary         -> 200
GET    /api/news/translate/status  -> 200
```

Búsqueda de restos: `git grep -i -E "admin_token|require_admin|check_admin|x-admin-token|x-export-token|puedeVerRedaccion|verificarToken|NA_EXPORT_TOKEN"`.
Fuera de `QuitarAdmin/`, CHANGELOG y las notas históricas, solo aparecen:

- pruebas que comprueban la **ausencia** del token (`test_security.py`, `test_security_api.py`,
  `test_translate_api.py`, `test_deploy_artifacts.py`, `newsroom*.test.ts` y `newsroom-translate.spec.ts`);
- documentación que explica que se retiró (`CLAUDE.md`, `deployment.md` y `limitations.md` 55 y 77);
- documentos **históricos** de otras etapas que no se reescriben: los prompts y resúmenes de
  `MejoraEIntegracion/`, `PROMPT_FASE6.md`, `NazePartePlan.md` y el `mockup-v0/`.

## 3. Desviaciones y pendientes

- **El único fallo es previo y ajeno al rol.** `test_dockerignore_deja_pasar_lo_que_el_runtime_necesita_y_excluye_lo_sensible`
  exige `frontend/public/models/presentadora_provisional.vrm`, que no está en git ni en esta máquina. Con el
  archivo presente pasa (comprobado en la Fase 3). Por ese fallo `scripts/verify.sh` se corta en pytest; para que el
  script termine de punta a punta, hay que copiar el VRM provisional a esa ruta.
- Docker no se construyó (el demonio está apagado), igual que en la Fase 6 original.
- Las 4 pruebas E2E omitidas (`sin-webgl` y `software`) ya se omitían antes en esta máquina.
