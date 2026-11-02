# Arranca el servicio BiTAM es->cni en 127.0.0.1:8100 (un solo worker: el modelo ocupa ~3 GB).
# Uso (desde noticias-ashaninka/traductor):  .\run.ps1   [-Puerto 8100] [-Device auto|cuda|cpu]
param(
    [int]$Puerto = 8100,
    [string]$Device = "auto"
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not $env:BITAM_MODELS_DIR) {
    $env:BITAM_MODELS_DIR = (Resolve-Path "..\..\..\bitam_modelos_entrega\modelos").Path
}
$env:BITAM_DEVICE = $Device
Write-Host "Modelos: $env:BITAM_MODELS_DIR | dispositivo: $Device | http://127.0.0.1:$Puerto"
uv run uvicorn servidor:app --host 127.0.0.1 --port $Puerto --workers 1
