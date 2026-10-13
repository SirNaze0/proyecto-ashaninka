"""Puntúa la escucha de inteligibilidad y MOS (tarea 5.7): MMS frente a eSpeak-NG.

Uso: uv run python -m eval.listening.inteligibilidad_mos.score respuestas_*.csv
         [--clave out/clave.csv] [--out eval/results/escucha_inteligibilidad_mos.json]

Cada archivo de respuestas viene de ``hoja_escucha.html`` (columnas ``oyente, variante, item,
transcripcion, mos, comentario``). La clave (``clave.csv``) la guarda quien aplica la prueba.

Métricas (``docs/metrics.md``, «Fase 6»): acierto y CER por palabra clave, MOS de 1 a 5, diferencia
pareada MMS − eSpeak por oyente, IC 95 % por bootstrap de OYENTES, desglose por variante, alfa de
Krippendorff ordinal (MOS), acuerdo medio por pares (aciertos) y fiabilidad con los ítems repetidos.
Con menos de 2 oyentes no se calculan IC ni acuerdo y el informe lo dice.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

from app.config import RESULTS_DIR

from eval.listening.inteligibilidad_mos import diseno as dz

HERE = Path(__file__).parent
MMS, ESP = dz.MOTORES


def leer_csv(ruta: Path) -> list[dict]:
    with ruta.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _mos(v: str | None) -> int | None:
    try:
        x = int(str(v).strip())
    except (TypeError, ValueError):
        return None
    return x if dz.MOS_MIN <= x <= dz.MOS_MAX else None


def _resumen(por_oyente: dict[str, float | None]) -> dict:
    vals = {k: v for k, v in por_oyente.items() if v is not None}
    if not vals:
        return {"media": None, "ic95": None, "n_oyentes": 0}
    boot = dz.bootstrap_oyentes(vals)
    if boot is None:
        return {
            "media": dz.media(list(vals.values())),
            "ic95": None,
            "n_oyentes": len(vals),
            "nota": dz.NO_CALCULABLE,
        }
    return {k: boot[k] for k in ("media", "ic95", "n_oyentes")}


def _por_oyente(respuestas: list[dict], clave: dict[str, dict]) -> tuple[dict, list[str]]:
    """{oyente: {variante, items: {item: {transcripcion, mos}}}} y advertencias."""
    adv: list[str] = []
    oyentes: dict[str, dict] = {}
    duplicadas = desconocidos = 0
    for r in respuestas:
        oy = (r.get("oyente") or "").strip()
        if not dz.RE_ID.match(oy):
            adv.append(f"fila con identificador de oyente no válido: {oy[:20]!r}")
            continue
        item = (r.get("item") or "").strip()
        if item not in clave:
            desconocidos += 1
            continue
        o = oyentes.setdefault(
            oy, {"variante": dz.limpiar_variante(r.get("variante")), "items": {}}
        )
        if item in o["items"]:
            duplicadas += 1
        o["items"][item] = {
            "transcripcion": r.get("transcripcion") or "",
            "mos": _mos(r.get("mos")),
        }
    if desconocidos:
        adv.append(f"{desconocidos} respuestas con ítems que no están en la clave (ignoradas)")
    if duplicadas:
        adv.append(f"{duplicadas} respuestas duplicadas (se conserva la última)")
    return oyentes, adv


def metricas_oyente(o: dict, clave: dict[str, dict]) -> dict:
    """Por motor: palabras acertadas, ediciones, letras, MOS y WER de oración; solo ítems no repetidos."""
    por_motor: dict[str, dict] = {
        m: {"aciertos": 0, "palabras": 0, "ediciones": 0, "letras": 0, "mos": []}
        for m in dz.MOTORES
    }
    for item, resp in o["items"].items():
        c = clave[item]
        if c["repite_de"]:
            continue
        ev = dz.evaluar_transcripcion(c["claves"].split("|"), resp["transcripcion"])
        m = por_motor[c["motor"]]
        m["aciertos"] += ev["aciertos"]
        m["palabras"] += ev["palabras"]
        m["ediciones"] += ev["ediciones"]
        m["letras"] += ev["letras"]
        if resp["mos"] is not None:
            m["mos"].append(resp["mos"])
    return por_motor


def _wer_oraciones(oyentes: dict, clave: dict[str, dict]) -> dict | None:
    """Contraste con jiwer (grupo eval): WER medio de la oración completa por motor."""
    try:
        import jiwer
    except ImportError:
        return None
    acum: dict[str, list[float]] = {m: [] for m in dz.MOTORES}
    for o in oyentes.values():
        for item, resp in o["items"].items():
            c = clave[item]
            if c["repite_de"] or not resp["transcripcion"].strip():
                continue
            ref = " ".join(dz.palabras(c["canonico"]))
            hyp = " ".join(dz.palabras(resp["transcripcion"]))
            if ref and hyp:
                acum[c["motor"]].append(jiwer.wer(ref, hyp))
    return {m: dz.media(v) for m, v in acum.items()}


def fiabilidad_repetidos(oyentes: dict, clave: dict[str, dict]) -> dict:
    difs: list[float] = []
    concord: list[float] = []
    for o in oyentes.values():
        for item, resp in o["items"].items():
            orig = clave[item]["repite_de"]
            if not orig or orig not in o["items"]:
                continue
            a, b = o["items"][orig], resp
            if a["mos"] is not None and b["mos"] is not None:
                difs.append(abs(a["mos"] - b["mos"]))
            claves = clave[orig]["claves"].split("|")
            ea = dz.evaluar_transcripcion(claves, a["transcripcion"])["hits"]
            eb = dz.evaluar_transcripcion(claves, b["transcripcion"])["hits"]
            concord.extend(float(x == y) for x, y in zip(ea, eb, strict=True))
    return {
        "pares_mos": len(difs),
        "diferencia_absoluta_media_mos": dz.media(difs),
        "pares_palabras": len(concord),
        "concordancia_aciertos": dz.media(concord),
    }


def puntuar(clave_rows: list[dict], respuestas: list[dict]) -> dict:
    clave = {r["item"]: r for r in clave_rows}
    oyentes, adv = _por_oyente(respuestas, clave)
    if not oyentes:
        return {"n_oyentes": 0, "advertencias": [*adv, "no hay respuestas válidas"]}
    met = {oy: metricas_oyente(o, clave) for oy, o in oyentes.items()}

    def serie(motor: str, f) -> dict[str, float | None]:
        return {oy: f(m[motor]) for oy, m in met.items()}

    acierto = lambda m: m["aciertos"] / m["palabras"] if m["palabras"] else None  # noqa: E731
    cer = lambda m: m["ediciones"] / m["letras"] if m["letras"] else None  # noqa: E731
    mos = lambda m: dz.media(m["mos"])  # noqa: E731

    motores = {
        e: {
            "acierto_palabra": _resumen(serie(e, acierto)),
            "cer_palabra": _resumen(serie(e, cer)),
            "mos": _resumen(serie(e, mos)),
        }
        for e in dz.MOTORES
    }

    def diferencia(f) -> dict:
        d = {
            oy: (None if f(m[MMS]) is None or f(m[ESP]) is None else f(m[MMS]) - f(m[ESP]))
            for oy, m in met.items()
        }
        return _resumen(d)

    diff = {
        "acierto_palabra": diferencia(acierto),
        "cer_palabra": diferencia(cer),
        "mos": diferencia(mos),
    }

    por_variante = {}
    for var, lista in dz.agrupar(oyentes.items(), lambda kv: kv[1]["variante"]).items():
        ids = [oy for oy, _ in lista]
        por_variante[var] = {
            "n_oyentes": len(ids),
            "insuficiente": len(ids) < dz.MIN_OYENTES_VARIANTE,
            **{
                e: {
                    "acierto_palabra": dz.media(
                        [v for oy in ids if (v := acierto(met[oy][e])) is not None]
                    ),
                    "mos": dz.media([v for oy in ids if (v := mos(met[oy][e])) is not None]),
                }
                for e in dz.MOTORES
            },
        }

    # acuerdo entre oyentes: solo ítems no repetidos
    unidades_mos: dict = defaultdict(list)
    unidades_hit: dict = defaultdict(dict)
    for oy, o in oyentes.items():
        for item, resp in o["items"].items():
            c = clave[item]
            if c["repite_de"]:
                continue
            if resp["mos"] is not None:
                unidades_mos[item].append(resp["mos"])
            ev = dz.evaluar_transcripcion(c["claves"].split("|"), resp["transcripcion"])
            for k, h in enumerate(ev["hits"]):
                unidades_hit[(item, k)][oy] = h
    if len(oyentes) >= 2:
        acuerdo = {
            "alfa_krippendorff_ordinal_mos": dz.krippendorff_alpha(unidades_mos, "ordinal"),
            "acuerdo_medio_por_pares_aciertos": dz.acuerdo_medio_por_pares(unidades_hit),
        }
    else:
        acuerdo = {
            "alfa_krippendorff_ordinal_mos": dz.NO_CALCULABLE,
            "acuerdo_medio_por_pares_aciertos": dz.NO_CALCULABLE,
        }

    vacias = sum(
        1 for o in oyentes.values() for r in o["items"].values() if not r["transcripcion"].strip()
    )
    total = sum(len(o["items"]) for o in oyentes.values())
    if len(oyentes) < 2:
        adv.append("un solo oyente: sin IC ni acuerdo; los resultados son descriptivos")
    if vacias:
        adv.append(f"{vacias} de {total} transcripciones vacías")
    return {
        "n_oyentes": len(oyentes),
        "items_no_repetidos": sum(1 for c in clave.values() if not c["repite_de"]),
        "motores": motores,
        "diferencia_mms_menos_espeak": diff,
        "por_variante": por_variante,
        "acuerdo": acuerdo,
        "fiabilidad_repetidos": fiabilidad_repetidos(oyentes, clave),
        "wer_oracion_jiwer": _wer_oraciones(oyentes, clave),
        "advertencias": adv,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("respuestas", nargs="+", type=Path)
    ap.add_argument("--clave", type=Path, default=HERE / "out" / "clave.csv")
    ap.add_argument("--out", type=Path, default=RESULTS_DIR / "escucha_inteligibilidad_mos.json")
    a = ap.parse_args(argv)
    filas = [r for p in a.respuestas for r in leer_csv(p)]
    res = puntuar(leer_csv(a.clave), filas)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"[escucha] {res['n_oyentes']} oyente(s) -> {a.out}")
    for adv in res.get("advertencias", []):
        print(f"[escucha] aviso: {adv}")
    if res["n_oyentes"]:
        for e, m in res["motores"].items():
            print(
                f"  {e}: acierto {m['acierto_palabra']['media']:.3f}  MOS {m['mos']['media']:.2f}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
