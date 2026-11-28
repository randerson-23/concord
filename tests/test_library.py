"""Spec library: two specs, sidecar files, escaping, links and determinism."""

from __future__ import annotations

import json
import re
from pathlib import Path

from concord.cli import _load, main
from concord.ir import (
    AlgoSpec,
    Citation,
    EnumValue,
    Parameter,
    ParamType,
    SourceDocument,
    Strategy,
)
from concord.library import LibraryEntry, entry_for, fact_counts, render_library, write_library

FIXTURE = Path(__file__).parent / "fixtures" / "fixatdl" / "example_broker.xml"


def _cite() -> list[Citation]:
    return [Citation(source_id="doc", page=1, quote="q")]


def _second() -> AlgoSpec:
    return AlgoSpec(
        provider="Acme <Algo> & Co",
        sources=[SourceDocument(id="doc", title="Synthetic", kind="pdf")],
        strategy_identifier_tag=7700,
        strategies=[
            Strategy(
                name="Zeta",
                wire_value="Z<1>",
                citations=_cite(),
                parameters=[
                    Parameter(
                        name="Qty",
                        type=ParamType.INT,
                        fix_tag=9001,
                        citations=_cite(),
                        enum_values=[EnumValue(wire_value="A", citations=_cite())],
                    ),
                    Parameter(name="Bare", type=ParamType.INT, fix_tag=9002),
                ],
            ),
            Strategy(name="Alpha", wire_value="A1", label="Alpha Algo", citations=_cite()),
        ],
    )


def _entries() -> list[LibraryEntry]:
    fixture = _load(str(FIXTURE))
    return [LibraryEntry(fixture), LibraryEntry(_second(), lint=[], review=[])]


def test_fact_counts() -> None:
    assert fact_counts(_second()) == (4, 5)  # Bare is uncited
    cited, total = fact_counts(_load(str(FIXTURE)))
    assert cited == 0 and total > 0  # a FIXatdl file carries no citations


def test_index_rows_counts_and_escaping() -> None:
    files = render_library(_entries())
    index = files["index.html"]
    assert "Acme &lt;Algo&gt; &amp; Co" in index and "<Algo>" not in index
    assert "4 / 5 cited" in index
    assert "0 / " in index and "cited" in index
    fixture = _load(str(FIXTURE))
    assert fixture.provider and fixture.provider in index
    assert f"<td>{len(fixture.strategies)}</td>" in index
    assert "<td>Z&lt;1&gt;</td>" not in index and "<code>Z&lt;1&gt;</code>" in index


def test_finder_is_sorted_and_links_resolve() -> None:
    files = render_library(_entries())
    index = files["index.html"]
    finder = index.split("<h2>Strategy finder</h2>")[1]
    rows = re.findall(r"<tr><td>(.*?)</td><td><a href=\"(.*?)\">(.*?)</a>", finder)
    providers = [r[0] for r in rows]
    assert providers == sorted(providers, key=str.lower)
    acme = [r for r in rows if r[0].startswith("Acme")]
    assert [r[2] for r in acme] == ["Alpha Algo", "Zeta"]  # by strategy name, shown by label
    for _, href, _ in rows:
        assert href in files, href
    for href in re.findall(r'<a href="([^"]+)">', index):
        assert href in files, href


def test_sidecar_counts_and_dash_when_absent(tmp_path: Path) -> None:
    folder = tmp_path / "acme"
    folder.mkdir()
    spec_path = folder / "spec.json"
    spec_path.write_text(_second().model_dump_json())
    (folder / "lint.json").write_text(
        json.dumps([{"severity": "error"}, {"severity": "warning"}, {"severity": "warning"}])
    )
    (folder / "review.json").write_text(json.dumps([{"reason": "unverified"}]))
    row = render_library([entry_for(_second(), spec_path)])["index.html"]
    assert "<td>1</td><td>2</td><td>1</td></tr>" in row  # errors, warnings, review items
    bare = render_library([entry_for(_second(), tmp_path / "none" / "spec.json")])["index.html"]
    assert "<td>-</td><td>-</td><td>-</td></tr>" in bare


def test_same_provider_gets_distinct_slugs() -> None:
    a, b = _second(), _second().model_copy(update={"strategy_identifier_tag": 7701})
    files = render_library([LibraryEntry(a), LibraryEntry(b)])
    assert "acme-algo-co/index.html" in files and "acme-algo-co-2/index.html" in files


def test_output_is_independent_of_order_and_deterministic(tmp_path: Path) -> None:
    entries = _entries()
    assert render_library(entries) == render_library(list(reversed(entries)))
    write_library(entries, tmp_path / "a")
    write_library(list(reversed(entries)), tmp_path / "b")
    snap = lambda root: {  # noqa: E731
        str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()
    }
    assert snap(tmp_path / "a") == snap(tmp_path / "b")


def test_cli_with_spec_files_and_from_corpus(tmp_path: Path, capsys) -> None:
    corpus = tmp_path / "corpus-out"
    for name, tag in (("one", 7700), ("two", 7701)):
        (corpus / name).mkdir(parents=True)
        spec = _second().model_copy(update={"strategy_identifier_tag": tag})
        (corpus / name / "spec.json").write_text(spec.model_dump_json())
    (corpus / "one" / "review.json").write_text("[]")
    out = tmp_path / "lib"
    assert main(["library", str(out), str(FIXTURE), "--from-corpus", str(corpus)]) == 0
    assert "wrote" in capsys.readouterr().out
    index = (out / "index.html").read_text()
    assert index.count("4 / 5 cited") == 2 and "<td>0</td></tr>" in index
    assert (out / "style.css").is_file()
    assert main(["library", str(tmp_path / "empty")]) == 1  # no specs given
    assert "no specs" in capsys.readouterr().err
    bad = tmp_path / "bad"
    (bad / "x").mkdir(parents=True)
    (bad / "x" / "spec.json").write_text(_second().model_dump_json())
    (bad / "x" / "lint.json").write_text("{not json")
    assert main(["library", str(tmp_path / "o2"), "--from-corpus", str(bad)]) == 1
    assert "lint.json" in capsys.readouterr().err
