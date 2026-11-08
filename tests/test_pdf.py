"""PDF text layer tests, using a synthetic PDF generated here (no third-party content)."""

from __future__ import annotations

import itertools
import os
import re
import subprocess
from pathlib import Path

import pytest

from concord.pdf import PdfError, Table, extract_tables, normalize, read_pdf, repair_split_glyphs


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


# --------------------------------------------------------------------------- wrapped tables


def _field_table_pdf(tmp_path: Path) -> Path:
    """Synthetic 4-column field table: wrapped descriptions, blank-line gaps, a group."""
    cols = (72, 200, 255, 320)  # Field | Tag | Req | Description
    items: list[tuple[int, int, str]] = [(72, 740, "Alpha Broker FIX Guide - Page 4")]
    y = 700

    def row(depth: int, name: str, tag: str, req: str, lines: list[str]) -> None:
        nonlocal y
        items.extend(
            [(cols[0] + 14 * depth, y, name), (cols[1], y, tag), (cols[2], y, req)]
            + [(cols[3], y - 12 * i, text) for i, text in enumerate(lines)]
        )
        y -= 12 * len(lines) + 12  # blank-line gap before the next row

    items += [(cols[0], y + 20, "Field"), (cols[1], y + 20, "Tag"), (cols[2], y + 20, "Req")]
    items += [(cols[3], y + 20, "Description")]
    row(
        0,
        "AlgoStyle",
        "7001",
        "Y",
        ["Chooses the pacing style.", "Wraps onto a second line,", "then a third line."],
    )
    row(0, "NoLegs", "7010", "N", ["Number of legs."])
    items.append((72, y + 12, "(repeating group)"))
    row(1, "LegRatio", "7011", "N", ["Ratio of this leg.", "Wrapped too."])
    row(1, "LegSide", "7012", "N", ["Side of this leg."])
    row(0, "EndTime", "7002", "N", ["When to stop."])
    p = tmp_path / "field_table.pdf"
    p.write_bytes(_make_pdf([items]))
    return p


def test_wrapped_field_table_is_one_table_with_merged_rows(tmp_path: Path) -> None:
    (page,) = read_pdf(_field_table_pdf(tmp_path))
    (table,) = page.tables
    names = [r[0] for r in table.rows]
    assert names == [
        "Field",
        "AlgoStyle",
        "NoLegs (repeating group)",
        "LegRatio",
        "LegSide",
        "EndTime",
    ]
    assert [r[1] for r in table.rows] == ["Tag", "7001", "7010", "7011", "7012", "7002"]
    algo = table.rows[1]
    assert algo[3] == "Chooses the pacing style. Wraps onto a second line, then a third line."
    assert table.rows[3][3] == "Ratio of this leg. Wrapped too."


def test_group_members_are_deeper_than_their_parent(tmp_path: Path) -> None:
    (page,) = read_pdf(_field_table_pdf(tmp_path))
    (table,) = page.tables
    depth = {r[0]: d for r, d in zip(table.rows, table.depths, strict=True)}
    assert depth["AlgoStyle"] == 0
    assert depth["LegRatio"] == depth["LegSide"] == 1
    assert depth["EndTime"] == 0


def test_prose_after_a_table_ends_it() -> None:
    layout = "\n".join(
        [
            "Name      Tag    Req",
            "A         1      Y",
            "",
            "This paragraph is prose and not a row.",
            "Name2     Tag2   Req2",
            "B    2    N",
        ]
    )
    tables = extract_tables(layout, 1)
    assert [len(t.rows) for t in tables] == [2, 2]


# --------------------------------------------------------------------------- split glyphs


def test_split_word_in_a_cell_is_repaired_from_plain_text() -> None:
    table = Table(
        page=1, rows=[["OrderCap acity", "528", "N", "Capacity of the order"]], depths=[0]
    )
    plain = "OrderCapacity 528 N Capacity of the order"
    (row,) = repair_split_glyphs(table, plain).rows
    assert row == ["OrderCapacity", "528", "N", "Capacity of the order"]


def test_three_way_split_is_repaired() -> None:
    table = Table(page=1, rows=[["Trd RegPublication Type", "2669"]], depths=[0])
    assert repair_split_glyphs(table, "TrdRegPublicationType 2669").rows[0][0] == (
        "TrdRegPublicationType"
    )


def test_genuine_two_word_cell_is_left_alone() -> None:
    table = Table(page=1, rows=[["Order Capacity", "528"]], depths=[0])
    plain = "Order Capacity 528 and elsewhere OrderCapacity"
    assert repair_split_glyphs(table, plain).rows[0][0] == "Order Capacity"


def test_unrelated_cell_text_is_untouched() -> None:
    table = Table(page=1, rows=[["Rules of", "engagement"]], depths=[1])
    repaired = repair_split_glyphs(table, "something else entirely")
    assert repaired.rows == table.rows and repaired.depths == [1]


# --------------------------------------------------------------------------- real spec (opt-in)

_COMMANDER_URL = "https://www.commanderfx.com/downloads/Commander_Rules_Of_Engagement.pdf"


def _fetch_public_pdf(corpus_id: str, url: str) -> Path:
    """Fetch once into the git-ignored corpus cache; skip (no retry) if not a real PDF."""
    dest = Path(__file__).resolve().parents[1] / "corpus" / "cache" / corpus_id / "doc.pdf"
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(
                [
                    "curl",
                    "-sSL",
                    "--max-time",
                    "90",
                    "-A",
                    "concord-corpus-fetch/0.1",
                    "-o",
                    str(dest),
                    url,
                ],
                check=True,
                capture_output=True,
            )
        except (subprocess.CalledProcessError, OSError) as e:
            dest.unlink(missing_ok=True)
            pytest.skip(f"cannot fetch {corpus_id}: {e}")
    if dest.read_bytes()[:4] != b"%PDF":
        dest.unlink()
        pytest.skip(f"{corpus_id}: server did not return a PDF (bot challenge?)")
    return dest


@pytest.mark.skipif(
    os.environ.get("CONCORD_PUBLIC_SAMPLES") != "1", reason="CONCORD_PUBLIC_SAMPLES not set"
)
def test_real_spec_field_table_page() -> None:
    """Commander FIX (use: ok in corpus/sources.yaml), page 28. Asserts names and tags only."""
    pages = read_pdf(_fetch_public_pdf("commanderfx-rules-of-engagement", _COMMANDER_URL))
    page = pages[27]
    rows = [
        (r[0].split(" (")[0], r[1], d)
        for t in page.tables
        for r, d in zip(t.rows, t.depths, strict=True)
    ]
    found = {(name, tag): depth for name, tag, depth in rows}
    for key in [("TargetStrategy", "847"), ("ExDestination", "100"), ("ClOrdLinkType", "20027")]:
        assert key in found, f"{key} missing from {sorted(found)[:8]}"
    assert found[("ClOrdLinkType", "20027")] > found[("NoClOrdLinkID", "20026")]
    assert len(page.tables) <= 3  # was dozens of 2-row fragments
    words = set(re.findall(r"[\w'\u2019-]+", page.text))
    for table in page.tables:
        for row in table.rows:
            tokens = row[0].split(" ")
            for a, b in itertools.pairwise(tokens):
                if a + b in words and f"{a} {b}" not in page.text:
                    pytest.fail(f"split glyph left in a name cell: {row[0]!r}")
