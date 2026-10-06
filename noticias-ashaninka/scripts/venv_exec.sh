#!/usr/bin/env bash
# Ejecuta una herramienta del entorno virtual del proyecto sin depender de `uv run`.
# Motivo: dentro de los ganchos de git en Windows, `uv run` no siempre encuentra los ejecutables
# del entorno (PATH heredado por Git para Windows). Uso: scripts/venv_exec.sh <herramienta> [args]
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
tool="$1"
shift
for dir in .venv/Scripts .venv/bin; do
  for candidate in "$dir/$tool.exe" "$dir/$tool"; do
    if [ -x "$candidate" ]; then
      exec "$candidate" "$@"
    fi
  done
done
echo "venv_exec: no se encontró '$tool' en .venv (ejecuta ./init.sh)" >&2
exit 127
