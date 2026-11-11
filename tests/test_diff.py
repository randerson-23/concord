from __future__ import annotations

import json

import pytest

from concord.cli import main
from concord.diff import diff_specs
from concord.fixatdl import read_fixatdl
from concord.ir import (
    AlgoSpec,
    EnumValue,
    Inclusion,
    Parameter,
    ParamType,
    Strategy,
)


def base() -> AlgoSpec:
    return AlgoSpec(
        provider="Acme",
        strategies=[
            Strategy(
                name="VWAP",
                wire_value="VWAP",
                label="VWAP",
                parameters=[
                    Parameter(
                        name="Style",
                        type=ParamType.CHAR,
                        fix_tag=9001,
                        enum_values=[
                            EnumValue(wire_value="P", label="Passive"),
                            EnumValue(wire_value="A", label="Aggressive"),
                        ],
                    ),
                    Parameter(
                        name="MaxPct",
                        type=ParamType.PERCENTAGE,
                        fix_tag=9002,
                        min_value="0",
                        max_value="50",
                        precision=2,
                    ),
                    Parameter(name="Note", type=ParamType.STRING, fix_tag=9003),
                ],
            ),
            Strategy(name="TWAP", wire_value="TWAP"),
        ],
    )


def mutate(fn) -> AlgoSpec:
    spec = base()
    fn(spec)
    return AlgoSpec.model_validate(spec.model_dump())


def kinds(old: AlgoSpec, new: AlgoSpec) -> dict[str, str]:
    return {c.kind: c.severity for c in diff_specs(old, new).changes}


def param(spec: AlgoSpec, name: str) -> Parameter:
    return spec.strategy("VWAP").parameter(name)


def test_identical_specs_have_no_changes():
    r = diff_specs(base(), base())
    assert r.changes == [] and r.to_text() == "No differences."


def test_fixture_against_itself(example_broker_bytes):
    spec = read_fixatdl(example_broker_bytes).spec
    assert diff_specs(spec, spec).changes == []


CASES = [
    ("strategy removed", lambda s: s.strategies.pop(1), "strategy_removed", "breaking"),
    (
        "strategy added",
        lambda s: s.strategies.append(Strategy(name="POV", wire_value="POV")),
        "strategy_added",
        "additive",
    ),
    (
        "strategy wire",
        lambda s: setattr(s.strategies[0], "wire_value", "VW2"),
        "wire_value_changed",
        "breaking",
    ),
    (
        "strategy label",
        lambda s: setattr(s.strategies[0], "label", "Vwap"),
        "label_changed",
        "cosmetic",
    ),
    ("param removed", lambda s: s.strategies[0].parameters.pop(2), "parameter_removed", "breaking"),
    (
        "optional added",
        lambda s: s.strategies[0].parameters.append(
            Parameter(name="New", type=ParamType.INT, fix_tag=9100)
        ),
        "parameter_added",
        "additive",
    ),
    (
        "required added",
        lambda s: s.strategies[0].parameters.append(
            Parameter(name="New", type=ParamType.INT, fix_tag=9100, required=True)
        ),
        "parameter_added_required",
        "breaking",
    ),
    (
        "became required",
        lambda s: setattr(param(s, "Note"), "required", True),
        "became_required",
        "breaking",
    ),
    ("became optional", None, "became_optional", "additive"),
    (
        "type changed",
        lambda s: setattr(param(s, "Note"), "type", ParamType.INT),
        "type_changed",
        "breaking",
    ),
    (
        "tag changed",
        lambda s: setattr(param(s, "Note"), "fix_tag", 9999),
        "fix_tag_changed",
        "breaking",
    ),
    ("enum removed", lambda s: param(s, "Style").enum_values.pop(), "enum_removed", "breaking"),
    (
        "enum added",
        lambda s: param(s, "Style").enum_values.append(EnumValue(wire_value="N")),
        "enum_added",
        "additive",
    ),
    (
        "enum label",
        lambda s: setattr(param(s, "Style").enum_values[0], "label", "Pass"),
        "enum[P] label_changed",
        "cosmetic",
    ),
    (
        "max narrowed",
        lambda s: setattr(param(s, "MaxPct"), "max_value", "25"),
        "max_value_changed",
        "breaking",
    ),
    (
        "min narrowed",
        lambda s: setattr(param(s, "MaxPct"), "min_value", "5"),
        "min_value_changed",
        "breaking",
    ),
    (
        "bound added",
        lambda s: setattr(param(s, "Note"), "max_length", 10),
        "max_length_changed",
        "breaking",
    ),
    (
        "precision lowered",
        lambda s: setattr(param(s, "MaxPct"), "precision", 1),
        "precision_changed",
        "breaking",
    ),
    (
        "const added",
        lambda s: setattr(param(s, "Note"), "const_value", "X"),
        "const_value_changed",
        "breaking",
    ),
    (
        "default added",
        lambda s: setattr(param(s, "Note"), "default_value", "X"),
        "default_value_changed",
        "additive",
    ),
    (
        "not mutable",
        lambda s: setattr(param(s, "Note"), "mutable_on_cxl_rpl", False),
        "mutable_changed",
        "breaking",
    ),
    (
        "param description",
        lambda s: setattr(param(s, "Note"), "description", "d"),
        "description_changed",
        "cosmetic",
    ),
]


@pytest.mark.parametrize("name,fn,kind,severity", CASES, ids=[c[0] for c in CASES])
def test_classification(name, fn, kind, severity):
    if fn is None:  # reverse of "became required"
        old, new = mutate(lambda s: setattr(param(s, "Note"), "required", True)), base()
    else:
        old, new = base(), mutate(fn)
    assert kinds(old, new).get(kind) == severity


def test_max_widened_is_additive_and_numeric_not_lexical():
    old = mutate(lambda s: setattr(param(s, "MaxPct"), "max_value", "9"))
    new = mutate(lambda s: setattr(param(s, "MaxPct"), "max_value", "10"))
    assert kinds(old, new) == {"max_value_changed": "additive"}


def test_rename_with_same_tag_is_cosmetic():
    new = mutate(lambda s: setattr(param(s, "Note"), "name", "Remark"))
    r = diff_specs(base(), new)
    assert [(c.kind, c.severity) for c in r.changes] == [("parameter_renamed", "cosmetic")]
    assert r.changes[0].path == "Strategy[@name='VWAP']/Parameter[@name='Note']"


def test_applicability_narrowing_and_widening():
    old = mutate(
        lambda s: setattr(
            s.strategies[0].applicability,
            "markets",
            [Inclusion(code="XNYS"), Inclusion(code="XLON")],
        )
    )
    new = mutate(
        lambda s: setattr(s.strategies[0].applicability, "markets", [Inclusion(code="XNYS")])
    )
    assert kinds(old, new) == {"applicability_narrowed": "breaking"}
    assert kinds(new, old) == {"applicability_widened": "additive"}
    # Excluding something from an unrestricted strategy narrows it.
    ex = mutate(
        lambda s: setattr(
            s.strategies[0].applicability, "markets", [Inclusion(code="XLON", include=False)]
        )
    )
    assert kinds(base(), ex) == {"applicability_narrowed": "breaking"}


def test_report_formats_and_order():
    new = mutate(
        lambda s: (
            setattr(param(s, "Note"), "required", True),
            setattr(s.strategies[0], "label", "V"),
            s.strategies.pop(1),
        )
    )
    r = diff_specs(base(), new)
    text = r.to_text()
    assert text.startswith("3 change(s): 2 breaking, 0 additive, 1 cosmetic")
    assert text.index("BREAKING") < text.index("COSMETIC")
    assert "Strategy[@name='TWAP']: strategy removed" in text
    data = json.loads(r.to_json())
    assert data["summary"] == {"breaking": 2, "additive": 0, "cosmetic": 1}
    assert r.to_json() == diff_specs(base(), new).to_json()  # deterministic


def test_cli_diff(tmp_path, capsys):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    a.write_text(base().model_dump_json())
    b.write_text(mutate(lambda s: s.strategies.pop(1)).model_dump_json())
    assert main(["diff", str(a), str(b)]) == 0
    assert "strategy removed" in capsys.readouterr().out
    assert main(["diff", str(a), str(b), "--fail-on-breaking", "--format", "json"]) == 2
    assert json.loads(capsys.readouterr().out)["summary"]["breaking"] == 1
    assert main(["diff", str(a), str(a), "--fail-on-breaking"]) == 0


def _rename_vwap(s: AlgoSpec) -> None:
    s.strategies[0].name = "VWAP2"


def test_strategy_rename_by_wire_value_is_cosmetic():
    r = diff_specs(base(), mutate(_rename_vwap))
    assert [(c.kind, c.severity) for c in r.changes] == [("strategy_renamed", "cosmetic")]
    c = r.changes[0]
    assert c.message == "renamed 'VWAP' -> 'VWAP2' (wire value VWAP)"
    assert (c.old, c.new) == ("VWAP", "VWAP2")
    data = json.loads(r.to_json())["changes"][0]
    assert (data["old"], data["new"]) == ("VWAP", "VWAP2")


def test_strategy_rename_plus_removed_parameter_reports_under_new_name():
    def fn(s: AlgoSpec) -> None:
        _rename_vwap(s)
        s.strategies[0].parameters.pop()  # Note

    r = diff_specs(base(), mutate(fn))
    assert kinds(base(), mutate(fn)) == {
        "strategy_renamed": "cosmetic",
        "parameter_removed": "breaking",
    }
    removed = next(c for c in r.changes if c.kind == "parameter_removed")
    assert removed.path == "Strategy[@name='VWAP2']/Parameter[@name='Note']"


def test_strategies_sharing_wire_value_are_not_matched():
    # The IR forbids duplicate wire values, so build the ambiguous specs unvalidated.
    old = AlgoSpec.model_construct(
        provider="Acme",
        strategies=[
            Strategy(name="A", wire_value="W"),
            Strategy(name="B", wire_value="W"),
        ],
    )
    new = AlgoSpec.model_construct(provider="Acme", strategies=[Strategy(name="C", wire_value="W")])
    r = diff_specs(old, new)
    assert sorted(c.kind for c in r.changes) == [
        "strategy_added",
        "strategy_removed",
        "strategy_removed",
    ]


def test_cli_fail_on_breaking_for_strategy_rename(tmp_path):
    a, b, c = (tmp_path / f"{n}.json" for n in "abc")
    a.write_text(base().model_dump_json())
    b.write_text(mutate(_rename_vwap).model_dump_json())
    c.write_text(
        mutate(lambda s: (_rename_vwap(s), s.strategies[0].parameters.pop())).model_dump_json()
    )
    assert main(["diff", str(a), str(b), "--fail-on-breaking"]) == 0
    assert main(["diff", str(a), str(c), "--fail-on-breaking"]) == 2


# --------------------------------------------------------------------------- wire contract (D16)


@pytest.mark.parametrize(
    ("attr", "old", "new", "severity"),
    [
        ("tag957_support", True, False, "breaking"),
        ("tag957_support", None, True, "additive"),
        ("change_strategy_on_cxl_rpl", True, False, "breaking"),
        ("change_strategy_on_cxl_rpl", False, True, "additive"),
        ("draft_flag_identifier_tag", 7699, 7700, "breaking"),
        ("draft_flag_identifier_tag", 7699, None, "breaking"),
        ("draft_flag_identifier_tag", None, 7699, "additive"),
    ],
)
def test_wire_contract_changes_are_classified(attr, old, new, severity):
    a, b = base(), base()
    setattr(a, attr, old)
    setattr(b, attr, new)
    (change,) = [c for c in diff_specs(a, b).changes if c.kind == f"{attr}_changed"]
    assert change.severity == severity and change.path == "spec"


def test_unset_and_false_wire_contract_do_not_differ():
    a, b = base(), base()
    b.tag957_support = False
    b.change_strategy_on_cxl_rpl = False
    assert diff_specs(a, b).changes == []
