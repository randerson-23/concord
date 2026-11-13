"""Orchestra writer tests: fields, code sets, determinism, conflicts (item 9a, D17)."""

from __future__ import annotations

import pytest
from lxml import etree

from concord.cli import main
from concord.fixatdl import read_fixatdl
from concord.ir import AlgoSpec, EnumValue, Parameter, ParamType, Strategy
from concord.orchestra import NS_REPOSITORY, OrchestraError, sanitize_name, write_orchestra

NS = {"fixr": NS_REPOSITORY}


@pytest.fixture
def doc(example_broker_bytes):
    spec = read_fixatdl(example_broker_bytes).spec
    return etree.fromstring(write_orchestra(spec).xml)


def _x(doc, path):
    return doc.xpath(path, namespaces=NS)


def test_namespace_and_header(doc) -> None:
    assert doc.tag == f"{{{NS_REPOSITORY}}}repository"
    assert NS_REPOSITORY.endswith("/2020/orchestra/repository")
    assert doc.get("name") == "EXBK" and doc.get("version") == "1.0"
    assert _x(doc, "fixr:metadata/*")[0].text == "EXBK algorithmic order parameters"


def test_one_field_per_tag_with_names_and_types(doc) -> None:
    fields = {
        f.get("id"): (f.get("name"), f.get("type")) for f in _x(doc, "//fixr:fields/fixr:field")
    }
    assert fields["7602"] == ("StartTime", "UTCTimestamp")  # shared by two strategies, once
    assert fields["7604"] == ("MaxPctVolume", "Percentage")
    assert fields["7607"] == ("MinFillQty", "Qty")
    assert fields["7610"] == ("Slices", "int")
    assert fields["7621"][0] == "StrategyVersionIdentifier"
    assert fields["7699"] == ("StrategyDraftFlag", "Boolean")
    assert len(_x(doc, "//fixr:fields/fixr:field[@id='7602']")) == 1
    ids = [int(f.get("id")) for f in _x(doc, "//fixr:fields/fixr:field")]
    assert ids == sorted(ids)


def test_enum_parameter_becomes_a_code_set(doc) -> None:
    (field,) = _x(doc, "//fixr:field[@id='7605']")
    assert field.get("type") == "UrgencyCodeSet"
    codes = _x(doc, "//fixr:codeSet[@name='UrgencyCodeSet']/fixr:code")
    assert [c.get("value") for c in codes] == ["L", "M", "H"]
    assert [c.get("name") for c in codes] == ["Passive", "Normal", "Aggressive"]
    assert [c.get("id") for c in codes] == ["7605001", "7605002", "7605003"]
    assert _x(doc, "//fixr:codeSet[@name='UrgencyCodeSet']")[0].get("type") == "char"


def test_strategy_identifier_code_set_holds_every_wire_value(doc) -> None:
    (cs,) = _x(doc, "//fixr:codeSet[@id='7620']")
    assert [c.get("value") for c in cs] == ["1", "2"]
    assert cs.get("type") == "int"
    assert _x(doc, "//fixr:field[@id='7620']")[0].get("type") == cs.get("name")


def test_every_field_type_resolves_to_a_datatype_or_code_set(doc) -> None:
    known = set(_x(doc, "//fixr:datatype/@name")) | set(_x(doc, "//fixr:codeSet/@name"))
    assert set(_x(doc, "//fixr:field/@type")) <= known


def test_standard_tags_are_annotated() -> None:
    spec = AlgoSpec(
        strategy_identifier_tag=847,
        strategies=[
            Strategy(
                name="S",
                wire_value="VWAP",
                parameters=[Parameter(name="ExDestination", type=ParamType.EXCHANGE, fix_tag=100)],
            )
        ],
    )
    out = etree.fromstring(write_orchestra(spec).xml)
    assert _x(out, "//fixr:field[@id='100']/fixr:annotation/fixr:documentation")
    assert _x(out, "//fixr:field[@id='847']")[0].get("name") == "TargetStrategy"
    assert _x(out, "//fixr:codeSet[@id='847']")[0].get("type") == "String"  # non-numeric wire


def test_output_is_deterministic(example_broker_bytes) -> None:
    spec = read_fixatdl(example_broker_bytes).spec
    assert write_orchestra(spec).xml == write_orchestra(spec).xml
    assert b"dcterms:date" not in write_orchestra(spec).xml  # no timestamps


def _two(a: Parameter, b: Parameter) -> AlgoSpec:
    return AlgoSpec(
        strategies=[
            Strategy(name="First", wire_value="1", parameters=[a]),
            Strategy(name="Second", wire_value="2", parameters=[b]),
        ]
    )


def test_same_tag_with_different_names_is_an_error() -> None:
    spec = _two(
        Parameter(name="Alpha", type=ParamType.INT, fix_tag=7001),
        Parameter(name="Beta", type=ParamType.INT, fix_tag=7001),
    )
    with pytest.raises(OrchestraError, match=r"tag 7001.*First.*Alpha.*Second.*Beta"):
        write_orchestra(spec)


def test_same_tag_with_different_enum_values_is_an_error() -> None:
    def p(vals):
        return Parameter(
            name="Mode",
            type=ParamType.CHAR,
            fix_tag=7001,
            enum_values=[EnumValue(wire_value=v) for v in vals],
        )

    with pytest.raises(OrchestraError, match="different enum values"):
        write_orchestra(_two(p("AB"), p("AC")))
    write_orchestra(_two(p("AB"), p("AB")))  # identical definitions are fine


def test_same_name_on_two_tags_is_an_error() -> None:
    spec = _two(
        Parameter(name="Cap", type=ParamType.INT, fix_tag=7001),
        Parameter(name="Cap", type=ParamType.INT, fix_tag=7002),
    )
    with pytest.raises(OrchestraError, match="field name 'Cap'"):
        write_orchestra(spec)


def test_group_parameters_are_listed_not_written() -> None:
    spec = AlgoSpec(
        tag957_support=True,
        strategies=[
            Strategy(
                name="S",
                wire_value="1",
                parameters=[
                    Parameter(name="Tagged", type=ParamType.INT, fix_tag=7001),
                    Parameter(name="Grouped", type=ParamType.INT),
                ],
            )
        ],
    )
    result = write_orchestra(spec)
    assert result.group_parameters == [("S", "Grouped")]
    out = etree.fromstring(result.xml)
    assert not _x(out, "//fixr:field[@name='Grouped']")  # not a field of its own
    codes = _x(out, "//fixr:codeSet[@name='StrategyParameterNameCodeSet']/fixr:code")
    assert [(c.get("value"), c.get("name")) for c in codes] == [("Grouped", "Grouped")]


def test_names_and_codes_are_made_legal() -> None:
    assert sanitize_name("Max % Volume") == "Max_Volume"
    assert sanitize_name("1st", "P") == "P_1st"
    spec = AlgoSpec(
        strategies=[
            Strategy(
                name="S",
                wire_value="1",
                parameters=[
                    Parameter(
                        name="Mode",
                        type=ParamType.CHAR,
                        fix_tag=7001,
                        enum_values=[
                            EnumValue(wire_value="A", label="Go fast!"),
                            EnumValue(wire_value="B", label="Go fast?"),
                            EnumValue(wire_value="C"),
                        ],
                    )
                ],
            )
        ]
    )
    out = etree.fromstring(write_orchestra(spec).xml)
    names = _x(out, "//fixr:codeSet[@id='7001']/fixr:code/@name")
    assert names == ["Go_fast", "Go_fast_2", "Code_C"]


def test_output_validates_against_the_orchestra_schema(
    example_broker_bytes, orchestra_schema
) -> None:
    spec = read_fixatdl(example_broker_bytes).spec
    doc = etree.fromstring(write_orchestra(spec).xml)
    assert orchestra_schema.validate(doc), orchestra_schema.error_log


# --------------------------------------------------------------------------- 9b: messages


def _msg(doc, scenario):
    (m,) = _x(doc, f"//fixr:message[@scenario='{scenario}']")
    return m


def test_one_new_order_single_per_strategy_scenario(doc) -> None:
    msgs = _x(doc, "//fixr:message")
    assert [(m.get("name"), m.get("msgType"), m.get("scenario")) for m in msgs] == [
        ("NewOrderSingle", "D", "EXBK_VWAP"),
        ("NewOrderSingle", "D", "EXBK_TWAP"),
    ]
    assert not _x(doc, "//fixr:scenarios")  # v1.0 has no scenario declarations


def test_identifier_is_a_constant_per_scenario(doc) -> None:
    for scenario, wire in (("EXBK_VWAP", "1"), ("EXBK_TWAP", "2")):
        (ref,) = _x(_msg(doc, scenario), "fixr:structure/fixr:fieldRef[@id='7620']")
        assert (ref.get("presence"), ref.get("value")) == ("constant", wire)


def test_presence_bounds_and_constants(doc) -> None:
    vwap = _msg(doc, "EXBK_VWAP")

    def ref(tag):
        return _x(vwap, f"fixr:structure/fixr:fieldRef[@id='{tag}']")[0]

    assert ref(7605).get("presence") == "required"  # Urgency
    assert ref(7604).get("presence") is None  # optional is the default
    assert (ref(7604).get("minInclusive"), ref(7604).get("maxInclusive")) == ("0.01", "0.5")
    assert (ref(7608).get("presence"), ref(7608).get("value")) == ("constant", "SMART")  # Venue
    twap = _msg(doc, "EXBK_TWAP")
    assert _x(twap, "fixr:structure/fixr:fieldRef[@id='7603']")[0].get("presence") == "required"
    assert not _x(twap, "fixr:structure/fixr:fieldRef[@id='7605']")  # not this strategy's


def test_957_group_has_fields_a_code_set_and_a_group_ref() -> None:
    spec = AlgoSpec(
        tag957_support=True,
        strategies=[
            Strategy(
                name="S",
                wire_value="1",
                parameters=[
                    Parameter(name="Tagged", type=ParamType.INT, fix_tag=7001),
                    Parameter(name="Grouped", type=ParamType.INT),
                    Parameter(name="Other", type=ParamType.STRING),
                ],
            ),
            Strategy(name="T", wire_value="2"),
        ],
    )
    out = etree.fromstring(write_orchestra(spec).xml)
    (grp,) = _x(out, "//fixr:group")
    assert (grp.get("id"), grp.get("name")) == ("957", "StrategyParametersGrp")
    assert _x(grp, "fixr:numInGroup/@id") == ["957"]
    assert _x(grp, "fixr:fieldRef/@id") == ["958", "959", "960"]
    assert [f.get("name") for f in _x(out, "//fixr:field[@id>='957' and @id<='960']")] == [
        "NoStrategyParameters",
        "StrategyParameterName",
        "StrategyParameterType",
        "StrategyParameterValue",
    ]
    assert _x(out, "//fixr:field[@id='958']/@type") == ["StrategyParameterNameCodeSet"]
    assert _x(out, "//fixr:codeSet[@id='958']/fixr:code/@value") == ["Grouped", "Other"]
    assert len(_x(_msg(out, "S"), "fixr:structure/fixr:groupRef[@id='957']")) == 1
    assert not _x(_msg(out, "T"), "fixr:structure/fixr:groupRef")  # only where used


def test_two_strategies_with_one_scenario_name_are_an_error() -> None:
    spec = AlgoSpec(
        strategies=[Strategy(name="A B", wire_value="1"), Strategy(name="A-B", wire_value="2")]
    )
    with pytest.raises(OrchestraError, match="both map to scenario 'A_B'"):
        write_orchestra(spec)


def test_cli_writes_orchestra_to_stdout(tmp_path, capsysbinary) -> None:
    fixture = "tests/fixtures/fixatdl/example_broker.xml"
    assert main(["convert", fixture, "--to", "orchestra"]) == 0
    out = capsysbinary.readouterr().out
    assert etree.fromstring(out).tag == f"{{{NS_REPOSITORY}}}repository"
    assert main(["convert", fixture, "--to", "orchestra"]) == 0
    assert capsysbinary.readouterr().out == out  # byte-identical


def test_cli_reports_orchestra_errors(tmp_path, capsys) -> None:
    src = tmp_path / "conflict.json"
    src.write_text(
        _two(
            Parameter(name="Alpha", type=ParamType.INT, fix_tag=7001),
            Parameter(name="Beta", type=ParamType.INT, fix_tag=7001),
        ).model_dump_json(exclude_none=True)
    )
    assert main(["convert", str(src), "--to", "orchestra"]) == 1
    assert "tag 7001" in capsys.readouterr().err
