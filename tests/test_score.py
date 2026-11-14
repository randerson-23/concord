"""Score rendering of FIXatdl edits (item 9c, D19): one case per operator."""

from __future__ import annotations

import pytest

from concord.ir import Edit
from concord.score import ScoreError, presence_rule, to_score


def _name(n: str) -> str:
    return n.removeprefix("FIX_")


def _code(field: str, value: str) -> str | None:
    return {"H": "High"}.get(value) if field == "Urgency" else None


def _score(edit: Edit) -> str:
    return to_score(edit, _name, _code)


@pytest.mark.parametrize(
    ("operator", "score"),
    [("EQ", "=="), ("NE", "!="), ("LT", "<"), ("LE", "<="), ("GT", ">"), ("GE", ">=")],
)
def test_comparison_operators(operator, score) -> None:
    assert _score(Edit(field="Qty", operator=operator, value="5")) == f"Qty {score} 5"
    assert _score(Edit(field="Qty", operator=operator, field2="FIX_OrderQty")) == (
        f"Qty {score} OrderQty"
    )


def test_presence_operators() -> None:
    assert _score(Edit(field="A", operator="EX")) == "exists A"
    assert _score(Edit(field="A", operator="NX")) == "!exists A"


def test_logic_operators_and_nesting() -> None:
    a, b, c = (Edit(field=n, operator="EX") for n in "ABC")
    assert _score(Edit(logic="AND", children=[a, b])) == "exists A && exists B"
    assert _score(Edit(logic="OR", children=[a, Edit(logic="AND", children=[b, c])])) == (
        "exists A || (exists B && exists C)"
    )
    assert _score(Edit(logic="NOT", children=[a])) == "!(exists A)"
    assert _score(Edit(logic="XOR", children=[a, b])) == (
        "((exists A) || (exists B)) && !((exists A) && (exists B))"
    )


def test_literals() -> None:
    assert _score(Edit(field="Urgency", operator="EQ", value="H")) == "Urgency == ^High"
    assert _score(Edit(field="Side", operator="EQ", value="Buy")) == 'Side == "Buy"'
    assert _score(Edit(field="Px", operator="GT", value="-1.5")) == "Px > -1.5"
    assert _score(Edit(field="S", operator="EQ", value='a"b')) == 'S == "a\\"b"'
    with pytest.raises(ScoreError):
        _score(Edit(field="S", operator="EQ", value=""))


def test_presence_pattern_recognition() -> None:
    nx = Edit(field="F", operator="NX")
    cond = Edit(field="C", operator="EQ", value="1")
    rule = presence_rule(Edit(logic="OR", children=[cond, nx]))  # position does not matter
    assert rule is not None and (rule.field, rule.presence) == ("F", "forbidden")
    assert rule.unless == cond
    assert (
        presence_rule(Edit(logic="OR", children=[Edit(field="F", operator="EX"), cond])).presence
        == "required"
    )
    self_ref = Edit(field="F", operator="LE", field2="C")
    assert presence_rule(Edit(logic="OR", children=[nx, self_ref])) is None  # value check
    assert presence_rule(Edit(logic="AND", children=[nx, cond])) is None
    assert presence_rule(cond) is None
