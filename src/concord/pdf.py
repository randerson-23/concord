"""Page-aware text and table extraction from PDFs.

Every result carries its 1-based page number so facts extracted downstream can
cite ``(source_id, page, quote)``. Uses ``pypdf`` (BSD-3-Clause); never PyMuPDF
(AGPL). Documents are untrusted: nothing is executed and nothing is fetched.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PyPdfError

_CELL = re.compile(r"\S+(?: \S+)*")  # words separated by one space; 2+ spaces split cells
_START_TOL = 6  # columns of slack when matching a cell to a column (centred/right-aligned text)
_INDENT_STEP = 3  # first-column indent beyond this many columns marks a nested row


class PdfError(ValueError):
    """The file could not be read as a PDF."""


@dataclass(frozen=True)
class Table:
    """A table-like block of layout lines.

    ``rows`` holds one list of cells per logical row (wrapped description lines are
    merged into the row above). ``depths`` is parallel to ``rows``: 0 for a top-level
    row, 1 for a row indented in the first column, such as a repeating-group member.
    """

    page: int
    rows: list[list[str]]
    depths: list[int] = field(default_factory=list)


@dataclass(frozen=True)
class Page:
    number: int  # 1-based
    text: str  # reading-order text
    layout_text: str  # column-preserving text
    tables: list[Table] = field(default_factory=list)


def _cells(line: str) -> list[tuple[int, str]]:
    return [(m.start(), m.group()) for m in _CELL.finditer(line.expandtabs())]


class _Block:
    """One table being assembled from layout lines."""

    def __init__(self, anchor: list[tuple[int, str]]) -> None:
        self.first_col = anchor[0][0]
        self.tag_col = anchor[1][0]
        self.last_col = anchor[-1][0]
        self.width = len(anchor)
        self.rows: list[list[str]] = []
        self.starts: list[int] = []
        self.add_row(anchor)

    def add_row(self, cells: list[tuple[int, str]]) -> None:
        texts = [t for _, t in cells]
        if len(texts) > self.width:  # stray text right of the last column belongs to it
            texts = [*texts[: self.width - 1], " ".join(texts[self.width - 1 :])]
        self.rows.append(texts)
        self.starts.append(cells[0][0])

    def is_row(self, cells: list[tuple[int, str]]) -> bool:
        return len(cells) >= 2 and abs(cells[1][0] - self.tag_col) <= _START_TOL

    def is_continuation(self, cells: list[tuple[int, str]]) -> bool:
        start = cells[0][0]
        return start >= self.last_col - _START_TOL and start > self.first_col + _START_TOL

    def append_last_cell(self, cells: list[tuple[int, str]]) -> None:
        row = self.rows[-1]
        row[-1] = f"{row[-1]} {' '.join(t for _, t in cells)}"

    def append_first_cell(self, text: str) -> None:
        self.rows[-1][0] = f"{self.rows[-1][0]} {text}"

    def table(self, page: int) -> Table:
        base = min(self.starts)
        depths = [1 if st - base > _INDENT_STEP else 0 for st in self.starts]
        return Table(page=page, rows=self.rows, depths=depths)


def extract_tables(layout_text: str, page: int, min_rows: int = 2) -> list[Table]:
    """Find tables in column-preserving layout text.

    Columns are inferred from the first line of a block with 2+ cells. Later lines are
    rows when their second cell lines up with that block's second column. A line that
    starts in the last column continues the row above it (wrapped descriptions, with
    blank-line gaps allowed). Text under the first column, directly below a row, is
    appended to that row's first cell (for example ``(repeating group)``), and anything
    to its right continues the description. Anything else ends the table.
    """
    tables: list[Table] = []
    block: _Block | None = None
    prev_was_row = False

    def flush() -> None:
        nonlocal block
        if block is not None and len(block.rows) >= min_rows:
            tables.append(block.table(page))
        block = None

    for line in layout_text.splitlines():
        cells = _cells(line)
        if not cells:  # blank lines are gaps inside a table, not its end
            prev_was_row = False
            continue
        if block is not None:
            if block.is_continuation(cells):
                block.append_last_cell(cells)
                prev_was_row = False
                continue
            if block.is_row(cells):
                block.add_row(cells)
                prev_was_row = True
                continue
            if prev_was_row and cells[0][0] < block.tag_col - _START_TOL:
                rest = cells[1:]
                if not rest or block.is_continuation(rest):
                    block.append_first_cell(cells[0][1])
                    if rest:
                        block.append_last_cell(rest)
                    continue
            flush()
        if len(cells) >= 2:
            block = _Block(cells)
            prev_was_row = True
        else:
            prev_was_row = False
    flush()
    return tables


_WORD = re.compile(r"[\w'\u2019-]+")
_MAX_JOIN = 3  # most adjacent tokens a split glyph can span


def repair_split_glyphs(table: Table, plain_text: str) -> Table:
    """Rejoin words that layout extraction split mid-word (``TrdRegPublicationTy pe``).

    pypdf's layout mode can insert a space inside a word; its plain mode does not. A run
    of 2-3 adjacent cell tokens is replaced by their concatenation only when that word
    appears in the page's plain text *and* the split form does not. Genuine two-word
    cells therefore stay as they are. Cells are never rewritten from anywhere else.
    """
    words = set(_WORD.findall(plain_text))
    flat = " ".join(plain_text.split())

    def fix(cell: str) -> str:
        tokens = cell.split(" ")
        out: list[str] = []
        i = 0
        while i < len(tokens):
            for n in range(min(_MAX_JOIN, len(tokens) - i), 1, -1):
                run = tokens[i : i + n]
                if " ".join(run) not in flat and "".join(run) in words:
                    out.append("".join(run))
                    i += n
                    break
            else:
                out.append(tokens[i])
                i += 1
        return " ".join(out)

    rows = [[fix(c) for c in row] for row in table.rows]
    return Table(page=table.page, rows=rows, depths=list(table.depths))


def read_pdf(path: str | Path) -> list[Page]:
    """Extract every page. Raises :class:`PdfError` naming the file on failure."""
    p = Path(path)
    try:
        reader = PdfReader(str(p))
        if reader.is_encrypted:
            raise PdfError(f"{p}: encrypted PDF; expected an unencrypted document")
        pages: list[Page] = []
        for i, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            layout = page.extract_text(extraction_mode="layout") or ""
            tables = [repair_split_glyphs(t, text) for t in extract_tables(layout, i)]
            pages.append(Page(i, text, layout, tables))
        return pages
    except PdfError:
        raise
    except (PyPdfError, OSError, ValueError, KeyError) as e:
        raise PdfError(f"{p}: could not read as PDF ({e}); expected a valid PDF file") from e


def normalize(text: str) -> str:
    """Whitespace- and hyphenation-tolerant form, for quote matching."""
    text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)
    return re.sub(r"\s+", " ", text).strip()
