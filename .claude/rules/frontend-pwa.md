---
paths:
  - "noticias-ashaninka/frontend/**"
---
# Reglas de Frontend, Avatar y PWA (Fase 4)
- Presupuesto < 3 MB: three y @pixiv/three-vrm siempre van con import() dinámico (carga diferida).
- Condiciones C1 (solo texto), C2 (solo voz), C3 (voz + texto resaltado con AudioClock), C4 (voz + texto + AvatarPanel).
- Segmentos bloqueados (sin P2d): se muestran solo en texto con aviso claro sin cortar la reproducción.
- Licencia: mostrar siempre el aviso de voz sintética CC-BY-NC 4.0.
