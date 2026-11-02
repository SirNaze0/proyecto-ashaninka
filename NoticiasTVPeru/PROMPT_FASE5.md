# PROMPT: Fase 5. Traducción en trozos (mejora de velocidad)

> Copia todo lo que está debajo de la línea en una sesión de Claude Code abierta en
> `C:\Users\Marco\Downloads\proyecto-ashaninka\proyecto-ashaninka`.
> Antes, lee `NoticiasTVPeru/PLAN_TVPERU.md` (sección Fase 5), `RESUMEN_FASE3.md` y `docs/tvperu.md`.

---

# ROL

Actúa como ingeniero backend y responsable de evaluación. Debes acelerar la traducción dentro del ciclo de TV Perú
sin tocar el modelo BiTAM, y medir el efecto en la velocidad y en la fidelidad.

# CONTEXTO

- El servicio BiTAM traduce cada petición en lotes internos de 8 (`traductor/servidor.py:104`). Con oraciones
  largas y la VRAM de 6 GB llena, un lote grande es lento.
- Ensayo exploratorio (una noticia de 13 textos):

  | Envío | Tiempo |
  |---|---|
  | de 1 en 1 | 224 s |
  | de 2 en 2 | 185 s |
  | de 4 en 4 | 160 s |
  | todo junto | 255 s |

  Según el agrupamiento, cambian 2–3 de 13 salidas.
- Fidelidad de referencia: `eval/results/traductor_fidelidad_float16.json` (dev, N = 200, semilla 13, lotes de 32
  desde el cliente): chrF++ 26,39.

# TAREAS

1. `EnTrozos(translator, trozo)` en `backend/app/translation/client.py` y `NA_FEED_TRANSLATOR_LOTE` (4 por
   defecto; 0 = todo junto) en `config.py` y en los tres `.env*.example`. El ciclo la usa; la Redacción no
   cambia.
2. Pruebas: el reparto en trozos conserva el orden y los metadatos; el ciclo usa el tamaño configurado.
3. Definir la medición en `docs/metrics.md` **antes** de medir.
4. Velocidad: `eval/tvperu/lotes.py` → `eval/results/tvperu_lotes.json`.
5. Fidelidad: `traductor/fidelidad.py --lote 4` → `eval/results/traductor_fidelidad_float16_lote4.json`.
6. Documentar en `docs/tvperu.md`, `README` y `CHANGELOG`. El recorte de 6 oraciones queda como **posible
   mejora** en `NoticiasTVPeru/README.md`, sin implementar.

# PRUEBAS OBLIGATORIAS (criterio de cierre)

| # | Prueba | Resultado esperado |
|---|---|---|
| 1 | `uv run pytest` | Verde, salvo el fallo previo del VRM |
| 2 | `uv run ruff check backend eval scripts traductor` | Sin errores |
| 3 | `eval/results/tvperu_lotes.json` y `traductor_fidelidad_float16_lote4.json` | Generados con cifras reales |

# RESTRICCIONES

- No se cambian los parámetros de generación de BiTAM (haz, longitud): pertenecen a la tesis de la compañera.
- No se usa el test de AmericasNLP (solo el dev).
- No se ajusta nada después de ver los resultados.
- Comentarios, documentos y commits en español.

# AL TERMINAR

Escribe `NoticiasTVPeru/RESUMEN_FASE5.md` y haz un commit en español.
