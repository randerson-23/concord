"""Write the Concord IR out as a FIXatdl 1.1 document.

The output is schema-valid FIXatdl 1.1 that a FIXatdl-aware OMS/EMS can render.
Element order follows the XSD's Strategy_t sequence exactly:

    Description, Regions, Markets, SecurityTypes, Parameter*, Edit*,
    StrategyLayout, RepeatingGroup, StrategyEdit*

A layout is generated: one panel per strategy, one control per non-constant
parameter, with the control type chosen from the parameter's type.
"""

from __future__ import annotations

from lxml import etree

from concord.fixatdl.schema import (
    IDENTIFIER,
    NS_CORE,
    NS_LAYOUT,
    NS_VALIDATION,
    NS_XSI,
    NSMAP,
    TYPE_ATTRIBUTES,
    XS_TIME,
    xsi_from_type,
)
from concord.ir import AlgoSpec, Edit, Parameter, ParamType, Strategy

_XSI_TYPE = f"{{{NS_XSI}}}type"


def _c(name: str) -> str:
    return f"{{{NS_CORE}}}{name}"


def _lay(name: str) -> str:
    return f"{{{NS_LAYOUT}}}{name}"


def _val(name: str) -> str:
    return f"{{{NS_VALIDATION}}}{name}"


def _xbool(v: bool) -> str:
    return "true" if v else "false"


def write_fixatdl(spec: AlgoSpec) -> bytes:
    """Serialise ``spec`` as a FIXatdl 1.1 document (UTF-8 bytes)."""
    root = etree.Element(_c("Strategies"), nsmap=NSMAP)
    root.set("strategyIdentifierTag", str(spec.strategy_identifier_tag))
    if spec.version_identifier_tag is not None:
        root.set("versionIdentifierTag", str(spec.version_identifier_tag))
    if spec.description:
        etree.SubElement(root, _c("Description")).text = spec.description
    for strategy in spec.strategies:
        _strategy(root, strategy)
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)


# --------------------------------------------------------------------------- strategy


def _strategy(parent: etree._Element, s: Strategy) -> None:
    el = etree.SubElement(parent, _c("Strategy"))
    el.set("name", s.name)
    if s.label:
        el.set("uiRep", s.label)
    el.set("wireValue", s.wire_value)
    el.set("version", s.version)
    for attr, value in (
        ("fixMsgType", s.fix_msg_type),
        ("providerID", s.provider_id),
        ("providerSubID", s.provider_sub_id),
    ):
        if value:
            el.set(attr, value)

    if s.description:
        etree.SubElement(el, _c("Description")).text = s.description

    app = s.applicability
    if app.regions:
        regions = etree.SubElement(el, _c("Regions"))
        for r in app.regions:
            region = etree.SubElement(regions, _c("Region"))
            region.set("name", r.code)
            region.set("inclusion", "Include" if r.include else "Exclude")
            for c in r.countries:
                country = etree.SubElement(region, _c("Country"))
                country.set("CountryCode", c.code)
                country.set("inclusion", "Include" if c.include else "Exclude")
    if app.markets:
        markets = etree.SubElement(el, _c("Markets"))
        for m in app.markets:
            market = etree.SubElement(markets, _c("Market"))
            market.set("MICCode", m.code)
            market.set("inclusion", "Include" if m.include else "Exclude")
    if app.security_types:
        sts = etree.SubElement(el, _c("SecurityTypes"))
        for st in app.security_types:
            node = etree.SubElement(sts, _c("SecurityType"))
            node.set("name", st.code)
            node.set("inclusion", "Include" if st.include else "Exclude")

    enum_ids = {p.name: _enum_ids(p) for p in s.parameters}
    for p in s.parameters:
        _parameter(el, p, enum_ids[p.name])

    controls = [p for p in s.parameters if p.const_value is None]
    if controls:
        layout = etree.SubElement(el, _lay("StrategyLayout"))
        panel = etree.SubElement(layout, _lay("StrategyPanel"))
        panel.set("title", s.label or s.name)
        panel.set("collapsible", "false")
        panel.set("orientation", "VERTICAL")
        for i, p in enumerate(controls, start=1):
            _control(panel, p, enum_ids[p.name], i)

    for se in s.edits:
        node = etree.SubElement(el, _val("StrategyEdit"))
        node.set("errorMessage", se.message)
        _edit(node, se.edit)


# --------------------------------------------------------------------------- parameter


def _enum_ids(p: Parameter) -> list[str]:
    """Return a schema-legal, per-parameter-unique enumID for every enum value."""
    ids: list[str] = []
    for i, e in enumerate(p.enum_values, start=1):
        candidate = e.enum_id if e.enum_id and IDENTIFIER.fullmatch(e.enum_id) else f"e{i}"
        while candidate in ids:
            candidate = f"{candidate}_{i}"
        ids.append(candidate)
    return ids


def _parameter(parent: etree._Element, p: Parameter, enum_ids: list[str]) -> None:
    el = etree.SubElement(parent, _c("Parameter"))
    el.set(_XSI_TYPE, xsi_from_type(p.type))
    el.set("name", p.name)
    if p.fix_tag is not None:
        el.set("fixTag", str(p.fix_tag))
    if p.required:
        el.set("use", "required")
    if p.mutable_on_cxl_rpl is not None:
        el.set("mutableOnCxlRpl", _xbool(p.mutable_on_cxl_rpl))
    if p.revert_on_cxl_rpl is not None:
        el.set("revertOnCxlRpl", _xbool(p.revert_on_cxl_rpl))
    if p.defined_by_fix is not None:
        el.set("definedByFIX", _xbool(p.defined_by_fix))

    allowed = TYPE_ATTRIBUTES[p.type]
    typed = {
        "minValue": p.min_value,
        "maxValue": p.max_value,
        "constValue": p.const_value,
        "precision": None if p.precision is None else str(p.precision),
        "minLength": None if p.min_length is None else str(p.min_length),
        "maxLength": None if p.max_length is None else str(p.max_length),
        "multiplyBy100": None if p.multiply_by_100 is None else _xbool(p.multiply_by_100),
        "trueWireValue": p.true_wire_value,
        "falseWireValue": p.false_wire_value,
        "invertOnWire": None if p.invert_on_wire is None else _xbool(p.invert_on_wire),
        "localMktTz": p.local_mkt_tz,
    }
    for attr, value in typed.items():
        if value is not None and attr in allowed:
            el.set(attr, value)

    if p.description:
        etree.SubElement(el, _c("Description")).text = p.description
    for enum, enum_id in zip(p.enum_values, enum_ids, strict=True):
        pair = etree.SubElement(el, _c("EnumPair"))
        pair.set("enumID", enum_id)
        pair.set("wireValue", enum.wire_value)
        if enum.description:
            etree.SubElement(pair, _c("Description")).text = enum.description


# --------------------------------------------------------------------------- layout


def _control(panel: etree._Element, p: Parameter, enum_ids: list[str], index: int) -> None:
    ctrl = etree.SubElement(panel, _lay("Control"))
    # Deterministic IDs keep generated files diffable run to run.
    ctrl.set("ID", f"c_{p.name}" if IDENTIFIER.fullmatch(f"c_{p.name}") else f"c{index}")
    ctrl.set("parameterRef", p.name)
    ctrl.set("label", _humanise(p.name))

    if p.enum_values:
        ctrl.set(_XSI_TYPE, "lay:DropDownList_t")
        default_id = None
        for enum, enum_id in zip(p.enum_values, enum_ids, strict=True):
            if enum.wire_value == p.default_value:
                default_id = enum_id
        if default_id:
            ctrl.set("initValue", default_id)
        for enum, enum_id in zip(p.enum_values, enum_ids, strict=True):
            item = etree.SubElement(ctrl, _lay("ListItem"))
            item.set("enumID", enum_id)
            item.set("uiRep", enum.label or enum.wire_value)
    elif p.type is ParamType.BOOLEAN:
        ctrl.set(_XSI_TYPE, "lay:CheckBox_t")
        if p.default_value is not None:
            true_wire = p.true_wire_value or "Y"
            ctrl.set("initValue", _xbool(p.default_value == true_wire))
    elif p.type.is_temporal:
        ctrl.set(_XSI_TYPE, "lay:Clock_t")
        if p.default_value and XS_TIME.fullmatch(p.default_value):
            ctrl.set("initValue", p.default_value)
        if p.local_mkt_tz and p.type in (ParamType.UTC_TIMESTAMP, ParamType.UTC_TIME_ONLY):
            ctrl.set("localMktTz", p.local_mkt_tz)
    else:
        ctrl.set(_XSI_TYPE, "lay:TextField_t")
        if p.default_value is not None:
            ctrl.set("initValue", p.default_value)


def _humanise(name: str) -> str:
    """'MaxPctVolume' -> 'Max Pct Volume'."""
    out: list[str] = []
    for i, ch in enumerate(name):
        prev = name[i - 1] if i else ""
        nxt = name[i + 1] if i + 1 < len(name) else ""
        if i and ch.isupper() and (prev.islower() or (nxt.islower() and prev.isupper())):
            out.append(" ")
        out.append(ch)
    return "".join(out)


# --------------------------------------------------------------------------- validation


def _edit(parent: etree._Element, e: Edit) -> None:
    node = etree.SubElement(parent, _val("Edit"))
    if e.logic:
        node.set("logicOperator", e.logic)
        for child in e.children:
            _edit(node, child)
        return
    node.set("field", e.field or "")
    node.set("operator", e.operator or "")
    if e.value is not None:
        node.set("value", e.value)
    if e.field2:
        node.set("field2", e.field2)
