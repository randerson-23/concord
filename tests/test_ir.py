from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from concord.ir import (
    AlgoSpec,
    Citation,
    Edit,
    EnumValue,
    Parameter,
    ParamType,
    SourceDocument,
    Strategy,
)


def test_duplicate_enum_wire_values_rejected():
    with pytest.raises(ValidationError, match="duplicate enum wire values"):
        Parameter(
            name="U",
            type=ParamType.CHAR,
            enum_values=[EnumValue(wire_value="L"), EnumValue(wire_value="L")],
        )


def test_multiply_by_100_only_on_percentage():
    with pytest.raises(ValidationError, match="only applies to Percentage"):
        Parameter(name="X", type=ParamType.FLOAT, multiply_by_100=True)


def test_duplicate_tags_within_strategy_rejected():
    with pytest.raises(ValidationError, match="tag used twice"):
        Strategy(
            name="S",
            wire_value="1",
            parameters=[
                Parameter(name="A", type=ParamType.INT, fix_tag=7600),
                Parameter(name="B", type=ParamType.INT, fix_tag=7600),
            ],
        )


def test_duplicate_strategy_wire_values_rejected():
    with pytest.raises(ValidationError, match="duplicate strategy wire values"):
        AlgoSpec(
            strategies=[Strategy(name="A", wire_value="1"), Strategy(name="B", wire_value="1")]
        )


def test_citations_must_reference_a_known_source():
    s = Strategy(name="A", wire_value="1", citations=[Citation(source_id="missing", page=4)])
    with pytest.raises(ValidationError, match="unknown sources"):
        AlgoSpec(strategies=[s])
    ok = AlgoSpec(
        strategies=[s.model_copy(update={"citations": [Citation(source_id="doc", page=4)]})],
        sources=[SourceDocument(id="doc", title="Spec", kind="pdf")],
    )
    assert next(ok.iter_citations()).page == 4


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"field": "A"}, "needs field and operator"),
        ({"field": "A", "operator": "EX", "value": "1"}, "takes no value"),
        ({"field": "A", "operator": "EQ"}, "exactly one of value or field2"),
        ({"field": "A", "operator": "EQ", "value": "1", "field2": "B"}, "exactly one"),
        ({"logic": "NOT", "children": []}, "exactly one child"),
        ({"logic": "AND", "children": [Edit(field="A", operator="EX")]}, "at least two"),
    ],
)
def test_edit_shape_rules(kwargs, message):
    with pytest.raises(ValidationError, match=message):
        Edit(**kwargs)


def test_ir_serialises_to_json_and_back():
    spec = AlgoSpec(
        strategies=[
            Strategy(
                name="S",
                wire_value="1",
                parameters=[Parameter(name="Q", type=ParamType.QTY, fix_tag=7600)],
            )
        ]
    )
    again = AlgoSpec.model_validate_json(spec.model_dump_json())
    assert again == spec


def test_json_schema_is_exportable():
    schema = AlgoSpec.model_json_schema()
    assert "Strategy" in json.dumps(schema)
