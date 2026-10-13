"""Análisis estadístico de la Fase 5, definido en ``docs/metrics.md`` («Plan de análisis»).

1. Exclusión: se descartan los participantes con menos de 4 bloques completados; los datos piloto
   NO entran en el análisis confirmatorio (``incluir_piloto=False`` por defecto).
2. Primario: modelo lineal mixto de la comprensión (statsmodels ``MixedLM``, REML), condición +
   posición + noticia + alfabetización, intercepto aleatorio por participante. Contrastes C2−C1,
   C3−C2 y C4−C3 con corrección de Holm.
3. Secundarios no paramétricos intra-sujeto: Friedman y Wilcoxon (con Holm y r = Z/√N) para
   comprensión, esfuerzo y aceptabilidad.
4. Bootstrap de participantes (percentiles, B = 2000, semilla fija) de las diferencias.
5. Sensibilidad: sin los bloques C4 con avatar degradado, y noticia como componente de varianza.

Uso con datos reales (carpeta que escribe ``python -m app.cli experiment export``)::

    uv run python -m eval.fase5.analysis data/export [--incluir-piloto]
"""

from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats
from statsmodels.stats.multitest import multipletests

from eval.fase5.modelo import CONDS, CONTRASTES

B_BOOTSTRAP = 2000
SEMILLA_BOOTSTRAP = 20261012
VARIABLES = ("comprension", "esfuerzo", "aceptabilidad")
FORMULA = (
    'comprension ~ C(condicion, Treatment("C1")) + C(posicion) + C(slot_noticia)'
    " + C(alfabetizacion)"
)


def cargar(carpeta: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    bloques = pd.read_csv(carpeta / "bloques.csv")
    sesiones = pd.read_csv(carpeta / "sesiones.csv")
    return bloques, sesiones


def preparar(bloques: pd.DataFrame, incluir_piloto: bool = False) -> tuple[pd.DataFrame, dict]:
    """Aplica las reglas de exclusión fijadas de antemano y devuelve (datos, resumen)."""
    df = bloques.copy()
    resumen: dict = {"participantes_exportados": int(df["participante"].nunique())}
    if not incluir_piloto:
        n = int(df["participante"].nunique())
        df = df[df["piloto"] == 0]
        resumen["excluidos_piloto"] = n - int(df["participante"].nunique())
    completos = df.groupby("participante")["completado"].sum()
    excluidos = sorted(completos[completos < 4].index)
    df = df[~df["participante"].isin(excluidos)].dropna(subset=["comprension", "esfuerzo"]).copy()
    resumen["excluidos_menos_de_4_bloques"] = excluidos
    resumen["participantes_analizados"] = int(df["participante"].nunique())
    resumen["bloques_analizados"] = int(len(df))
    return df, resumen


def _formula(df: pd.DataFrame) -> str:
    f = FORMULA
    if df["bloqueados_prop"].nunique() > 1:
        f += " + bloqueados_prop"  # covariable (limitación 42); constante si no hay bloqueados
    return f


def ajustar(df: pd.DataFrame, formula: str | None = None):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return smf.mixedlm(formula or _formula(df), df, groups=df["participante"]).fit(
            reml=True, method=["bfgs", "powell"]
        )


def contrastes_mixto(res) -> list[dict]:
    """C2−C1, C3−C2 y C4−C3 con IC 95 % (normal) y p corregidos por Holm."""
    nombres = list(res.fe_params.index)
    k = len(nombres)
    cov = np.asarray(res.cov_params())[:k, :k]
    beta = np.asarray(res.fe_params)

    def pos(c: str) -> int | None:
        return None if c == "C1" else nombres.index(f'C(condicion, Treatment("C1"))[T.{c}]')

    filas = []
    for a, b in CONTRASTES:
        v = np.zeros(k)
        if pos(a) is not None:
            v[pos(a)] += 1
        if pos(b) is not None:
            v[pos(b)] -= 1
        est = float(v @ beta)
        se = float(np.sqrt(v @ cov @ v))
        z = est / se if se > 0 else float("nan")
        p = float(2 * stats.norm.sf(abs(z)))
        filas.append(
            {
                "contraste": f"{a}-{b}",
                "estimado": est,
                "ee": se,
                "ic95": [est - 1.959964 * se, est + 1.959964 * se],
                "z": z,
                "p": p,
            }
        )
    holm = multipletests([f["p"] for f in filas], method="holm")[1]
    for f, ph in zip(filas, holm, strict=True):
        f["p_holm"] = float(ph)
    return filas


def modelo_primario(df: pd.DataFrame) -> dict:
    res = ajustar(df)
    return {
        "formula": _formula(df),
        "n_bloques": int(len(df)),
        "n_participantes": int(df["participante"].nunique()),
        "converge": bool(getattr(res, "converged", True)),
        "var_participante": float(res.cov_re.iloc[0, 0]),
        "var_residual": float(res.scale),
        "contrastes": contrastes_mixto(res),
    }


def sensibilidad_sin_degradados(df: pd.DataFrame) -> dict:
    sub = df[~((df["condicion"] == "C4") & (df["degradacion_avatar"] == 1))]
    return {
        "bloques_quitados": int(len(df) - len(sub)),
        "contrastes": contrastes_mixto(ajustar(sub)),
    }


def sensibilidad_noticia_aleatoria(df: pd.DataFrame) -> dict:
    """Noticia y participante como componentes de varianza cruzados (un solo grupo)."""
    fija = 'comprension ~ C(condicion, Treatment("C1")) + C(posicion) + C(alfabetizacion)'
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            m = smf.mixedlm(
                fija,
                df.assign(grupo=1),
                groups="grupo",
                vc_formula={
                    "participante": "0 + C(participante)",
                    "noticia": "0 + C(slot_noticia)",
                },
            )
            res = m.fit(reml=True, method=["bfgs", "powell"])
        return {"contrastes": contrastes_mixto(res), "var_comp": [float(x) for x in res.vcomp]}
    except Exception as e:  # el modelo cruzado puede no converger con pocos datos: se informa
        return {"error": f"{type(e).__name__}: {e}"}


def no_parametricos(df: pd.DataFrame) -> dict:
    out: dict = {}
    for var in VARIABLES:
        w = df.pivot(index="participante", columns="condicion", values=var).dropna()[list(CONDS)]
        fr = stats.friedmanchisquare(*[w[c] for c in CONDS])
        medias = {c: float(w[c].mean()) for c in CONDS}
        filas = []
        for a, b in CONTRASTES:
            d = w[a] - w[b]
            if (d == 0).all():
                p, z = 1.0, 0.0
            else:
                p = float(stats.wilcoxon(w[a], w[b], zero_method="wilcox").pvalue)
                z = float(stats.norm.isf(max(p, 1e-300) / 2))
            filas.append(
                {
                    "contraste": f"{a}-{b}",
                    "p": p,
                    "r": z / np.sqrt(len(w)),
                    "mediana_dif": float(d.median()),
                }
            )
        holm = multipletests([f["p"] for f in filas], method="holm")[1]
        for f, ph in zip(filas, holm, strict=True):
            f["p_holm"] = float(ph)
        out[var] = {
            "n": int(len(w)),
            "medias": medias,
            "friedman": {"chi2": float(fr.statistic), "p": float(fr.pvalue)},
            "wilcoxon": filas,
        }
    return out


def bootstrap(df: pd.DataFrame, b: int = B_BOOTSTRAP, seed: int = SEMILLA_BOOTSTRAP) -> dict:
    """IC 95 % percentil de la diferencia media por contraste, remuestreando participantes."""
    rng = np.random.default_rng(seed)
    out: dict = {"B": b, "semilla": seed}
    for var in VARIABLES:
        w = df.pivot(index="participante", columns="condicion", values=var).dropna()[list(CONDS)]
        n = len(w)
        idx = rng.integers(0, n, size=(b, n))
        filas = []
        for x, y in CONTRASTES:
            d = (w[x] - w[y]).to_numpy()
            medias = d[idx].mean(axis=1)
            filas.append(
                {
                    "contraste": f"{x}-{y}",
                    "dif_media": float(d.mean()),
                    "ic95": [float(np.percentile(medias, 2.5)), float(np.percentile(medias, 97.5))],
                }
            )
        out[var] = filas
    return out


def analizar(bloques: pd.DataFrame, incluir_piloto: bool = False, completo: bool = True) -> dict:
    df, resumen = preparar(bloques, incluir_piloto)
    out: dict = {"datos": resumen, "primario": modelo_primario(df)}
    if completo:
        out["no_parametricos"] = no_parametricos(df)
        out["bootstrap"] = bootstrap(df)
        out["sensibilidad"] = {
            "sin_c4_degradado": sensibilidad_sin_degradados(df),
            "noticia_componente_varianza": sensibilidad_noticia_aleatoria(df),
        }
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("carpeta", type=Path, help="carpeta de la exportación (bloques.csv)")
    ap.add_argument("--incluir-piloto", action="store_true")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()
    bloques, _ = cargar(a.carpeta)
    res = analizar(bloques, a.incluir_piloto)
    destino = a.out or a.carpeta / "analisis.json"
    destino.write_text(json.dumps(res, indent=1, ensure_ascii=False), "utf-8")
    for c in res["primario"]["contrastes"]:
        print(
            f"{c['contraste']}: {c['estimado']:+.3f} IC95 [{c['ic95'][0]:+.3f}, {c['ic95'][1]:+.3f}] p_holm={c['p_holm']:.3f}"
        )
    print(f"-> {destino}")


if __name__ == "__main__":
    main()
