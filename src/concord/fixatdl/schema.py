"""Facts about the FIXatdl 1.1 schema that the reader and writer share.

Derived from the official FIXatdl 1.1 XSDs (core, layout, validation). Kept as
plain data so the writer can never emit an attribute the schema forbids.
"""

from __future__ import annotations

import re

from concord.ir import ParamType

NS_CORE = "http://www.fixprotocol.org/FIXatdl-1-1/Core"
NS_LAYOUT = "http://www.fixprotocol.org/FIXatdl-1-1/Layout"
NS_VALIDATION = "http://www.fixprotocol.org/FIXatdl-1-1/Validation"
NS_FLOW = "http://www.fixprotocol.org/FIXatdl-1-1/Flow"
NS_XSI = "http://www.w3.org/2001/XMLSchema-instance"

NSMAP = {None: NS_CORE, "lay": NS_LAYOUT, "val": NS_VALIDATION, "xsi": NS_XSI}

# Identifier lexical rule shared by EnumPair/@enumID and Control/@ID.
IDENTIFIER = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,255}")

# Attributes each parameter type adds to the Parameter_t base, per the XSD.
_RANGE = ("minValue", "maxValue", "constValue")
_NUMERIC = (*_RANGE, "precision")
_LENGTH = ("minLength", "maxLength", "constValue")
TYPE_ATTRIBUTES: dict[ParamType, tuple[str, ...]] = {
    ParamType.INT: _RANGE,
    ParamType.LENGTH: ("constValue",),
    ParamType.NUM_IN_GROUP: ("constValue",),
    ParamType.SEQ_NUM: ("constValue",),
    ParamType.TAG_NUM: ("constValue",),
    ParamType.FLOAT: _NUMERIC,
    ParamType.QTY: _NUMERIC,
    ParamType.PRICE: _NUMERIC,
    ParamType.PRICE_OFFSET: _NUMERIC,
    ParamType.AMT: _NUMERIC,
    ParamType.PERCENTAGE: (*_NUMERIC, "multiplyBy100"),
    ParamType.CHAR: ("constValue",),
    ParamType.BOOLEAN: ("constValue", "trueWireValue", "falseWireValue"),
    ParamType.STRING: _LENGTH,
    ParamType.DATA: _LENGTH,
    ParamType.MULTIPLE_CHAR_VALUE: (*_LENGTH, "invertOnWire"),
    ParamType.MULTIPLE_STRING_VALUE: (*_LENGTH, "invertOnWire"),
    ParamType.CURRENCY: ("constValue",),
    ParamType.EXCHANGE: ("constValue",),
    ParamType.COUNTRY: ("constValue",),
    ParamType.LANGUAGE: ("constValue",),
    ParamType.TENOR: ("constValue",),
    ParamType.MONTH_YEAR: _RANGE,
    ParamType.LOCAL_MKT_DATE: _RANGE,
    ParamType.UTC_DATE_ONLY: _RANGE,
    ParamType.UTC_TIMESTAMP: (*_RANGE, "localMktTz"),
    ParamType.UTC_TIME_ONLY: (*_RANGE, "localMktTz"),
    ParamType.TZ_TIMESTAMP: _RANGE,
    ParamType.TZ_TIME_ONLY: _RANGE,
}

# Layout controls whose initValue names an enumID rather than a wire value.
ENUM_CONTROLS = frozenset(
    {
        "DropDownList_t",
        "EditableDropDownList_t",
        "SingleSelectList_t",
        "MultiSelectList_t",
        "RadioButtonList_t",
        "CheckBoxList_t",
        "Slider_t",
    }
)
# Controls whose initValue is xs:boolean.
BOOLEAN_CONTROLS = frozenset({"CheckBox_t", "RadioButton_t"})

# Clock_t/@initValue is xs:time.
XS_TIME = re.compile(r"\d{2}:\d{2}:\d{2}(\.\d+)?")


def type_from_xsi(xsi_type: str) -> ParamType:
    """'Qty_t' or 'core:Qty_t' -> ParamType.QTY."""
    local = xsi_type.rsplit(":", 1)[-1]
    if not local.endswith("_t"):
        raise ValueError(f"not a FIXatdl parameter type: {xsi_type!r}")
    return ParamType(local[:-2])


def xsi_from_type(t: ParamType) -> str:
    return f"{t.value}_t"
