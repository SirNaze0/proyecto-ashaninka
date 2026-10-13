"""Fase 6: la app arranca y sirve con SOLO lo que el Dockerfile copia a la imagen.

No hay demonio de Docker en todas partes, así que se reproduce el *layout* de la imagen en una
carpeta temporal (``COPY backend``, ``eval``, ``scripts/verify_models.py``, ``models.lock.json`` y la
PWA compilada; sin ``data/``, ``docs/``, el ``.env`` ni los modelos) y se arranca la aplicación desde
ahí con las variables de producción del contenedor. Si el código dependiera de algo que la imagen
no lleva (un archivo de ``data/``, ``docs/``, el ``.env`` de desarrollo...), esto lo delata.
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]

SCRIPT = r"""
import json, os
from pathlib import Path
import app
assert str(Path(app.__file__).resolve()).startswith(os.environ["IMG"]), app.__file__
from fastapi.testclient import TestClient
from app.main import app as asgi

ADMIN = {"x-admin-token": os.environ["NA_ADMIN_TOKEN"]}
NEWS = {
    "titulo_cni": "Kipatsi", "cuerpo_cni": "Okantzi kemetsa. Tzimatsi kitaiteri.",
    "variante_dialectal": "desconocida", "fuente_original": "prueba",
    "procedencia": {"tipo": "traduccion_automatica", "sistema": "x", "version": "1"},
}
out = {}
with TestClient(asgi, base_url="https://localhost") as c:  # https: HSTS y esquema como detrás de Caddy
    out["health"] = c.get("/api/health").json()["status"]
    out["ready"] = c.get("/api/health/ready").json()
    pwa = c.get("/")
    out["pwa"] = [pwa.status_code, "id=\"app\"" in pwa.text, pwa.headers.get("cache-control")]
    asset = c.get("/assets/app-abc123.js")
    out["asset"] = [asset.status_code, asset.headers.get("cache-control")]
    out["hsts"] = c.get("/api/health").headers.get("strict-transport-security")
    out["docs"] = [c.get("/docs").status_code, c.get("/openapi.json").status_code]
    out["cerrado"] = [c.get("/api/events/summary").status_code, c.get("/api/news").status_code]
    out["abierto"] = c.get("/api/events/summary", headers=ADMIN).status_code
    nid = c.post("/api/news", json=NEWS, headers=ADMIN).json()["id"]
    out["proceso"] = c.post(f"/api/news/{nid}/process", headers=ADMIN).json()["estado"]
    from app.batch.service import run_batch
    run_batch([nid])
    m = c.get(f"/static/news/{nid}/manifest.json")
    seg = m.json()["segments"][0]
    audio = c.get(seg["audio"]["opus"], headers={"range": "bytes=0-99"})
    out["manifiesto"] = [m.status_code, len(m.json()["segments"])]
    out["audio_206"] = [audio.status_code, len(audio.content), audio.headers.get("content-range", "")[:12]]
    out["catalogo"] = [x["id"] for x in c.get("/api/catalog").json()]
    with c.stream("GET", f"/api/synthesize/{nid}") as r:
        eventos = [json.loads(l) for l in r.iter_lines() if l]
    out["ndjson"] = [e["event"] for e in eventos][-1]
    out["export"] = c.get("/api/experiment/export").status_code
print("RESULTADO=" + json.dumps(out))
"""


@pytest.fixture(scope="module")
def imagen(tmp_path_factory) -> Path:
    """Carpeta con el mismo contenido que /app en la imagen."""
    img = tmp_path_factory.mktemp("imagen") / "app"
    ignorar = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", "out")
    shutil.copytree(ROOT / "backend", img / "backend", ignore=ignorar)
    shutil.copytree(
        ROOT / "eval",
        img / "eval",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "out", "results"),
    )
    (img / "scripts").mkdir()
    shutil.copy(ROOT / "scripts" / "verify_models.py", img / "scripts" / "verify_models.py")
    for f in ("models.lock.json", "LICENSES.md", "pyproject.toml"):
        shutil.copy(ROOT / f, img / f)
    dist = img / "frontend" / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(
        '<!doctype html><html><body><div id="app"></div></body></html>', encoding="utf-8"
    )
    (dist / "assets" / "app-abc123.js").write_text("console.log(1)", encoding="utf-8")
    # lo que NO lleva la imagen: data/, docs/, .env, models/, static/, frontend/src...
    for ausente in ("data", "docs", ".env", "models", "static"):
        assert not (img / ausente).exists()
    return img


def _entorno(img: Path, extra: dict | None = None) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("NA_")}
    env.update(
        {
            "IMG": str(img),
            "PYTHONPATH": str(img / "backend"),
            "NA_ENV": "production",
            "NA_DATABASE_URL": f"sqlite:///{(img.parent / 'data' / 'noticias.db').as_posix()}",
            "NA_STATIC_DIR": str(img.parent / "static"),
            "NA_MODELS_DIR": str(img.parent / "models"),
            "NA_FRONTEND_DIST": str(img / "frontend" / "dist"),
            "NA_TRUST_PROXY": "true",
            "NA_TTS_ENGINE": "fake",
            "NA_ADMIN_TOKEN": "token-de-la-imagen-simulada-0123456789",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    (img.parent / "data").mkdir(exist_ok=True)
    env.update(extra or {})
    return env


def test_la_app_arranca_y_sirve_con_solo_lo_que_copia_el_dockerfile(imagen):
    r = subprocess.run(
        [sys.executable, "-c", SCRIPT],
        cwd=imagen,
        env=_entorno(imagen),
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert r.returncode == 0, r.stderr[-2000:]
    out = json.loads(re.search(r"RESULTADO=(.*)", r.stdout).group(1))
    assert out["health"] == "ok" and out["ready"] == {
        "status": "ok",
        "db": True,
        "static": True,
        "tts": True,
    }
    assert out["pwa"] == [200, True, "no-cache"]  # index sin caché: una versión nueva se instala
    assert out["asset"] == [200, "public, max-age=31536000, immutable"]
    assert "max-age=31536000" in out["hsts"]
    assert out["docs"] == [404, 404]  # producción: sin documentación interactiva
    assert out["cerrado"] == [403, 403] and out["abierto"] == 200
    assert (
        out["proceso"] == "processed" and out["manifiesto"][0] == 200 and out["manifiesto"][1] >= 1
    )
    assert out["audio_206"][:2] == [206, 100] and out["audio_206"][2].startswith("bytes 0-99/")
    assert len(out["catalogo"]) == 1
    assert out["ndjson"] == "done"
    assert out["export"] == 403  # la exportación sigue cerrada por HTTP en producción sin piloto


def test_sin_token_configurado_los_endpoints_administrativos_quedan_cerrados_en_la_imagen(imagen):
    codigo = (
        "from fastapi.testclient import TestClient\n"
        "from app.main import app\n"
        "with TestClient(app) as c:\n"
        "    print('R=', c.get('/api/events/summary', headers={'x-admin-token': 'cualquiera-largo-0123456789'}).status_code)\n"
    )
    r = subprocess.run(
        [sys.executable, "-c", codigo],
        cwd=imagen,
        env=_entorno(imagen, {"NA_ADMIN_TOKEN": "", "NA_EXPORT_TOKEN": ""}),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert r.returncode == 0, r.stderr[-1500:]
    assert "R= 403" in r.stdout
    assert "NA_ADMIN_TOKEN" in r.stderr  # el arranque avisa de que falta el token en producción
