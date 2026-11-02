# Resumen de la Fase 3: documentación y medición

**Estado: Culminada (2026-11-02).**

## 1. Qué se hizo

- **Documentación:**
  - `docs/tvperu.md`, **nuevo**: flujo, configuración, API, qué pasa cuando algo falla, despliegue y resultados
    medidos.
  - Actualizados: `docs/pwa.md`, `docs/translation.md`, `docs/deployment.md`, `README.md`, `CHANGELOG.md`
    (entrada «NoticiasTVPeru») y `CLAUDE.md`.
  - **Limitaciones 78 a 81:**
    - 78: traducción sin revisar;
    - 79: dependencia del formato del RSS;
    - 80: licencia de reutilización no verificada con el IRTP;
    - 81: solo se traduce un resumen y se pierden nombres propios.
- **Medición:**
  - se definió en `docs/metrics.md` **antes** de medir (commit `2353c33`);
  - script `eval/tvperu/run.py` (base temporal; no guarda texto de TV Perú ni de BiTAM: URL, recuentos,
    tiempos y hashes).
- **Corrección hallada al medir:** se añadió `NA_FEED_TRANSLATOR_TIMEOUT` (900 s), la espera del traductor dentro
  del ciclo de fondo, en `config.py`, `feed/servicio.py` y los tres `.env*.example`, con su prueba.

## 2. Resultados reales

**Primer intento** (`eval/results/tvperu_intento1.json`):
- BiTAM disponible y 15 noticias nuevas, pero **0 publicadas**.
- La primera traducción (una noticia, ≈ 13 oraciones en un lote) superó los 120 s de `NA_TRANSLATOR_TIMEOUT`, la
  espera pensada para la Redacción. Todo quedó `pendiente`, que es el comportamiento previsto cuando el traductor
  no responde.
- GPU al 100 % y VRAM llena (6.004 de 6.144 MiB).
- Antes de repetir se registraron en `docs/metrics.md` el intento y el cambio. Lo que cambió fue la configuración
  del sistema, no la medición.

**Segundo intento** (`eval/results/tvperu.json`, el que vale):

| Noticia | Enviado | Traducción | s/oración | Síntesis | Segmentos (audio / bloqueados) | Audio |
|---|---|---|---|---|---|---|
| cultural | 12 or., 2.007 car. | 315 s | 24,3 | 41 s | 9 (8 / 1) | 150 s |
| política | 12 or., 1.776 car. | 198 s | 15,3 | 17 s | 9 (5 / 4) | 78 s |
| nacionales | 10 or., 1.950 car. | 341 s | 31,0 | 19 s | 8 (4 / 4) | 84 s |

- Ciclo: **933 s (≈ 15,5 min)**, 3 publicadas, 12 en cola y 0 errores. 17 de 26 segmentos con voz (65 %).
- Una oración suelta tardó **6,4 s** en la misma GPU justo antes: **la traducción en lote es de 2,5 a 5 veces más
  lenta** que oración por oración en esta GPU de 6 GB.

Pruebas:

```
$ uv run ruff check backend eval scripts         All checks passed!
$ uv run ruff format --check backend eval scripts   168 files already formatted
$ uv run pytest -q
1 failed, 362 passed, 8 skipped     (el fallo previo del VRM; con BiTAM encendido, ahora también corre
                                     la prueba contra el servicio real)
```

## 3. Desviaciones y pendientes

- **Hubo dos intentos.** El primero se conserva y se informa; la causa (la espera del cliente) se corrigió en el
  sistema, sin tocar el recorte, el parser ni el pipeline.
- **Pendiente con prioridad:** traducir en lotes pequeños (o de una oración) dentro del ciclo. Según la medición,
  bajaría cada noticia de unos 5 min a unos 1,5 min, pero **no se ajustó** después de ver los datos: hay que hacerlo
  como cambio aparte y medirlo con otra ejecución.
- **Recomendación de uso** hasta entonces: intervalo de 30 min o más, o 1–2 noticias por ciclo. El intervalo cuenta
  desde que **termina** el ciclo anterior, así que los ciclos nunca se solapan.
- Los motivos de bloqueo se agregaron a su primera parte («bloqueado para TTS»), así que no distinguen la causa
  exacta (letra fuera del vocabulario frente a nombre propio sin P2d).
- El feed cambió entre los dos intentos: las noticias medidas no son las mismas del primero (es un feed vivo).
