# Resumen de la Fase 5: traducción en trozos (mejora de velocidad)

**Estado: Culminada (2026-11-02).**

## 1. Qué se hizo

- **Ensayo exploratorio** (no cuenta como medición): una noticia de 13 textos traducida de 1 en 1 (224 s), de 2 en 2
  (185 s), de 4 en 4 (160 s) y entera (255 s). De ahí salió el valor 4, fijado **antes** de medir.
- **Código:**
  - `EnTrozos(translator, trozo)` en `backend/app/translation/client.py`: reparte los textos en peticiones de
    `trozo` y une las salidas en orden.
  - `NA_FEED_TRANSLATOR_LOTE`: 4 por defecto; 0 = la noticia entera, como hasta la Fase 4. Está en `config.py`
    y en los tres `.env*.example`.
  - El ciclo de TV Perú lo usa; la Redacción **no** cambia.
- **Pruebas:**
  - `test_en_trozos_conserva_el_orden_y_los_metadatos`;
  - `test_el_ciclo_traduce_en_trozos_del_tamano_configurado`, parametrizada con 4, 0 y 1, que da peticiones
    de [4, 4, 1], [9] y 9 × [1].
- **Medición** definida en `docs/metrics.md` antes de ejecutar (commit `08a3983`), con dos scripts:
  - `eval/tvperu/lotes.py` (velocidad);
  - `traductor/fidelidad.py --lote` (fidelidad).
- **Documentado** en `docs/tvperu.md` (sección «Traducción en trozos»), `CHANGELOG.md` y `README.md` de esta
  carpeta.
- **Recortar a 6 oraciones** queda **solo** como posible mejora en el README, como pidió el usuario.

## 2. Resultados reales

**Velocidad** (`eval/results/tvperu_lotes.json`, 3 noticias reales del RSS en el momento de medir, orden alternado):

| Noticia | Textos | Trozos de 4 | Entera | Ahorro | Salidas distintas |
|---|---|---|---|---|---|
| penal El Milagro → Challapalca | 13 | 157,1 s | 303,7 s | 48,3 % | 3 |
| reserva nacional de Tambopata | 13 | 196,5 s | 482,5 s | 59,3 % | 4 |
| carretera Federico Basadre | 11 | 140,1 s | 192,0 s | 27,0 % | 2 |
| **Total** | 37 | **493,7 s** | **978,2 s** | **49,5 %** | 9 |

**Fidelidad** (`eval/results/traductor_fidelidad_float16_lote4.json`; dev de AmericasNLP, los mismos 200 pares con
semilla 13, nunca el test):

```
traductor_fidelidad_float16_lote4.json: chrF++=26.32 chrF=32.63 (1210 s)
float16 (lotes de 32):                  chrF++=26.39 chrF=32.68 | salidas idénticas: 176/200
```

Diferencia de chrF++: **0,07**, por debajo del criterio de **≤ 0,5** → **se acepta**, y el valor por defecto queda en 4.

Pruebas:

```
$ uv run ruff check backend eval scripts traductor    All checks passed!
$ uv run pytest -q
1 failed, 366 passed, 8 skipped        (el fallo previo del VRM; +4 pruebas nuevas)
```

## 3. Desviaciones y pendientes

- **Hallazgo:** con oraciones **cortas** (las del dev), los trozos de 4 son **8 veces más lentos** (1.210 s frente a
  146 s en lotes de 32). El beneficio aparece solo con las oraciones largas de las noticias, en las que el lote
  grande satura los 6 GB de VRAM. Por eso el cambio se limita al ciclo de TV Perú, y la Redacción sigue enviando
  todo junto.
- **El agrupamiento cambia algunas salidas** (fp16): 9 de 37 en las noticias y 24 de 200 en el dev, sin efecto
  medible en chrF++. Ya pasaba antes, porque el servicio agrupa de 8 en 8 por dentro.
- **El ciclo completo no se volvió a medir de punta a punta.** Los 9–10 min salen de sumar la traducción medida
  (494 s) y la síntesis de la Fase 3 (≈ 77 s).
- Una sola ejecución por configuración: la variación entre ejecuciones no está cuantificada.
- BiTAM sigue encendido en el puerto 8100.
