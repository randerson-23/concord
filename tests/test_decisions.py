"""Human decisions on review cards (item 16b part 1, D31)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from test_review import folder  # noqa: F401  (fixture)

from concord.cli import main
from concord.decisions import apply_decisions, apply_to_folder, load_decisions
from concord.ir import AlgoSpec, EnumValue, Parameter, ParamType, Strategy
from concord.library import fact_counts
from concord.review import card_ids
from concord.site import render_site

AT = "2026-11-26"


def _spec() -> AlgoSpec:
    return AlgoSpec(
        provider="Acme",
        strategies=[
            Strategy(
                name="VWAP",
                wire_value="1",
                parameters=[
                    Parameter(name="A", type=ParamType.INT, fix_tag=9001, max_value="5"),
                    Parameter(name="B", type=ParamType.INT, fix_tag=9002),
                    Parameter(
                        name="C",
                        type=ParamType.STRING,
                        fix_tag=9003,
                        enum_values=[EnumValue(wire_value="P"), EnumValue(wire_value="X")],
                    ),
                ],
            ),
            Strategy(name="TWAP", wire_value="2"),
        ],
    )


P = "Strategy[@name='VWAP']"
ITEMS = [
    {"page": None, "location": f"{P}/Parameter[@name='A']", "reason": "lint_error", "detail": "a"},
    {"page": 1, "location": f"{P}/Parameter[@name='B']", "reason": "conflict", "detail": "b"},
    {
        "page": 1,
        "location": f"{P}/Parameter[@name='C']/EnumValue[@wireValue='X']",
        "reason": "verify_failed",
        "detail": "c",
    },
    {"page": 1, "location": "Strategy[@name='Gone']", "reason": "unverified", "detail": "d"},
    {"page": None, "location": "Strategy[@name='TWAP']", "reason": "lint_warning", "detail": "w"},
]


def _d(decision: str, **extra) -> dict:
    return {"decision": decision, "reviewer": "ryan", "at": AT, **extra}


def test_accept_marks_the_fact_human_verified_and_counts_it_cited() -> None:
    ids = card_ids(ITEMS)
    res = apply_decisions(_spec(), ITEMS, {ids[0]: _d("accept", note="checked")})
    a = res.spec.strategies[0].parameter("A")
    assert a.review.decision == "accepted" and a.review.reviewer == "ryan"
    assert a.review.at == date(2026, 11, 26) and a.review.card_id == ids[0]
    assert fact_counts(res.spec) == (1, 7)  # strategy x2, params x3, enum values x2
    html = render_site(res.spec)["strategies/vwap.html"]
    assert "human-verified" in html and "ryan, 2026-11-26" in html


def test_reject_drops_a_parameter_an_enum_value_and_nothing_else() -> None:
    ids = card_ids(ITEMS)
    res = apply_decisions(_spec(), ITEMS, {ids[1]: _d("reject"), ids[2]: _d("reject")})
    vwap = res.spec.strategy("VWAP")
    assert [p.name for p in vwap.parameters] == ["A", "C"]
    assert [e.wire_value for e in vwap.parameter("C").enum_values] == ["P"]
    assert {a["decision"] for a in res.applied} == {"reject"}


def test_correct_applies_the_value_and_records_it() -> None:
    ids = card_ids(ITEMS)
    d = _d("correct", corrections={"max_value": "100"})
    res = apply_decisions(_spec(), ITEMS, {ids[0]: d})
    a = res.spec.strategies[0].parameter("A")
    assert a.max_value == "100" and a.review.decision == "corrected"
    bad = apply_decisions(_spec(), ITEMS, {ids[0]: _d("correct", corrections={"fix_tag": "x"})})
    assert bad.unapplied[0]["reason"].startswith("correction rejected")
    assert bad.spec.strategies[0].parameter("A").max_value == "5"  # unchanged


def test_dropped_facts_open_cards_and_warnings() -> None:
    ids = card_ids(ITEMS)
    res = apply_decisions(_spec(), ITEMS, {ids[3]: _d("accept"), "nope": _d("accept")})
    reasons = {u["card_id"]: u["reason"] for u in res.unapplied}
    assert "does not carry the dropped fact" in reasons[ids[3]]  # an older review file
    assert reasons["nope"] == "unknown card id"
    assert res.open_cards == ids[:3]  # the lint warning never blocks
    assert not res.resolved
    rejected = apply_decisions(_spec(), ITEMS, {ids[3]: _d("reject")})
    assert any(a["card_id"] == ids[3] for a in rejected.applied)  # already absent


def test_decisions_file_is_validated(tmp_path: Path) -> None:
    f = tmp_path / "decisions.json"
    for bad, msg in [
        ({"x": _d("maybe")}, "decision must be"),
        ({"x": {**_d("accept"), "reviewer": " "}}, "reviewer is required"),
        ({"x": {**_d("accept"), "at": "yesterday"}}, "ISO date"),
        ({"x": _d("correct")}, "non-empty 'corrections'"),
        ({"x": _d("correct", corrections={"citations": []})}, "may not touch"),
    ]:
        f.write_text(json.dumps(bad))
        with pytest.raises(ValueError, match=msg):
            load_decisions(f)
    f.write_text("[1]")
    with pytest.raises(ValueError, match="JSON object"):
        load_decisions(f)


def test_folder_apply_changes_outputs_and_is_idempotent(folder: Path, capsys) -> None:  # noqa: F811
    items = json.loads((folder / "review.json").read_text())
    ids = card_ids(items)
    lint = next(i for i, it in enumerate(items) if it["reason"] == "lint_error")
    (folder / "decisions.json").write_text(json.dumps({ids[lint]: _d("accept", note="ok")}))
    before = (folder / "spec.json").read_bytes()

    res = apply_to_folder(folder)
    assert (folder / "spec.extracted.json").read_bytes() == before
    spec = AlgoSpec.model_validate_json((folder / "spec.json").read_text())
    assert spec.strategy("TWAP").parameter("BadTag").review.decision == "accepted"
    assert "human-verified" in (folder / "site" / "strategies" / "twap.html").read_text()
    assert not res.resolved  # the other cards are still open
    snap = {p.name: p.read_bytes() for p in folder.iterdir() if p.is_file()}
    apply_to_folder(folder)
    assert snap == {p.name: p.read_bytes() for p in folder.iterdir() if p.is_file()}
    applied = json.loads((folder / "applied.json").read_text())
    assert [a["card_id"] for a in applied["applied"]] == [ids[lint]]

    assert main(["review", str(folder), "--apply-decisions"]) == 2
    assert "open" in capsys.readouterr().out
    everything = {cid: _d("reject") for cid in ids}
    everything[ids[lint]] = _d("accept")
    (folder / "decisions.json").write_text(json.dumps(everything))
    assert main(["review", str(folder), "--apply-decisions"]) == 0
    assert "unapplied 0, open 0" in capsys.readouterr().out


# ------------------------------------------------------------------ restoring dropped facts


def _dropped_items() -> list[dict]:
    p = "Strategy[@name='VWAP']"
    return [
        {
            "page": 1,
            "location": f"{p}/Parameter[@name='New']",
            "reason": "unverified",
            "detail": "parameter",
            "fact": {"name": "New", "type": "Int", "fix_tag": 9100, "max_value": "5"},
        },
        {
            "page": 1,
            "location": f"{p}/Parameter[@name='C']/EnumValue[@wireValue='Z']",
            "reason": "unverified",
            "detail": "enum",
            "fact": {"wire_value": "Z", "label": "Zed"},
        },
        {
            "page": 1,
            "location": "Strategy[@name='Lost']/Parameter[@name='Orphan']",
            "reason": "unverified",
            "detail": "parameter",
            "fact": {"name": "Orphan", "type": "Int", "fix_tag": 9200},
        },
        {
            "page": 1,
            "location": "Strategy[@name='Lost']",
            "reason": "unverified",
            "detail": "strategy",
            "fact": {"name": "Lost", "wire_value": "7"},
        },
    ]


def test_extraction_stores_the_dropped_fact_without_its_citations() -> None:
    from test_extract import PAGES, RESPONSES, SRC, Recorded

    from concord.extract import extract_spec

    res = extract_spec(
        PAGES, SRC, Recorded({n: json.dumps(r) for n, r in RESPONSES.items()}), provider="Acme"
    )
    items = [r.to_dict() for r in res.review if r.reason == "unverified"]
    nocite = next(i for i in items if i["location"].endswith("Parameter[@name='NoCite']"))
    assert nocite["fact"]["name"] == "NoCite" and nocite["fact"]["fix_tag"] == 9003
    assert all('"citations"' not in json.dumps(i["fact"]) for i in items)  # stored uncited
    ghost = next(i for i in items if i["location"] == "Strategy[@name='Ghost']")
    assert ghost["fact"]["wire_value"] == "9" and ghost["quotes"]
    # the Accept path: restoring it from the stored JSON gives a valid, reviewed spec
    ids = card_ids(items)
    res2 = apply_decisions(res.spec, items, {ids[items.index(nocite)]: _d("accept")})
    restored = res2.spec.strategy("VWAP").parameter("NoCite")
    assert restored.fix_tag == 9003 and restored.review.decision == "accepted"


def test_accept_and_correct_restore_dropped_facts_in_place() -> None:
    items = _dropped_items()
    ids = card_ids(items)
    decisions = {
        ids[0]: _d("correct", corrections={"max_value": "50"}),
        ids[1]: _d("accept"),
        ids[3]: _d("accept"),
        ids[2]: _d("accept"),  # listed before its Strategy; parents are applied first
    }
    res = apply_decisions(_spec(), items, decisions)
    assert res.resolved and len(res.applied) == 4
    vwap = res.spec.strategy("VWAP")
    assert [p.name for p in vwap.parameters] == ["A", "B", "C", "New"]  # appended, in order
    new = vwap.parameter("New")
    assert new.max_value == "50" and new.review.decision == "corrected"
    assert [e.wire_value for e in vwap.parameter("C").enum_values] == ["P", "X", "Z"]
    assert vwap.parameter("C").enum_values[-1].review.decision == "accepted"
    assert [s.name for s in res.spec.strategies] == ["VWAP", "TWAP", "Lost"]
    assert res.spec.strategy("Lost").parameter("Orphan").review.card_id == ids[2]


def test_reject_leaves_dropped_facts_out_and_a_missing_parent_is_named() -> None:
    items = _dropped_items()
    ids = card_ids(items)
    res = apply_decisions(_spec(), items, {ids[0]: _d("reject"), ids[2]: _d("accept")})
    assert [p.name for p in res.spec.strategy("VWAP").parameters] == ["A", "B", "C"]
    (bad,) = res.unapplied
    assert bad["card_id"] == ids[2]
    assert "parent Strategy[@name='Lost'] is also dropped; restore it first" in bad["reason"]
    invalid = apply_decisions(_spec(), items, {ids[0]: _d("correct", corrections={"fix_tag": "x"})})
    assert invalid.unapplied[0]["reason"].startswith("restore rejected")


def test_restore_reaches_the_written_outputs_and_is_byte_identical(tmp_path: Path) -> None:
    root = tmp_path / "out"
    root.mkdir()
    (root / "spec.json").write_text(_spec().model_dump_json(exclude_none=True))
    items = _dropped_items()
    (root / "review.json").write_text(json.dumps(items))
    ids = card_ids(items)
    (root / "decisions.json").write_text(
        json.dumps({ids[0]: _d("accept"), ids[1]: _d("accept"), ids[3]: _d("reject")})
    )
    apply_to_folder(root)
    spec = json.loads((root / "spec.json").read_text())
    names = [p["name"] for p in spec["strategies"][0]["parameters"]]
    assert names == ["A", "B", "C", "New"]
    assert (
        'name="New"' in (root / "strategies.xml").read_text()
        or "New" in (root / "strategies.xml").read_text()
    )
    assert "9100" in (root / "orchestra.xml").read_text()
    assert "human-verified" in (root / "site" / "strategies" / "vwap.html").read_text()
    snap = {p.name: p.read_bytes() for p in root.iterdir() if p.is_file()}
    apply_to_folder(root)
    assert snap == {p.name: p.read_bytes() for p in root.iterdir() if p.is_file()}
