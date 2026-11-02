"""Mide la latencia del servicio BiTAM con oraciones del split DEV de AmericasNLP (nunca el test).

Solo usa la biblioteca estándar: puede ejecutarse con cualquier Python 3.11 mientras el servicio
está encendido.

    python traductor/bench.py --corpus data/corpus/americasnlp2021 [--n 20] [--semilla 13]

Escribe ``eval/results/traductor_servicio.json`` con las latencias medidas, la respuesta de
``/salud`` (dispositivo, dtype, versiones, carga, VRAM), la semilla y los hashes de entrada.
El test oficial de AmericasNLP es el que BiTAM usó para evaluarse: se rechaza explícitamente.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import statistics
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SALIDA = RAIZ / "eval" / "results" / "traductor_servicio.json"
# Mismo hash que backend/app/corpus/loader.py (commit d3f519c del corpus)
SHA256_DEV_ES = "5ea9455bee5e67f56db261a7969cf410a8f833305afc669cc6d5ee39ef7b10d3"


def _pedir(url: str, cuerpo: dict | None = None, timeout: float = 600) -> dict:
    datos = None if cuerpo is None else json.dumps(cuerpo).encode("utf-8")
    req = urllib.request.Request(url, data=datos, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def cargar_dev(corpus: Path, split: str) -> list[str]:
    if split != "dev":
        raise ValueError("solo se permite el split dev (el test es el de evaluación de BiTAM)")
    ruta = corpus / "dev.es"
    sha = hashlib.sha256(ruta.read_bytes()).hexdigest()
    if sha != SHA256_DEV_ES:
        raise ValueError(f"hash distinto en {ruta}: {sha}")
    return [x.strip() for x in ruta.read_text(encoding="utf-8").splitlines() if x.strip()]


def percentil(valores: list[float], q: float) -> float:
    ordenados = sorted(valores)
    k = (len(ordenados) - 1) * q
    i, f = int(k), k - int(k)
    sig = ordenados[min(i + 1, len(ordenados) - 1)]
    return ordenados[i] + (sig - ordenados[i]) * f


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--corpus", type=Path, default=RAIZ / "data" / "corpus" / "americasnlp2021")
    ap.add_argument("--split", default="dev")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--semilla", type=int, default=13)
    ap.add_argument("--url", default="http://127.0.0.1:8100")
    ap.add_argument("--salida", type=Path, default=SALIDA)
    args = ap.parse_args()

    oraciones = random.Random(args.semilla).sample(cargar_dev(args.corpus, args.split), args.n)
    salud = _pedir(f"{args.url}/salud")

    # 1) calentamiento (no se cuenta): la primera generación compila kernels CUDA
    _pedir(f"{args.url}/traducir", {"texts": [oraciones[0]]})

    # 2) una oración por petición: latencia que verá el backend por oración
    lat: list[float] = []
    salidas: list[str] = []
    for o in oraciones:
        t0 = time.perf_counter()
        r = _pedir(f"{args.url}/traducir", {"texts": [o]})
        lat.append(time.perf_counter() - t0)
        salidas.append(r["translations"][0])

    # 3) todas en una petición (lotes de 8 internos): como una noticia completa
    t0 = time.perf_counter()
    _pedir(f"{args.url}/traducir", {"texts": oraciones})
    lote_s = time.perf_counter() - t0

    salud_final = _pedir(f"{args.url}/salud")
    resultado = {
        "fecha": datetime.now(UTC).isoformat(timespec="seconds"),
        "split": args.split,
        "n": args.n,
        "semilla": args.semilla,
        "palabras_media": round(statistics.mean(len(o.split()) for o in oraciones), 2),
        "salud": salud,
        "vram_max_mb_final": salud_final.get("vram_max_mb"),
        "latencia_oracion_s": {
            "media": round(statistics.mean(lat), 3),
            "p50": round(percentil(lat, 0.5), 3),
            "p95": round(percentil(lat, 0.95), 3),
            "min": round(min(lat), 3),
            "max": round(max(lat), 3),
        },
        "lote_completo_s": round(lote_s, 3),
        "lote_s_por_oracion": round(lote_s / args.n, 3),
        "salidas_en_minusculas": sum(s == s.lower() for s in salidas),
        "salidas_vacias": sum(not s.strip() for s in salidas),
        # El corpus no se redistribuye: no se guarda texto, solo hashes de cada salida (permiten
        # comparar dos ejecuciones, p. ej. bf16 frente a fp16, oración por oración).
        "sha256_salidas": [hashlib.sha256(s.encode("utf-8")).hexdigest()[:16] for s in salidas],
    }
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(json.dumps(resultado, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
