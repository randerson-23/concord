"""HTML text layer tests on a synthetic page (no third-party content)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from concord.cli import main
from concord.extract import build_prompt
from concord.html import MAX_DEPTH, HtmlError, read_html
from concord.ir import Citation, SourceDocument
from concord.verify import Status, verify_citation

DOC = """<!doctype html><html><head><title>Ignored title</title>
<style>.x { color: red }</style><script>var secret = "SCRIPTED";</script></head>
<body>
<p>Preamble before any heading.</p>
<h1>Overview</h1>
<p>Acme VWAP slices the order <b>over</b> the day.</p>
<h2>Parameters &amp; tags</h2>
<p>Fields for the strategy.</p>
<table>
<tr><th>Name</th><th>Tag</th><th>Description</th></tr>
<tr><td>TargetStrategy</td><td>847</td><td>Strategy id,
  wrapped here.</td></tr>
<tr><td>StartTime</td><td>168</td><td>When to begin</td></tr>
</table>
<h3>Not a section</h3><p>Stays in section 3.</p>
</body></html>
"""


@pytest.fixture
def doc(tmp_path: Path) -> Path:
    p = tmp_path / "spec.html"
    p.write_text(DOC)
    return p


def test_sections_and_locators(doc: Path) -> None:
    pages = read_html(doc)
    assert [p.number for p in pages] == [1, 2, 3]
    assert [p.locator for p in pages] == [None, "Overview", "Parameters & tags"]
    assert "Preamble" in pages[0].text
    assert "slices the order over the day." in pages[1].text
    assert "Stays in section 3." in pages[2].text
    joined = "\n".join(p.text for p in pages)
    assert "SCRIPTED" not in joined and "Ignored title" not in joined and "color" not in joined


def test_table_rows(doc: Path) -> None:
    (table,) = read_html(doc)[2].tables
    assert table.page == 3
    assert table.rows == [
        ["Name", "Tag", "Description"],
        ["TargetStrategy", "847", "Strategy id, wrapped here."],
        ["StartTime", "168", "When to begin"],
    ]


def test_verify_pass_and_fail(doc: Path) -> None:
    pages = read_html(doc)

    def cite(page: int, quote: str) -> Citation:
        return Citation(source_id="s", page=page, quote=quote, locator="x")

    assert verify_citation(cite(3, "TargetStrategy 847 Strategy id"), pages)[0] is Status.VERIFIED
    assert verify_citation(cite(2, "slices the order over the day"), pages)[0] is Status.VERIFIED
    assert verify_citation(cite(3, "slices the order"), pages) == (Status.WRONG_PAGE, (2,))
    assert verify_citation(cite(2, "invented rule"), pages)[0] is Status.NOT_FOUND


def test_prompt_names_the_section(doc: Path) -> None:
    pages = read_html(doc)
    src = SourceDocument(id="s", title="T", kind="html")
    assert 'section "Overview"' in build_prompt(src, pages[1])
    assert 'locator="Overview"' in build_prompt(src, pages[1])
    assert "page 1" in build_prompt(src, pages[0])  # no heading: falls back to the page number


def test_deterministic(doc: Path) -> None:
    assert read_html(doc) == read_html(doc)


def test_bounded_depth_and_size(tmp_path: Path) -> None:
    deep = tmp_path / "deep.html"
    deep.write_text("<div>" * (MAX_DEPTH + 5) + "x")
    with pytest.raises(HtmlError, match=r"deep\.html.*nesting"):
        read_html(deep)
    with pytest.raises(HtmlError, match="could not read"):
        read_html(tmp_path / "missing.html")


def test_empty_and_malformed(tmp_path: Path) -> None:
    p = tmp_path / "e.html"
    p.write_text("<html><body></body></html>")
    assert read_html(p) == []
    p.write_text("<h1>Only</h1><table><tr><td>a<td>b</table><p>unclosed <b>bold")
    pages = read_html(p)
    assert pages[0].locator == "Only" and "unclosed bold" in pages[0].text


def test_cli_verify_accepts_html(doc: Path, tmp_path: Path) -> None:
    spec = tmp_path / "spec.json"
    spec.write_text(
        '{"ir_version": "0.1", "provider": "Acme", "sources": '
        '[{"id": "s", "title": "T", "kind": "html"}], "strategies": []}'
    )
    assert main(["verify", str(spec), "--source", f"s={doc}"]) == 0


@pytest.mark.skipif(
    os.environ.get("CONCORD_PUBLIC_SAMPLES") != "1", reason="CONCORD_PUBLIC_SAMPLES not set"
)
def test_real_saxo_page_has_tag_847_in_a_table() -> None:
    path = Path(__file__).parents[1] / "corpus/cache/saxo-algo-order-fix-tags/doc.html"
    if not path.exists():
        pytest.skip("run `concord corpus fetch saxo-algo-order-fix-tags` first")
    pages = read_html(path)
    assert pages
    assert any(r[0:2] and "847" in r for p in pages for t in p.tables for r in t.rows)
