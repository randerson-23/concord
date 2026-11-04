"""PDF text layer tests, using a synthetic PDF generated here (no third-party content)."""

from __future__ import annotations

from pathlib import Path

import pytest

from concord.pdf import PdfError, extract_tables, normalize, read_pdf


def _make_pdf(pages: list[list[tuple[int, int, str]]]) -> bytes:
    """Minimal PDF: each page is a list of (x, y, text) in Helvetica 10pt."""
    objs: list[bytes] = []
    n = len(pages)
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(n))
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objs.append(f"<< /Type /Pages /Kids [{kids}] /Count {n} >>".encode())
    font_id = 3 + 2 * n
    for i, items in enumerate(pages):
        content_id = 4 + 2 * i
        objs.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {content_id} 0 R "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> >>".encode()
        )
        ops = (
            "BT /F1 10 Tf " + " ".join(f"1 0 0 1 {x} {y} Tm ({t}) Tj" for x, y, t in items) + " ET"
        )
        objs.append(f"<< /Length {len(ops)} >>\nstream\n{ops}\nendstream".encode())
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, o in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    page1 = [(72, 720, "Participation Rate Strategy"), (72, 700, "Sends slices over the day.")]
    page2 = [
        (72, 720, "Table 1 Parameters"),
        (72, 700, "Tag"),
        (200, 700, "Name"),
        (350, 700, "Required"),
        (72, 685, "7001"),
        (200, 685, "MaxPct"),
        (350, 685, "Y"),
        (72, 670, "7002"),
        (200, 670, "StartTime"),
        (350, 670, "N"),
    ]
    p = tmp_path / "synthetic.pdf"
    p.write_bytes(_make_pdf([page1, page2]))
    return p


def test_pages_are_numbered_from_one(sample_pdf: Path) -> None:
    pages = read_pdf(sample_pdf)
    assert [p.number for p in pages] == [1, 2]
    assert "Participation Rate Strategy" in pages[0].text
    assert "Participation Rate Strategy" not in pages[1].text


def test_table_rows_extracted_with_page(sample_pdf: Path) -> None:
    pages = read_pdf(sample_pdf)
    assert pages[0].tables == []
    (table,) = pages[1].tables
    assert table.page == 2
    assert table.rows == [
        ["Tag", "Name", "Required"],
        ["7001", "MaxPct", "Y"],
        ["7002", "StartTime", "N"],
    ]


def test_extract_tables_needs_two_rows_and_two_columns() -> None:
    assert extract_tables("one line only   two", 1) == []
    assert extract_tables("plain prose line\nanother line", 1) == []
    assert len(extract_tables("a   b\nc   d", 3)) == 1


def test_normalize_handles_whitespace_and_hyphenation() -> None:
    assert normalize("part-\n icipation   rate\n limit") == "participation rate limit"


def test_not_a_pdf_names_the_file(tmp_path: Path) -> None:
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"not a pdf")
    with pytest.raises(PdfError, match=r"bad\.pdf"):
        read_pdf(bad)
