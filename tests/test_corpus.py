"""Corpus fetch and plan (item 25a, D22). The network is replaced; CI makes no requests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml
from test_pdf import _make_pdf

from concord import corpus
from concord.cli import main
from concord.corpus import CorpusError, fetch_sources, load_sources, plan_sources, plan_text

PDF = _make_pdf([[(72, 720, "Participation Rate Strategy"), (72, 700, "Sends slices.")]])
PAGE = (
    b"<html><head><title>Algo guide</title></head><body><h1>VWAP</h1><p>Tag 847</p></body></html>"
)
CHALLENGE = b"<html><head><title>Just a moment...</title></head><body>checking</body></html>"


def _src(sid: str, kind: str = "pdf", use: str = "ok") -> dict:
    return {"id": sid, "url": f"https://example.com/{sid}", "kind": kind, "use": use}


class FakeNet:
    def __init__(self, responses: dict[str, tuple[int, str, bytes]]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def __call__(self, url: str, timeout: float = 60.0):
        self.calls.append(url)
        return self.responses[url]


@pytest.fixture
def net(monkeypatch) -> FakeNet:
    fake = FakeNet(
        {
            "https://example.com/good-pdf": (200, "application/pdf", PDF),
            "https://example.com/fake-pdf": (200, "application/pdf", CHALLENGE),
            "https://example.com/good-html": (200, "text/html", PAGE),
            "https://example.com/challenge-html": (200, "text/html", CHALLENGE),
            "https://example.com/forbidden": (403, "text/html", b""),
        }
    )
    monkeypatch.setattr(corpus, "http_get", fake)
    return fake


def _status(results):
    return {r.id: r.status for r in results}


def test_pdf_is_fetched_with_meta(tmp_path: Path, net: FakeNet) -> None:
    results = fetch_sources([_src("good-pdf")], tmp_path)
    assert _status(results) == {"good-pdf": "fetched"}
    assert (tmp_path / "good-pdf" / "doc.pdf").read_bytes() == PDF
    meta = json.loads((tmp_path / "good-pdf" / "meta.json").read_text())
    assert meta["sha256"] == hashlib.sha256(PDF).hexdigest()
    assert meta["bytes"] == len(PDF) and meta["url"] == "https://example.com/good-pdf"
    assert meta["id"] == "good-pdf" and meta["kind"] == "pdf" and meta["fetched_at"]


def test_a_pdf_that_is_really_a_challenge_page_is_blocked(tmp_path: Path, net: FakeNet) -> None:
    (result,) = fetch_sources([_src("fake-pdf")], tmp_path)
    assert result.status == "blocked" and "not a PDF" in result.detail
    assert not (tmp_path / "fake-pdf").exists()


def test_html_ok_challenge_and_http_errors(tmp_path: Path, net: FakeNet) -> None:
    sources = [
        _src("good-html", "html"),
        _src("challenge-html", "html"),
        _src("forbidden", "html"),
    ]
    results = fetch_sources(sources, tmp_path)
    assert _status(results) == {
        "good-html": "fetched",
        "challenge-html": "blocked",
        "forbidden": "blocked",
    }
    assert [r.detail for r in results][1:] == ["bot-challenge page", "HTTP 403"]
    assert (tmp_path / "good-html" / "doc.html").read_bytes() == PAGE
    assert not (tmp_path / "forbidden").exists()


def test_only_use_ok_pdf_or_html_is_fetched(tmp_path: Path, net: FakeNet) -> None:
    sources = [
        _src("a", use="restricted"),
        _src("b", use="unreachable"),
        _src("c", kind="orchestra"),
        {"id": "d", "url": "https://example.com/d", "kind": "pdf"},  # no use field
    ]
    results = fetch_sources(sources, tmp_path)
    assert set(_status(results).values()) == {"skipped"}
    assert net.calls == []  # not even a request
    assert "use: restricted" in results[0].detail


def test_cache_is_reused_without_a_second_request(tmp_path: Path, net: FakeNet) -> None:
    fetch_sources([_src("good-pdf")], tmp_path)
    assert len(net.calls) == 1
    again = fetch_sources([_src("good-pdf")], tmp_path)
    assert _status(again) == {"good-pdf": "cached"} and len(net.calls) == 1


def test_an_existing_document_without_meta_gets_meta(tmp_path: Path, net: FakeNet) -> None:
    doc = tmp_path / "old" / "doc.pdf"
    doc.parent.mkdir()
    doc.write_bytes(PDF)
    assert _status(fetch_sources([_src("old")], tmp_path)) == {"old": "cached"}
    meta = json.loads((doc.parent / "meta.json").read_text())
    assert meta["sha256"] == hashlib.sha256(PDF).hexdigest()
    assert net.calls == []


def test_selecting_ids_and_unknown_ids(tmp_path: Path, net: FakeNet) -> None:
    sources = [_src("good-pdf"), _src("good-html", "html")]
    assert _status(fetch_sources(sources, tmp_path, ["good-html"])) == {"good-html": "fetched"}
    with pytest.raises(CorpusError, match="unknown source id"):
        fetch_sources(sources, tmp_path, ["nope"])


def test_plan_sizes_pdf_and_html(tmp_path: Path, net: FakeNet) -> None:
    sources = [_src("good-pdf"), _src("good-html", "html"), _src("missing", use="restricted")]
    fetch_sources(sources, tmp_path)
    rows = plan_sources(sources, tmp_path)
    by_id = {r.id: r for r in rows}
    assert set(by_id) == {"good-pdf", "good-html"}  # the unfetched one is not listed
    assert by_id["good-pdf"].units == "1 pages" and by_id["good-pdf"].chars > 20
    assert by_id["good-html"].chars == len("Algo guide VWAP Tag 847")
    assert by_id["good-html"].tokens == by_id["good-html"].chars // 4
    text = plan_text(rows)
    assert "total" in text and "estimate" in text and "cost" not in text
    assert "estimated input cost at 2.5 per million tokens" in plan_text(rows, 2.5)
    assert "run `concord corpus fetch`" in plan_text([])


def _sources_file(tmp_path: Path) -> Path:
    path = tmp_path / "sources.yaml"
    path.write_text(yaml.safe_dump({"sources": [_src("good-pdf"), _src("x", use="restricted")]}))
    return path


def test_cli_fetch_and_plan(tmp_path: Path, net: FakeNet, capsys) -> None:
    args = ["--sources", str(_sources_file(tmp_path)), "--cache-dir", str(tmp_path / "cache")]
    assert main(["corpus", "fetch", *args]) == 0
    out = capsys.readouterr().out
    assert "fetched  good-pdf" in out and "skipped  x" in out and "1 fetched, 1 skipped" in out
    assert main(["corpus", "plan", "--price-per-mtok", "3", *args]) == 0
    assert "good-pdf" in capsys.readouterr().out
    assert main(["corpus", "fetch", "nope", *args]) == 1
    assert "unknown source id" in capsys.readouterr().err


def test_load_sources_rejects_a_bad_file(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("not: a list")
    with pytest.raises(CorpusError, match="top-level 'sources' list"):
        load_sources(bad)
    assert len(load_sources(_sources_file(tmp_path))) == 2


def test_the_real_sources_file_parses() -> None:
    sources = load_sources(Path(__file__).parents[1] / "corpus" / "sources.yaml")
    assert len(sources) >= 25 and all("id" in s and "url" in s for s in sources)
