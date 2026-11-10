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
    assert len(render_site(_spec())) == 5  # index, style.css, three strategies


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


# --------------------------------------------------------------------------- change report


def _versions() -> tuple[AlgoSpec, AlgoSpec]:
    def build(*, new: bool) -> AlgoSpec:
        style_values = [EnumValue(wire_value="P", label="Passive")]
        if new:
            style_values.append(EnumValue(wire_value="A", label="Aggressive"))
        params = [
            Parameter(name="Style", type=ParamType.CHAR, fix_tag=7001, enum_values=style_values)
        ]
        if not new:
            params.append(Parameter(name="Cap<b>", type=ParamType.INT, fix_tag=7002))
        return AlgoSpec(
            provider="Acme",
            strategies=[
                Strategy(name="VWAP", wire_value="1", parameters=params),
                Strategy(name="Legacy" if not new else "Classic", wire_value="2"),
            ],
        )

    return build(new=False), build(new=True)


def test_change_report_page_groups_changes_by_severity() -> None:
    old, new = _versions()
    files = render_site(new, old)
    page = files["changes.html"]
    assert "1 breaking · 1 additive · 1 cosmetic" in page
    order = [page.index(f">{h}") for h in ("Breaking (1)", "Additive (1)", "Cosmetic (1)")]
    assert order == sorted(order)
    breaking, rest = page.split(">Additive (1)")
    assert "Cap&lt;b&gt;" in breaking and "<b>" not in page
    assert "VWAP \u203a Cap&lt;b&gt;" in breaking
    assert "enum value" in rest and "Legacy" in rest.split(">Cosmetic (1)")[1]
    assert page.count('class="sev"') == 3 and "BREAKING" in page and "COSMETIC" in page
    index = files["index.html"]
    assert 'href="changes.html"' in index and "1 breaking · 1 additive · 1 cosmetic" in index
    assert 'href="style.css"' in page and "<style>" not in page


def test_no_diff_means_no_change_report() -> None:
    _, new = _versions()
    assert "changes.html" not in render_site(new)
    assert "changes.html" not in render_site(new)["index.html"]
    assert "No differences." in render_site(new, new)["changes.html"]


def test_change_report_is_deterministic_and_cli_writes_it(tmp_path: Path) -> None:
    old, new = _versions()
    assert render_site(new, old) == render_site(new, old)
    (tmp_path / "old.json").write_text(old.model_dump_json(exclude_none=True))
    (tmp_path / "new.json").write_text(new.model_dump_json(exclude_none=True))
    outs = []
    for name in ("a", "b"):
        out = tmp_path / name
        args = ["site", str(tmp_path / "new.json"), str(out), "--diff", str(tmp_path / "old.json")]
        assert main(args) == 0
        outs.append(out)
    for rel in ("changes.html", "index.html", "style.css"):
        assert (outs[0] / rel).read_bytes() == (outs[1] / rel).read_bytes()
    css = (outs[0] / "style.css").read_text()
    assert "prefers-color-scheme:dark" in css


# ------------------------------------------------------------------ amendability, navigation


def _amend_spec() -> AlgoSpec:
    return AlgoSpec(
        strategies=[
            Strategy(
                name="First",
                wire_value="1",
                parameters=[
                    Parameter(
                        name="Locked<i>", type=ParamType.INT, fix_tag=7001, mutable_on_cxl_rpl=False
                    ),
                    Parameter(
                        name="Free", type=ParamType.INT, fix_tag=7002, mutable_on_cxl_rpl=True
                    ),
                ],
            ),
            Strategy(name="Second", wire_value="2", label="Second Label"),
            Strategy(name="Third", wire_value="3"),
        ]
    )


def test_immutable_parameter_gets_badge_and_summary_above_the_table() -> None:
    page = render_site(_amend_spec())["strategies/first.html"]
    assert page.count("cannot amend</span>") == 1  # badge on Locked only
    summary = "<strong>Cannot amend on cancel/replace:</strong> <code>Locked&lt;i&gt;</code>"
    assert summary in page
    assert page.index(summary) < page.index("<table>")
    assert "<i>" not in page


def test_summary_says_none_stated_when_nothing_is_immutable() -> None:
    page = render_site(_amend_spec())["strategies/second.html"]
    assert "Cannot amend on cancel/replace:</strong> none stated." in page
    assert "badge cannot" not in page


def test_every_strategy_page_links_to_index_and_neighbours() -> None:
    files = render_site(_amend_spec())
    for slug in ("first", "second", "third"):
        assert 'href="../index.html"' in files[f"strategies/{slug}.html"]
    assert 'href="second.html">Second Label \u2192</a>' in files["strategies/first.html"]
    assert "\u2190" not in files["strategies/first.html"]
    second = files["strategies/second.html"]
    assert 'href="first.html">\u2190 First</a>' in second
    assert 'href="third.html">Third \u2192</a>' in second
    assert "\u2192" not in files["strategies/third.html"]
