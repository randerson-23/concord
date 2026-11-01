from __future__ import annotations

from lxml import etree

from concord.fixatdl import read_fixatdl, write_fixatdl
from concord.fixatdl.schema import IDENTIFIER
from concord.ir import AlgoSpec, EnumValue, Parameter, ParamType, Strategy


def _strip_citations(spec: AlgoSpec) -> dict:
    data = spec.model_dump()

    def walk(node):
        if isinstance(node, dict):
            node.pop("citations", None)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(data)
    return data


def test_round_trip_preserves_the_ir(example_broker_bytes):
    original = read_fixatdl(example_broker_bytes).spec
    again = read_fixatdl(write_fixatdl(original)).spec
    assert _strip_citations(again) == _strip_citations(original)


def test_written_fixture_is_schema_valid(example_broker_bytes, fixatdl_schema):
    assert fixatdl_schema.validate(etree.fromstring(example_broker_bytes)), fixatdl_schema.error_log
    out = write_fixatdl(read_fixatdl(example_broker_bytes).spec)
    doc = etree.fromstring(out)
    assert fixatdl_schema.validate(doc), fixatdl_schema.error_log


def test_hand_built_spec_is_schema_valid(fixatdl_schema):
    """A spec as the PDF extractor would build it: no enumIDs, odd names."""
    spec = AlgoSpec(
        strategies=[
            Strategy(
                name="Arrival",
                wire_value="IS",
                parameters=[
                    Parameter(
                        name="Aggression",
                        type=ParamType.INT,
                        fix_tag=7700,
                        precision=2,  # illegal on Int_t in FIXatdl: must be dropped
                        enum_values=[EnumValue(wire_value="1"), EnumValue(wire_value="2")],
                        default_value="2",
                    ),
                    Parameter(name="DarkOnly", type=ParamType.BOOLEAN, fix_tag=7701),
                    Parameter(name="Limit", type=ParamType.PRICE_OFFSET, fix_tag=7702),
                ],
            )
        ]
    )
    doc = etree.fromstring(write_fixatdl(spec))
    assert fixatdl_schema.validate(doc), fixatdl_schema.error_log


def test_int_precision_is_never_emitted():
    spec = AlgoSpec(
        strategies=[
            Strategy(
                name="S",
                wire_value="1",
                parameters=[Parameter(name="N", type=ParamType.INT, fix_tag=7600, precision=3)],
            )
        ]
    )
    assert b"precision" not in write_fixatdl(spec)


def test_generated_enum_ids_are_legal_and_unique():
    p = Parameter(
        name="Style",
        type=ParamType.CHAR,
        enum_values=[
            EnumValue(wire_value="A", enum_id="9bad"),  # illegal: starts with a digit
            EnumValue(wire_value="B"),
            EnumValue(wire_value="C", enum_id="e2"),  # collides with a generated id
        ],
    )
    out = write_fixatdl(AlgoSpec(strategies=[Strategy(name="S", wire_value="1", parameters=[p])]))
    ids = etree.fromstring(out).xpath("//*[local-name()='EnumPair']/@enumID")
    assert len(ids) == len(set(ids)) == 3
    assert all(IDENTIFIER.fullmatch(i) for i in ids)


def test_output_is_deterministic(example_broker_bytes):
    spec = read_fixatdl(example_broker_bytes).spec
    assert write_fixatdl(spec) == write_fixatdl(spec)


def test_constant_parameters_get_no_control(example_broker_bytes):
    out = write_fixatdl(read_fixatdl(example_broker_bytes).spec)
    refs = etree.fromstring(out).xpath("//*[local-name()='Control']/@parameterRef")
    assert "Venue" not in refs
    assert "Urgency" in refs
