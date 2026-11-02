#!/usr/bin/env bash
# Arranca el servicio BiTAM es->cni en 127.0.0.1 (un solo worker: el modelo ocupa ~3 GB).
# Uso (desde noticias-ashaninka/traductor):  ./run.sh [puerto] [auto|cuda|cpu]
set -euo pipefail
cd "$(dirname "$0")"
PUERTO="${1:-8100}"
export BITAM_DEVICE="${2:-auto}"
export BITAM_MODELS_DIR="${BITAM_MODELS_DIR:-$(cd ../../../bitam_modelos_entrega/modelos && pwd)}"
echo "Modelos: $BITAM_MODELS_DIR | dispositivo: $BITAM_DEVICE | http://127.0.0.1:$PUERTO"
exec uv run uvicorn servidor:app --host 127.0.0.1 --port "$PUERTO" --workers 1
