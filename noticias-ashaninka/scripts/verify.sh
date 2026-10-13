#!/usr/bin/env bash
# Verificación completa en un solo comando (Fase 6, tarea 6.4): lint, pruebas de Python, PWA
# (vitest, tipos, compilación y E2E en Chromium real) y consolidación en eval/results/fase_6.json.
#
# Uso: scripts/verify.sh [--sin-e2e]
# Requisitos: ./init.sh ya ejecutado; Node 20+ y, la primera vez, `npx playwright install chromium`.
set -euo pipefail
cd "$(dirname "$0")/.."

e2e=1
for arg in "$@"; do
  case "$arg" in
    --sin-e2e) e2e=0 ;;
    *) echo "opción desconocida: $arg" >&2; exit 2 ;;
  esac
done

out="eval/fase6/out"
mkdir -p "$out"

echo "== Python: lint y formato"
uv run ruff check backend eval scripts
uv run ruff format --check backend eval scripts

echo "== Python: pruebas"
uv run pytest -q --junitxml="$out/pytest.xml"

echo "== PWA: dependencias, pruebas, tipos y compilación"
(
  cd frontend
  [ -d node_modules ] || npm ci --no-audit --no-fund
  npx vitest run --reporter=json --outputFile="../$out/vitest.json" >/dev/null
  npm test
  npm run typecheck
  npm run build
  if [ "$e2e" -eq 1 ]; then
    echo "== PWA: E2E en Chromium real"
    PLAYWRIGHT_JSON_OUTPUT_NAME="../$out/e2e.json" npx playwright test --reporter=list,json
  fi
)

echo "== Consolidación (eval/results/fase_6.json)"
uv run python -m eval.fase6.run

echo "== Todo en orden"
