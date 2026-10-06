"""Convierte noticias de prueba al contrato del §2 (JSON) y las guarda en data/news/.

Formatos admitidos:
  .txt / .docx : primera línea no vacía = título; el resto = cuerpo
  .json        : objeto o lista con al menos titulo_cni y cuerpo_cni
  .csv         : columnas titulo_cni, cuerpo_cni (y opcionalmente las demás del contrato)

Los metadatos que falten se rellenan con un valor EXPLÍCITO ("desconocido"), nunca inventado.
La procedencia por defecto es traducción automática SIN revisión (no apta para el experimento).

Uso: uv run python scripts/convert_test_news.py <archivo_o_carpeta> [--tipo traduccion_humana]
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.schemas import NewsIn  # noqa: E402


def docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    paras = re.findall(r"<w:p[ >].*?</w:p>", xml, flags=re.S)
    lines = ["".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", p, flags=re.S)) for p in paras]
    return "\n".join(lines)


def from_text(text: str, source: str, defaults: dict) -> dict:
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    if len(lines) < 2:
        raise ValueError(f"{source}: se necesita título (1.ª línea) y cuerpo")
    return {
        "titulo_cni": lines[0],
        "cuerpo_cni": "\n".join(lines[1:]),
        "fuente_original": source,
        **defaults,
    }


def convert(path: Path, defaults: dict) -> list[dict]:
    suf = path.suffix.lower()
    if suf == ".txt":
        return [from_text(path.read_text(encoding="utf-8"), path.name, defaults)]
    if suf == ".docx":
        return [from_text(docx_text(path), path.name, defaults)]
    if suf == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        return [{**defaults, **d} for d in (data if isinstance(data, list) else [data])]
    if suf == ".csv":
        with open(path, encoding="utf-8", newline="") as f:
            return [
                {**defaults, **{k: v for k, v in row.items() if v}} for row in csv.DictReader(f)
            ]
    raise ValueError(f"Formato no admitido: {path.name}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("--out", default=str(ROOT / "data" / "news"))
    ap.add_argument(
        "--tipo",
        default="traduccion_automatica",
        choices=["traduccion_humana", "traduccion_automatica", "automatica_revisada"],
    )
    ap.add_argument("--sistema", default="desconocido")
    ap.add_argument("--variante", default="desconocida")
    args = ap.parse_args(argv)

    defaults = {
        "variante_dialectal": args.variante,
        "procedencia": {
            "tipo": args.tipo,
            "sistema": args.sistema,
            "version": "desconocida",
            "revisado_por_hablante": False,
            "revisor_id": None,
        },
    }
    src = Path(args.source)
    files = sorted(p for p in src.iterdir() if p.is_file()) if src.is_dir() else [src]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    n = 0
    for f in files:
        for i, item in enumerate(convert(f, defaults)):
            news = NewsIn.model_validate(item)  # valida contra el contrato
            target = out / f"{f.stem}_{i:02d}.json"
            target.write_text(news.model_dump_json(indent=2), encoding="utf-8")
            n += 1
    print(f"[convert] {n} noticias escritas en {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
