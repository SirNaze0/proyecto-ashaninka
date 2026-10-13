"""Fase 6: la documentación de despliegue y de arquitectura coincide con el código y las mediciones."""

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
REPO = ROOT.parent

pytestmark = pytest.mark.smoke


def _leer(ruta: str) -> str:
    return (ROOT / ruta).read_text(encoding="utf-8").replace("\r\n", "\n")


# ------------------------------------------------------------------ architecture.md (generado)
def test_architecture_md_esta_al_dia_con_las_mediciones():
    from eval.fase6 import architecture

    esperado = architecture.render(architecture.cargar()).replace("\r\n", "\n")
    assert _leer("docs/architecture.md") == esperado, (
        "regenerar con: uv run python -m eval.fase6.architecture"
    )


def test_architecture_md_dice_que_no_esta_medido():
    doc = _leer("docs/architecture.md")
    for pendiente in ("servidor real", "Android de gama media", "docker build"):
        assert pendiente in doc
    assert "pendiente" in doc and "<!--" not in doc


# ------------------------------------------------------------------ rutas administrativas
@pytest.fixture
def clasificacion(temp_db, monkeypatch):
    """(administrativas, abiertas) por COMPORTAMIENTO: una ruta es administrativa si, sin token,
    responde 403 antes de mirar el cuerpo. Se recorre el esquema OpenAPI (no los internos de FastAPI)."""
    monkeypatch.setenv("NA_TTS_ENGINE", "fake")
    monkeypatch.setenv(
        "NA_RATE_LIMIT_PER_MIN", "0"
    )  # el límite de tasa daría 429 y falsearía el 403
    for var in ("NA_EXPORT_TOKEN", "NA_EXPERIMENT_PILOTO", "NA_ENV"):
        monkeypatch.delenv(var, raising=False)
    from app.main import app
    from fastapi.testclient import TestClient

    cliente = TestClient(app)
    admin, abiertas = set(), set()
    for ruta, ops in cliente.get("/openapi.json").json()["paths"].items():
        if not ruta.startswith("/api/"):
            continue
        for metodo in ops:
            metodo = metodo.upper()
            if metodo not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                continue
            url = re.sub(r"\{[^}]+\}", "1", ruta)
            cuerpo = {} if metodo in {"POST", "PUT", "PATCH"} else None
            r = cliente.request(metodo, url, json=cuerpo)
            (admin if r.status_code == 403 else abiertas).add((metodo, ruta))
    return admin, abiertas


def test_toda_ruta_administrativa_esta_documentada_en_deployment(clasificacion):
    admin, _ = clasificacion
    doc = _leer("docs/deployment.md")
    assert {
        ("GET", "/api/events/summary"),
        ("POST", "/api/news"),
        ("GET", "/api/experiment/export"),
    } <= admin
    for _metodo, ruta in admin:
        base = ruta.split("{")[0].rstrip("/")  # /api/news/{id}/process -> /api/news
        assert base in doc, f"{ruta} es administrativa y deployment.md no la menciona ({base})"


# Escrituras públicas A PROPÓSITO (las usa la PWA); cualquier otra debe ser administrativa
ESCRITURAS_PUBLICAS = {
    ("POST", "/api/events"),
    ("POST", "/api/experiment/sessions"),
    ("POST", "/api/experiment/sessions/{code}/finish"),
    ("POST", "/api/experiment/responses"),
}


def test_no_hay_escrituras_sin_proteger_fuera_de_la_lista_consciente(clasificacion):
    _, abiertas = clasificacion
    escrituras = {k for k in abiertas if k[0] in {"POST", "PUT", "PATCH", "DELETE"}}
    assert escrituras == ESCRITURAS_PUBLICAS, (
        "una escritura nueva debe protegerse con require_admin o añadirse aquí a conciencia: "
        f"{sorted(escrituras ^ ESCRITURAS_PUBLICAS)}"
    )


def test_lecturas_abiertas_no_exponen_datos_internos(clasificacion):
    _, abiertas = clasificacion
    lecturas = {r for (m, r) in abiertas if m == "GET"}
    permitidas = {
        "/api/health",
        "/api/health/ready",
        "/api/catalog",
        "/api/catalog/{news_id}",
        "/api/catalog/{news_id}/meta",
        "/api/experiment/config",
        "/api/experiment/sessions/{code}",
        "/api/synthesize/{news_id}",
    }
    assert lecturas == permitidas, (
        f"lectura pública distinta de la revisada: {sorted(lecturas ^ permitidas)}"
    )


# ------------------------------------------------------------------ deployment.md
def test_deployment_md_trae_los_comandos_y_variables_clave():
    doc = _leer("docs/deployment.md")
    for comando in (
        "docker compose --profile setup run --rm setup",
        "docker compose up -d --build",
        "scripts/backup.sh",
        "/api/health/ready",
        "x-admin-token",
        "app.cli experiment export",
        "app.batch build --all",
    ):
        assert comando in doc, comando
    prod = _leer(".env.production.example")
    for var in (
        "NA_ADMIN_TOKEN",
        "NA_DOMAIN",
        "NA_RATE_LIMIT_PER_MIN",
        "NA_TTS_WORKERS",
        "NA_EXPERIMENT_PILOTO",
        "NA_ENV",
    ):
        assert var in doc or var in prod
    for var in (
        "NA_ADMIN_TOKEN",
        "NA_DOMAIN",
        "NA_RATE_LIMIT_PER_MIN",
        "NA_TTS_WORKERS",
        "NA_EXPERIMENT_PILOTO",
    ):
        assert var in doc, f"deployment.md no explica {var}"


def test_deployment_md_es_honesto_sobre_lo_no_verificado():
    doc = _leer("docs/deployment.md")
    seccion = doc[doc.index("## 8. Verificación de este documento") :]
    for no_verificado in (
        "docker build",
        "Let's Encrypt",
        "caddy validate",
        "persona ajena",
        "6.3",
    ):
        assert no_verificado in seccion, no_verificado


def test_los_volumenes_y_el_modelo_documentados_existen_en_compose():
    import yaml

    compose = yaml.safe_load(_leer("docker-compose.yml"))
    doc = _leer("docs/deployment.md")
    for vol in compose["volumes"]:
        assert vol in doc, f"el volumen {vol} no está documentado"


def test_el_numero_de_limitacion_citado_existe_y_dice_lo_que_se_cita():
    lim = _leer("docs/limitations.md")
    numeros = [int(m) for m in re.findall(r"^(\d+)\. ", lim, re.M)]
    assert numeros == list(range(1, len(numeros) + 1)), (
        "la numeración de limitaciones tiene huecos o repeticiones"
    )
    assert len(numeros) >= 69
    assert re.search(
        r"^60\. \*\*`GET /api/experiment/sessions/\{código\}` se puede enumerar", lim, re.M
    )
    assert re.search(r"^44\. \*\*El Service Worker solo funciona con HTTPS", lim, re.M)
    assert re.search(r"^59\. \*\*La imagen Docker no se construyó", lim, re.M)


# ------------------------------------------------------------------ enlaces y licencias
@pytest.mark.parametrize("doc", ["README.md", "docs/deployment.md", "docs/architecture.md"])
def test_los_enlaces_relativos_existen(doc):
    base = (ROOT / doc).parent
    rotos = []
    for destino in re.findall(r"\]\(([^)\s]+)\)", _leer(doc)):
        if destino.startswith(("http://", "https://", "#", "mailto:")):
            continue
        ruta = destino.split("#")[0]
        if ruta and not (base / ruta).exists():
            rotos.append(destino)
    assert not rotos, f"enlaces rotos en {doc}: {rotos}"


def test_el_readme_cubre_las_seis_fases_y_los_dos_caminos():
    r = _leer("README.md")
    for fase in range(1, 7):
        assert f"| **{fase}** " in r, f"falta la fase {fase} en el mapa"
        assert f"resumen_fase{fase}" in r
    assert "De cero a funcionando" in r and "docker compose up -d --build" in r and "./init.sh" in r
    assert "scripts/verify.sh" in r and "x-admin-token" in r


def test_licenses_refleja_las_dependencias_reales():
    lic = _leer("LICENSES.md")
    assert (
        "Solo en evaluación (grupo `eval`) |" not in lic.split("PyTorch")[1].split("\n")[0]
    )  # torch ya es principal
    assert "Dependencias principales" in lic
    for nuevo in ("Caddy", "Docker", "CC-BY-NC"):
        assert nuevo in lic
    # las dependencias principales que declara pyproject están entre las licencias o son transitorias
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "torch" in pyproject.split("[dependency-groups]")[0]


# ------------------------------------------------------------------ resumen y resultados
def test_resumen_fase6_coincide_con_fase_6_json():
    resultados = ROOT / "eval" / "results" / "fase_6.json"
    resumen = ROOT / "resumen_fase6.md"
    if not resultados.exists() or not resumen.exists():
        pytest.skip("aún no se generó el cierre de la Fase 6")
    d = json.loads(resultados.read_text(encoding="utf-8"))
    texto = resumen.read_text(encoding="utf-8")
    assert (REPO / "resumen_fase6.md").read_text(
        encoding="utf-8"
    ) == texto  # raíz y noticias-ashaninka/
    estado = d["docker"]["build"]["estado"]
    if estado == "pendiente":
        assert "demonio" in texto and "no se construyó" in texto.lower()
    elif estado == "ok":
        assert "se construyó" in texto.lower()
    for k, c in d["criterios"].items():
        if c["cumple"] is False:
            assert k in texto, f"el criterio incumplido {k} debe figurar en el resumen"
