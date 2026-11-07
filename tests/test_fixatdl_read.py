from __future__ import annotations

import pytest

from concord.fixatdl import FixatdlError, read_fixatdl
from concord.ir import Edit, ParamType, SourceDocument


def test_document_level(example_broker_bytes):
    result = read_fixatdl(example_broker_bytes)
    spec = result.spec
    assert spec.strategy_identifier_tag == 7620
    assert spec.version_identifier_tag == 7621
    assert spec.provider == "EXBK"
    assert spec.description == "Example Broker algorithmic suite for cash equities."
    assert [s.name for s in spec.strategies] == ["EXBK_VWAP", "EXBK_TWAP"]
    assert result.warnings == []


def test_strategy_attributes_and_applicability(example_broker_bytes):
    vwap = read_fixatdl(example_broker_bytes).spec.strategy("EXBK_VWAP")
    assert (vwap.wire_value, vwap.version, vwap.label, vwap.fix_msg_type) == ("1", "3", "VWAP", "D")
    app = vwap.applicability
    assert app.regions[0].code == "TheAmericas" and app.regions[0].include
    assert [(c.code, c.include) for c in app.regions[0].countries] == [("CA", False)]
    assert [m.code for m in app.markets] == ["XNYS", "XNAS"]
    assert [s.code for s in app.security_types] == ["CS"]


def test_parameter_types_and_attributes(example_broker_bytes):
    vwap = read_fixatdl(example_broker_bytes).spec.strategy("EXBK_VWAP")

    start = vwap.parameter("StartTime")
    assert start.type is ParamType.UTC_TIMESTAMP
    assert start.fix_tag == 7602
    assert start.local_mkt_tz == "America/New_York"
    assert start.description == "Time the algo begins working. Exchange local time."

    pct = vwap.parameter("MaxPctVolume")
    assert pct.type is ParamType.PERCENTAGE
    assert (pct.min_value, pct.max_value, pct.precision) == ("0.01", "0.5", 2)
    assert pct.multiply_by_100 is True

    urgency = vwap.parameter("Urgency")
    assert urgency.required is True

    auction = vwap.parameter("AllowAuction")
    assert (auction.true_wire_value, auction.false_wire_value) == ("1", "0")
    assert auction.mutable_on_cxl_rpl is False

    assert vwap.parameter("Venue").const_value == "SMART"


def test_enum_labels_come_from_layout_list_items(example_broker_bytes):
    """FIXatdl keeps the human label on lay:ListItem, not on EnumPair."""
    urgency = read_fixatdl(example_broker_bytes).spec.strategy("EXBK_VWAP").parameter("Urgency")
    assert [(e.wire_value, e.label) for e in urgency.enum_values] == [
        ("L", "Passive"),
        ("M", "Normal"),
        ("H", "Aggressive"),
    ]
    assert urgency.enum_by_wire("H").description == "Front-loads execution; expect higher impact."


def test_defaults_resolved_to_wire_values(example_broker_bytes):
    vwap = read_fixatdl(example_broker_bytes).spec.strategy("EXBK_VWAP")
    # DropDownList initValue is an enumID; the IR stores the wire value it maps to.
    assert vwap.parameter("Urgency").default_value == "M"
    # CheckBox initValue is xs:boolean; mapped through the custom trueWireValue.
    assert vwap.parameter("AllowAuction").default_value == "1"
    # Plain controls carry the value through.
    assert vwap.parameter("StartTime").default_value == "09:30:00"
    assert vwap.parameter("MaxPctVolume").default_value == "0.2"
    assert vwap.parameter("MinFillQty").default_value is None


def test_edit_ref_is_resolved_inline(example_broker_bytes):
    spec = read_fixatdl(example_broker_bytes).spec
    expected = Edit(
        logic="OR",
        children=[
            Edit(field="EndTime", operator="NX"),
            Edit(field="EndTime", operator="GT", field2="StartTime"),
        ],
    )
    for name in ("EXBK_VWAP", "EXBK_TWAP"):
        first = spec.strategy(name).edits[0]
        assert first.message == "End time must be after start time."
        assert first.edit == expected


def test_standard_fix_fields_in_edits_are_not_dangling(example_broker_bytes):
    vwap = read_fixatdl(example_broker_bytes).spec.strategy("EXBK_VWAP")
    assert "FIX_OrderQty" in vwap.edits[2].edit.fields()
    assert vwap.dangling_edit_fields() == set()


def test_source_citations_point_at_elements(example_broker_bytes):
    src = SourceDocument(id="exbk", title="Example Broker FIXatdl", kind="fixatdl")
    spec = read_fixatdl(example_broker_bytes, source=src).spec
    assert spec.sources == [src]
    cite = spec.strategy("EXBK_VWAP").parameter("Urgency").citations[0]
    assert cite.source_id == "exbk"
    assert cite.locator == "Strategy[@name='EXBK_VWAP']/Parameter[@name='Urgency']"


# --------------------------------------------------------------------------- tolerance & errors

_MINIMAL = b"""<Strategies strategyIdentifierTag="847"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <Strategy name="S" wireValue="1" version="1">%s</Strategy>
</Strategies>"""


def test_namespaceless_documents_are_accepted():
    data = _MINIMAL % b'<Parameter xsi:type="Qty_t" name="Q" fixTag="7600"/>'
    spec = read_fixatdl(data).spec
    assert spec.strategy("S").parameter("Q").type is ParamType.QTY


def test_prefixed_xsi_type_is_accepted():
    data = _MINIMAL % b'<Parameter xsi:type="core:Price_t" name="P" fixTag="7600"/>'
    assert read_fixatdl(data).spec.strategy("S").parameter("P").type is ParamType.PRICE


def test_repeating_group_warns_rather_than_silently_dropping():
    data = (
        _MINIMAL
        % b'<RepeatingGroup minSize="0"><Parameter xsi:type="Int_t" name="X"/></RepeatingGroup>'
    )
    result = read_fixatdl(data)
    assert any("RepeatingGroup" in w for w in result.warnings)


def test_control_for_unknown_parameter_warns():
    data = _MINIMAL % (
        b"<StrategyLayout><StrategyPanel>"
        b'<Control xsi:type="TextField_t" ID="c" parameterRef="Ghost"/>'
        b"</StrategyPanel></StrategyLayout>"
    )
    assert any("Ghost" in w for w in read_fixatdl(data).warnings)


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (b'<Parameter name="Q" fixTag="1"/>', "missing xsi:type"),
        (b'<Parameter xsi:type="Bogus_t" name="Q"/>', "unknown parameter type"),
        (b'<Parameter xsi:type="Int_t" name="Q" fixTag="abc"/>', "expected an integer"),
        (
            b'<StrategyEdit errorMessage="x"><EditRef id="nope"/></StrategyEdit>',
            "undefined edit",
        ),
    ],
)
def test_errors_name_the_location(body, message):
    with pytest.raises(FixatdlError, match=message):
        read_fixatdl(_MINIMAL % body)


def test_duplicate_parameter_names_are_rejected():
    body = b'<Parameter xsi:type="Int_t" name="Q"/><Parameter xsi:type="Int_t" name="Q"/>'
    with pytest.raises(FixatdlError, match=r"Strategy\[@name='S'\].*duplicate parameter names"):
        read_fixatdl(_MINIMAL % body)


def test_duplicate_tags_name_the_strategy():
    body = (
        b'<Parameter xsi:type="Int_t" name="A" fixTag="7001"/>'
        b'<Parameter xsi:type="Int_t" name="B" fixTag="7001"/>'
    )
    with pytest.raises(FixatdlError, match=r"Strategy\[@name='S'\].*tag used twice"):
        read_fixatdl(_MINIMAL % body)


def test_wrong_root_is_rejected():
    with pytest.raises(FixatdlError, match="expected <Strategies>"):
        read_fixatdl(b"<fixr/>")


def test_external_entities_are_not_resolved(tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("TOP-SECRET")
    data = (
        f'<?xml version="1.0"?><!DOCTYPE s [<!ENTITY x SYSTEM "file://{secret}">]>'
        f'<Strategies strategyIdentifierTag="847"><Description>&x;</Description>'
        f'<Strategy name="S" wireValue="1" version="1"/></Strategies>'
    ).encode()
    spec = read_fixatdl(data).spec
    assert "TOP-SECRET" not in (spec.description or "")
