"""Static site tests: escaping, citations, determinism, slugs, CLI."""

from __future__ import annotations

from pathlib import Path

from concord.cli import _load, main
from concord.ir import (
    AlgoSpec,
    Citation,
    Edit,
    EnumValue,
    Parameter,
    ParamType,
    SourceDocument,
    Strategy,
    StrategyEdit,
)
from concord.site import edit_text, render_site, strategy_slugs

FIXTURE = Path(__file__).parent / "fixtures" / "fixatdl" / "example_broker.xml"


def _spec() -> AlgoSpec:
    cite = Citation(source_id="doc", page=3, quote='say "hi" <b>')
    return AlgoSpec(
        provider="Acme <Bank>",
        sources=[
            SourceDocument(id="doc", title="Acme spec", kind="pdf", url="https://example.com/a.pdf")
        ],
        strategies=[
            Strategy(
                name="VWAP",
                wire_value="1",
                description="<script>alert(1)</script>",
                citations=[cite],
                parameters=[
                    Parameter(
                        name="Style",
                        type=ParamType.CHAR,
                        fix_tag=7001,
                        enum_values=[EnumValue(wire_value="P", label="Passive", citations=[cite])],
                    ),
                    Parameter(name="Bare", type=ParamType.INT, fix_tag=7002),
                ],
                edits=[
                    StrategyEdit(
                        message="Need qty",
                        edit=Edit(
                            logic="AND",
                            children=[
                                Edit(field="Side", operator="EQ", value="1"),
                                Edit(field="OrderQty", operator="GT", value="0"),
                            ],
                        ),
                    )
                ],
            ),
            Strategy(name="V W-A P", wire_value="2"),
            Strategy(name="v-w-a-p", wire_value="3"),
        ],
    )


def test_escaping_and_citations() -> None:
    files = render_site(_spec())
    page = files["strategies/vwap.html"]
    assert "<script>" not in page
    assert "&lt;script&gt;" in page
    assert "Acme &lt;Bank&gt;" in files["index.html"]
    assert 'href="https://example.com/a.pdf#page=3"' in page
    assert "[doc p.3]" in page
    assert "&lt;b&gt;" in page and 'title="say &quot;hi&quot; &lt;b&gt;"' in page
    assert "<code>P</code> — Passive" in page
    assert page.count("uncited") >= 2  # Bare parameter and the rule
    assert "Side == 1 AND OrderQty &gt; 0" in page


def test_edit_text_nesting() -> None:
    e = Edit(
        logic="OR",
        children=[
            Edit(field="A", operator="EX"),
            Edit(logic="NOT", children=[Edit(field="B", operator="LE", field2="C")]),
        ],
    )
    assert edit_text(e) == "A exists OR NOT (B <= C)"


def test_slug_collisions() -> None:
    slugs = strategy_slugs(_spec())
    assert list(slugs.values()) == ["vwap", "v-w-a-p", "v-w-a-p-2"]
    assert len(render_site(_spec())) == 4


def test_deterministic(tmp_path: Path) -> None:
    spec = _load(str(FIXTURE))
    assert render_site(spec) == render_site(spec)
    a, b = tmp_path / "a", tmp_path / "b"
    assert main(["site", str(FIXTURE), str(a)]) == 0
    assert main(["site", str(FIXTURE), str(b)]) == 0
    fa = sorted(p.relative_to(a) for p in a.rglob("*.html"))
    assert fa == sorted(p.relative_to(b) for p in b.rglob("*.html"))
    assert all((a / p).read_bytes() == (b / p).read_bytes() for p in fa)


def test_cli_writes_expected_files(tmp_path: Path, capsys) -> None:
    spec = _load(str(FIXTURE))
    assert main(["site", str(FIXTURE), str(tmp_path / "out")]) == 0
    out = tmp_path / "out"
    assert (out / "index.html").exists()
    for slug in strategy_slugs(spec).values():
        assert (out / "strategies" / f"{slug}.html").exists()
    assert spec.provider is None or "<h1>" in (out / "index.html").read_text()
