"""Consolida la Fase 5 en ``eval/results/fase_5.json``.

Ejecuta de punta a punta: balance del cuadrado de Williams → simulación sintética por la API real
→ exportación → privacidad y diccionario → análisis estadístico → recuperación de parámetros,
cobertura y potencia por réplicas. Todos los criterios automáticos se comparan con la VERDAD
conocida de la simulación; los que dependen de personas quedan como «pendiente».

Uso: uv run python -m eval.fase5.run [--n 32] [--replicas 200]
Resultados de las pruebas (opcional, los escribe el cierre de la fase en eval/fase5/out/):
  pytest.xml (--junitxml), vitest.json (--reporter=json), e2e.json (Playwright, reporter json)
"""

from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from app.experiment import export, latin
from app.experiment.privacy import verificar_sin_pii

from eval.fase4 import bundle
from eval.fase4.run import criterio, git, hardware, leer
from eval.fase5 import analysis, power
from eval.fase5.modelo import PARAMETROS, SEMILLA, contrastes_verdaderos, generar
from eval.fase5.simulate import OUT, ROOT, simular

RES = ROOT / "eval" / "results"
MB = 1024 * 1024
TOLERANCIA_MS = 5  # los tiempos exportados salen de marcas de tiempo con redondeo a ms


def _csv(carpeta: Path, nombre: str) -> pd.DataFrame:
    return pd.read_csv(carpeta / f"{nombre}.csv", keep_default_na=False, na_values=[""])


def verificar_exportacion(carpeta: Path, resumen: dict, n: int, seed: int) -> dict:
    """Compara la exportación con la verdad de la simulación (valores, tiempos y conteos)."""
    verdad = generar(n, seed, PARAMETROS)
    bloques = _csv(carpeta, "bloques")
    ses = _csv(carpeta, "sesiones")
    idx = bloques.set_index(["participante", "posicion"])
    peor_ms = {"t_escucha_ms": 0, "t_pantalla_ms": 0}
    valores_mal = 0
    visitados = 0
    for p in verdad:
        for b in p["bloques"]:
            visitados += 1
            fila = idx.loc[(p["codigo"], b["posicion"])]
            esc, pan = resumen["tiempos_reales"][f"{p['codigo']}:{b['posicion']}"]
            peor_ms["t_escucha_ms"] = max(
                peor_ms["t_escucha_ms"], abs(int(fila["t_escucha_ms"]) - esc)
            )
            peor_ms["t_pantalla_ms"] = max(
                peor_ms["t_pantalla_ms"], abs(int(fila["t_pantalla_ms"]) - pan)
            )
            ok = (
                fila["condicion"] == b["condicion"]
                and abs(float(fila["comprension"]) - sum(b["comp"]) / 4) < 1e-9
                and int(fila["esfuerzo"]) == b["esfuerzo"]
                and abs(float(fila["aceptabilidad"]) - sum(b["acep"]) / 3) < 1e-3
                and int(fila["repeticiones"]) == b["repeticiones"]
                and int(fila["pausas"]) == b["pausas"]
                and int(fila["cambios_velocidad"]) == b["cambios_velocidad"]
                and int(fila["degradacion_avatar"]) == int(b["degradacion"])
                and int(fila["completado"]) == 1
            )
            valores_mal += not ok
    esperado_filas = {
        "sesiones": n,
        "bloques": 4 * n,
        "eventos": resumen["eventos_enviados"],
    }
    filas = resumen["filas"]
    return {
        "bloques_visitados": visitados,
        "bloques_con_valores_distintos": valores_mal,
        "peor_diferencia_ms": peor_ms,
        "filas_exportadas": filas,
        "filas_esperadas": esperado_filas,
        "filas_ok": all(filas[k] == v for k, v in esperado_filas.items()),
        "sesiones_completas_exportadas": int((ses["estado"] == "completa").sum()),
        "sesiones_abandonadas_exportadas": int((ses["estado"] == "abandonada").sum()),
    }


def verificar_privacidad(carpeta: Path) -> dict:
    tablas = {t: json.loads((carpeta / f"{t}.json").read_text("utf-8")) for t in export.COLUMNAS}
    problemas = verificar_sin_pii(tablas)
    # control negativo: el verificador DEBE detectar un dato personal inyectado
    sucio = {
        **tablas,
        "respuestas": [*tablas["respuestas"], {"participante": "P001", "valor": "ana@correo.com"}],
    }
    sucio["sesiones"] = [{**tablas["sesiones"][0], "telefono": "987654321"}]
    detecta = verificar_sin_pii(sucio)
    return {
        "problemas": problemas,
        "control_negativo_detectado": len(detecta) >= 2,
        "tablas_revisadas": {t: len(f) for t, f in tablas.items()},
    }


def verificar_diccionario(carpeta: Path) -> dict:
    md = (ROOT / "data" / "DATA_DICTIONARY.md").read_text("utf-8")
    columnas = {}
    for tabla in export.COLUMNAS:
        cab = (carpeta / f"{tabla}.csv").read_text("utf-8").splitlines()[0].split(",")
        columnas[tabla] = {
            "csv": len(cab),
            "diccionario": len(export.columnas(tabla)),
            "coinciden": cab == export.columnas(tabla),
            "todas_documentadas": all(f"`{c}`" in md for c in cab),
        }
    total = sum(v["csv"] for v in columnas.values())
    documentadas = sum(v["csv"] for v in columnas.values() if v["todas_documentadas"])
    return {
        "columnas": columnas,
        "total": total,
        "cobertura": documentadas / total,
        "archivo_al_dia": md.replace("\r\n", "\n") == export.diccionario_md().replace("\r\n", "\n"),
    }


def balance() -> dict:
    return {str(n): latin.verificar_balance(n) for n in (16, 32, 48)}


def resumen_pruebas() -> dict:
    """Lee los resultados de las pruebas si el cierre de la fase los dejó en ``eval/fase5/out``."""
    out: dict = {}
    xml = OUT / "pytest.xml"
    if xml.exists():
        s = ET.parse(xml).getroot()
        s = s if s.tag == "testsuite" else s[0]
        t, f, e, k = (int(s.get(x, 0)) for x in ("tests", "failures", "errors", "skipped"))
        out["pytest"] = {"total": t, "pasaron": t - f - e - k, "fallaron": f + e, "omitidas": k}
    vj = leer(OUT / "vitest.json")
    if vj:
        out["vitest"] = {
            "total": vj["numTotalTests"],
            "pasaron": vj["numPassedTests"],
            "fallaron": vj["numFailedTests"],
        }
    ej = leer(OUT / "e2e.json")
    if ej:
        st = ej["stats"]
        out["e2e"] = {
            "total": st["expected"] + st["unexpected"] + st["skipped"] + st["flaky"],
            "pasaron": st["expected"],
            "fallaron": st["unexpected"],
            "omitidas": st["skipped"],
        }
    return out


def criterios(d: dict) -> dict:
    c: dict = {}
    b = d["balance"]
    c["balance_williams"] = criterio(
        "cuadrado de Williams y rotación balanceados en 16, 32 y 48 participantes",
        {
            n: all(
                v[k]
                for k in (
                    "condicion_x_posicion",
                    "condicion_x_noticia",
                    "noticia_x_posicion",
                    "arrastre",
                )
            )
            for n, v in b.items()
        },
        all(
            all(
                v[k]
                for k in (
                    "condicion_x_posicion",
                    "condicion_x_noticia",
                    "noticia_x_posicion",
                    "arrastre",
                )
            )
            for v in b.values()
        ),
    )
    s = d["simulacion"]
    c["idempotencia"] = criterio(
        "reenviar sesión, eventos y respuestas no crea duplicados",
        {
            "eventos_nuevos_en_reenvio": s["eventos_nuevos_en_reenvio"],
            "respuestas_nuevas_en_reenvio": s["respuestas_nuevas_en_reenvio"],
            "sesion_repetida_idempotente": s["sesion_repetida_idempotente"],
        },
        s["eventos_nuevos_en_reenvio"] == 0
        and s["respuestas_nuevas_en_reenvio"] == 0
        and s["sesion_repetida_idempotente"],
    )
    v = d["verificacion_exportacion"]
    c["exportacion_sin_errores"] = criterio(
        "todas las tablas exportadas, con las filas esperadas y los valores de la simulación",
        {
            "filas": v["filas_exportadas"],
            "bloques_con_valores_distintos": v["bloques_con_valores_distintos"],
        },
        v["filas_ok"] and v["bloques_con_valores_distintos"] == 0,
    )
    c["tiempos_exportados"] = criterio(
        f"t_pantalla y t_escucha coinciden con los tiempos simulados (≤ {TOLERANCIA_MS} ms)",
        v["peor_diferencia_ms"],
        max(v["peor_diferencia_ms"].values()) <= TOLERANCIA_MS,
    )
    p = d["privacidad"]
    c["privacidad"] = criterio(
        "ninguna columna ni valor identificable; el verificador detecta un dato personal inyectado",
        {"problemas": len(p["problemas"]), "control_negativo": p["control_negativo_detectado"]},
        not p["problemas"] and p["control_negativo_detectado"],
    )
    dic = d["diccionario"]
    c["diccionario_100pct"] = criterio(
        "el diccionario cubre el 100 % de las columnas exportadas y está al día",
        {"cobertura": dic["cobertura"], "columnas": dic["total"], "al_dia": dic["archivo_al_dia"]},
        dic["cobertura"] == 1.0
        and dic["archivo_al_dia"]
        and all(x["coinciden"] for x in dic["columnas"].values()),
    )
    a = d["analisis"]["primario"]
    ver = d["recuperacion"]["verdaderos"]
    dentro = {
        k["contraste"]: k["ic95"][0] <= ver[k["contraste"]] <= k["ic95"][1] for k in a["contrastes"]
    }
    c["recuperacion_un_ajuste"] = criterio(
        "los 3 efectos verdaderos caen dentro del IC 95 % del modelo mixto (simulación de 32)",
        dentro,
        all(dentro.values()) and a["converge"],
        "semilla fija declarada antes de ejecutar; no se reajustó",
    )
    cob = d["recuperacion"]["cobertura_ic95"]
    c["cobertura_replicas"] = criterio(
        f"cobertura del IC 95 % ≥ 0,90 en {d['recuperacion']['replicas']} réplicas",
        {k: round(x, 3) for k, x in cob.items()},
        all(x >= 0.90 for x in cob.values()),
    )
    pot = d["potencia"]
    c["potencia"] = criterio(
        f"N mínimo con potencia ≥ {pot['meta_potencia']} para d = {pot['d']} (C3 frente a C1)",
        pot["n_minimo"],
        pot["n_minimo"] is not None,
        "estimación bajo el modelo simulado; se recalcula con la varianza real del piloto",
    )
    paq = d["paquete"]
    c["carga_inicial"] = criterio(
        "carga inicial de la PWA < 3 MB con el flujo del experimento incluido",
        round(paq["inicial_gzip_bytes"] / MB, 4) if paq else None,
        paq["cumple_presupuesto_inicial"] if paq else None,
        "" if paq else "compile antes: (cd frontend && npm run build)",
    )
    pr = d["pruebas"]
    for nombre in ("pytest", "vitest", "e2e"):
        r = pr.get(nombre)
        c[f"pruebas_{nombre}"] = criterio(
            "0 fallos",
            f"{r['pasaron']}/{r['total']}" if r else None,
            (r["fallaron"] == 0) if r else None,
            "" if r else f"sin resultados de {nombre} en eval/fase5/out/",
        )
    for k, meta in {
        "consentimiento_comite": "texto del consentimiento aprobado por el comité de ética, con su audio en asháninka (5.1)",
        "items_comprension_hablante": "ítems de comprensión redactados por un hablante, modalidad oral (5.4)",
        "noticias_revisadas_p4": "≥ 8 noticias revisadas por un hablante (P4); hoy el selector exige 4 aptas",
        "piloto_con_personas": "piloto completo con 2–3 personas y exportación a CSV sin errores (5.8)",
        "escucha_mos_inteligibilidad": "guiones de escucha: inteligibilidad y MOS (5.7, eval/listening/)",
    }.items():
        c[k] = criterio(meta, None, None, "requiere personas; no se simula ni se inventa")
    return c


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--n", type=int, default=32)
    ap.add_argument("--replicas", type=int, default=power.REPLICAS)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    carpeta = OUT / "export"

    sim = simular(a.n, SEMILLA, PARAMETROS, carpeta)
    ver = verificar_exportacion(carpeta, sim, a.n, SEMILLA)
    bloques = pd.read_csv(carpeta / "bloques.csv")
    res = analysis.analizar(bloques, incluir_piloto=True)
    (OUT / "analisis.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), "utf-8")
    cob = power.cobertura(a.n, a.replicas)
    pot = power.potencia(replicas=a.replicas)
    (OUT / "potencia.json").write_text(
        json.dumps({"potencia": pot, "cobertura": cob}, indent=1, ensure_ascii=False), "utf-8"
    )

    sim_pub = {k: v for k, v in sim.items() if k != "tiempos_reales"}
    d = {
        "fase": 5,
        "commit": git("rev-parse", "HEAD"),
        "fecha": datetime.now(UTC).isoformat(timespec="seconds"),
        "hardware": hardware(None),
        "material": {
            "tipo": "SINTÉTICO: participantes simulados por la API real, marcados piloto; no son datos reales",
            "semilla": SEMILLA,
            "parametros_verdaderos": PARAMETROS,
            "contrastes_verdaderos": contrastes_verdaderos(),
        },
        "balance": balance(),
        "simulacion": sim_pub,
        "verificacion_exportacion": ver,
        "privacidad": verificar_privacidad(carpeta),
        "diccionario": verificar_diccionario(carpeta),
        "analisis": res,
        "recuperacion": cob,
        "potencia": pot,
        "paquete": bundle.medir() if (bundle.DIST / "sw.js").exists() else None,
        "pruebas": resumen_pruebas(),
    }
    d["criterios"] = criterios(d)
    RES.mkdir(parents=True, exist_ok=True)
    (RES / "fase_5.json").write_text(json.dumps(d, indent=1, ensure_ascii=False), "utf-8")
    for k, x in d["criterios"].items():
        marca = "OK " if x["cumple"] is True else ("-- " if x["cumple"] == "pendiente" else "NO ")
        print(f"{marca}{k}: {x['valor']}")


if __name__ == "__main__":
    main()
