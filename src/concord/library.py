"""Spec library: one index across many specs, each rendered with the per-spec site (item 12).

``render_library`` maps relative paths to content for ``OUT_DIR``: a top-level ``index.html`` (a
table of providers with accuracy and lint figures, then a strategy finder), the shared
``style.css``, and each spec's own site under ``<provider-slug>/``. Stdlib only, no JS, works from
``file://``, all text escaped. Output depends only on the specs and their sidecar files, never on
argument order.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any

from concord.ir import AlgoSpec
from concord.site import STYLE_CSS, render_site, slugify, strategy_slugs

UNKNOWN_PROVIDER = "(unknown provider)"


@dataclass(frozen=True)
class LibraryEntry:
    spec: AlgoSpec
    lint: list[dict[str, Any]] | None = None  # lint.json next to the spec, when present
    review: list[dict[str, Any]] | None = None  # review.json next to the spec, when present

    @property
    def provider(self) -> str:
        return self.spec.provider or UNKNOWN_PROVIDER


def _read_list(path: Path) -> list[dict[str, Any]] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"{path}: could not read ({exc}); expected a JSON list") from exc
    if not isinstance(data, list):
        raise ValueError(f"{path}: expected a JSON list, got {type(data).__name__}")
    return data


def entry_for(spec: AlgoSpec, spec_path: str | Path | None = None) -> LibraryEntry:
    """Attach ``lint.json`` and ``review.json`` found beside ``spec_path``, if any."""
    if spec_path is None:
        return LibraryEntry(spec)
    folder = Path(spec_path).parent
    return LibraryEntry(spec, _read_list(folder / "lint.json"), _read_list(folder / "review.json"))


def fact_counts(spec: AlgoSpec) -> tuple[int, int]:
    """(cited, total) over every fact that can carry a citation or a human review."""
    cited = total = 0
    for s in spec.strategies:
        nodes = [s, *s.edits]
        for p in s.parameters:
            nodes.append(p)
            nodes.extend(p.enum_values)
        total += len(nodes)
        # a human-verified fact counts as cited (D31)
        cited += sum(1 for n in nodes if n.citations or n.review is not None)
    return cited, total


def _sort_key(entry: LibraryEntry) -> tuple[str, str]:
    return entry.provider.lower(), entry.spec.model_dump_json(exclude_none=True)


def _count(items: list[dict[str, Any]] | None, key: str, value: str) -> str:
    if items is None:
        return "-"
    return str(sum(1 for i in items if isinstance(i, dict) and i.get(key) == value))


def _lint_counts(entry: LibraryEntry) -> tuple[str, str]:
    return _count(entry.lint, "severity", "error"), _count(entry.lint, "severity", "warning")


def _library_slugs(ordered: Sequence[LibraryEntry]) -> list[str]:
    used: set[str] = set()
    slugs = []
    for entry in ordered:
        base = slugify(entry.spec.provider) if entry.spec.provider else "spec"
        slug, n = base, 2
        while slug in used:
            slug = f"{base}-{n}"
            n += 1
        used.add(slug)
        slugs.append(slug)
    return slugs


def _page(body: str) -> str:
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en"><head><meta charset="utf-8"><title>Spec library</title>'
        '<link rel="stylesheet" href="style.css"></head>\n'
        f"<body>\n{body}\n</body></html>\n"
    )


def render_library(entries: Sequence[LibraryEntry]) -> dict[str, str]:
    """Relative path -> content, in a stable order, whatever order ``entries`` arrive in."""
    ordered = sorted(entries, key=_sort_key)
    slugs = _library_slugs(ordered)
    files: dict[str, str] = {"style.css": STYLE_CSS}
    providers = [
        "<tr><th>Provider</th><th>Strategies</th><th>Strategy tag</th><th>Parameters</th>"
        "<th>Cited facts</th><th>Lint errors</th><th>Lint warnings</th><th>Review items</th></tr>"
    ]
    finder: list[tuple[str, str, str, str, str]] = []
    for entry, slug in zip(ordered, slugs, strict=True):
        spec = entry.spec
        for rel, text in render_site(spec).items():
            files[f"{slug}/{rel}"] = text
        cited, total = fact_counts(spec)
        errors, warnings = _lint_counts(entry)
        review = "-" if entry.review is None else str(len(entry.review))
        params = sum(len(s.parameters) for s in spec.strategies)
        providers.append(
            f'<tr><td><a href="{escape(slug)}/index.html">{escape(entry.provider)}</a></td>'
            f"<td>{len(spec.strategies)}</td><td>{spec.strategy_identifier_tag}</td>"
            f"<td>{params}</td><td>{cited} / {total} cited</td>"
            f"<td>{errors}</td><td>{warnings}</td><td>{review}</td></tr>"
        )
        page_slugs = strategy_slugs(spec)
        for s in spec.strategies:
            href = f"{slug}/strategies/{page_slugs[s.name]}.html"
            finder.append((entry.provider, s.label or s.name, s.wire_value, href, s.name))
    finder.sort(key=lambda r: (r[0].lower(), r[4], r[3]))
    rows = [
        f'<tr><td>{escape(p)}</td><td><a href="{escape(href)}">{escape(label)}</a></td>'
        f"<td><code>{escape(wire)}</code></td></tr>"
        for p, label, wire, href, _ in finder
    ]
    body = [
        "<h1>Spec library</h1>",
        f"<p>{len(ordered)} specs, {len(finder)} strategies.</p>",
        "<h2>Providers</h2>",
        f"<table>{''.join(providers)}</table>",
        "<h2>Strategy finder</h2>",
        "<table><tr><th>Provider</th><th>Strategy</th><th>Wire value</th></tr>"
        f"{''.join(rows)}</table>",
    ]
    files["index.html"] = _page("\n".join(body))
    return dict(sorted(files.items()))


def write_library(entries: Sequence[LibraryEntry], out_dir: str | Path) -> list[Path]:
    out = Path(out_dir)
    written = []
    for rel, text in render_library(entries).items():
        path = out / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))
        written.append(path)
    return written
