"""Static spec site: render one ``AlgoSpec`` as deterministic, self-contained HTML.

Stdlib only, one shared ``style.css``, no JS and no external assets, so the output works from
``file://``. All IR text is escaped. Every fact shows its citation, or a visible
``uncited`` marker: Concord does not hide guesses.
"""

from __future__ import annotations

import re
from html import escape
from pathlib import Path

from concord.diff import SEVERITIES, Change, DiffReport, diff_specs
from concord.ir import AlgoSpec, Citation, Edit, Parameter, Strategy

STYLE_CSS = """\
:root{--bg:#fff;--fg:#1a1a1a;--line:#ccc;--head:#f3f3f3;--code:#f3f3f3;--badge:#eee;--warn:#a40;
--breaking:#b00020;--additive:#1b6e2d;--cosmetic:#555;--link:#0b5cad}
@media (prefers-color-scheme:dark){:root{--bg:#161616;--fg:#e8e8e8;--line:#444;--head:#242424;
--code:#242424;--badge:#333;--warn:#ffb070;--breaking:#ff8a96;--additive:#7fd98f;
--cosmetic:#b5b5b5;--link:#7db7ff}}
body{font:15px/1.5 system-ui,sans-serif;margin:2rem auto;max-width:70rem;padding:0 1rem;
background:var(--bg);color:var(--fg)}
a{color:var(--link)}
table{border-collapse:collapse;width:100%;margin:1rem 0}
th,td{border:1px solid var(--line);padding:.3rem .5rem;text-align:left;vertical-align:top}
th{background:var(--head)}
code{background:var(--code);padding:0 .2rem}
.cite{font-size:.85em;margin-left:.3rem}
.uncited{font-size:.85em;margin-left:.3rem;color:var(--warn);font-weight:600}
.badge{font-size:.8em;background:var(--badge);border-radius:3px;padding:0 .3rem}
.sev{font-size:.8em;font-weight:700;letter-spacing:.04em;border:1px solid currentColor;
border-radius:3px;padding:0 .35rem;margin-right:.4rem}
.breaking{color:var(--breaking)}.additive{color:var(--additive)}.cosmetic{color:var(--cosmetic)}
.change{margin:.6rem 0;padding-left:.6rem;border-left:4px solid currentColor}
.change .loc{font-weight:600}.change small{display:block;color:var(--cosmetic)}
"""

_OPS = {
    "EQ": "==",
    "NE": "!=",
    "LT": "<",
    "LE": "<=",
    "GT": ">",
    "GE": ">=",
}


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "strategy"


def strategy_slugs(spec: AlgoSpec) -> dict[str, str]:
    """Map strategy name to a unique slug, keeping IR order."""
    used: set[str] = set()
    out: dict[str, str] = {}
    for s in spec.strategies:
        base = slugify(s.name)
        slug, n = base, 2
        while slug in used:
            slug = f"{base}-{n}"
            n += 1
        used.add(slug)
        out[s.name] = slug
    return out


def edit_text(edit: Edit, nested: bool = False) -> str:
    """Readable expression, e.g. ``Side == 1 AND OrderQty > 0``."""
    if edit.logic is not None:
        if edit.logic == "NOT":
            return f"NOT ({edit_text(edit.children[0], True)})"
        text = f" {edit.logic} ".join(edit_text(c, True) for c in edit.children)
        return f"({text})" if nested else text
    assert edit.field is not None and edit.operator is not None
    if edit.operator == "EX":
        return f"{edit.field} exists"
    if edit.operator == "NX":
        return f"{edit.field} does not exist"
    rhs = edit.field2 if edit.field2 is not None else edit.value
    return f"{edit.field} {_OPS[edit.operator]} {rhs}"


class _Renderer:
    def __init__(self, spec: AlgoSpec, report: DiffReport | None = None) -> None:
        self.spec = spec
        self.report = report
        self.sources = {s.id: s for s in spec.sources}
        self.slugs = strategy_slugs(spec)

    # -- fragments

    def cites(self, citations: list[Citation]) -> str:
        if not citations:
            return '<span class="uncited">uncited</span>'
        parts = []
        for c in citations:
            label = f"[{c.source_id}" + (f" p.{c.page}" if c.page else "") + "]"
            attrs = ""
            if c.quote:
                attrs += f' title="{escape(c.quote)}"'
            src = self.sources.get(c.source_id)
            url = src.url if src else None
            if url and url.lower().startswith(("http://", "https://")):
                href = url + (f"#page={c.page}" if c.page else "")
                parts.append(f'<a class="cite" href="{escape(href)}"{attrs}>{escape(label)}</a>')
            else:
                parts.append(f'<span class="cite"{attrs}>{escape(label)}</span>')
        return " ".join(parts)

    def page(self, title: str, body: str, root: str) -> str:
        return (
            "<!DOCTYPE html>\n"
            '<html lang="en"><head><meta charset="utf-8">'
            f"<title>{escape(title)}</title>"
            f'<link rel="stylesheet" href="{root}style.css"></head>\n'
            f'<body><p><a href="{root}index.html">Index</a></p>\n{body}\n</body></html>\n'
        )

    # -- pages

    def changes_page(self, report: DiffReport) -> str:
        h = ["<h1>Changes</h1>", f"<p>{summary_line(report)}</p>"]
        for sev in SEVERITIES:
            group = report.by_severity(sev)
            if not group:
                continue
            h.append(f'<h2 class="{sev}">{sev.capitalize()} ({len(group)})</h2>')
            h.extend(_change_html(c) for c in group)
        if not report.changes:
            h.append("<p>No differences.</p>")
        return self.page("Changes", "\n".join(h), "")

    def index(self) -> str:
        spec = self.spec
        h = [f"<h1>{escape(spec.provider or 'Algo specification')}</h1>"]
        if spec.description:
            h.append(f"<p>{escape(spec.description)}</p>")
        h.append(f"<p>Strategy identifier tag: <code>{spec.strategy_identifier_tag}</code></p>")
        if spec.sources:
            h.append("<h2>Sources</h2><ul>")
            for src in spec.sources:
                title = escape(src.title)
                if src.url and src.url.lower().startswith(("http://", "https://")):
                    title = f'<a href="{escape(src.url)}">{title}</a>'
                h.append(f"<li><code>{escape(src.id)}</code> {title}</li>")
            h.append("</ul>")
        if self.report is not None:
            counts = summary_line(self.report)
            h.append(
                f'<p><a href="changes.html">Changes from the previous version</a>: {counts}</p>'
            )
        h.append("<h2>Strategies</h2><table><tr><th>Name</th><th>Label</th>")
        h.append("<th>Wire value</th><th>Parameters</th></tr>")
        for s in spec.strategies:
            link = f"strategies/{self.slugs[s.name]}.html"
            h.append(
                f'<tr><td><a href="{escape(link)}">{escape(s.name)}</a></td>'
                f"<td>{escape(s.label or '')}</td>"
                f"<td><code>{escape(s.wire_value)}</code></td>"
                f"<td>{len(s.parameters)}</td></tr>"
            )
        h.append("</table>")
        return self.page(spec.provider or "Algo specification", "\n".join(h), "")

    def param_row(self, p: Parameter) -> str:
        enums = "<br>".join(
            f"<code>{escape(e.wire_value)}</code> — {escape(e.label or '')}"
            f"{self.cites(e.citations)}"
            for e in p.enum_values
        )
        rng = ""
        if p.min_value is not None or p.max_value is not None:
            rng = f"{escape(p.min_value or '')} .. {escape(p.max_value or '')}"
        mutable = ""
        if p.mutable_on_cxl_rpl is not None:
            mutable = "yes" if p.mutable_on_cxl_rpl else "no"
        desc = f"<br>{escape(p.description)}" if p.description else ""
        cells = [
            f"{escape(p.name)}{desc}{self.cites(p.citations)}",
            str(p.fix_tag) if p.fix_tag else "",
            escape(p.type.value),
            "yes" if p.required else "no",
            escape(p.default_value or ""),
            rng,
            enums,
            mutable,
        ]
        return "<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>"

    def strategy_page(self, s: Strategy) -> str:
        h = [f"<h1>{escape(s.label or s.name)}</h1>"]
        h.append(
            f"<p>Name <code>{escape(s.name)}</code>, wire value "
            f"<code>{escape(s.wire_value)}</code>, version {escape(s.version)}"
            f"{self.cites(s.citations)}</p>"
        )
        if s.description:
            h.append(f"<p>{escape(s.description)}</p>")
        h.append("<h2>Parameters</h2>")
        if s.parameters:
            h.append(
                "<table><tr><th>Name</th><th>FIX tag</th><th>Type</th><th>Required</th>"
                "<th>Default</th><th>Min .. Max</th><th>Values</th>"
                "<th>Mutable on cancel/replace</th></tr>"
            )
            h.extend(self.param_row(p) for p in s.parameters)
            h.append("</table>")
        else:
            h.append("<p>None.</p>")
        h.append("<h2>Rules</h2>")
        if s.edits:
            h.append("<ul>")
            for e in s.edits:
                h.append(
                    f"<li>{escape(e.message)}: valid when <code>{escape(edit_text(e.edit))}"
                    f"</code>{self.cites(e.citations)}</li>"
                )
            h.append("</ul>")
        else:
            h.append("<p>None.</p>")
        a = s.applicability
        rows = []
        for label, items in (
            ("Regions", a.regions),
            ("Markets", a.markets),
            ("Security types", a.security_types),
        ):
            if items:
                text = ", ".join(("" if i.include else "not ") + i.code for i in items)
                rows.append(f"<li>{label}: {escape(text)}</li>")
        h.append("<h2>Applicability</h2>")
        h.append(f"<ul>{''.join(rows)}</ul>" if rows else "<p>Unrestricted.</p>")
        return self.page(s.label or s.name, "\n".join(h), "../")


_NAME = re.compile(r"\[@name='([^']*)'\]")


def summary_line(report: DiffReport) -> str:
    return " · ".join(f"{len(report.by_severity(sev))} {sev}" for sev in SEVERITIES)


def _change_html(c: Change) -> str:
    names = _NAME.findall(c.path)
    where = " \u203a ".join(escape(n) for n in names) if names else escape(c.path)
    detail = ""
    if c.old is not None and c.new is not None:
        detail = f" <code>{escape(c.old)}</code> → <code>{escape(c.new)}</code>"
    return (
        f'<div class="change {c.severity}"><span class="sev">{c.severity.upper()}</span>'
        f'<span class="loc">{where}</span> — {escape(c.message)}{detail}'
        f"<small>{escape(c.path)}</small></div>"
    )


def render_site(spec: AlgoSpec, old: AlgoSpec | None = None) -> dict[str, str]:
    """Relative path -> content, in a stable order. Pass ``old`` to add a change report."""
    report = diff_specs(old, spec) if old is not None else None
    r = _Renderer(spec, report)
    files = {"index.html": r.index(), "style.css": STYLE_CSS}
    if report is not None:
        files["changes.html"] = r.changes_page(report)
    for s in spec.strategies:
        files[f"strategies/{r.slugs[s.name]}.html"] = r.strategy_page(s)
    return files


def write_site(spec: AlgoSpec, out_dir: str | Path, old: AlgoSpec | None = None) -> list[Path]:
    out = Path(out_dir)
    written = []
    for rel, text in render_site(spec, old).items():
        path = out / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))
        written.append(path)
    return written
