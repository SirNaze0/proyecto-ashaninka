"""Comprueba que el dtype de cómputo del servicio no degrada la traducción (bf16 frente a fp16).

NO evalúa la calidad de BiTAM (eso es de la tesis de la compañera; contrato §2). Mide si el ajuste
de despliegue (fp16 en GPUs sin bf16 nativo) conserva lo que la entrega produce en bf16: chrF++ y
chrF sobre una muestra fija del split DEV de AmericasNLP (nunca el test, que es el de evaluación de
BiTAM) y concordancia exacta oración a oración entre dos ejecuciones.

    python fidelidad.py --corpus <...>/americasnlp2021 [--n 200] [--semilla 13]
    # -> ../eval/results/traductor_fidelidad_<dtype>.json   (dtype leído de /salud)

Con dos ejecuciones (una por dtype) imprime la comparación.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import time
from datetime import UTC, datetime
from pathlib import Path

from bench import RAIZ, _pedir
from sacrebleu.metrics import CHRF

SHA256 = {
    "dev.es": "5ea9455bee5e67f56db261a7969cf410a8f833305afc669cc6d5ee39ef7b10d3",
    "dev.cni": "90c85ba9bee92e3ff871e3128a6d2f376387978d108538f552d87874b9f35161",
}


def cargar_pares(corpus: Path, split: str) -> list[tuple[int, str, str]]:
    if split != "dev":
        raise ValueError("solo se permite el split dev (el test es el de evaluación de BiTAM)")
    lineas = {}
    for nombre, esperado in SHA256.items():
        ruta = corpus / nombre
        sha = hashlib.sha256(ruta.read_bytes()).hexdigest()
        if sha != esperado:
            raise ValueError(f"hash distinto en {ruta}: {sha}")
        lineas[nombre] = ruta.read_text(encoding="utf-8").splitlines()
    return [
        (i + 1, es.strip(), cni.strip())
        for i, (es, cni) in enumerate(zip(lineas["dev.es"], lineas["dev.cni"], strict=True))
        if es.strip() and cni.strip()
    ]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--corpus", type=Path, required=True)
    ap.add_argument("--split", default="dev")
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--semilla", type=int, default=13)
    ap.add_argument("--url", default="http://127.0.0.1:8100")
    args = ap.parse_args()

    pares = random.Random(args.semilla).sample(cargar_pares(args.corpus, args.split), args.n)
    salud = _pedir(f"{args.url}/salud")
    t0 = time.perf_counter()
    hip: list[str] = []
    for k in range(0, len(pares), 32):
        lote = [es for _, es, _ in pares[k : k + 32]]
        hip.extend(_pedir(f"{args.url}/traducir", {"texts": lote})["translations"])
    segundos = time.perf_counter() - t0
    refs = [[cni for _, _, cni in pares]]

    resultado = {
        "fecha": datetime.now(UTC).isoformat(timespec="seconds"),
        "split": args.split,
        "n": args.n,
        "semilla": args.semilla,
        "lineas_dev": [i for i, _, _ in pares],
        "dtype": salud["dtype"],
        "dispositivo": salud["dispositivo"],
        "version": salud["version"],
        "chrf_pp": round(CHRF(word_order=2).corpus_score(hip, refs).score, 2),
        "chrf": round(CHRF().corpus_score(hip, refs).score, 2),
        "segundos_total": round(segundos, 1),
        "s_por_oracion_en_lotes_32": round(segundos / args.n, 3),
        "sha256_salidas": [hashlib.sha256(h.encode("utf-8")).hexdigest()[:16] for h in hip],
    }
    salida = RAIZ / "eval" / "results" / f"traductor_fidelidad_{salud['dtype']}.json"
    salida.write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(
        f"{salida.name}: chrF++={resultado['chrf_pp']} chrF={resultado['chrf']} ({segundos:.0f} s)"
    )

    otros = {"float16": "bfloat16", "bfloat16": "float16"}
    otro = salida.with_name(f"traductor_fidelidad_{otros.get(salud['dtype'], '')}.json")
    if otro.exists():
        b = json.loads(otro.read_text("utf-8"))
        if b["lineas_dev"] == resultado["lineas_dev"]:
            iguales = sum(
                x == y
                for x, y in zip(b["sha256_salidas"], resultado["sha256_salidas"], strict=True)
            )
            print(
                f"{b['dtype']}: chrF++={b['chrf_pp']} chrF={b['chrf']} | salidas idénticas: "
                f"{iguales}/{args.n}"
            )


if __name__ == "__main__":
    main()
