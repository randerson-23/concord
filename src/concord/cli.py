"""Command-line entry point: ``concord <command>``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from concord.diff import diff_specs
from concord.fixatdl import FixatdlError, read_fixatdl_file, write_fixatdl
from concord.ir import AlgoSpec
from concord.pdf import read_pdf
from concord.verify import verify_spec


def _load(path: str) -> AlgoSpec:
    p = Path(path)
    if p.suffix == ".json":
        return AlgoSpec.model_validate_json(p.read_text())
    result = read_fixatdl_file(p)
    for w in result.warnings:
        print(f"warning: {w}", file=sys.stderr)
    return result.spec


def _inspect(spec: AlgoSpec) -> str:
    lines = [f"provider: {spec.provider or '-'}   strategy tag: {spec.strategy_identifier_tag}"]
    for s in spec.strategies:
        lines.append("")
        lines.append(f"{s.label or s.name}  [{s.name}]  wire={s.wire_value}  v{s.version}")
        for p in s.parameters:
            tag = str(p.fix_tag) if p.fix_tag else "-"
            flags = "req" if p.required else "   "
            extra = []
            if p.enum_values:
                extra.append(
                    "{"
                    + ", ".join(
                        f"{e.wire_value}={e.label}" if e.label else e.wire_value
                        for e in p.enum_values
                    )
                    + "}"
                )
            if p.min_value or p.max_value:
                extra.append(f"[{p.min_value or ''}..{p.max_value or ''}]")
            if p.default_value is not None:
                extra.append(f"default={p.default_value}")
            if p.const_value is not None:
                extra.append(f"const={p.const_value}")
            lines.append(f"  {tag:>6} {flags} {p.name:<20} {p.type.value:<14} {' '.join(extra)}")
        for e in s.edits:
            lines.append(f"  rule: {e.message}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="concord", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("inspect", help="summarise a FIXatdl or IR JSON file")
    i.add_argument("file")
    c = sub.add_parser("convert", help="convert between FIXatdl and IR JSON")
    c.add_argument("file")
    c.add_argument("--to", choices=["json", "fixatdl"], required=True)
    d = sub.add_parser("diff", help="classify the changes between two specs")
    d.add_argument("old")
    d.add_argument("new")
    d.add_argument("--format", choices=["text", "json"], default="text")
    d.add_argument(
        "--fail-on-breaking", action="store_true", help="exit 2 if any breaking change is found"
    )
    v = sub.add_parser("verify", help="check every citation quote appears on its cited PDF page")
    v.add_argument("spec")
    v.add_argument(
        "--source",
        action="append",
        default=[],
        metavar="ID=PDF",
        help="map a source id to its PDF (repeatable)",
    )
    v.add_argument("--format", choices=["text", "json"], default="text")
    sub.add_parser("schema", help="print the IR JSON Schema")
    args = ap.parse_args(argv)

    try:
        if args.cmd == "schema":
            print(json.dumps(AlgoSpec.model_json_schema(), indent=2))
        elif args.cmd == "inspect":
            print(_inspect(_load(args.file)))
        elif args.cmd == "diff":
            report = diff_specs(_load(args.old), _load(args.new))
            print(report.to_json() if args.format == "json" else report.to_text())
            if args.fail_on_breaking and report.has_breaking:
                return 2
        elif args.cmd == "verify":
            docs = {}
            for item in args.source:
                sid, sep, path = item.partition("=")
                if not sep or not sid or not path:
                    raise ValueError(f"--source {item!r}: expected ID=PDF_PATH")
                docs[sid] = read_pdf(path)
            vr = verify_spec(_load(args.spec), docs)
            print(vr.to_json() if args.format == "json" else vr.to_text())
            if not vr.ok:
                return 2
        elif args.cmd == "convert":
            spec = _load(args.file)
            if args.to == "json":
                print(spec.model_dump_json(indent=2, exclude_none=True))
            else:
                sys.stdout.buffer.write(write_fixatdl(spec))
    except (FixatdlError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
