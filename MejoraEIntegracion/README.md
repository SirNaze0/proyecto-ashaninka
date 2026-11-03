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
| [`PROMPT_FASE4.md`](PROMPT_FASE4.md) | Fase 4: medición ortográfica, documentación, licencias y cierre | **Culminada** (2026-11-02): ver [`RESUMEN_FASE4.md`](RESUMEN_FASE4.md) |
| `RESUMEN_FASE1.md` … `RESUMEN_FASE4.md` | Resumen de culminación de cada fase | Escritos los 4 |

**Plan completo: 4 de 4 fases culminadas (2026-11-02).** Los pendientes que necesitan personas,
archivos externos o infraestructura están en la sección 7 de `RESUMEN_FASE4.md`.

## Qué falta para que funcione correctamente

**Lo que ya funciona:** la traducción en la Redacción, la revisión del borrador, la publicación con
la voz MMS y la reproducción en C1, C2, C3 y C4. Está comprobado de punta a punta con los modelos
reales (`RESUMEN_FASE4.md` §5). Lo que sigue es lo que todavía falta, ordenado por urgencia.

### 1. Puesta en marcha en cada máquina (obligatorio)

Sin estos pasos, la Redacción muestra «Traductor no disponible» y responde 503. Todos los comandos se
ejecutan desde `noticias-ashaninka/`.

| # | Paso | Cómo | Estado en esta PC |
|---|---|---|---|
| 1 | Tener la entrega de BiTAM descomprimida **fuera del repo** | `bitam_modelos_entrega/` junto a la carpeta del repositorio, o una ruta propia en `BITAM_MODELS_DIR` | ✅ |
| 2 | Instalar el entorno propio del traductor | `cd traductor; uv sync` (torch 2.6 cu124; **no** se mezcla con el del backend) | ✅ |
| 3 | Descargar el modelo base NLLB-200 1.3B (~5,5 GB) | Se descarga solo la primera vez que arranca el servicio (`~/.cache/huggingface`) | ✅ |
| 4 | Descargar la voz MMS | `uv run python scripts/verify_models.py --descargar` (verifica el SHA-256) | ✅ |
| 5 | Configurar `.env` del backend | `NA_TRANSLATOR_URL=http://127.0.0.1:8100`, `NA_TTS_ENGINE=mms_vits` (desde QuitarAdmin ya no hace falta `NA_ADMIN_TOKEN`) | ✅ `.env` creado (2026-11-02) desde `.env.local.example` |
| 6 | Arrancar el traductor (primero) | `cd traductor; .\run.ps1` y esperar a que cargue (~20–30 s) | Manual cada vez |
| 7 | Compilar la PWA y arrancar el backend | `cd frontend; npm run build`, y después `uv run uvicorn app.main:app` | Manual cada vez |
| 8 | Comprobarlo | Sala de redacción → debe decir «Traductor disponible: BiTAM es2cni (…, cuda:0)» | — |

**Archivo `.env` (paso 5).** Hay dos plantillas en `noticias-ashaninka/`:

| Archivo | Para qué | Se versiona |
|---|---|---|
| `.env.example` | Plantilla general del proyecto; el traductor viene **desactivado** (`NA_TRANSLATOR_URL` vacío) | Sí |
| `.env.local.example` | Igual, pero lista para esta integración: `NA_TRANSLATOR_URL=http://127.0.0.1:8100` | Sí |
| `.env` | Configuración real de cada máquina | **No** (`.gitignore`) |

En una máquina nueva:

```powershell
cd noticias-ashaninka
Copy-Item .env.local.example .env
```

Desde QuitarAdmin (`../QuitarAdmin/`) no hay rol administrador ni token: la Sala de redacción está
abierta. Si su `.env` todavía tiene `NA_ADMIN_TOKEN`, se ignora. El `.env` nunca va en git.
Si se añade una variable nueva a `.env.example`, hay que añadirla también a `.env.local.example`.

Si el puerto 8100 queda ocupado después de cerrar la consola (pasa en Windows), consulta
«Problemas frecuentes» en `noticias-ashaninka/traductor/README.md`.

### 2. Archivo que falta en el repositorio

- **VRM de la presentadora** (`frontend/public/models/presentadora_provisional.vrm`). No está en git:
  desde el 2026-11-03 lo descarga y reduce `./init.sh` (commit de three-vrm y SHA-256 fijados).
  - Sin él, en C4 el avatar 3D cae a una **imagen fija**.
  - Sin él, `test_dockerignore…` falla, las 4 E2E del avatar se saltan y `scripts/verify.sh` no
    termina en verde.
  - No es un fallo del traductor; ya ocurría antes de esta integración.

### 3. Defectos conocidos del traductor (técnicos, sin resolver)

| Problema | Efecto | Qué falta |
|---|---|---|
| BiTAM a veces **omite el punto final** (limitación 73) | Varias oraciones quedan en un solo fragmento de audio y aparecen mayúsculas a mitad de segmento | Copiar el signo final de la fuente cuando falte, y medirlo con **otra** muestra del dev (no con la ya usada) |
| **Nombres castellanos con `d` o `l`** | 3,9 % de segmentos bloqueados para la voz (salen solo como texto) | Depende de la reescritura es→cni (P2d), que necesita validación lingüística |
| BiTAM **copia pocos nombres propios** (3 de 36) | Pocos nombres recuperan la mayúscula; el resto los adapta o los omite | Revisión del hablante; no se corrige automáticamente |
| **Latencia** de la Fase 4 medida con el escritorio cargado | La cifra (6,16 s/oración) no es válida | Repetir `eval.traductor.run` con la GPU libre (cerrar Wallpaper Engine, navegadores, etc.). Referencia limpia: 2,21 s/oración (Fase 1) |

### 4. Lo que necesita personas (no lo puede hacer el código)

1. **Revisión por un hablante de cada noticia traducida** antes de usarla en el experimento (P4).
   BiTAM da un borrador (chrF++ ≈ 25). La Redacción lo guarda como «traducción automática» y nunca
   lo marca como revisado.
2. **Vocales largas (P1).** BiTAM las elimina todas (0 por 100 palabras frente a 20,67 en el corpus).
   Un hablante o lingüista debe decir si eso afecta a la comprensión o a la pronunciación de la voz.
3. **Cita de la tesis BiTAM.** Completar con la compañera la autoría y los datos de publicación en
   `noticias-ashaninka/CITATION.md`.
4. **Textos de la interfaz en asháninka.** `cni.json` sigue vacío a propósito, también para las 20
   claves nuevas de la Redacción.

### 5. Despliegue en producción

- El traductor **no está en `docker compose`**. Necesita una máquina con GPU NVIDIA y los pesos, que
  no se pueden redistribuir: CC BY-NC.
- Si el backend corre en Docker, `127.0.0.1:8100` apunta al contenedor, no al equipo donde corre el
  traductor. `NA_TRANSLATOR_URL` tendría que apuntar a la máquina que lo ejecuta, y ese acceso hay que
  restringirlo a la red interna.
- Esto está documentado en `docs/translation.md` y `docs/deployment.md`, pero **nunca se probó**.

## Reglas de esta carpeta

- Las fases van **en orden**: cada una depende de la anterior.
- Una fase se da por culminada solo cuando **todas sus pruebas obligatorias pasan**. Entonces se
  escribe su `RESUMEN_FASEn.md` y se actualiza el estado en esta tabla.
- Los resúmenes copian la **salida real** de las pruebas y las mediciones (los JSON de
  `eval/results/`). No se escriben por adelantado ni con cifras estimadas presentadas como medidas,
  igual que los `resumen_faseN.md` del proyecto.
- Todo va en español, como el resto de los documentos de la tesis.
