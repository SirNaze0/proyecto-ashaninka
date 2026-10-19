# NazeParte · Conversación de la sesión

> Archivo de seguimiento **temporal de esta sesión** (no es instrucción permanente del proyecto).

## Sesión 2026-10-19

### Solicitudes relevantes

1. Iniciar el proyecto y resumir qué hace.
2. Preparar la integración futura del traductor español→asháninka (tesis de una compañera, aún sin
   terminar): nueva pantalla de traducción como entrada principal, sin traducciones simuladas,
   conservando noticias, voz y avatar. Registrar el trabajo en tres archivos `NazeParte*.md`.
3. Al revisar el plan: **el avatar debe estar al costado del campo de texto a traducir.**
4. Commit en el **repositorio original** (`https://github.com/SirNaze0/proyecto-ashaninka.git`) y
   **push a una rama nueva**.

### Hallazgos

- La carpeta de trabajo (`proyecto-ashaninka-main`) es una descarga zip: no es repo git. El clon del
  original tiene el mismo contenido (solo difieren finales de línea, CRLF por `autocrlf`).
- Al iniciar el proyecto:
  - `init.sh` omitió la descarga del modelo de voz (pide confirmación y no había terminal).
  - Faltaba el avatar `presentadora_provisional.vrm` (no se versiona).
  - **Bug:** con `NA_FRONTEND_DIST=` vacío (valor de `.env.example`) la PWA no se montaba y `/`
    devolvía 404. Se corrigió en `backend/app/main.py`.
- La voz y el avatar solo funcionan para noticias guardadas y sintetizadas en el backend; no hay
  síntesis de texto libre.
- `PLAN_DESARROLLO.md` §2 ya define el contrato del traductor (`POST /api/news` con procedencia
  `traduccion_automatica`).
- La CSP solo permite conexiones al mismo origen.
- `EventQueue` adjunta a cada evento la condición y la noticia del contexto activo.

### Decisiones y justificaciones

| Decisión | Justificación |
|---|---|
| Solo cambios de frontend | No existe API del traductor; crear un endpoint sería inventarla |
| `#/` → traductor, lista en `#/noticias` | «Entrada principal» pedida; amplía el enrutador existente |
| Traductor por defecto «pendiente» que no llama a nada | Prohibido simular traducciones o inventar integraciones |
| Interfaz `Translator` inyectable | Las pruebas validan carga/resultado/error sin traducción ficticia en la app |
| Reutilizar `AvatarPanel` en reposo, con `import()` diferido | Pedido del usuario; no duplica el avatar y respeta el presupuesto inicial |
| Sin botón de voz para la traducción | Necesita un endpoint nuevo de síntesis (decisión de arquitectura y seguridad pendiente) |
| La portada no emite eventos del avatar | Saldrían con la condición y noticia de otra pantalla y contaminarían el análisis |

### Limitaciones

- La traducción no funciona: el servicio está pendiente de integración y así se muestra.
- El avatar de la portada no habla: sin audio no hay visemas.
- Los textos nuevos de la interfaz solo están en castellano (`cni.json` en `null`, pendiente de un
  hablante).
