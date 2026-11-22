"""`concord corpus convert`: replayed responses over synthetic cached documents, no network."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from test_lint import FIX42, LATEST
from test_pdf import _make_pdf

from concord.cli import main
from concord.corpus import CorpusError
from concord.extract import ReplayBackend
from concord.fixdict import DictionaryError
from concord.pipeline import convert_source

OUTPUTS = ["spec.json", "strategies.xml", "orchestra.xml", "review.json", "lint.json", "usage.json"]
HTML_DOC = """<html><body><h1>Overview</h1><p>Acme TWAP spreads the order evenly.</p>
<h2>Fields</h2><table><tr><th>Name</th><th>Tag</th></tr>
<tr><td>ExDestination</td><td>100</td></tr></table></body></html>"""


def _cite(page: int, quote: str, locator: str | None = None) -> dict:
    c = {"source_id": "pdf-doc", "page": page, "quote": quote}
    return c | ({"locator": locator} if locator else {})


@pytest.fixture
def world(tmp_path: Path) -> dict[str, Path]:
    """sources.yaml, a cache with one PDF and one HTML source, recordings, dictionaries."""
    cache = tmp_path / "cache"
    (cache / "pdf-doc").mkdir(parents=True)
    (cache / "pdf-doc" / "doc.pdf").write_bytes(
        _make_pdf([[(72, 700, "StrategyWireValue is 7"), (72, 680, "BadTag is tag 99 an Int")]])
    )
    (cache / "html-doc").mkdir()
    (cache / "html-doc" / "doc.html").write_text(HTML_DOC)
    sources = tmp_path / "sources.yaml"
    sources.write_text(
        yaml.safe_dump(
            {
                "sources": [
                    {"id": "pdf-doc", "title": "Synthetic PDF", "kind": "pdf", "use": "ok"},
                    {
                        "id": "html-doc",
                        "title": "Synthetic HTML",
                        "kind": "html",
                        "use": "ok",
                        "publisher": "Acme",
                        "url": "https://example.test/spec",
                    },
                    {"id": "closed", "title": "No", "kind": "pdf", "use": "restricted"},
                ]
            }
        )
    )
    rec_pdf = tmp_path / "rec-pdf"
    rec_pdf.mkdir()
    (rec_pdf / "page-1.json").write_text(
        json.dumps(
            {
                "strategies": [
                    {
                        "name": "VWAP",
                        "wire_value": "7",
                        "citations": [_cite(1, "StrategyWireValue is 7")],
                        "parameters": [
                            {
                                "name": "BadTag",
                                "type": "Int",
                                "fix_tag": 99,  # standard range, defined in no dictionary
                                "citations": [_cite(1, "BadTag is tag 99 an Int")],
                            }
                        ],
                    },
                    {"name": "Ghost", "wire_value": "9", "citations": [_cite(1, "never said")]},
                ]
            }
        )
    )
    (rec_pdf / "page-1.usage.json").write_text(json.dumps({"input_tokens": 40, "output_tokens": 9}))
    rec_html = tmp_path / "rec-html"
    rec_html.mkdir()
    cite = {"source_id": "html-doc", "page": 1, "locator": "Overview"}
    (rec_html / "page-1.json").write_text(
        json.dumps(
            {
                "strategies": [
                    {
                        "name": "TWAP",
                        "wire_value": "2",
                        "citations": [cite | {"quote": "Acme TWAP spreads the order evenly."}],
                    }
                ]
            }
        )
    )
    (rec_html / "page-2.json").write_text(
        json.dumps(
            {
                "strategies": [
                    {
                        "name": "TWAP",
                        "wire_value": "2",
                        "parameters": [
                            {
                                "name": "ExDestination",
                                "type": "String",
                                "fix_tag": 100,
                                "citations": [
                                    {
                                        "source_id": "html-doc",
                                        "page": 2,
                                        "locator": "Fields",
                                        "quote": "ExDestination 100",
                                    }
                                ],
                            }
                        ],
                    }
                ]
            }
        )
    )
    dicts = tmp_path / "dicts"
    dicts.mkdir()
    (dicts / "OrchestraFIXLatest.xml").write_text(LATEST)
    (dicts / "OrchestraFIX42.xml").write_text(FIX42)
    return {
        "tmp": tmp_path,
        "cache": cache,
        "sources": sources,
        "rec_pdf": rec_pdf,
        "rec_html": rec_html,
        "dicts": dicts,
    }


def _convert(w: dict[str, Path], sid: str, rec: str, out: str = "out", **kw):
    return convert_source(
        sid,
        ReplayBackend(w[rec]),
        sources=w["sources"],
        cache_dir=w["cache"],
        out_root=w["tmp"] / out,
        dict_dir=w["dicts"],
        **kw,
    )


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()
    }


def test_pdf_replay_writes_every_output_and_reviews_lint_and_unverified(world) -> None:
    res = _convert(world, "pdf-doc", "rec_pdf")
    out = world["tmp"] / "out" / "pdf-doc"
    assert res.out_dir == out
    for name in OUTPUTS:
        assert (out / name).is_file(), name
    assert (out / "site" / "index.html").is_file()
    review = json.loads((out / "review.json").read_text())
    reasons = {(r["reason"], r["location"]) for r in review}
    assert ("unverified", "Strategy[@name='Ghost']") in reasons
    lint = [r for r in review if r["reason"] == "lint_error"]
    assert [r["location"] for r in lint] == ["Strategy[@name='VWAP']/Parameter[@name='BadTag']"]
    assert json.loads((out / "spec.json").read_text())["strategies"][0]["name"] == "VWAP"
    usage = json.loads((out / "usage.json").read_text())
    assert usage["total"]["input_tokens"] == 40
    assert res.review == review


def test_html_replay_carries_locators_and_is_clean(world) -> None:
    res = _convert(world, "html-doc", "rec_html")
    assert res.review == []
    spec = json.loads((res.out_dir / "spec.json").read_text())
    assert spec["provider"] == "Acme" and spec["sources"][0]["kind"] == "html"
    strategy = spec["strategies"][0]
    assert strategy["citations"][0]["locator"] == "Overview"
    assert strategy["parameters"][0]["citations"][0]["locator"] == "Fields"
    assert json.loads((res.out_dir / "review.json").read_text()) == []


def test_output_is_byte_identical_across_runs(world) -> None:
    _convert(world, "pdf-doc", "rec_pdf", "a")
    _convert(world, "pdf-doc", "rec_pdf", "b")
    first, second = _snapshot(world["tmp"] / "a"), _snapshot(world["tmp"] / "b")
    assert first == second and len(first) > 6


def test_token_cap_is_threaded_through(world) -> None:
    res = _convert(world, "html-doc", "rec_html", max_input_tokens=1)
    assert [r["reason"] for r in res.review] == ["token_cap"]
    usage = json.loads((res.out_dir / "usage.json").read_text())
    assert usage["max_input_tokens"] == 1 and usage["stopped_at_page"] == 1


def test_bad_requests_fail_before_any_work(world) -> None:
    with pytest.raises(CorpusError, match="unknown source id"):
        _convert(world, "nope", "rec_pdf")
    with pytest.raises(CorpusError, match="use is 'restricted'"):
        _convert(world, "closed", "rec_pdf")
    (world["cache"] / "pdf-doc" / "doc.pdf").unlink()
    with pytest.raises(CorpusError, match="corpus fetch pdf-doc"):
        _convert(world, "pdf-doc", "rec_pdf")
    with pytest.raises(DictionaryError):
        convert_source(
            "html-doc",
            ReplayBackend(world["rec_html"]),
            sources=world["sources"],
            cache_dir=world["cache"],
            out_root=world["tmp"] / "o",
            dict_dir=world["tmp"] / "no-dicts",
        )
    assert not (world["tmp"] / "o").exists()


def test_cli_exit_codes(world, capsys) -> None:
    base = [
        "corpus",
        "convert",
        "--sources",
        str(world["sources"]),
        "--cache-dir",
        str(world["cache"]),
        "--out-dir",
        str(world["tmp"] / "cli"),
        "--dict-dir",
        str(world["dicts"]),
    ]
    assert main([*base, "html-doc", "--replay", str(world["rec_html"])]) == 0
    assert "no items need review" in capsys.readouterr().out
    assert main([*base, "pdf-doc", "--replay", str(world["rec_pdf"])]) == 2
    assert "lint_error" in capsys.readouterr().out
    assert main([*base, "nope", "--replay", str(world["rec_pdf"])]) == 1
