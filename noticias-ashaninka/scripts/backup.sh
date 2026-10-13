#!/usr/bin/env bash
# Copia de seguridad de la base de datos del servicio en Docker (noticias, sesiones del experimento,
# respuestas y eventos). Es consistente con el servidor escribiendo (API de respaldo de SQLite).
#
# Uso: scripts/backup.sh [carpeta-destino]      (por defecto ./backups)
# Restaurar: detenga el servicio y copie el archivo a /data/noticias.db del volumen na_data.
set -euo pipefail
cd "$(dirname "$0")/.."

destino="${1:-backups}"
sello="$(date +%Y%m%d-%H%M%S)"
archivo="noticias-${sello}.db"

mkdir -p "$destino"
docker compose exec -T app python -m app.cli db-backup --out "/export/${archivo}"
docker compose cp "app:/export/${archivo}" "${destino}/${archivo}"
docker compose exec -T app rm -f "/export/${archivo}"
echo "[backup] ${destino}/${archivo}"
