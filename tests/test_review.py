"""Review page (item 16a): built from a replayed `corpus convert` folder."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml
from test_lint import FIX42, LATEST

from concord.cli import main
from concord.extract import ReplayBackend
from concord.pipeline import convert_source
from concord.review import build_review, card_ids

DOC = """<html><body><h1>Overview</h1>
<p>Acme TWAP spreads the order evenly.</p>
<p>BadTag is tag 99 an Int.</p>
<p>Careful: &lt;script&gt;alert(1)&lt;/script&gt; &amp; more.</p>
<h2>Second</h2><p>Other strategy text.</p></body></html>"""


def _cite(page: int, quote: str, locator: str | None = None) -> dict:
    return {"source_id": "doc", "page": page, "quote": quote, "locator": locator}


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    cache = tmp_path / "cache" / "doc"
    cache.mkdir(parents=True)
    (cache / "doc.html").write_text(DOC)
    sources = tmp_path / "sources.yaml"
    sources.write_text(
        yaml.safe_dump(
            {"sources": [{"id": "doc", "title": "Synthetic", "kind": "html", "use": "ok"}]}
        )
    )
    rec = tmp_path / "rec"
    rec.mkdir()
    (rec / "page-1.json").write_text(
        json.dumps(
            {
                "strategies": [
                    {
                        "name": "TWAP",
                        "wire_value": "2",
                        "citations": [_cite(1, "Acme TWAP spreads the order evenly.", "Overview")],
                        "parameters": [
                            {
                                "name": "BadTag",
                                "type": "Int",
                                "fix_tag": 99,
                                "citations": [_cite(1, "BadTag is tag 99 an Int.", "Overview")],
                            }
                        ],
                    },
                    {"name": "Ghost", "wire_value": "9", "citations": [_cite(1, "never said")]},
                    {
                        "name": "Mis",
                        "wire_value": "5",
                        "citations": [_cite(1, "spreads the order evenly", "Wrong heading")],
                    },
                ]
            }
        )
    )
    (rec / "page-2.json").write_text(
        json.dumps(
            {
                "strategies": [
                    {
                        "name": "Other",
                        "wire_value": "2",  # already used by TWAP: a conflict
                        "citations": [_cite(2, "Other strategy text", "Second")],
                    }
                ]
            }
        )
    )
    dicts = tmp_path / "dicts"
    dicts.mkdir()
    (dicts / "OrchestraFIXLatest.xml").write_text(LATEST)
    (dicts / "OrchestraFIX42.xml").write_text(FIX42)
    convert_source(
        "doc",
        ReplayBackend(rec),
        sources=sources,
        cache_dir=tmp_path / "cache",
        out_root=tmp_path / "out",
        dict_dir=dicts,
    )
    return tmp_path / "out" / "doc"


def _index(folder: Path) -> str:
    return (folder / "review" / "index.html").read_text()


def test_counts_cards_and_kinds(folder: Path) -> None:
    build_review(folder)
    html = _index(folder)
    cards = re.findall(r'<div class="card" id="([0-9a-f]{12}(?:-\d+)?)"', html)
    reasons = json.loads((folder / "review.json").read_text())
    assert len(cards) == len(reasons) == len(set(cards))
    kinds = {r["reason"] for r in reasons}
    assert {"unverified", "conflict", "lint_error"} <= kinds
    for kind in ("unverified", "conflict", "lint_error"):
        assert f"{sum(1 for r in reasons if r['reason'] == kind)} {kind}" in html
    assert (folder / "review" / "style.css").is_file()
    assert '<link rel="stylesheet" href="style.css">' in html


def test_found_quote_is_marked_and_fabricated_quote_is_reported(folder: Path) -> None:
    build_review(folder)
    html = _index(folder)
    assert "<mark>spreads the order evenly</mark>" in html  # locator mismatch: quote is there
    assert "quote not found on page 1: never said" in html
    assert "not kept in spec.json" in html  # the dropped facts


def test_document_text_is_escaped(folder: Path) -> None:
    build_review(folder)
    html = _index(folder)
    assert "<script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_lint_error_card_has_no_page_and_conflict_shows_its_page(folder: Path) -> None:
    build_review(folder)
    html = _index(folder)
    assert "No source page (standard-tag check)." in html
    assert "Cited page 2, section Second" in html


def test_output_is_byte_identical_and_ids_are_stable(folder: Path) -> None:
    build_review(folder)
    first = {p.name: p.read_bytes() for p in (folder / "review").iterdir()}
    build_review(folder)
    assert first == {p.name: p.read_bytes() for p in (folder / "review").iterdir()}
    items = json.loads((folder / "review.json").read_text())
    assert card_ids(items) == card_ids(list(items))
    assert card_ids([items[0], items[0]])[1].endswith("-2")  # a repeat is still unique


def test_cli_and_source_override(folder: Path, tmp_path: Path, capsys) -> None:
    assert main(["review", str(folder)]) == 0
    assert "wrote 2 files" in capsys.readouterr().out
    (folder / "source.json").unlink()
    assert main(["review", str(folder)]) == 0
    assert "Source document not available" in _index(folder)
    alt = tmp_path / "alt.html"
    alt.write_text(DOC)
    assert main(["review", str(folder), "--source", str(alt)]) == 0
    assert "<mark>" in _index(folder)
    (folder / "review.json").write_text("{broken")
    assert main(["review", str(folder)]) == 1
    assert "review.json" in capsys.readouterr().err
