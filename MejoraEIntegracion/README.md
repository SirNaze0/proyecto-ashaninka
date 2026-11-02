# MejoraEIntegracion: integración del traductor BiTAM (es→cni)

Esta carpeta contiene el plan y los prompts por fase para integrar en el servicio de noticias el
traductor castellano→asháninka **BiTAM**, que es la tesis de la compañera. También guardará el
resumen de culminación de cada fase.

## Flujo objetivo

1. El **Administrador** escribe o pega una noticia en castellano en la Redacción.
2. El servidor la traduce **una sola vez** con BiTAM.
3. El administrador revisa el borrador y lo publica (`/api/news` → `process` → `build`).
4. El **Ciudadano** solo ve, en el tablero, noticias ya traducidas (texto, voz y avatar).

## Documentos

| Archivo | Qué es | Estado |
|---|---|---|
| [`PLAN_INTEGRACION.md`](PLAN_INTEGRACION.md) | Plan maestro: veredicto de compatibilidad, arquitectura, fases, criterios de aceptación y riesgos | Aprobado (2026-11-02) |
| [`PROMPT_FASE1.md`](PROMPT_FASE1.md) | Fase 1: servicio BiTAM aparte (entorno propio y GPU) | **Culminada** (2026-11-02): ver [`RESUMEN_FASE1.md`](RESUMEN_FASE1.md) |
| [`PROMPT_FASE2.md`](PROMPT_FASE2.md) | Fase 2: backend (cliente, mayúsculas, `POST /api/news/translate`) | **Culminada** (2026-11-02): ver [`RESUMEN_FASE2.md`](RESUMEN_FASE2.md) |
| [`PROMPT_FASE3.md`](PROMPT_FASE3.md) | Fase 3: Redacción en la PWA (tarjeta «Traducir desde castellano») | **Culminada** (2026-11-02): ver [`RESUMEN_FASE3.md`](RESUMEN_FASE3.md) |
| [`PROMPT_FASE4.md`](PROMPT_FASE4.md) | Fase 4: medición ortográfica, documentación, licencias y cierre | Pendiente |
| `RESUMEN_FASE1.md` … `RESUMEN_FASE4.md` | Resumen de culminación de cada fase | Se escriben al cerrar cada fase |

## Reglas de esta carpeta

- Las fases van **en orden**: cada una depende de la anterior.
- Una fase se da por culminada solo cuando **todas sus pruebas obligatorias pasan**. Entonces se
  escribe su `RESUMEN_FASEn.md` y se actualiza el estado en esta tabla.
- Los resúmenes copian la **salida real** de las pruebas y las mediciones (los JSON de
  `eval/results/`). No se escriben por adelantado ni con cifras estimadas presentadas como medidas,
  igual que los `resumen_faseN.md` del proyecto.
- Todo va en español, como el resto de los documentos de la tesis.
