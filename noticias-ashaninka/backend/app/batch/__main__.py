"""Modo por lotes (tarea 2.6).

Uso:
  uv run python -m app.batch build --all [--engine mms_vits]
  uv run python -m app.batch build --news 3
  uv run python -m app.batch schema      # exporta docs/manifest.schema.json
"""

from __future__ import annotations

import argparse
import json
import sys

from app.cli import _utf8_stdout


def main(argv: list[str] | None = None) -> int:
    _utf8_stdout()
    ap = argparse.ArgumentParser(prog="app.batch")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--all", action="store_true")
    b.add_argument("--news", type=int, action="append")
    b.add_argument("--engine", default=None)
    sub.add_parser("schema")
    args = ap.parse_args(argv)

    if args.cmd == "schema":
        from app.batch.manifest import export_schema
        from app.config import DOCS_DIR

        print(f"[batch] {export_schema(DOCS_DIR / 'manifest.schema.json')}")
        return 0
    if not args.all and not args.news:
        print("indica --all o --news ID", file=sys.stderr)
        return 2
    from app.batch.service import run_batch

    stats = run_batch(None if args.all else args.news, args.engine)
    print("[batch] " + json.dumps(stats, ensure_ascii=False))
    return 1 if stats["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
