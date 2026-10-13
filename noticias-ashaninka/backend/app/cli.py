"""CLI del proyecto: ``uv run python -m app.cli <orden>``.

Órdenes:
  db-init                     crea el esquema de la base de datos (idempotente)
  validate-resources          valida los YAML y muestra el recuento por estado
  import <dir>                importa noticias JSON con el contrato del §2
  import --from-corpus dev    importa oraciones del corpus como pseudo-noticias de prueba
  process --all | --news ID   procesa noticias (segmentación, normalización, adaptador, G2P)
  report --news ID            reporte editorial legible
  build-docs                  regenera docs/normalization_rules.md
  corpus report               informe del corpus -> docs/corpus_report.md
  corpus extract              candidatos -> data/candidates/*.yaml
  corpus inventory            inventario de grafemas candidato -> g2p/rules/inventory.yaml
  experiment export|dictionary  exportación del experimento (Fase 5) y diccionario de datos
"""

from __future__ import annotations

import argparse
import json
import sys


def _utf8_stdout() -> None:
    # En Windows la consola puede no ser UTF-8; evita UnicodeEncodeError con ñ, á, etc.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass


def cmd_experiment(args: argparse.Namespace) -> int:
    from pathlib import Path

    from sqlmodel import Session

    from app.config import ROOT
    from app.db.session import get_engine, init_db
    from app.experiment import export

    if args.action == "dictionary":
        destino = Path(args.out) if args.out else ROOT / "data" / "DATA_DICTIONARY.md"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(export.diccionario_md(), encoding="utf-8")
        print(f"[experimento] diccionario -> {destino}")
        return 0
    engine = get_engine()
    init_db(engine)
    formatos = tuple(f.strip() for f in args.format.split(",") if f.strip())
    with Session(engine) as session:
        cuentas = export.escribir(
            session, Path(args.out or ROOT / "data" / "export"), formatos, args.incluir_piloto
        )
    for tabla, n in cuentas.items():
        print(f"[experimento] {tabla}: {n} filas")
    return 0


def cmd_db_init(_: argparse.Namespace) -> int:
    from app.db.session import init_db

    init_db()
    print("[db] esquema aplicado")
    return 0


def cmd_validate_resources(_: argparse.Namespace) -> int:
    from app.pipeline.resources import validate_all

    counts = validate_all()
    for name, c in counts.items():
        detail = ", ".join(f"{k}={v}" for k, v in sorted(c.items())) or "sin entradas"
        print(f"[recursos] {name}: {detail}")
    return 0


def cmd_import(args: argparse.Namespace) -> int:
    from app.services import import_from_corpus, import_news_dir

    if args.from_corpus:
        ids = import_from_corpus(args.from_corpus, limit=args.limit)
    elif args.path:
        ids = import_news_dir(args.path)
    else:
        print("indica una carpeta o --from-corpus", file=sys.stderr)
        return 2
    print(f"[import] {len(ids)} noticias importadas")
    return 0


def cmd_process(args: argparse.Namespace) -> int:
    from app.services import process_all, process_news_by_id

    if args.all:
        stats = process_all()
    elif args.news:
        stats = process_news_by_id(args.news)
    else:
        print("indica --all o --news ID", file=sys.stderr)
        return 2
    print("[process] " + json.dumps(stats, ensure_ascii=False))
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    from app.services import editorial_report_text

    print(editorial_report_text(args.news))
    return 0


def cmd_build_docs(_: argparse.Namespace) -> int:
    from app.docs_builder import build_normalization_docs

    path = build_normalization_docs()
    print(f"[docs] {path}")
    return 0


def cmd_corpus(args: argparse.Namespace) -> int:
    if args.action == "report":
        from app.corpus.report import write_report

        rep = write_report()
        diffs = rep["diferencias_con_plan"]
        print("[corpus] docs/corpus_report.md generado")
        print("[corpus] diferencias con el plan: " + ("; ".join(diffs) if diffs else "ninguna"))
    elif args.action == "extract":
        from app.corpus.extract import extract_all

        counts = extract_all()
        print("[corpus] candidatos: " + json.dumps(counts, ensure_ascii=False))
    elif args.action == "inventory":
        from app.pipeline.g2p.inventory_builder import write_inventory

        path = write_inventory()
        print(f"[corpus] inventario candidato escrito en {path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="app.cli", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("db-init").set_defaults(func=cmd_db_init)
    sub.add_parser("validate-resources").set_defaults(func=cmd_validate_resources)

    imp = sub.add_parser("import")
    imp.add_argument("path", nargs="?")
    imp.add_argument("--from-corpus", choices=["train", "dev"])
    imp.add_argument("--limit", type=int, default=20)
    imp.set_defaults(func=cmd_import)

    proc = sub.add_parser("process")
    proc.add_argument("--all", action="store_true")
    proc.add_argument("--news", type=int)
    proc.set_defaults(func=cmd_process)

    rep = sub.add_parser("report")
    rep.add_argument("--news", type=int, required=True)
    rep.set_defaults(func=cmd_report)

    sub.add_parser("build-docs").set_defaults(func=cmd_build_docs)

    exp = sub.add_parser("experiment")
    exp.add_argument("action", choices=["export", "dictionary"])
    exp.add_argument("--out", default=None, help="carpeta (export) o archivo (dictionary)")
    exp.add_argument("--format", default="csv,json", help="csv,json,parquet")
    exp.add_argument("--incluir-piloto", action="store_true", help="incluye sesiones piloto")
    exp.set_defaults(func=cmd_experiment)

    cor = sub.add_parser("corpus")
    cor.add_argument("action", choices=["report", "extract", "inventory"])
    cor.set_defaults(func=cmd_corpus)
    return p


def main(argv: list[str] | None = None) -> int:
    _utf8_stdout()
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
