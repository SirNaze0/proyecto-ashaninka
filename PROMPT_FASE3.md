cd /h/PROYECTOS-TRABAJO/PROYECTO-ASHANINKA/proyecto-ashaninka
grep -qxF 'export PATH="$PATH:/c/Program Files/eSpeak NG"' ~/.bashrc || echo 'export PATH="$PATH:/c/Program Files/eSpeak NG"' >> ~/.bashrc
grep -qxF ".vscode/" .gitignore || echo ".vscode/" >> .gitignore
grep -qxF "CLAUDE.local.md" .gitignore || echo "CLAUDE.local.md" >> .gitignore
git checkout -- CLAUDE.md 2>/dev/null || true

cat << 'EOF' > CLAUDE.local.md

# Preferencias personales de sesión

- Idioma obligatorio: comunícate, redacta planes, commits y reportes siempre en español.
- Meta prioritaria: completar las Fases 4 y 5 del experimento (condiciones C1, C2, C3 y C4) cumpliendo TTFA p95 < 2 s (por lotes), carga inicial < 3 MB, desfase <= 80 ms y 60 FPS.
- Autonomía: ante disyuntivas técnicas dentro de una fase, evalúa con datos reales, elige la opción que cumpla las métricas de la tesis y documéntala sin detener la ejecución.
  EOF

mkdir -p .claude/rules

## cat << 'EOF' > .claude/rules/frontend-pwa.md

paths:

- "noticias-ashaninka/frontend/\*\*"

---

# Reglas de Frontend, Avatar y PWA (Fase 4)

- Presupuesto < 3 MB: three y @pixiv/three-vrm siempre van con import() dinámico (carga diferida).
- Condiciones C1 (solo texto), C2 (solo voz), C3 (voz + texto resaltado con AudioClock), C4 (voz + texto + AvatarPanel).
- Segmentos bloqueados (sin P2d): se muestran solo en texto con aviso claro sin cortar la reproducción.
- Licencia: mostrar siempre el aviso de voz sintética CC-BY-NC 4.0.
  EOF

## cat << 'EOF' > .claude/rules/evaluacion-y-datos.md

paths:

- "noticias-ashaninka/eval/\*\*"
- "noticias-ashaninka/backend/\*\*"

---

# Reglas de Rigor Experimental y Lingüístico

- Disciplina de splits: train para reglas, dev para ajuste/calibración, test SOLO para medición final.
- Cero invención lingüística: usar marcadores validado, candidato-corpus o SUPUESTO-LING con hash SHA-256.
- Definir métricas en docs/metrics.md antes de medir.
  EOF

sed -i 's/pendiente de aprobación/APROBADA el 2026-10-12/g' resumen_fase3.md noticias-ashaninka/resumen_fase3.md
git add .
git commit -m "feat(fase3): implementar alineacion, visemas, visor VRM y completar linea base espeak"
