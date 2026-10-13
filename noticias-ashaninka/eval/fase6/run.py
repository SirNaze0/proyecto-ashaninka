"""Consolida la Fase 6 en ``eval/results/fase_6.json``.

Qué comprueba (definido en ``docs/metrics.md``, «Fase 6», antes de construir):
* **Seguridad, despliegue, kit de escucha y documentación:** el resultado de las pruebas de cada área
  (``eval/fase6/out/pytest.xml``, que escribe ``scripts/verify.sh``; si falta, las ejecuta).
* **Docker, con exactitud:** versión del CLI, ``docker compose config`` sobre una copia con el
  ``.env`` de producción y el estado del demonio. El **build** solo se intenta si ``docker info``
  responde; si no, queda «pendiente» con el mensaje real del demonio. Nunca se da por construido
  lo que no se construyó.
* **Modelos:** SHA-256 de los pesos contra ``models.lock.json``.
* **Kit de escucha:** construcción con ambos motores, y recuperación de valores conocidos con
  oyentes SIMULADOS (no es una medición).
* **Regresión:** carga inicial de la PWA y los criterios de la Fase 5.
* **Pendientes:** todo lo que requiere personas o infraestructura que no hay.

Uso: uv run python -m eval.fase6.run [--sin-build]
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from eval.fase4 import bundle
from eval.fase4.run import criterio, git, hardware, leer
from eval.listening.inteligibilidad_mos import build as escucha_build
from eval.listening.inteligibilidad_mos import diseno as escucha_dz
from eval.listening.inteligibilidad_mos import score as escucha_score
from eval.listening.inteligibilidad_mos.simular import VERDAD, simular_oyentes

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "eval" / "fase6" / "out"
RES = ROOT / "eval" / "results"
MB = 1024 * 1024
IMAGEN = "noticias-ashaninka:fase6"

# Área -> archivos de prueba que la cubren
AREAS = {
    "seguridad": ["test_security.py", "test_security_api.py"],
    "despliegue": ["test_deploy_artifacts.py", "test_imagen_simulada.py"],
    "escucha": ["test_listening_kit.py"],
    "documentacion": ["test_docs_fase6.py"],
}


def _ejecutar(cmd: list[str], timeout: int = 120, **kw) -> tuple[int | None, str, str]:
    """(código, stdout, stderr); código ``None`` si el programa no existe o se agotó el tiempo."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, **kw)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except FileNotFoundError:
        return None, "", f"{cmd[0]}: no está instalado"
    except subprocess.TimeoutExpired:
        return None, "", f"{' '.join(cmd[:3])}: tiempo agotado ({timeout} s)"


# ------------------------------------------------------------------ pruebas por área
def _casos(xml: Path) -> list[dict]:
    raiz = ET.parse(xml).getroot()
    out = []
    for c in raiz.iter("testcase"):
        estado = "ok"
        if c.find("failure") is not None or c.find("error") is not None:
            estado = "falla"
        elif c.find("skipped") is not None:
            estado = "omitida"
        out.append({"archivo": c.get("classname", "").split(".")[-1] + ".py", "estado": estado})
    return out


def pruebas_por_area(xml: Path | None = None) -> dict:
    """Conteo por área. Si no hay ``pytest.xml`` (lo deja verify.sh), ejecuta las pruebas de las áreas."""
    xml = xml or OUT / "pytest.xml"
    if not xml.exists():
        OUT.mkdir(parents=True, exist_ok=True)
        archivos = [f"backend/tests/**/{f}" for fs in AREAS.values() for f in fs]
        xml = OUT / "pytest_areas.xml"
        import glob

        rutas = [p for patron in archivos for p in glob.glob(str(ROOT / patron), recursive=True)]
        _ejecutar(
            [sys.executable, "-m", "pytest", "-q", f"--junitxml={xml}", *rutas],
            timeout=900,
            cwd=ROOT,
        )
    casos = _casos(xml)
    por_archivo: dict[str, dict] = defaultdict(lambda: {"ok": 0, "falla": 0, "omitida": 0})
    for c in casos:
        por_archivo[c["archivo"]][c["estado"]] += 1
    out = {}
    for area, archivos in AREAS.items():
        tot = {"ok": 0, "falla": 0, "omitida": 0}
        for a in archivos:
            for k, v in por_archivo.get(a, {}).items():
                tot[k] += v
        out[area] = {
            "archivos": archivos,
            "pasaron": tot["ok"],
            "fallaron": tot["falla"],
            "omitidas": tot["omitida"],
            "total": sum(tot.values()),
        }
    return out


def pruebas_globales() -> dict:
    out: dict = {}
    xml = OUT / "pytest.xml"
    if xml.exists():
        c = _casos(xml)
        out["pytest"] = {
            "total": len(c),
            "pasaron": sum(x["estado"] == "ok" for x in c),
            "fallaron": sum(x["estado"] == "falla" for x in c),
            "omitidas": sum(x["estado"] == "omitida" for x in c),
        }
    v = leer(OUT / "vitest.json")
    if v:
        out["vitest"] = {
            "total": v["numTotalTests"],
            "pasaron": v["numPassedTests"],
            "fallaron": v["numFailedTests"],
        }
    e = leer(OUT / "e2e.json")
    if e:
        s = e["stats"]
        out["e2e"] = {
            "total": s["expected"] + s["unexpected"] + s["skipped"] + s["flaky"],
            "pasaron": s["expected"],
            "fallaron": s["unexpected"],
            "omitidas": s["skipped"],
        }
    return out


# ------------------------------------------------------------------ Docker
def docker(sin_build: bool) -> dict:
    """Estado exacto de Docker. El build se intenta solo si el demonio responde."""
    d: dict = {"cli": None, "compose": None, "compose_config": None, "demonio": None, "build": None}
    cod, ver, err = _ejecutar(["docker", "--version"])
    if cod != 0:
        d["cli"] = {"disponible": False, "detalle": err or ver}
        d["demonio"] = {"activo": False, "detalle": "sin CLI de docker"}
        d["build"] = {"estado": "pendiente", "motivo": "sin CLI de docker"}
        return d
    d["cli"] = {"disponible": True, "version": ver}
    cod, ver, _ = _ejecutar(["docker", "compose", "version"])
    d["compose"] = {"disponible": cod == 0, "version": ver}

    # `compose config` no necesita el demonio: valida sintaxis, anclas, variables y el .env de producción
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        for f in ("docker-compose.yml", "Caddyfile"):
            shutil.copy(ROOT / f, t / f)
        shutil.copy(ROOT / ".env.production.example", t / ".env")
        cod, sal, err = _ejecutar(
            ["docker", "compose", "--project-directory", str(t), "config", "--format", "json"]
        )
        if cod == 0:
            cfg = json.loads(sal)
            d["compose_config"] = {
                "valido": True,
                "servicios": sorted(cfg["services"]),
                "puertos_publicados": {
                    s: [p["published"] for p in v.get("ports", [])]
                    for s, v in cfg["services"].items()
                    if v.get("ports")
                },
                "volumenes": sorted(cfg.get("volumes", {})),
            }
        else:
            d["compose_config"] = {"valido": False, "detalle": err[-500:]}

    cod, _, err = _ejecutar(["docker", "info", "--format", "{{.ServerVersion}}"], timeout=30)
    if cod != 0:
        mensaje = err.splitlines()[0] if err else "sin respuesta"
        d["demonio"] = {"activo": False, "detalle": mensaje[:300]}
        d["build"] = {
            "estado": "pendiente",
            "motivo": "el demonio de Docker no está activo",
            "mensaje_docker": mensaje[:300],
        }
        return d
    d["demonio"] = {"activo": True}
    if sin_build:
        d["build"] = {"estado": "pendiente", "motivo": "omitido con --sin-build"}
        return d

    cod, _, err = _ejecutar(["docker", "build", "-t", IMAGEN, "."], timeout=3600, cwd=ROOT)
    if cod != 0:
        d["build"] = {"estado": "falla", "detalle": err[-1500:]}
        return d
    comprobaciones = {}
    for nombre, cmd in {
        "app_importa": ["python", "-c", "import app.main; print('ok')"],
        "espeak": ["espeak-ng", "--version"],
        "ffmpeg": ["ffmpeg", "-version"],
        "usuario_no_root": ["id", "-u"],
        "pwa_compilada": ["test", "-f", "/app/frontend/dist/index.html"],
    }.items():
        c, s, _ = _ejecutar(
            ["docker", "run", "--rm", "--entrypoint", cmd[0], IMAGEN, *cmd[1:]], timeout=300
        )
        comprobaciones[nombre] = {"codigo": c, "salida": s.splitlines()[0][:120] if s else ""}
    d["build"] = {"estado": "ok", "imagen": IMAGEN, "comprobaciones": comprobaciones}
    return d


# ------------------------------------------------------------------ modelos y kit de escucha
def modelos() -> dict:
    sys.path.insert(0, str(ROOT / "scripts"))
    import verify_models as vm

    lock = json.loads((ROOT / "models.lock.json").read_text(encoding="utf-8"))
    res = vm.verificar(lock, vm.MODELS, solo_servicio=False)
    return {
        "codigo": vm.codigo_de_salida(res),
        "archivos_ok": sum(r["estado"] == "ok" for r in res),
        "archivos_total": len(res),
        "omitidos": [r["modelo"] for r in res if r["estado"] == "omitido"],
        "fallos": [r for r in res if r["estado"] in {"distinto", "falta"}],
    }


def escucha_simulada(n_oyentes: int = 30) -> dict:
    """Kit con motor de prueba + oyentes simulados con valores verdaderos conocidos."""
    palabras = [
        "okantzi",
        "kemetsa",
        "tzimatsi",
        "kitaiteri",
        "irotake",
    ]  # texto de prueba, no lingüístico
    oraciones = []
    for i in range(12):
        w = [palabras[(i + k) % len(palabras)] for k in range(5)]
        oraciones.append(
            {"ref": f"s{i:02d}", "canonical": " ".join(w) + ".", "text_tts": " ".join(w)}
        )
    with tempfile.TemporaryDirectory() as tmp:
        kit = Path(tmp) / "kit"
        resumen = escucha_build.construir(
            oraciones, kit, escucha_build.MOTORES_FAKE, semilla=escucha_build.SEMILLA
        )
        import csv

        with (kit / "clave.csv").open(encoding="utf-8", newline="") as f:
            clave = list(csv.DictReader(f))
        r = escucha_score.puntuar(clave, simular_oyentes(clave, n_oyentes, 20261012))
    dentro = {}
    for motor, v in VERDAD.items():
        ic = r["motores"][motor]["acierto_palabra"]["ic95"]
        dentro[f"acierto_{motor}"] = ic[0] <= v["p_acierto"] <= ic[1]
        dentro[f"mos_{motor}"] = abs(r["motores"][motor]["mos"]["media"] - v["mos"]) < 0.2
    dif = r["diferencia_mms_menos_espeak"]["acierto_palabra"]["ic95"]
    return {
        "nota": "SIMULADO: oyentes sintéticos con acierto y MOS verdaderos conocidos; no es una medición",
        "n_oyentes": n_oyentes,
        "items": resumen["items"],
        "repetidos": resumen["repetidos"],
        "verdad": VERDAD,
        "estimado": {
            m: {"acierto": r["motores"][m]["acierto_palabra"], "mos": r["motores"][m]["mos"]}
            for m in escucha_dz.MOTORES
        },
        "recupera_dentro_del_ic": dentro,
        "diferencia_acierto_ic95": dif,
        "alfa_krippendorff_ordinal_mos": r["acuerdo"]["alfa_krippendorff_ordinal_mos"],
        "fiabilidad_repetidos": r["fiabilidad_repetidos"],
    }


def kit_real() -> dict:
    """Estado del kit con audio real (``build`` sin ``--fake``), si ya se construyó."""
    salida = escucha_build.OUT
    diseno = leer(salida / "diseno.json")
    if not diseno:
        return {
            "construido": False,
            "nota": "ejecute: uv run python -m eval.listening.inteligibilidad_mos.build",
        }
    import zipfile

    with zipfile.ZipFile(salida / "kit_escucha.zip") as z:
        nombres = z.namelist()
    return {
        "construido": True,
        **{
            k: diseno[k] for k in ("oraciones", "items", "repetidos", "regla_clave", "rms_objetivo")
        },
        "audios_en_zip": sum(n.startswith("audio/") for n in nombres),
        "clave_fuera_del_zip": not any("clave" in n.lower() for n in nombres),
        "motores": diseno["motores"],
    }


# ------------------------------------------------------------------ regresión
def regresion_fase5() -> dict | None:
    f5 = leer(RES / "fase_5.json")
    if not f5:
        return None
    auto = {
        k: v["cumple"]
        for k, v in f5["criterios"].items()
        if v["cumple"] is not True and v["cumple"] != "pendiente"
    }
    return {
        "commit_fase5": f5.get("commit"),
        "criterios_automaticos_en_fallo": auto,
        "criterios_cumplidos": sum(v["cumple"] is True for v in f5["criterios"].values()),
        "criterios_pendientes": sum(v["cumple"] == "pendiente" for v in f5["criterios"].values()),
    }


# ------------------------------------------------------------------ criterios
def _area(c: dict, d: dict, area: str, meta: str) -> None:
    a = d["pruebas_por_area"][area]
    c[f"pruebas_{area}"] = criterio(
        meta,
        f"{a['pasaron']}/{a['total']}",
        a["total"] > 0 and a["fallaron"] == 0 and a["pasaron"] > 0,
    )


def criterios(d: dict) -> dict:
    c: dict = {}
    _area(
        c,
        d,
        "seguridad",
        "endpoints administrativos cerrados por defecto, cabeceras, CSP, límite de tasa y salud: 0 fallos",
    )
    _area(
        c,
        d,
        "despliegue",
        "Dockerfile, Compose, Caddyfile, .dockerignore, variables, modelos y arranque con el layout de la imagen: 0 fallos",
    )
    _area(
        c,
        d,
        "escucha",
        "kit de escucha (reglas, alfa de Krippendorff, build y score con oyentes simulados): 0 fallos",
    )
    _area(
        c,
        d,
        "documentacion",
        "documentación de despliegue, arquitectura y README consistentes con el código y las mediciones: 0 fallos",
    )

    dk = d["docker"]
    cc = dk["compose_config"]
    c["docker_compose_config"] = criterio(
        "`docker compose config` valida el Compose con el .env de producción",
        (cc or {}).get("valido"),
        (cc["valido"] if cc else None),
        "" if cc else "sin CLI de docker",
    )
    pub = (cc or {}).get("puertos_publicados", {})
    c["solo_caddy_publica_puertos"] = criterio(
        "solo el proxy publica puertos; la aplicación queda en la red interna",
        pub,
        (set(pub) == {"caddy"}) if cc and cc.get("valido") else None,
    )
    b = dk["build"]
    if b["estado"] == "ok":
        cmp = b["comprobaciones"]
        build_ok: bool | None = (
            all(x["codigo"] == 0 for x in cmp.values()) and cmp["usuario_no_root"]["salida"] != "0"
        )
    elif b["estado"] == "falla":
        build_ok = False
    else:  # pendiente: el demonio no está activo o se omitió; no se da por construido
        build_ok = None
    c["docker_build_y_arranque"] = criterio(
        "la imagen se construye y contiene app, eSpeak-NG, ffmpeg y la PWA, sin correr como root",
        b["estado"],
        build_ok,
        b.get("mensaje_docker") or b.get("motivo", ""),
    )

    m = d["modelos"]
    c["modelos_sha256"] = criterio(
        "los pesos descargados coinciden con models.lock.json",
        f"{m['archivos_ok']}/{m['archivos_total']}",
        m["codigo"] == 0 and m["archivos_ok"] > 0 if m["archivos_total"] else None,
        "modelos de evaluación no descargados: " + ", ".join(m["omitidos"])
        if m["omitidos"]
        else "",
    )

    s = d["escucha_simulada"]
    c["escucha_recupera_valores_simulados"] = criterio(
        "el kit recupera el acierto y el MOS verdaderos dentro del IC 95 % (oyentes simulados)",
        s["recupera_dentro_del_ic"],
        all(s["recupera_dentro_del_ic"].values()),
        s["nota"],
    )
    k = d["kit_real"]
    c["kit_real_construido"] = criterio(
        "kit con audio real de MMS y eSpeak construido, con la clave fuera del zip",
        {k2: k.get(k2) for k2 in ("construido", "items", "audios_en_zip", "clave_fuera_del_zip")},
        (k["construido"] and k["clave_fuera_del_zip"] and k["audios_en_zip"] == k["items"])
        if k["construido"]
        else None,
        "" if k["construido"] else k["nota"],
    )

    paq = d["paquete"]
    c["carga_inicial"] = criterio(
        "carga inicial de la PWA < 3 MB tras añadir seguridad y el flujo del experimento",
        round(paq["inicial_gzip_bytes"] / MB, 4) if paq else None,
        paq["cumple_presupuesto_inicial"] if paq else None,
        "" if paq else "compile antes: (cd frontend && npm run build)",
    )
    r5 = d["regresion_fase5"]
    c["regresion_fase5"] = criterio(
        "los criterios automáticos de la Fase 5 siguen cumpliéndose",
        r5
        and {
            "cumplidos": r5["criterios_cumplidos"],
            "en_fallo": r5["criterios_automaticos_en_fallo"],
        },
        (not r5["criterios_automaticos_en_fallo"]) if r5 else None,
        "reejecute: uv run python -m eval.fase5.run" if not r5 else "",
    )
    for nombre in ("pytest", "vitest", "e2e"):
        x = d["pruebas"].get(nombre)
        c[f"pruebas_{nombre}"] = criterio(
            "0 fallos",
            f"{x['pasaron']}/{x['total']}" if x else None,
            (x["fallaron"] == 0) if x else None,
            ""
            if x
            else f"sin resultados de {nombre} en eval/fase6/out/ (los deja scripts/verify.sh)",
        )

    for clave, meta in {
        "banco_en_servidor_6_3": "repetir las mediciones de las Fases 2 a 4 en el servidor desplegado (local frente a servidor)",
        "readme_persona_ajena_6_4": "una persona ajena reproduce el sistema y el banco de pruebas solo con el README",
        "escucha_real_5_7": "sesiones de escucha con hablantes: inteligibilidad y MOS reales por variante",
        "https_real_dominio": "certificado y HTTPS reales con un dominio público (Let's Encrypt)",
    }.items():
        c[clave] = criterio(
            meta, None, None, "requiere infraestructura o personas; no se simula ni se inventa"
        )
    return c


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument(
        "--sin-build",
        action="store_true",
        help="no construir la imagen aunque el demonio esté activo",
    )
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    d = {
        "fase": 6,
        "commit": git("rev-parse", "HEAD"),
        "fecha": datetime.now(UTC).isoformat(timespec="seconds"),
        "hardware": hardware(None),
        "docker": docker(a.sin_build),
        "modelos": modelos(),
        "escucha_simulada": escucha_simulada(),
        "kit_real": kit_real(),
        "paquete": bundle.medir() if (bundle.DIST / "sw.js").exists() else None,
        "regresion_fase5": regresion_fase5(),
        "pruebas_por_area": pruebas_por_area(),
        "pruebas": pruebas_globales(),
    }
    d["criterios"] = criterios(d)
    RES.mkdir(parents=True, exist_ok=True)
    (RES / "fase_6.json").write_text(json.dumps(d, indent=1, ensure_ascii=False), "utf-8")
    for k, x in d["criterios"].items():
        marca = "OK " if x["cumple"] is True else ("-- " if x["cumple"] == "pendiente" else "NO ")
        print(f"{marca}{k}: {x['valor']}")


if __name__ == "__main__":
    main()
