"""Text layer for HTML sources: one :class:`~concord.pdf.Page` per ``h1``/``h2`` section.

A page's ``number`` is the 1-based section index and its ``locator`` the section heading,
so a citation reads ``(source_id, page=N, locator=heading, quote)`` and the verifier and
extractor treat an HTML source like a PDF. Tables become column-aligned layout text, so
:func:`concord.pdf.extract_tables` finds them. Stdlib ``html.parser`` only: nothing is
executed or fetched, scripts and styles are dropped, nesting depth and file size are bounded.
"""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path

from concord.pdf import Page, extract_tables

MAX_DEPTH = 200  # element nesting beyond this is rejected (untrusted input)
MAX_BYTES = 20_000_000
_VOID = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param",
    "source", "track", "wbr",
}  # fmt: skip
_SKIP = {"script", "style", "head", "noscript", "template"}
_BLOCK = {
    "p", "div", "li", "ul", "ol", "pre", "blockquote", "section", "article", "tr",
    "h1", "h2", "h3", "h4", "h5", "h6", "table", "dd", "dt", "dl", "br",
}  # fmt: skip
_CELLS = {"td", "th"}
_GAP = "  "  # two spaces split cells in layout text (see pdf._CELL)


class HtmlError(ValueError):
    """The file could not be read as an HTML document."""


class _Section:
    def __init__(self, locator: str | None) -> None:
        self.locator = locator
        self.text: list[str] = []  # reading-order lines
        self.layout: list[str] = []  # column-preserving lines


class _Table:
    def __init__(self) -> None:
        self.rows: list[list[str]] = []
        self.row: list[str] | None = None
        self.cell: list[str] | None = None


def _clean(parts: list[str]) -> str:
    return " ".join("".join(parts).split())


class _Reader(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.sections: list[_Section] = []
        self.cur = _Section(None)
        self.buf: list[str] = []  # text of the current block
        self.depth = 0
        self.skip = 0
        self.heading: list[str] | None = None
        self.tables: list[_Table] = []

    # -- output helpers
    def _flush_block(self) -> None:
        line = _clean(self.buf)
        self.buf = []
        if line:
            self.cur.text.append(line)
            self.cur.layout.append(line)

    def _new_section(self, locator: str | None) -> None:
        self._flush_block()
        if self.cur.text or self.cur.locator is not None:
            self.sections.append(self.cur)
        self.cur = _Section(locator)

    # -- parser callbacks
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _VOID:
            if tag == "br":
                self._text_break()
            return
        self.depth += 1
        if self.depth > MAX_DEPTH:
            raise HtmlError(f"element nesting deeper than {MAX_DEPTH}; expected a normal document")
        if tag in _SKIP:
            self.skip += 1
            return
        if self.skip:
            return
        if tag in ("h1", "h2"):
            self._flush_block()
            self.heading = []
        elif tag == "table":
            if not self.tables:
                self._flush_block()
            self.tables.append(_Table())
        elif self.tables:
            t = self.tables[-1]
            if tag == "tr":
                self._end_row(t)
                t.row = []
            elif tag in _CELLS:
                self._end_cell(t)
                if t.row is None:
                    t.row = []
                t.cell = []
        elif tag in _BLOCK:
            self._flush_block()

    def _text_break(self) -> None:
        if self.tables and self.tables[-1].cell is not None:
            self.tables[-1].cell.append(" ")
        elif not self.skip:
            self._flush_block()

    def handle_endtag(self, tag: str) -> None:
        if tag in _VOID:
            return
        self.depth = max(0, self.depth - 1)
        if tag in _SKIP:
            self.skip = max(0, self.skip - 1)
            return
        if self.skip:
            return
        if tag in ("h1", "h2") and self.heading is not None:
            title = _clean(self.heading)
            self.heading = None
            self._new_section(title or None)
            if title:
                self.cur.text.append(title)
                self.cur.layout.append(title)
        elif tag in _CELLS and self.tables:
            self._end_cell(self.tables[-1])
        elif tag == "tr" and self.tables:
            self._end_row(self.tables[-1])
        elif tag == "table" and self.tables:
            self._close_table()
        elif tag in _BLOCK and not self.tables:
            self._flush_block()

    def handle_data(self, data: str) -> None:
        if self.skip:
            return
        if self.heading is not None:
            self.heading.append(data)
        elif self.tables:
            t = self.tables[-1]
            if t.cell is not None:
                t.cell.append(data)
        else:
            self.buf.append(data)

    # -- tables
    @staticmethod
    def _end_cell(t: _Table) -> None:
        if t.cell is not None and t.row is not None:
            t.row.append(_clean(t.cell))
        t.cell = None

    def _end_row(self, t: _Table) -> None:
        self._end_cell(t)
        if t.row and any(t.row):
            t.rows.append(t.row)
        t.row = None

    def _close_table(self) -> None:
        t = self.tables.pop()
        self._end_row(t)
        if self.tables:  # nested table: flatten into the enclosing cell
            outer = self.tables[-1]
            if outer.cell is not None:
                outer.cell.append(" ".join(c for r in t.rows for c in r if c))
            return
        if not t.rows:
            return
        ncols = max(len(r) for r in t.rows)
        widths = [0] * ncols
        for r in t.rows:
            for i, c in enumerate(r):
                widths[i] = max(widths[i], len(c))
        for r in t.rows:
            self.cur.text.append(" ".join(c for c in r if c))
            padded = [c.ljust(widths[i]) for i, c in enumerate(r[:-1])] + r[-1:]
            self.cur.layout.append(_GAP.join(padded).rstrip())
        self.cur.layout.append("")  # a blank line ends a table block

    def finish(self) -> list[_Section]:
        while self.tables:
            self._close_table()
        self._flush_block()
        if self.cur.text or self.cur.locator is not None:
            self.sections.append(self.cur)
        return self.sections


def read_html(path: str | Path) -> list[Page]:
    """Split an HTML document into one :class:`Page` per ``h1``/``h2`` section.

    Text before the first heading is its own section with no locator. A document with no
    text at all yields an empty list. Raises :class:`HtmlError` naming the file when it is
    too large, nested too deeply, or unreadable.
    """
    p = Path(path)
    try:
        raw = p.read_bytes()
    except OSError as e:
        raise HtmlError(f"{p}: could not read ({e}); expected an HTML file") from e
    if len(raw) > MAX_BYTES:
        raise HtmlError(f"{p}: {len(raw)} bytes; expected at most {MAX_BYTES}")
    reader = _Reader()
    try:
        reader.feed(raw.decode("utf-8", errors="replace"))
        reader.close()
    except HtmlError as e:
        raise HtmlError(f"{p}: {e}") from e
    pages: list[Page] = []
    for i, sec in enumerate(reader.finish(), start=1):
        layout = "\n".join(sec.layout)
        pages.append(
            Page(
                number=i,
                text="\n".join(sec.text),
                layout_text=layout,
                tables=extract_tables(layout, i),
                locator=sec.locator,
            )
        )
    return pages
