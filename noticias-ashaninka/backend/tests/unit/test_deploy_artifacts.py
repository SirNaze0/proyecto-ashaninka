"""Fase 6: validación de los artefactos de despliegue sin necesidad del demonio de Docker.

Dockerfile, docker-compose.yml, Caddyfile y .dockerignore se leen y se comprueban contra lo que el
sistema necesita de verdad (archivos que se copian, rutas montadas, variables documentadas). Si el
CLI de Docker existe, ``docker compose config`` valida además el Compose real. El build y el
arranque reales de los contenedores solo pueden hacerse con el demonio activo y quedan registrados
como «pendiente» en ``eval/results/fase_6.json`` cuando no lo está.
"""

import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
REPO = ROOT.parent

pytestmark = pytest.mark.smoke


def _leer(nombre: str) -> str:
    return (ROOT / nombre).read_text(encoding="utf-8")


# ------------------------------------------------------------------ .dockerignore como Docker
def _regex(patron: str) -> re.Pattern:
    """Patrón de .dockerignore (Go filepath.Match + `**`) a expresión regular."""
    p = patron.strip("/")
    out, i = "", 0
    while i < len(p):
        if p.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
        elif p.startswith("**", i):
            out += ".*"
            i += 2
        elif p[i] == "*":
            out += "[^/]*"
            i += 1
        elif p[i] == "?":
            out += "[^/]"
            i += 1
        else:
            out += re.escape(p[i])
            i += 1
    return re.compile(out)


def ignorado(ruta: str, reglas: list[str]) -> bool:
    """Una ruta se excluye si el patrón coincide con ella o con alguna carpeta que la contiene;
    `!patrón` la vuelve a incluir (gana la última regla que coincida)."""
    partes = ruta.strip("/").split("/")
    prefijos = ["/".join(partes[: i + 1]) for i in range(len(partes))]
    resultado = False
    for regla in reglas:
        negada = regla.startswith("!")
        rx = _regex(regla[1:] if negada else regla)
        if any(rx.fullmatch(p) for p in prefijos):
            resultado = not negada
    return resultado


def _reglas_dockerignore() -> list[str]:
    return [
        ln.strip()
        for ln in _leer(".dockerignore").splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    ]


def test_el_evaluador_de_dockerignore_se_comporta_como_docker():
    r = ["models/", "**/out/", "*.zip", ".env", ".env.*", "!.env.example", "frontend/node_modules/"]
    assert ignorado("models/facebook__mms-tts-cni/model.safetensors", r)
    assert ignorado("eval/fase5/out/export/bloques.csv", r) and ignorado("a/b/out/x", r)
    assert ignorado(".env", r) and ignorado(".env.production", r)
    assert not ignorado(".env.example", r)  # la negación vuelve a incluirla
    assert ignorado("kit.zip", r) and not ignorado("docs/kit.zip", r)  # `*.zip` solo en la raíz
    assert ignorado("frontend/node_modules/preact/index.js", r)
    assert not ignorado("backend/app/main.py", r)


# ------------------------------------------------------------------ Dockerfile
@pytest.fixture(scope="module")
def dockerfile() -> str:
    return _leer("Dockerfile")


def _instrucciones(texto: str) -> list[tuple[str, str]]:
    """(INSTRUCCIÓN, argumentos) uniendo las líneas continuadas con barra invertida."""
    logicas, actual = [], ""
    for ln in texto.splitlines():
        if ln.lstrip().startswith("#") and not actual:
            continue
        actual += ln.rstrip("\\").rstrip() + " " if ln.rstrip().endswith("\\") else ln + "\n"
        if not ln.rstrip().endswith("\\"):
            logicas.append(actual.strip())
            actual = ""
    out = []
    for lg in logicas:
        if lg:
            nombre, _, resto = lg.partition(" ")
            out.append((nombre.upper(), resto.strip()))
    return out


def test_dockerfile_tiene_dos_etapas_y_versiones_fijadas(dockerfile):
    ins = _instrucciones(dockerfile)
    froms = [a for n, a in ins if n == "FROM"]
    assert len(froms) == 2
    assert froms[0].endswith("AS frontend") and froms[1].endswith("AS app")
    assert "node:" in froms[0] and "python:" in froms[1]
    for f in froms:
        assert ":latest" not in f
    args = dict(a.split("=", 1) for n, a in ins if n == "ARG" and "=" in a)
    assert args["PYTHON_VERSION"] == "3.11"  # requires-python = ">=3.11,<3.12"
    assert re.fullmatch(r"\d+(\.\d+)*", args["UV_VERSION"]) and re.fullmatch(
        r"\d+", args["NODE_VERSION"]
    )
    assert any(n == "COPY" and "--from=frontend" in a and "frontend/dist" in a for n, a in ins)


def test_dockerfile_instala_espeak_ffmpeg_y_uv_con_el_lock(dockerfile):
    ins = _instrucciones(dockerfile)
    run = " ".join(a for n, a in ins if n == "RUN")
    for paquete in ("espeak-ng", "ffmpeg", "libsndfile1"):
        assert paquete in run
    assert "--no-install-recommends" in run and "rm -rf /var/lib/apt/lists" in run
    assert "npm ci" in run and "npm run build" in run
    assert (
        run.count("uv sync --frozen --no-dev") == 2
    )  # sin el proyecto (capa de dependencias) y con él
    assert "ghcr.io/astral-sh/uv" in dockerfile


def test_dockerfile_usuario_sin_privilegios_healthcheck_y_arranque(dockerfile):
    ins = _instrucciones(dockerfile)
    usuarios = [a for n, a in ins if n == "USER"]
    assert usuarios == ["app"]  # nunca root al final
    idx = {n: i for i, (n, _) in enumerate(ins)}
    assert idx["USER"] > max(
        i for i, (n, a) in enumerate(ins) if n == "RUN"
    )  # los RUN van como root
    assert any(n == "HEALTHCHECK" and "/api/health" in a and "--start-period" in a for n, a in ins)
    cmd = next(a for n, a in ins if n == "CMD")
    assert (
        "uvicorn" in cmd and "app.main:app" in cmd and "--proxy-headers" in cmd and "0.0.0.0" in cmd
    )
    env = " ".join(a for n, a in ins if n == "ENV")
    assert "NA_ENV=production" in env and "NA_STATIC_DIR=/srv/static" in env
    assert "EXPOSE" in dockerfile and "8000" in dockerfile


def test_dockerfile_no_hornea_secretos_ni_modelos(dockerfile):
    copias = [a for n, a in _instrucciones(dockerfile) if n == "COPY"]
    for c in copias:
        assert (
            ".env" not in c.replace(".env.example", "") and "models/" not in c and "data/" not in c
        )
    assert not re.search(r"(TOKEN|SECRET|PASSWORD)\s*=\s*\S", dockerfile)  # ni valores de secretos
    assert "NA_ADMIN_TOKEN" not in dockerfile


def test_todo_lo_que_copia_el_dockerfile_existe_y_no_esta_excluido(dockerfile):
    reglas = _reglas_dockerignore()
    for n, a in _instrucciones(dockerfile):
        if n != "COPY" or "--from=" in a:
            continue
        *fuentes, _destino = a.split()
        for f in fuentes:
            assert (ROOT / f).exists(), f"el Dockerfile copia {f}, que no existe"
            assert not ignorado(f.rstrip("/"), reglas), f"{f} está excluido por .dockerignore"


def test_dockerignore_deja_pasar_lo_que_el_runtime_necesita_y_excluye_lo_sensible():
    reglas = _reglas_dockerignore()
    necesarios = [
        "backend/app/main.py",
        "backend/app/pipeline/normalize/resources/numerals_cni.yaml",
        "backend/tests/fixtures/mms_cni_vocab.json",  # lo lee app.config.MMS_VOCAB en producción
        "frontend/package-lock.json",
        "frontend/src/app/App.tsx",
        "frontend/public/models/presentadora_provisional.vrm",
        "eval/fase1/download_models.py",
        "models.lock.json",
        "uv.lock",
    ]
    for ruta in necesarios:
        assert not ignorado(ruta, reglas), f"{ruta} no debe excluirse"
        assert (ROOT / ruta).exists() or ruta.endswith("numerals_cni.yaml"), ruta
    secretos = [
        ".env",
        ".env.production",
        "data/noticias.db",
        "data/noticias.db-wal",
        "data/export/bloques.csv",
        "data/corpus/americasnlp2021/train.cni",
        "models/facebook__mms-tts-cni/model.safetensors",
        "static/audio/4f/x.opus",
        "frontend/node_modules/preact/package.json",
        "frontend/dist/index.html",
        "eval/fase5/out/export/bloques.csv",
        ".git/config",
        ".venv/pyvenv.cfg",
    ]
    for ruta in secretos:
        assert ignorado(ruta, reglas), f"{ruta} debe excluirse del contexto de build"


# ------------------------------------------------------------------ docker-compose.yml
@pytest.fixture(scope="module")
def compose() -> dict:
    return yaml.safe_load(_leer("docker-compose.yml"))


def test_compose_solo_publica_caddy(compose):
    s = compose["services"]
    assert set(s) == {"app", "caddy", "setup"}
    assert "ports" not in s["app"] and s["app"]["expose"] == [
        "8000"
    ]  # la app solo en la red interna
    assert {"80:80", "443:443"} <= set(s["caddy"]["ports"])
    assert "ports" not in s["setup"]


def test_compose_endurece_los_contenedores(compose):
    for nombre in ("app", "setup"):
        assert compose["services"][nombre]["security_opt"] == ["no-new-privileges:true"]
        assert compose["services"][nombre]["cap_drop"] == ["ALL"]
    assert compose["services"]["caddy"]["security_opt"] == ["no-new-privileges:true"]
    assert compose["services"]["app"]["restart"] == "unless-stopped"
    assert compose["services"]["caddy"]["restart"] == "unless-stopped"
    assert "mem_limit" in compose["services"]["app"]
    assert re.fullmatch(
        r"caddy:\d+\.\d+(-alpine)?", compose["services"]["caddy"]["image"]
    )  # versión fijada


def test_compose_espera_a_que_la_app_este_sana_y_la_comprueba(compose):
    assert compose["services"]["caddy"]["depends_on"]["app"] == {"condition": "service_healthy"}
    hc = compose["services"]["app"]["healthcheck"]
    assert "/api/health" in " ".join(hc["test"]) and hc["start_period"] == "90s"


def test_compose_rutas_y_modo_de_produccion_ganan_al_env(compose):
    env = compose["services"]["app"]["environment"]
    assert env["NA_ENV"] == "production" and env["NA_TRUST_PROXY"] == "true"
    montajes = {v.split(":")[1] for v in compose["services"]["app"]["volumes"]}
    assert montajes == {"/data", "/srv/static", "/models", "/export"}
    # cada ruta de datos del contenedor cae dentro de un volumen con nombre (no se pierde al recrear)
    assert env["NA_DATABASE_URL"] == "sqlite:////data/noticias.db"
    for var, ruta in (
        ("NA_STATIC_DIR", env["NA_STATIC_DIR"]),
        ("NA_MODELS_DIR", env["NA_MODELS_DIR"]),
    ):
        assert any(ruta == m or ruta.startswith(m + "/") for m in montajes), var
    assert env["NA_FRONTEND_DIST"] == "/app/frontend/dist"  # va en la imagen, no en un volumen


def test_compose_volumenes_declarados_y_setup_verifica_el_modelo(compose):
    declarados = set(compose["volumes"])
    usados = {
        v.split(":")[0]
        for sv in compose["services"].values()
        for v in sv.get("volumes", [])
        if not v.startswith(".")
    }
    assert (
        usados <= declarados
        and {"na_data", "na_static", "na_models", "na_export", "caddy_data"} <= declarados
    )
    setup = compose["services"]["setup"]
    assert setup["profiles"] == ["setup"] and setup["image"] == compose["services"]["app"]["image"]
    assert setup["command"] == ["python", "scripts/verify_models.py", "--descargar"]
    assert "./Caddyfile:/etc/caddy/Caddyfile:ro" in compose["services"]["caddy"]["volumes"]


@pytest.mark.skipif(shutil.which("docker") is None, reason="no hay CLI de docker")
def test_docker_compose_config_valida_el_archivo_real(tmp_path):
    """`docker compose config` no necesita el demonio: valida sintaxis, anclas y variables."""
    for nombre in ("docker-compose.yml", "Caddyfile"):
        shutil.copy(ROOT / nombre, tmp_path / nombre)
    shutil.copy(ROOT / ".env.production.example", tmp_path / ".env")
    r = subprocess.run(
        ["docker", "compose", "--project-directory", str(tmp_path), "config", "--format", "json"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode == 0, r.stderr
    cfg = json.loads(r.stdout)
    assert cfg["services"]["app"]["environment"]["NA_ENV"] == "production"
    assert cfg["services"]["app"]["environment"]["NA_TTS_WORKERS"] == "1"  # del .env de producción


# ------------------------------------------------------------------ Caddyfile
@pytest.fixture(scope="module")
def caddyfile() -> str:
    return _leer("Caddyfile")


def _sin_comentarios(t: str) -> str:
    return "\n".join(ln for ln in t.splitlines() if not ln.strip().startswith("#"))


def test_caddyfile_llaves_balanceadas_y_sin_tabs_mezclados(caddyfile):
    codigo = _sin_comentarios(caddyfile)
    assert codigo.count("{") == codigo.count("}")
    nivel = 0
    for ln in codigo.splitlines():
        nivel -= (
            ln.count("}")
            - (1 if ln.strip().startswith("}") and ln.count("}") > ln.count("{") else 0) * 0
        )
        nivel += ln.count("{")
    assert nivel == codigo.count("{") - codigo.count("}") == 0


def test_caddyfile_sitio_https_automatico_y_proxy_a_la_app(caddyfile):
    codigo = _sin_comentarios(caddyfile)
    assert re.search(r"^\{\$NA_DOMAIN:localhost\} \{", codigo, re.M)
    assert "tls " not in codigo  # sin `tls`, Caddy obtiene el certificado solo
    proxies = re.findall(r"reverse_proxy app:8000", codigo)
    assert len(proxies) == 3 and codigo.count("header_up -Accept-Encoding") == 3
    assert "Strict-Transport-Security" in codigo and "-Server" in codigo
    assert "max_size" in codigo


def test_caddyfile_comprime_solo_texto_y_respeta_range_del_audio(caddyfile):
    codigo = _sin_comentarios(caddyfile)
    encode = re.search(r"encode \{(.*?)\n\t\}", codigo, re.S).group(1)
    assert "zstd" in encode and "gzip" in encode
    for tipo in ("text/*", "application/javascript*", "application/json*", "image/svg+xml*"):
        assert f"header Content-Type {tipo}" in encode
    for no_comprimir in ("audio", "ndjson", "octet-stream", "video"):
        assert no_comprimir not in encode  # el audio ya va comprimido; NDJSON es streaming
    # el audio se sirve con caché inmutable (el nombre lleva el hash) y sin tocar el cuerpo
    audio = re.search(r"@audio path (\S+)\n\thandle @audio \{(.*?)\n\t\}", codigo, re.S)
    assert audio.group(1) == "/static/audio/*"
    assert "public, max-age=31536000, immutable" in audio.group(2)


def test_caddyfile_revalida_la_pwa_y_los_manifiestos(caddyfile):
    codigo = _sin_comentarios(caddyfile)
    m = re.search(r"@revalidar path (.*)\n", codigo)
    for ruta in ("/index.html", "/sw.js", "/manifest.webmanifest", "/static/news/*"):
        assert ruta in m.group(1).split()
    assert 'header_down Cache-Control "no-cache"' in codigo
    assert "/assets" not in m.group(1)  # los assets con hash los marca la app como inmutables


@pytest.mark.skipif(shutil.which("caddy") is None, reason="no hay binario de caddy")
def test_caddy_validate_acepta_el_archivo(tmp_path):
    r = subprocess.run(
        ["caddy", "validate", "--config", str(ROOT / "Caddyfile"), "--adapter", "caddyfile"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode == 0, r.stderr


# ------------------------------------------------------------------ variables de entorno
def _variables_de(texto: str) -> set[str]:
    return set(re.findall(r"\bNA_[A-Z0-9_]+\b", texto))


def test_toda_variable_NA_que_lee_el_codigo_esta_documentada():
    usadas: set[str] = set()
    for p in (ROOT / "backend" / "app").rglob("*.py"):
        usadas |= _variables_de(p.read_text(encoding="utf-8"))
    documentadas = _variables_de(_leer(".env.example"))
    assert usadas, "no se encontraron variables NA_* en el código"
    faltan = usadas - documentadas
    assert not faltan, f"variables que el código lee y .env.example no documenta: {sorted(faltan)}"


def test_el_env_de_produccion_cubre_lo_que_usa_compose_y_no_trae_secretos():
    prod = _leer(".env.production.example")
    asignadas = dict(re.findall(r"^(NA_[A-Z0-9_]+)=(.*)$", prod, re.M))
    assert asignadas["NA_ADMIN_TOKEN"] == ""  # el secreto lo genera quien despliega
    assert asignadas["NA_EXPERIMENT_PILOTO"] == "false"
    assert asignadas["NA_TTS_WORKERS"] == "1" and asignadas["NA_TTS_PRELOAD"] == "true"
    compose = _leer("docker-compose.yml")
    for var in set(re.findall(r"\$\{(NA_[A-Z0-9_]+)", compose)):
        assert var in asignadas, f"compose usa ${{{var}}} y .env.production.example no lo define"
    ejemplo = _leer(".env.example")
    assert re.search(r"^NA_ADMIN_TOKEN=$", ejemplo, re.M)  # vacío: nunca un token de ejemplo válido


# ------------------------------------------------------------------ hashes de los modelos
def _cargar_script(nombre: str):
    spec = importlib.util.spec_from_file_location(nombre, ROOT / "scripts" / f"{nombre}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[nombre] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def vm():
    return _cargar_script("verify_models")


def test_models_lock_coincide_con_las_revisiones_fijadas(vm):
    from app.config import MMS_ASR_REVISION, MMS_TTS_REVISION

    lock = json.loads((ROOT / "models.lock.json").read_text(encoding="utf-8"))
    tts = lock["modelos"]["facebook/mms-tts-cni"]
    assert tts["revision"] == MMS_TTS_REVISION and tts["necesario_para"] == "servicio"
    assert lock["modelos"]["facebook/mms-1b-all"]["revision"] == MMS_ASR_REVISION
    assert {"model.safetensors", "config.json", "vocab.json"} <= set(tts["archivos"])
    for m in lock["modelos"].values():
        for nombre, a in m["archivos"].items():
            assert re.fullmatch(r"[0-9a-f]{64}", a["sha256"]) and a["bytes"] > 0, nombre


def test_verify_models_detecta_cambios_faltas_y_omite_lo_opcional(vm, tmp_path):
    def sha(b):
        return hashlib.sha256(b).hexdigest()

    modelos = tmp_path / "models"
    (modelos / "a__svc").mkdir(parents=True)
    (modelos / "a__svc" / "w.bin").write_bytes(b"pesos")
    (modelos / "a__svc" / "c.json").write_bytes(b"{}")
    lock = {
        "modelos": {
            "a/svc": {
                "necesario_para": "servicio",
                "revision": "r",
                "archivos": {
                    "w.bin": {"sha256": sha(b"pesos"), "bytes": 5},
                    "c.json": {"sha256": sha(b"{}"), "bytes": 2},
                },
            },
            "b/eval": {
                "necesario_para": "evaluacion",
                "revision": "r",
                "archivos": {"x": {"sha256": "0" * 64, "bytes": 1}},
            },
        }
    }
    r = vm.verificar(lock, modelos)
    assert {(x["modelo"], x["estado"]) for x in r} == {("a/svc", "ok"), ("b/eval", "omitido")}
    assert vm.codigo_de_salida(r) == vm.OK  # un modelo de evaluación ausente no es error
    (modelos / "a__svc" / "w.bin").write_bytes(b"PESOS")  # mismo tamaño, otro contenido
    assert vm.codigo_de_salida(vm.verificar(lock, modelos)) == vm.DISTINTO
    (modelos / "a__svc" / "w.bin").write_bytes(b"pe")  # truncado
    assert any(x.get("motivo") == "tamaño" for x in vm.verificar(lock, modelos))
    (modelos / "a__svc" / "w.bin").unlink()
    assert vm.codigo_de_salida(vm.verificar(lock, modelos)) == vm.FALTA
    shutil.rmtree(modelos / "a__svc")
    assert (
        vm.codigo_de_salida(vm.verificar(lock, modelos)) == vm.FALTA
    )  # el del servicio es obligatorio
    assert vm.verificar(lock, modelos, solo_servicio=True) and all(
        x["modelo"] == "a/svc" for x in vm.verificar(lock, modelos, True)
    )


def test_los_modelos_locales_coinciden_con_el_lock_si_estan_descargados(vm):
    if not (ROOT / "models" / "facebook__mms-tts-cni").is_dir():
        pytest.skip("modelo de voz no descargado")
    lock = json.loads((ROOT / "models.lock.json").read_text(encoding="utf-8"))
    r = vm.verificar(lock, ROOT / "models", solo_servicio=True)
    assert vm.codigo_de_salida(r) == vm.OK, r


# ------------------------------------------------------------------ scripts
def _bash_utilizable() -> bool:
    """En Windows `bash` puede ser el lanzador de WSL sin distribución: solo vale si ejecuta."""
    if not shutil.which("bash"):
        return False
    try:
        return (
            subprocess.run(["bash", "-c", "exit 0"], capture_output=True, timeout=20).returncode
            == 0
        )
    except (OSError, subprocess.TimeoutExpired):
        return False


@pytest.mark.parametrize("nombre", ["init.sh", "scripts/backup.sh", "scripts/verify.sh"])
def test_scripts_de_shell_con_sintaxis_valida_y_modo_estricto(nombre):
    texto = _leer(nombre)
    assert texto.startswith("#!/usr/bin/env bash") and "set -euo pipefail" in texto.replace(
        "set -uo pipefail", "set -euo pipefail"
    )
    if _bash_utilizable():
        r = subprocess.run(["bash", "-n", str(ROOT / nombre)], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr


def test_backup_usa_la_cli_y_no_copia_el_archivo_en_caliente():
    sh = _leer("scripts/backup.sh")
    assert "app.cli db-backup" in sh and "docker compose cp" in sh
    assert "cp " not in sh.replace(
        "compose cp", ""
    )  # nada de `cp noticias.db`: no es consistente en WAL


def test_verify_ejecuta_toda_la_bateria():
    sh = _leer("scripts/verify.sh")
    for paso in (
        "ruff check",
        "ruff format --check",
        "pytest",
        "vitest",
        "npm run typecheck",
        "npm run build",
        "playwright test",
        "eval.fase6.run",
    ):
        assert paso in sh, paso


# ------------------------------------------------------------------ CLI db-backup
def test_db_backup_es_consistente_no_pisa_y_verifica(temp_db, tmp_path):
    from app.cli import main
    from app.db.models import News, Provenance
    from sqlmodel import Session

    with Session(temp_db) as s:
        n = News(titulo_cni="t", cuerpo_cni="Okantzi kemetsa.")
        n.provenance = Provenance(tipo="traduccion_automatica")
        s.add(n)
        s.commit()
    destino = tmp_path / "copias" / "b.db"
    assert main(["db-backup", "--out", str(destino)]) == 0 and destino.is_file()
    import sqlite3

    con = sqlite3.connect(destino)
    assert con.execute("select count(*) from news").fetchone()[0] == 1
    assert con.execute("pragma integrity_check").fetchone()[0] == "ok"
    con.close()
    assert main(["db-backup", "--out", str(destino)]) == 2  # no sobrescribe sin --force
    assert main(["db-backup", "--out", str(destino), "--force"]) == 0


def test_db_backup_rechaza_lo_que_no_es_sqlite_ni_existe(temp_db, tmp_path, monkeypatch):
    from app.cli import main

    monkeypatch.setenv("NA_DATABASE_URL", f"sqlite:///{(tmp_path / 'no_existe.db').as_posix()}")
    assert main(["db-backup", "--out", str(tmp_path / "x.db")]) == 2
    monkeypatch.setenv("NA_DATABASE_URL", "postgresql://u:p@h/db")
    assert main(["db-backup", "--out", str(tmp_path / "y.db")]) == 2
