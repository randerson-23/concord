"""Command-line entry point: ``concord <command>``."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from concord.corpus import (
    DEFAULT_CACHE,
    DEFAULT_SOURCES,
    fetch_sources,
    load_sources,
    plan_sources,
    plan_text,
)
from concord.diff import diff_specs
from concord.extract import AnthropicBackend, RecordingBackend, ReplayBackend, extract_spec
from concord.fixatdl import FixatdlError, read_fixatdl_file, write_fixatdl
from concord.fixdict import dictionary_path, load_dictionary
from concord.html import read_html
from concord.ir import AlgoSpec, SourceDocument
from concord.lint import lint_spec
from concord.orchestra import write_orchestra
from concord.pdf import Page, read_pdf
from concord.pipeline import DEFAULT_OUT, convert_source
from concord.site import write_site
from concord.verify import verify_spec


def _is_html(path: str) -> bool:
    return Path(path).suffix.lower() in (".html", ".htm")


def _read_pages(path: str) -> list[Page]:
    return read_html(path) if _is_html(path) else read_pdf(path)


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
    c.add_argument("--to", choices=["json", "fixatdl", "orchestra"], required=True)
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
    x = sub.add_parser("extract", help="extract an AlgoSpec from a PDF (LLM; citations verified)")
    x.add_argument("pdf")
    x.add_argument("--id", required=True, help="source id used in citations")
    x.add_argument("--title", required=True)
    x.add_argument("--url", help="public URL the PDF was published at")
    x.add_argument("--provider")
    x.add_argument("--out", required=True, help="where to write the IR JSON")
    x.add_argument("--review-out", help="where to write the review list (JSON)")
    x.add_argument("--replay", metavar="DIR", help="use recorded page-N.json responses, no API")
    x.add_argument("--record", metavar="DIR", help="save raw responses and usage (live runs)")
    x.add_argument(
        "--max-input-tokens",
        type=int,
        default=150_000,
        help="stop before the call that would exceed this many input tokens (default 150000)",
    )
    co = sub.add_parser("corpus", help="fetch the public sources and plan extraction")
    cosub = co.add_subparsers(dest="corpus_cmd", required=True)
    for name, text in (
        ("fetch", "download eligible sources into the cache"),
        ("plan", "size them"),
    ):
        cp = cosub.add_parser(name, help=text)
        cp.add_argument("ids", nargs="*", help="source ids (default: all)")
        cp.add_argument("--sources", default=str(DEFAULT_SOURCES))
        cp.add_argument("--cache-dir", default=str(DEFAULT_CACHE))
        if name == "plan":
            cp.add_argument("--price-per-mtok", type=float, help="price per million input tokens")
    cv = cosub.add_parser(
        "convert", help="extract, verify, lint and write every output for a source"
    )
    cv.add_argument("id", help="source id from corpus/sources.yaml (fetch it first)")
    cv.add_argument("--sources", default=str(DEFAULT_SOURCES))
    cv.add_argument("--cache-dir", default=str(DEFAULT_CACHE))
    cv.add_argument("--out-dir", default=str(DEFAULT_OUT), help="default corpus/out")
    cv.add_argument("--replay", metavar="DIR", help="use recorded page-N.json responses, no API")
    cv.add_argument("--record", metavar="DIR", help="save raw responses and usage (live runs)")
    cv.add_argument("--max-input-tokens", type=int, default=150_000)
    cv.add_argument("--fix-version", choices=["4.2", "4.4", "latest"], default="latest")
    cv.add_argument("--dict-dir", help="directory holding the Orchestra dictionary files")
    li = sub.add_parser("lint", help="check standard FIX tags against the FIX dictionary")
    li.add_argument("spec")
    li.add_argument("--fix-version", choices=["4.2", "4.4", "latest"], default="latest")
    li.add_argument("--dict-dir", help="directory holding the Orchestra dictionary files")
    li.add_argument("--format", choices=["text", "json"], default="text")
    st = sub.add_parser("site", help="render a spec as a static HTML site")
    st.add_argument("spec")
    st.add_argument("out_dir")
    st.add_argument("--diff", metavar="OLD", help="previous version; adds a changes.html report")
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
                docs[sid] = _read_pages(path)
            vr = verify_spec(_load(args.spec), docs)
            print(vr.to_json() if args.format == "json" else vr.to_text())
            if not vr.ok:
                return 2
        elif args.cmd == "extract":
            backend = ReplayBackend(args.replay) if args.replay else AnthropicBackend()
            if args.record:
                backend = RecordingBackend(backend, args.record)
            kind = "html" if _is_html(args.pdf) else "pdf"
            src = SourceDocument(id=args.id, title=args.title, kind=kind, url=args.url)
            res = extract_spec(
                _read_pages(args.pdf),
                src,
                backend,
                provider=args.provider,
                max_input_tokens=args.max_input_tokens,
            )
            Path(args.out).write_text(res.spec.model_dump_json(indent=2, exclude_none=True))
            Path(f"{args.out}.usage.json").write_text(
                json.dumps(res.usage_dict(args.max_input_tokens), indent=2) + "\n"
            )
            print(res.usage_text(), file=sys.stderr)
            if args.review_out:
                Path(args.review_out).write_text(
                    json.dumps([r.to_dict() for r in res.review], indent=2)
                )
            print(res.review_text())
            if res.review:
                return 2
        elif args.cmd == "corpus":
            if args.corpus_cmd == "convert":
                backend = ReplayBackend(args.replay) if args.replay else AnthropicBackend()
                if args.record:
                    backend = RecordingBackend(backend, args.record)
                done = convert_source(
                    args.id,
                    backend,
                    sources=args.sources,
                    cache_dir=args.cache_dir,
                    out_root=args.out_dir,
                    fix_version=args.fix_version,
                    dict_dir=args.dict_dir,
                    max_input_tokens=args.max_input_tokens,
                )
                if done.extraction is not None:
                    print(done.extraction.usage_text(), file=sys.stderr)
                print(f"wrote {done.out_dir}")
                print(done.review_text())
                return 2 if done.review else 0
            sources = load_sources(args.sources)
            if args.corpus_cmd == "fetch":
                results = fetch_sources(sources, args.cache_dir, args.ids)
                print("\n".join(r.to_text() for r in results))
                tally = Counter(r.status for r in results)
                print(", ".join(f"{n} {k}" for k, n in sorted(tally.items())))
            else:
                rows = plan_sources(sources, args.cache_dir, args.ids)
                print(plan_text(rows, args.price_per_mtok))
        elif args.cmd == "lint":
            version = args.fix_version
            wanted = load_dictionary(dictionary_path(version, args.dict_dir))
            latest = None
            if version != "latest":
                latest = load_dictionary(dictionary_path("latest", args.dict_dir))
            findings = lint_spec(_load(args.spec), wanted, latest)
            if args.format == "json":
                print(json.dumps([f.to_dict() for f in findings], indent=2))
            else:
                print("\n".join(f.to_text() for f in findings) or "no findings")
            if any(f.severity == "error" for f in findings):
                return 2
        elif args.cmd == "site":
            old = _load(args.diff) if args.diff else None
            files = write_site(_load(args.spec), args.out_dir, old)
            print(f"wrote {len(files)} files to {args.out_dir}")
        elif args.cmd == "convert":
            spec = _load(args.file)
            if args.to == "json":
                print(spec.model_dump_json(indent=2, exclude_none=True))
            elif args.to == "orchestra":
                result = write_orchestra(spec)
                sys.stdout.buffer.write(result.xml)
                for strategy_name, message in result.unenforced:
                    print(
                        f"note: not enforceable in Orchestra 1.0 (kept as annotation): "
                        f"{strategy_name}: {message}",
                        file=sys.stderr,
                    )
            else:
                sys.stdout.buffer.write(write_fixatdl(spec))
    except (FixatdlError, ValueError, OSError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
