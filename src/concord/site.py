"""Static spec site: render one ``AlgoSpec`` as deterministic, self-contained HTML.

Stdlib only, inline CSS, no JS and no external assets, so the output works from
``file://``. All IR text is escaped. Every fact shows its citation, or a visible
``uncited`` marker: Concord does not hide guesses.
"""

from __future__ import annotations

import re
from html import escape
from pathlib import Path

from concord.ir import AlgoSpec, Citation, Edit, Parameter, Strategy

_CSS = """
body{font:15px/1.5 system-ui,sans-serif;margin:2rem auto;max-width:70rem;padding:0 1rem}
table{border-collapse:collapse;width:100%;margin:1rem 0}
th,td{border:1px solid #ccc;padding:.3rem .5rem;text-align:left;vertical-align:top}
th{background:#f3f3f3}
code{background:#f3f3f3;padding:0 .2rem}
.cite{font-size:.85em;margin-left:.3rem}
.uncited{font-size:.85em;margin-left:.3rem;color:#a40;font-weight:600}
.badge{font-size:.8em;background:#eee;border-radius:3px;padding:0 .3rem}
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
    def __init__(self, spec: AlgoSpec) -> None:
        self.spec = spec
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
            f"<title>{escape(title)}</title><style>{_CSS}</style></head>\n"
            f'<body><p><a href="{root}index.html">Index</a></p>\n{body}\n</body></html>\n'
        )

    # -- pages

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


def render_site(spec: AlgoSpec) -> dict[str, str]:
    """Relative path -> HTML, in a stable order."""
    r = _Renderer(spec)
    files = {"index.html": r.index()}
    for s in spec.strategies:
        files[f"strategies/{r.slugs[s.name]}.html"] = r.strategy_page(s)
    return files


def write_site(spec: AlgoSpec, out_dir: str | Path) -> list[Path]:
    out = Path(out_dir)
    written = []
    for rel, html in render_site(spec).items():
        path = out / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(html.encode("utf-8"))
        written.append(path)
    return written
