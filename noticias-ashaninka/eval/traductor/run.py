"""Compatibilidad de la salida de BiTAM con el pipeline y latencia del servicio (Fase 4).

Métricas, muestra y reglas definidas ANTES de ejecutar en ``docs/metrics.md`` (sección
«Integración del traductor BiTAM»). NO evalúa la calidad de la traducción (contrato §2).

    # con el servicio encendido (traductor/run.ps1):
    uv run python -m eval.traductor.run [--corpus data/corpus/americasnlp2021] [--n 100]

Solo el split DEV (el test es el de evaluación de BiTAM: se rechaza). El resultado no guarda texto
del corpus (no se redistribuye): recuentos, números de línea y hashes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import statistics
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from app.config import CORPUS_DIR, RESULTS_DIR
from app.corpus.loader import EXPECTED_SHA256
from app.pipeline.normalize.classify import strip_accents
from app.translation import HttpTranslator, restaurar_mayusculas
from app.translation.service import _PALABRA, _clave

SALIDA = RESULTS_DIR / "traductor.json"
CATEGORIAS_PROPIO = {"nombre_propio", "nombre_propio_nativo"}
_VV = re.compile(r"(aa|ee|ii|oo)")


def cargar_pares(corpus: Path, split: str = "dev") -> list[tuple[int, str, str]]:
    """(línea 1-based, es, cni) del split, con hash verificado. Solo ``dev``."""
    if split != "dev":
        raise ValueError(
            f"split {split!r} no permitido: solo dev (el test es el de evaluación de BiTAM)"
        )
    lineas: dict[str, list[str]] = {}
    for lado in ("es", "cni"):
        ruta = corpus / f"dev.{lado}"
        sha = hashlib.sha256(ruta.read_bytes()).hexdigest()
        if sha != EXPECTED_SHA256[f"dev.{lado}"]:
            raise ValueError(f"hash distinto en {ruta}: {sha}")
        lineas[lado] = ruta.read_text(encoding="utf-8").splitlines()
    return [
        (i + 1, es.strip(), cni.strip())
        for i, (es, cni) in enumerate(zip(lineas["es"], lineas["cni"], strict=True))
        if es.strip() and cni.strip()
    ]


def candidatos_propios(fuente: str) -> list[str]:
    """Misma regla que ``restaurar_mayusculas``: mayúscula fuera del inicio, o sigla."""
    palabras = [m.group() for m in _PALABRA.finditer(fuente)]
    return [
        w
        for i, w in enumerate(palabras)
        if (i > 0 and w[0].isupper()) or (len(w) > 1 and w.isupper())
    ]


def vv_por_100_palabras(textos: list[str]) -> float:
    palabras = [w.lower() for t in textos for w in _PALABRA.findall(t)]
    if not palabras:
        return 0.0
    return round(100 * sum(len(_VV.findall(w)) for w in palabras) / len(palabras), 2)


def propios_detectados(segmentos: list[dict]) -> int:
    return sum(
        1 for s in segmentos for span in s["alignment_map"] if span["category"] in CATEGORIAS_PROPIO
    )


def percentil(valores: list[float], q: float) -> float:
    v = sorted(valores)
    k = (len(v) - 1) * q
    i = int(k)
    return v[i] + (v[min(i + 1, len(v) - 1)] - v[i]) * (k - i)


def medir(corpus: Path, n: int, semilla: int, url: str, split: str = "dev") -> dict:
    from app.services import Pipeline

    pares = random.Random(semilla).sample(cargar_pares(corpus, split), n)
    tr = HttpTranslator(url, timeout=600)
    salud = tr.salud()

    # --- latencia: calentamiento descartado, luego una petición por oración y el lote completo
    tr.translate_batch([pares[0][1]])
    lat: list[float] = []
    crudas: list[str] = []
    for _, es, _ in pares:
        t0 = time.perf_counter()
        crudas.append(tr.translate_batch([es]).translations[0])
        lat.append(time.perf_counter() - t0)
    t0 = time.perf_counter()
    tr.translate_batch([es for _, es, _ in pares])
    lote_s = time.perf_counter() - t0

    restauradas = [restaurar_mayusculas(es, c) for (_, es, _), c in zip(pares, crudas, strict=True)]

    # --- pipeline (normalización, adaptador MMS, G2P) sobre la salida cruda y la restaurada
    pipe = Pipeline.default()
    nativas = pipe.normalizer.native_letters
    seg_crudos = [pipe.process_text(c) for c in crudas if c.strip()]
    seg_rest = [pipe.process_text(r) for r in restauradas if r.strip()]
    planos = [s for segs in seg_rest for s in segs]
    bloqueados = [s for s in planos if not s["tts_ready"]]
    oov = Counter(
        ch
        for s in bloqueados
        for u in s["unresolved"]
        if "fuera del vocabulario" in u["reason"]
        for ch in u["reason"].rsplit("'", 2)[-2]
    )
    palabras = [w for r in restauradas for w in _PALABRA.findall(r)]
    ajenas = [w for w in palabras if any(c not in nativas for c in strip_accents(w.lower()))]

    candidatos = [c for _, es, _ in pares for c in candidatos_propios(es)]
    copiados = sum(
        1
        for (_, es, _), cruda in zip(pares, crudas, strict=True)
        for c in candidatos_propios(es)
        if _clave(c) in {_clave(w) for w in _PALABRA.findall(cruda)}
    )

    return {
        "fecha": datetime.now(UTC).isoformat(timespec="seconds"),
        "definicion": "docs/metrics.md#integración-del-traductor-bitam-mejoraeintegracion-fase-4",
        "split": split,
        "n": n,
        "semilla": semilla,
        "lineas_dev": [i for i, _, _ in pares],
        "servicio": salud,
        "latencia": {
            "s_por_oracion": {
                "media": round(statistics.mean(lat), 3),
                "p50": round(percentil(lat, 0.5), 3),
                "p95": round(percentil(lat, 0.95), 3),
                "max": round(max(lat), 3),
            },
            "lote_completo_s": round(lote_s, 2),
            "lote_s_por_oracion": round(lote_s / n, 3),
        },
        "salidas_vacias": sum(1 for c in crudas if not c.strip()),
        "salidas_en_minusculas": sum(1 for c in crudas if c == c.lower()),
        "pipeline": {
            "segmentos": len(planos),
            "segmentos_bloqueados": len(bloqueados),
            "pct_bloqueados": round(100 * len(bloqueados) / len(planos), 1) if planos else None,
            "oov_mas_frecuentes": oov.most_common(10),
            "adaptador": pipe.adapter.__class__.__name__,
        },
        "letras_ajenas": {
            "palabras": len(palabras),
            "palabras_con_letras_ajenas": len(ajenas),
            "pct": round(100 * len(ajenas) / len(palabras), 1) if palabras else None,
        },
        "nombres_propios": {
            "candidatos_en_fuente": len(candidatos),
            "copiados_por_bitam": copiados,
            "pct_copiados": round(100 * copiados / len(candidatos), 1) if candidatos else None,
            "detectados_classify_antes": sum(propios_detectados(s) for s in seg_crudos),
            "detectados_classify_despues": sum(propios_detectados(s) for s in seg_rest),
        },
        "vocales_dobles_por_100_palabras": {
            "salida_bitam": vv_por_100_palabras(crudas),
            "referencia_dev_cni": vv_por_100_palabras([cni for _, _, cni in pares]),
        },
        "sha256_salidas": [hashlib.sha256(c.encode("utf-8")).hexdigest()[:16] for c in crudas],
    }


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Compatibilidad BiTAM ↔ pipeline (Fase 4)")
    ap.add_argument("--corpus", type=Path, default=CORPUS_DIR)
    ap.add_argument("--split", default="dev")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--semilla", type=int, default=13)
    ap.add_argument("--url", default="http://127.0.0.1:8100")
    ap.add_argument("--salida", type=Path, default=SALIDA)
    a = ap.parse_args(argv)
    res = medir(a.corpus, a.n, a.semilla, a.url, a.split)
    a.salida.parent.mkdir(parents=True, exist_ok=True)
    a.salida.write_text(json.dumps(res, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {k: v for k, v in res.items() if k != "sha256_salidas"}, ensure_ascii=False, indent=1
        )
    )


if __name__ == "__main__":
    main()
