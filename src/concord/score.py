"""FIXatdl validation edits rendered in Orchestra's Score DSL (item 9c, D19).

Score syntax follows ``Score.g4`` at tag v1.6 of FIXTradingCommunity/fix-orchestra
(Apache-2.0): ``== != < <= > >= && || !``, ``exists F``, code references ``^CodeName``,
quoted strings and numbers.

A FIXatdl ``StrategyEdit`` holds the condition under which an order is VALID. Orchestra
field rules say when a field is required or forbidden, so only the presence patterns
``F NX OR C`` (F is forbidden unless C) and ``F EX OR C`` (F is required unless C) map
onto a rule; every other edit is a value check with no Orchestra 1.0 equivalent.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from concord.ir import Edit

SCORE_OPERATORS = {"EQ": "==", "NE": "!=", "LT": "<", "LE": "<=", "GT": ">", "GE": ">="}
_NUMBER = re.compile(r"-?\d+(\.\d+)?")

FieldName = Callable[[str], str]  # IR field name -> Score identifier
CodeName = Callable[[str, str], str | None]  # (IR field, wire value) -> code name, if any


class ScoreError(ValueError):
    """An edit has no Score form (for example an empty string literal)."""


@dataclass(frozen=True)
class PresenceRule:
    field: str  # IR field name the rule attaches to
    presence: Literal["forbidden", "required"]
    unless: Edit  # the condition C of ``F NX|EX OR C``


def _literal(field: str, value: str, code_name: CodeName) -> str:
    code = code_name(field, value)
    if code is not None:
        return f"^{code}"
    if _NUMBER.fullmatch(value):
        return value
    if value == "":
        raise ScoreError("an empty string has no Score literal")
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def to_score(edit: Edit, field_name: FieldName, code_name: CodeName, nested: bool = False) -> str:
    """Render one edit as a Score expression. ``nested`` wraps groups in parentheses."""
    if edit.logic is not None:
        kids = [to_score(c, field_name, code_name, True) for c in edit.children]
        if edit.logic == "NOT":
            return f"!({to_score(edit.children[0], field_name, code_name)})"
        if edit.logic == "XOR":  # Score has no xor: (a || b) && !(a && b), folded left
            text = kids[0]
            for kid in kids[1:]:
                text = f"(({text}) || ({kid})) && !(({text}) && ({kid}))"
        else:
            text = f" {'&&' if edit.logic == 'AND' else '||'} ".join(kids)
        return f"({text})" if nested else text
    assert edit.field is not None and edit.operator is not None
    name = field_name(edit.field)
    if edit.operator == "EX":
        return f"exists {name}"
    if edit.operator == "NX":
        return f"!exists {name}"
    if edit.field2 is not None:
        rhs = field_name(edit.field2)
    else:
        assert edit.value is not None
        rhs = _literal(edit.field, edit.value, code_name)
    return f"{name} {SCORE_OPERATORS[edit.operator]} {rhs}"


def presence_rule(edit: Edit) -> PresenceRule | None:
    """Recognise ``F NX OR C`` / ``F EX OR C`` where C does not mention F."""
    if edit.logic != "OR":
        return None
    for i, child in enumerate(edit.children):
        if child.logic is None and child.operator in ("EX", "NX"):
            assert child.field is not None
            rest = [c for j, c in enumerate(edit.children) if j != i]
            unless = rest[0] if len(rest) == 1 else Edit(logic="OR", children=rest)
            if child.field in unless.fields():
                return None  # C reads F itself: a value check, not a presence rule
            presence = "forbidden" if child.operator == "NX" else "required"
            return PresenceRule(child.field, presence, unless)
    return None
