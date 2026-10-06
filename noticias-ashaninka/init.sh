#!/usr/bin/env bash
# init.sh — inicializa el proyecto noticias-ashaninka en cualquier máquina.
#
# Compatible con Linux, macOS, WSL y Git Bash (Windows). Idempotente.
# No usa sudo ni instala paquetes del sistema: si falta algo, indica cómo instalarlo.
#
# Códigos de salida: 0 ok · 1 falta un requisito del sistema · 2 falló una etapa · 3 hash no coincide
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# ---------------------------------------------------------------- versiones fijadas
AMERICASNLP_COMMIT="d3f519c6b38299d8149311e65a369047350e6849"
AMERICASNLP_RAW="https://raw.githubusercontent.com/AmericasNLP/americasnlp2021/${AMERICASNLP_COMMIT}"
CORPUS_DIR="data/corpus/americasnlp2021"
# formato: ruta_remota|archivo_local|sha256
CORPUS_FILES=(
  "data/ashaninka-spanish/train.cni|train.cni|dd528a5b61284dde62d1c957a8e7bdbad296f40cb9ed128b592e5aaa9bdf6d84"
  "data/ashaninka-spanish/train.es|train.es|d86a5aecc2b9ea0e1ac684cb1984d8fb6420482c8d750d3ed58d04739348002e"
  "data/ashaninka-spanish/dev.cni|dev.cni|90c85ba9bee92e3ff871e3128a6d2f376387978d108538f552d87874b9f35161"
  "data/ashaninka-spanish/dev.es|dev.es|5ea9455bee5e67f56db261a7969cf410a8f833305afc669cc6d5ee39ef7b10d3"
  "test_data/test.cni|test.cni|9927b2daa5a4d607945cfed06bfd83a83517fa455af31d0753e911d9a0a1e004"
  "data/ashaninka-spanish/test.es|test.es|a30e58fe429dcaeaf17699e38e2e23ffc13722ae530c4c724f9855d26c73aa8f"
)
MMS_TTS_REPO="facebook/mms-tts-cni"
MMS_TTS_REVISION="a744890bf8b52fd17ed322d8d995dec6cf77809b"
MMS_VOCAB_SHA="e1c795b28e1077be9a9baf60d2399639ed698774014bbc930de601f8dd4fa62b"
MMS_VOCAB_PATH="backend/tests/fixtures/mms_cni_vocab.json"
MMS_ASR_REPO="facebook/mms-1b-all"
MMS_ASR_REVISION="3d33597edbdaaba14a8e858e2c8caa76e3cec0cd"
MONO_URL="https://github.com/iapucp/multilingual-data-peru"

# ---------------------------------------------------------------- opciones
WITH_DATA=0; WITH_MONO=0; WITH_AUDIO=0; WITH_ASR=0; CHECK=0; RESET_DB=0; YES=0

usage() {
  cat <<'EOF'
Uso: ./init.sh [opciones]

Sin opciones: verifica requisitos, instala uv y Python 3.11, instala dependencias,
crea .env y la base de datos, descarga y verifica el corpus AmericasNLP y el
vocabulario de mms-tts-cni, configura pre-commit, valida los recursos YAML y
ejecuta la prueba rápida.

Opciones:
  --with-data        Además importa noticias de prueba (data/news/), genera el informe
                     y los candidatos del corpus, y procesa todo.
  --with-monolingual Además descarga el corpus monolingüe iapucp (carpeta cni).
  --with-audio-eval  Además instala el grupo eval y descarga mms-tts-cni (tarea 1.8).
  --with-asr-eval    Además descarga mms-1b-all (~3,9 GB) para la tarea 1.9.
  --check            Solo verifica el estado, sin modificar nada.
  --reset-db         Borra y recrea la base de datos (pide confirmación salvo --yes).
  --yes              Responde "sí" a las confirmaciones.
  -h, --help         Muestra esta ayuda.

Ejemplos:
  ./init.sh
  ./init.sh --with-data
  ./init.sh --with-audio-eval --with-asr-eval --yes
  ./init.sh --check
EOF
}

for arg in "$@"; do
  case "$arg" in
    --with-data) WITH_DATA=1 ;;
    --with-monolingual) WITH_MONO=1 ;;
    --with-audio-eval) WITH_AUDIO=1 ;;
    --with-asr-eval) WITH_ASR=1; WITH_AUDIO=1 ;;
    --check) CHECK=1 ;;
    --reset-db) RESET_DB=1 ;;
    --yes|-y) YES=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "[init] opción desconocida: $arg" >&2; usage; exit 2 ;;
  esac
done

# ---------------------------------------------------------------- utilidades
SUMMARY=()
log() { printf '[init] %s\n' "$*"; }
ok() { SUMMARY+=("OK      $*"); log "OK: $*"; }
skip() { SUMMARY+=("OMITIDO $*"); log "omitido: $*"; }
fail() { SUMMARY+=("FALLO   $*"); log "FALLO: $*"; }

print_summary() {
  echo
  echo "[init] ---------------- resumen ----------------"
  local line
  for line in "${SUMMARY[@]}"; do echo "[init] $line"; done
}

die() { # die <código> <mensaje>
  fail "$2"
  print_summary
  exit "$1"
}

confirm() { # confirm <pregunta>
  if [ "$YES" -eq 1 ]; then return 0; fi
  local reply
  read -r -p "[init] $1 [s/N] " reply || return 1
  [[ "$reply" =~ ^[sSyY] ]]
}

OS="$(uname -s)"
case "$OS" in
  Linux*) PLATFORM="linux" ;;
  Darwin*) PLATFORM="macos" ;;
  MINGW*|MSYS*|CYGWIN*) PLATFORM="windows" ;;
  *) PLATFORM="desconocido" ;;
esac
if [ "$PLATFORM" = "linux" ] && grep -qi microsoft /proc/version 2>/dev/null; then
  PLATFORM="wsl"
fi

sha256_of() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | awk '{print $1}'
  else
    echo "sin-herramienta"
  fi
}

install_hint() { # install_hint <herramienta>
  case "$PLATFORM" in
    windows) echo "  Instala '$1' con Git for Windows (https://git-scm.com) o winget." ;;
    macos) echo "  Instala '$1' con: brew install $1" ;;
    linux|wsl) echo "  Instala '$1' con el gestor de tu distribución, p. ej.: sudo apt install $1" ;;
    *) echo "  Instala '$1' manualmente." ;;
  esac
}

# Descarga a un archivo temporal y lo mueve solo si el hash coincide.
fetch_verified() { # fetch_verified <url> <destino> <sha256>
  local url="$1" dest="$2" expected="$3" tmp
  if [ -f "$dest" ] && [ "$(sha256_of "$dest")" = "$expected" ]; then
    return 0
  fi
  if [ "$CHECK" -eq 1 ]; then
    return 4
  fi
  mkdir -p "$(dirname "$dest")"
  tmp="${dest}.part"
  curl -fsSL --retry 3 -o "$tmp" "$url" || { rm -f "$tmp"; return 2; }
  local got
  got="$(sha256_of "$tmp")"
  if [ "$got" != "$expected" ]; then
    rm -f "$tmp"
    log "hash esperado $expected, obtenido $got para $url"
    return 3
  fi
  mv "$tmp" "$dest"
}

log "plataforma detectada: $PLATFORM ($OS)"
[ "$CHECK" -eq 1 ] && log "modo --check: no se modificará nada"

# ---------------------------------------------------------------- 1. requisitos
for tool in git curl; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    install_hint "$tool"
    die 1 "falta la herramienta del sistema: $tool"
  fi
done
if [ "$(sha256_of "$0")" = "sin-herramienta" ]; then
  install_hint "coreutils"
  die 1 "no hay sha256sum ni shasum"
fi
ok "requisitos del sistema (git, curl, sha256)"

# ---------------------------------------------------------------- 2. uv
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
if ! command -v uv >/dev/null 2>&1; then
  if [ "$CHECK" -eq 1 ]; then
    fail "uv no está instalado"
  else
    log "instalando uv con su instalador oficial (en el directorio del usuario, sin sudo)"
    if [ "$PLATFORM" = "windows" ]; then
      powershell.exe -NoProfile -ExecutionPolicy ByPass -Command \
        "irm https://astral.sh/uv/install.ps1 | iex" || die 2 "no se pudo instalar uv"
    else
      curl -LsSf https://astral.sh/uv/install.sh | sh || die 2 "no se pudo instalar uv"
    fi
    export PATH="$HOME/.local/bin:$PATH"
    command -v uv >/dev/null 2>&1 || die 2 "uv instalado pero no está en PATH (abre una terminal nueva)"
  fi
fi
if command -v uv >/dev/null 2>&1; then
  ok "uv $(uv --version | awk '{print $2}')"
fi

# ---------------------------------------------------------------- 3. Python y dependencias
if [ "$CHECK" -eq 1 ]; then
  if [ -d .venv ]; then ok "entorno .venv presente"; else fail "entorno .venv ausente"; fi
else
  uv python install 3.11 >/dev/null || die 2 "uv python install 3.11"
  SYNC_ARGS=(--python 3.11)
  [ "$WITH_AUDIO" -eq 1 ] && SYNC_ARGS+=(--group eval)
  uv sync "${SYNC_ARGS[@]}" || die 2 "uv sync"
  ok "Python 3.11 y dependencias (uv sync ${SYNC_ARGS[*]})"
fi

run_py() { uv run --no-sync python "$@"; }

# ---------------------------------------------------------------- 4. .env
if [ -f .env ]; then
  ok ".env existente (no se sobrescribe)"
elif [ "$CHECK" -eq 1 ]; then
  fail ".env ausente"
else
  cp .env.example .env
  ok ".env creado desde .env.example"
fi

# ---------------------------------------------------------------- 5. base de datos
if [ "$CHECK" -eq 1 ]; then
  if [ -f data/noticias.db ]; then ok "base de datos presente"; else fail "base de datos ausente"; fi
else
  if [ "$RESET_DB" -eq 1 ]; then
    if confirm "¿Borrar y recrear data/noticias.db?"; then
      rm -f data/noticias.db
      log "base de datos borrada"
    else
      skip "--reset-db cancelado"
    fi
  fi
  run_py -m app.cli db-init || die 2 "creación de la base de datos"
  ok "base de datos SQLite (esquema aplicado)"
fi

# ---------------------------------------------------------------- 6. corpus AmericasNLP
if [ "$CHECK" -eq 0 ]; then
  log "Corpus AmericasNLP 2021 asháninka–castellano (commit ${AMERICASNLP_COMMIT:0:7})."
  log "Uso académico con citas obligatorias: Ortega et al. (2020); Cushimariano Romano y"
  log "Sebastián Q. (2008); Mihas (2011). Ver CITATION.md. No se redistribuye en este repositorio."
fi
corpus_ok=1
for spec in "${CORPUS_FILES[@]}"; do
  IFS='|' read -r remote local sha <<<"$spec"
  set +e
  fetch_verified "$AMERICASNLP_RAW/$remote" "$CORPUS_DIR/$local" "$sha"
  rc=$?
  set -e
  case "$rc" in
    0) ;;
    3) die 3 "hash del corpus no coincide: $local" ;;
    4) corpus_ok=0; fail "corpus ausente o modificado: $local" ;;
    *) die 2 "descarga del corpus: $local" ;;
  esac
done
[ "$corpus_ok" -eq 1 ] && ok "corpus AmericasNLP verificado (6 archivos, SHA-256)"

# ---------------------------------------------------------------- 7. vocabulario MMS
if [ "$CHECK" -eq 0 ] && [ ! -f "$MMS_VOCAB_PATH" ]; then
  log "Vocabulario de $MMS_TTS_REPO. Licencia CC-BY-NC 4.0: uso NO comercial."
fi
set +e
fetch_verified "https://huggingface.co/$MMS_TTS_REPO/resolve/$MMS_TTS_REVISION/vocab.json" \
  "$MMS_VOCAB_PATH" "$MMS_VOCAB_SHA"
rc=$?
set -e
case "$rc" in
  0) ok "vocabulario mms-tts-cni verificado" ;;
  3) die 3 "hash del vocabulario MMS no coincide" ;;
  4) fail "vocabulario MMS ausente" ;;
  *) die 2 "descarga del vocabulario MMS" ;;
esac

# ---------------------------------------------------------------- 8. pre-commit
if [ -d .git ]; then
  if [ "$CHECK" -eq 1 ]; then
    if [ -f .git/hooks/pre-commit ]; then ok "pre-commit instalado"; else fail "pre-commit no instalado"; fi
  else
    uv run --no-sync pre-commit install >/dev/null || die 2 "pre-commit install"
    ok "pre-commit instalado"
  fi
else
  skip "pre-commit (no hay repositorio git)"
fi

# ---------------------------------------------------------------- 9. recursos YAML
if run_py -m app.cli validate-resources; then
  ok "recursos YAML válidos"
else
  die 2 "validación de recursos YAML"
fi

# ---------------------------------------------------------------- opcionales
if [ "$CHECK" -eq 0 ] && [ "$WITH_MONO" -eq 1 ]; then
  log "Corpus monolingüe iapucp (cita: Bustamante, Oncevay y Zariquiey, 2020)."
  if [ -d data/corpus/iapucp ]; then
    skip "corpus monolingüe ya descargado"
  else
    if git clone --depth 1 --filter=blob:none --sparse "$MONO_URL" data/corpus/iapucp >/dev/null 2>&1 \
      && git -C data/corpus/iapucp sparse-checkout set ShaShiYaYi/cni >/dev/null 2>&1; then
      ok "corpus monolingüe iapucp (cni)"
    else
      fail "descarga del corpus monolingüe"
    fi
  fi
fi

download_model() { # download_model <repo> <revisión> <tamaño legible>
  local repo="$1" rev="$2" size="$3"
  log "Modelo $repo ($size). Licencia CC-BY-NC 4.0: uso NO comercial."
  if [ "$PLATFORM" != "windows" ]; then
    log "espacio libre: $(df -h . | awk 'NR==2{print $4}')"
  fi
  if ! confirm "¿Descargar $repo ($size)?"; then
    skip "descarga de $repo"
    return 0
  fi
  run_py -m eval.fase1.download_models "$repo" "$rev" || die 2 "descarga de $repo"
  ok "modelo $repo@${rev:0:7}"
}

if [ "$CHECK" -eq 0 ] && [ "$WITH_AUDIO" -eq 1 ]; then
  download_model "$MMS_TTS_REPO" "$MMS_TTS_REVISION" "~150 MB"
fi
if [ "$CHECK" -eq 0 ] && [ "$WITH_ASR" -eq 1 ]; then
  download_model "$MMS_ASR_REPO" "$MMS_ASR_REVISION" "~3,9 GB"
fi

if [ "$CHECK" -eq 0 ] && [ "$WITH_DATA" -eq 1 ]; then
  run_py -m app.cli corpus report || die 2 "informe del corpus"
  run_py -m app.cli corpus extract || die 2 "extracción de candidatos"
  if compgen -G "data/news/*.json" >/dev/null; then
    run_py -m app.cli import data/news/ || die 2 "importación de noticias"
  else
    log "no hay noticias en data/news/: se importan 20 oraciones de dev como pseudo-noticias de prueba"
    run_py -m app.cli import --from-corpus dev --limit 20 || die 2 "importación desde el corpus"
  fi
  run_py -m app.cli process --all || die 2 "procesamiento"
  ok "datos importados y procesados"
fi

# ---------------------------------------------------------------- 10. prueba rápida
if [ "$CHECK" -eq 0 ]; then
  if uv run --no-sync pytest -q -m smoke --no-header -p no:cacheprovider; then
    ok "prueba rápida (pytest -m smoke)"
  else
    die 2 "prueba rápida (pytest -m smoke)"
  fi
fi

print_summary
for line in "${SUMMARY[@]}"; do
  if [[ "$line" == FALLO* ]]; then exit 2; fi
done
exit 0
