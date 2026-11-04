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

_COLUMN_GAP = re.compile(r"\s{2,}|\t")


class PdfError(ValueError):
    """The file could not be read as a PDF."""


@dataclass(frozen=True)
class Table:
    """A table-like block: consecutive layout lines that split into >=2 columns."""

    page: int
    rows: list[list[str]]


@dataclass(frozen=True)
class Page:
    number: int  # 1-based
    text: str  # reading-order text
    layout_text: str  # column-preserving text
    tables: list[Table] = field(default_factory=list)


def extract_tables(layout_text: str, page: int, min_rows: int = 2) -> list[Table]:
    """Find table-like blocks in layout text by splitting rows on wide gaps."""
    tables: list[Table] = []
    block: list[list[str]] = []

    def flush() -> None:
        if len(block) >= min_rows:
            tables.append(Table(page=page, rows=[list(r) for r in block]))
        block.clear()

    for line in layout_text.splitlines():
        cells = [c for c in _COLUMN_GAP.split(line.strip()) if c]
        if len(cells) >= 2:
            block.append(cells)
        else:
            flush()
    flush()
    return tables


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
            pages.append(Page(i, text, layout, extract_tables(layout, i)))
        return pages
    except PdfError:
        raise
    except (PyPdfError, OSError, ValueError, KeyError) as e:
        raise PdfError(f"{p}: could not read as PDF ({e}); expected a valid PDF file") from e


def normalize(text: str) -> str:
    """Whitespace- and hyphenation-tolerant form, for quote matching."""
    text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)
    return re.sub(r"\s+", " ", text).strip()
