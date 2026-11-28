"""Corpus pipeline, part 2: one command from a cached source to every output (item 25c).

``convert_source`` reads a document fetched by ``concord corpus fetch``, extracts an
``AlgoSpec`` (live or from recorded responses), verifies every citation, lints standard tags
against the FIX dictionary, and writes ``corpus/out/<id>/``: ``spec.json``, ``strategies.xml``
(FIXatdl), ``orchestra.xml``, ``site/``, ``review.json``, ``lint.json``, ``source.json`` and
``usage.json``. The
output is derived from a third-party document and stays git-ignored (hard rule 2). Same inputs,
same bytes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from concord.corpus import DEFAULT_CACHE, CorpusError, doc_path, load_sources
from concord.extract import Backend, ExtractionResult, extract_spec
from concord.fixatdl import write_fixatdl
from concord.fixdict import dictionary_path, load_dictionary
from concord.html import read_html
from concord.ir import SourceDocument
from concord.lint import Finding, lint_spec
from concord.orchestra import write_orchestra
from concord.pdf import read_pdf
from concord.site import write_site
from concord.verify import verify_spec

DEFAULT_OUT = Path("corpus/out")


@dataclass
class ConvertResult:
    out_dir: Path
    review: list[dict[str, Any]] = field(default_factory=list)
    lint_warnings: list[Finding] = field(default_factory=list)
    extraction: ExtractionResult | None = None

    def review_text(self) -> str:
        if not self.review:
            return "no items need review"
        lines = [f"{len(self.review)} items need review:"]
        for r in self.review:
            page = f"p.{r['page']} " if r["page"] is not None else ""
            lines.append(f"  {page}{r['location']}: {r['reason']} - {r['detail']}")
        return "\n".join(lines)


def _write(path: Path, data: bytes | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))


def convert_source(
    source_id: str,
    backend: Backend,
    *,
    sources: str | Path,
    cache_dir: str | Path = DEFAULT_CACHE,
    out_root: str | Path = DEFAULT_OUT,
    fix_version: str = "latest",
    dict_dir: str | Path | None = None,
    max_input_tokens: int | None = None,
) -> ConvertResult:
    """Run extract, verify and lint on one cached source and write its outputs."""
    entries = [e for e in load_sources(sources) if e.get("id") == source_id]
    if not entries:
        raise CorpusError(f"unknown source id {source_id!r}; expected an id from {sources}")
    entry = entries[0]
    if entry.get("use") != "ok" or entry.get("kind") not in ("pdf", "html"):
        raise CorpusError(
            f"{source_id}: use is {entry.get('use')!r} and kind {entry.get('kind')!r}; "
            "expected use: ok with kind pdf or html"
        )
    path = doc_path(Path(cache_dir), entry)
    if not path.is_file():
        raise CorpusError(f"{path}: not fetched; run `concord corpus fetch {source_id}` first")
    # Load the dictionaries first: a missing one should fail before any model call.
    wanted = load_dictionary(dictionary_path(fix_version, dict_dir))
    latest = (
        load_dictionary(dictionary_path("latest", dict_dir)) if fix_version != "latest" else None
    )

    pages = read_pdf(path) if entry["kind"] == "pdf" else read_html(path)
    source = SourceDocument(
        id=source_id,
        title=entry["title"],
        kind=entry["kind"],
        url=entry.get("url"),
        publisher=entry.get("publisher"),
    )
    extraction = extract_spec(
        pages, source, backend, provider=entry.get("publisher"), max_input_tokens=max_input_tokens
    )
    spec = extraction.spec

    review = [r.to_dict() for r in extraction.review]
    for r in verify_spec(spec, {source_id: pages}).failures:
        c = r.citation
        detail = f'{r.status.value} [{c.source_id} p.{c.page}] "{c.quote}"'
        item: dict[str, Any] = {
            "page": c.page,
            "location": r.location,
            "reason": "verify_failed",
            "detail": detail,
        }
        if c.quote:
            item["quotes"] = [{"page": c.page, "quote": c.quote}]
        review.append(item)
    findings = lint_spec(spec, wanted, latest)
    for f in findings:
        if f.severity == "error":
            review.append(
                {"page": None, "location": f.location, "reason": "lint_error", "detail": f.message}
            )

    out = Path(out_root) / source_id
    _write(out / "spec.json", spec.model_dump_json(indent=2, exclude_none=True) + "\n")
    _write(out / "strategies.xml", write_fixatdl(spec))
    _write(out / "orchestra.xml", write_orchestra(spec).xml)
    write_site(spec, out / "site")
    source_info = {"id": source_id, "kind": entry["kind"], "path": str(path)}
    _write(out / "source.json", json.dumps(source_info, indent=2) + "\n")
    _write(out / "lint.json", json.dumps([f.to_dict() for f in findings], indent=2) + "\n")
    _write(out / "review.json", json.dumps(review, indent=2) + "\n")
    _write(out / "usage.json", json.dumps(extraction.usage_dict(max_input_tokens), indent=2) + "\n")
    return ConvertResult(out, review, [f for f in findings if f.severity != "error"], extraction)
