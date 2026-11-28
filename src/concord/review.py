"""Review screen, part 1: a static, read-only page for clearing a review list (item 16a).

``build_review(out_dir)`` reads a ``concord corpus convert`` output folder (``spec.json``,
``review.json``, ``lint.json``, ``source.json``), re-reads the source document with the same
readers the verifier uses, and writes ``review/index.html`` plus ``review/style.css``. Each item is
a card: the cited page on the left with the quote highlighted where it is found, the fact and the
reason on the right. No JS, works from ``file://``. Everything taken from a document or a spec is
escaped, since both are untrusted. Same folder in, same bytes out.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from html import escape
from pathlib import Path
from typing import Any

from concord.html import read_html
from concord.ir import AlgoSpec
from concord.pdf import Page, read_pdf
from concord.site import STYLE_CSS
from concord.verify import fold

REVIEW_CSS = """\
.cards{display:grid;gap:1rem}
.card{border:1px solid var(--line);border-radius:4px;padding:.6rem .8rem}
.card .cols{display:grid;grid-template-columns:1fr 1fr;gap:1rem}
@media (max-width:50rem){.card .cols{grid-template-columns:1fr}}
.card pre{white-space:pre-wrap;background:var(--code);padding:.5rem;max-height:22rem;overflow:auto}
mark{background:#ffe066;color:#1a1a1a}
.kind{font-size:.8em;font-weight:700;border:1px solid currentColor;border-radius:3px;
padding:0 .35rem;margin-right:.4rem}
.kind.unverified,.kind.verify_failed,.kind.lint_error,.kind.invalid_response{color:var(--breaking)}
.kind.conflict,.kind.lint_warning,.kind.token_cap{color:var(--warn)}
.miss{color:var(--breaking);font-weight:600}
"""

_SEG = re.compile(r"(Strategy|Parameter|EnumValue)\[@(?:name|wireValue)='([^']*)'\]")


def card_ids(items: list[dict[str, Any]]) -> list[str]:
    """Stable ids: a hash of location, kind and page; a repeat gets a numeric suffix."""
    seen: Counter[str] = Counter()
    ids = []
    for it in items:
        key = f"{it.get('location')}|{it.get('reason')}|{it.get('page')}"
        base = hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
        seen[base] += 1
        ids.append(base if seen[base] == 1 else f"{base}-{seen[base]}")
    return ids


def _read_json(path: Path, what: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(
            f"{path}: could not read {what} ({exc}); expected a convert folder"
        ) from exc


def _fact(spec: AlgoSpec | None, location: str) -> str:
    """A one-line description of the fact at ``location``, or why there is none."""
    if spec is None:
        return "spec.json not available"
    segs = _SEG.findall(location)
    if not segs:
        return "no fact (run-level item)"
    name = segs[0][1]
    try:
        strategy = next(s for s in spec.strategies if s.name == name)
    except StopIteration:
        return "not kept in spec.json"
    desc = f"strategy wire value {strategy.wire_value}"
    if len(segs) > 1:
        try:
            param = strategy.parameter(segs[1][1])
        except KeyError:
            return "not kept in spec.json"
        desc = f"{param.type.value}, tag {param.fix_tag if param.fix_tag else '-'}"
        if param.min_value is not None or param.max_value is not None:
            desc += f", range {param.min_value}..{param.max_value}"
        if len(segs) > 2:
            if segs[2][1] not in [e.wire_value for e in param.enum_values]:
                return "not kept in spec.json"
            desc = f"enum value {segs[2][1]} of {desc}"
    return desc


def _highlight(text: str, quote: str) -> tuple[str, str]:
    """(escaped page html, status). Marks the quote when it appears with its own spacing."""
    words = quote.split()
    if words:
        pattern = r"\s+".join(re.escape(w) for w in words)
        m = re.search(pattern, text)
        if m:
            html = f"{escape(text[: m.start()])}<mark>{escape(m.group())}</mark>"
            return html + escape(text[m.end() :]), "found"
    if fold(quote) and fold(quote) in fold(text):
        return escape(text), "found after normalising (hyphenation or typography)"
    return escape(text), "not found"


def _page_for(pages: list[Page], number: int | None) -> Page | None:
    if number is None or not 1 <= number <= len(pages):
        return None
    return pages[number - 1]


def _left(item: dict[str, Any], pages: list[Page] | None) -> str:
    number = item.get("page")
    if pages is None:
        return "<p>Source document not available; pass <code>--source</code>.</p>"
    page = _page_for(pages, number)
    if page is None:
        return "<p>No source page for this item.</p>"
    where = f"page {page.number}" + (f", section {escape(page.locator)}" if page.locator else "")
    out = [f"<h4>Cited {where}</h4>"]
    quotes = [q for q in item.get("quotes", []) if q.get("page") in (None, number) and q["quote"]]
    body = escape(page.text)
    for q in quotes:
        body, status = _highlight(page.text, q["quote"])
        if status == "not found":
            out.append(
                f'<p class="miss">quote not found on page {page.number}: {escape(q["quote"])}</p>'
            )
        else:
            out.append(f"<p>quote {status}</p>")
        break  # one highlighted quote per card keeps the markup unambiguous
    out.append(f"<pre>{body}</pre>")
    return "\n".join(out)


def _card(
    cid: str,
    item: dict[str, Any],
    pages: list[Page] | None,
    spec: AlgoSpec | None,
    extra: str = "",
) -> str:
    loc = item.get("location", "")
    names = [n for _, n in _SEG.findall(loc)]
    shown = " &rsaquo; ".join(escape(n) for n in names) if names else escape(loc)
    reason = escape(str(item.get("reason", "")))
    page = item.get("page")
    left = _left(item, pages) if page is not None else "<p>No source page (standard-tag check).</p>"
    right = (
        f'<p><span class="kind {reason}">{reason}</span><strong>{shown}</strong></p>'
        f"<p>{escape(str(item.get('detail', '')))}</p>"
        f"<p><small>Fact: {escape(_fact(spec, loc))}</small></p>"
        f"<p><small><code>{escape(loc)}</code></small></p>{extra}"
    )
    return (
        f'<div class="card" id="{cid}"><div class="cols"><div>{left}</div><div>{right}</div></div>'
        "</div>"
    )


def _live_form(cid: str, live: dict[str, Any]) -> str:
    """The plain HTML form for one card (no JavaScript) shown by ``concord review --serve``."""
    token = escape(live["token"])
    done = live["decisions"].get(cid)
    state = ""
    if isinstance(done, dict):
        who = f"{done.get('reviewer', '')}, {done.get('at', '')}"
        state = (
            f"<p><strong>Decision: {escape(str(done.get('decision')))}</strong> ({escape(who)})</p>"
        )
    return (
        f'{state}<form method="post" action="/decide?t={token}">'
        f'<input type="hidden" name="card" value="{escape(cid)}">'
        f'<p><label>Reviewer <input name="reviewer" value="{escape(live["reviewer"])}"></label> '
        '<label>Note <input name="note"></label></p>'
        '<p><label>Correct field <input name="field"></label> '
        '<label>to <input name="value"></label></p>'
        '<p><button name="decision" value="accept">Accept</button> '
        '<button name="decision" value="reject">Reject</button> '
        '<button name="decision" value="correct">Correct</button></p></form>'
    )


def _live_header(live: dict[str, Any]) -> str:
    token = escape(live["token"])
    applied = live.get("applied")
    status = "Not applied yet."
    if isinstance(applied, dict):
        status = (
            f"Last apply: {len(applied.get('applied', []))} applied, "
            f"{len(applied.get('unapplied', []))} unapplied, {len(applied.get('open', []))} open."
        )
    return (
        f'<form method="post" action="/apply?t={token}"><p>{escape(status)} '
        "<button>Apply decisions and rebuild</button> "
        f'<a href="/site/index.html?t={token}">Rebuilt site</a></p></form>'
    )


def render_review(
    items: list[dict[str, Any]],
    pages: list[Page] | None,
    spec: AlgoSpec | None,
    live: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Static page, or with ``live`` (token, decisions, applied, reviewer) the served version."""
    ids = card_ids(items)
    counts = Counter(str(i.get("reason")) for i in items)
    summary = (
        ", ".join(f"{n} {escape(k)}" for k, n in sorted(counts.items())) or "nothing to review"
    )
    cards = "\n".join(
        _card(c, i, pages, spec, _live_form(c, live) if live else "")
        for c, i in zip(ids, items, strict=True)
    )
    css = f"style.css?t={escape(live['token'])}" if live else "style.css"
    header = _live_header(live) if live else ""
    page = (
        "<!DOCTYPE html>\n"
        '<html lang="en"><head><meta charset="utf-8"><meta name="viewport" '
        'content="width=device-width,initial-scale=1"><title>Review</title>'
        f'<link rel="stylesheet" href="{css}"></head>\n'
        f"<body><h1>Review</h1><p>{len(items)} items: {summary}.</p>\n{header}"
        f'<div class="cards">\n{cards}\n</div></body></html>\n'
    )
    return {"index.html": page, "style.css": STYLE_CSS + REVIEW_CSS}


def load_items(root: Path) -> list[dict[str, Any]]:
    """The review list of a convert folder: ``review.json`` plus lint warnings as items."""
    items = list(_read_json(root / "review.json", "review.json"))
    lint = root / "lint.json"
    if lint.is_file():
        for f in _read_json(lint, "lint.json"):
            if f.get("severity") == "warning":
                items.append(
                    {
                        "page": None,
                        "location": f.get("location", ""),
                        "reason": "lint_warning",
                        "detail": f.get("message", ""),
                    }
                )
    return items


def load_context(
    root: Path, source: str | Path | None = None
) -> tuple[list[dict[str, Any]], list[Page] | None, AlgoSpec | None]:
    """Items, source pages (if the document can be found) and the extracted spec of a folder."""
    items = load_items(root)
    spec_file = root / "spec.json"
    spec = AlgoSpec.model_validate_json(spec_file.read_text()) if spec_file.is_file() else None
    pages = None
    src = Path(source) if source else None
    info = root / "source.json"
    if src is None and info.is_file():
        src = Path(_read_json(info, "source.json")["path"])
    if src is not None and src.is_file():
        pages = read_html(src) if src.suffix.lower() in (".html", ".htm") else read_pdf(src)
    return items, pages, spec


def build_review(out_dir: str | Path, source: str | Path | None = None) -> list[Path]:
    """Write ``OUT_DIR/review/``; returns the files written."""
    root = Path(out_dir)
    items, pages, spec = load_context(root, source)
    written = []
    for rel, text in render_review(items, pages, spec).items():
        path = root / "review" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))
        written.append(path)
    return written
