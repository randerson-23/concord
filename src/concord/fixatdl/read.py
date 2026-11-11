"""Read FIXatdl 1.1 documents into the Concord IR.

Real-world FIXatdl files are inconsistent about namespaces: some bind the core
namespace as default, some prefix it, some omit namespaces entirely. Elements
are therefore matched by local name, and ``xsi:type`` values have any prefix
stripped.

Parsing is hardened for untrusted input: no entity resolution, no network
access, no DTD loading.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from lxml import etree
from pydantic import ValidationError

from concord.fixatdl.schema import BOOLEAN_CONTROLS, ENUM_CONTROLS, NS_XSI, type_from_xsi
from concord.ir import (
    AlgoSpec,
    Applicability,
    Citation,
    Edit,
    EnumValue,
    Inclusion,
    Parameter,
    ParamType,
    RegionInclusion,
    SourceDocument,
    Strategy,
    StrategyEdit,
    parameter_transport,
)

_XSI_TYPE = f"{{{NS_XSI}}}type"


class FixatdlError(ValueError):
    """The document is not FIXatdl Concord can read. The message says where."""


@dataclass
class ReadResult:
    spec: AlgoSpec
    warnings: list[str] = field(default_factory=list)


def _parser() -> etree.XMLParser:
    return etree.XMLParser(
        resolve_entities=False, no_network=True, load_dtd=False, remove_comments=True
    )


def read_fixatdl_file(path: str | Path, source: SourceDocument | None = None) -> ReadResult:
    return read_fixatdl(Path(path).read_bytes(), source=source)


def read_fixatdl(data: bytes, source: SourceDocument | None = None) -> ReadResult:
    """Parse FIXatdl bytes. Pass ``source`` to attach a citation to every fact."""
    try:
        root = etree.fromstring(data, _parser())
    except etree.XMLSyntaxError as exc:
        raise FixatdlError(f"not well-formed XML: {exc}") from exc
    return _Reader(source).read(root)


# --------------------------------------------------------------------------- helpers


def _first_error(exc: ValidationError) -> str:
    """The IR's own message for the first failed check, without pydantic's framing."""
    err = exc.errors()[0]
    msg = str(err["msg"]).removeprefix("Value error, ")
    loc = ".".join(str(x) for x in err["loc"])
    return f"{msg} (at {loc})" if loc else msg


def _local(el: etree._Element) -> str:
    return etree.QName(el).localname


def _children(el: etree._Element, name: str) -> list[etree._Element]:
    return [c for c in el if isinstance(c.tag, str) and _local(c) == name]


def _child(el: etree._Element, name: str) -> etree._Element | None:
    found = _children(el, name)
    return found[0] if found else None


def _bool(value: str | None) -> bool | None:
    if value is None:
        return None
    if value in ("true", "1"):
        return True
    if value in ("false", "0"):
        return False
    raise FixatdlError(f"invalid xs:boolean {value!r}")


def _int(value: str | None, where: str) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise FixatdlError(f"{where}: expected an integer, got {value!r}") from exc


def _description(el: etree._Element) -> str | None:
    d = _child(el, "Description")
    if d is None:
        return None
    text = " ".join("".join(d.itertext()).split())
    return text or None


# --------------------------------------------------------------------------- reader


class _Reader:
    def __init__(self, source: SourceDocument | None) -> None:
        self.source = source
        self.warnings: list[str] = []
        self.named_edits: dict[str, etree._Element] = {}

    def _cite(self, locator: str) -> list[Citation]:
        if self.source is None:
            return []
        return [Citation(source_id=self.source.id, locator=locator)]

    def read(self, root: etree._Element) -> ReadResult:
        if _local(root) != "Strategies":
            raise FixatdlError(f"root element is <{_local(root)}>, expected <Strategies>")

        tag = _int(root.get("strategyIdentifierTag"), "Strategies/@strategyIdentifierTag")
        if tag is None:
            raise FixatdlError("Strategies/@strategyIdentifierTag is required")

        # Document-level named edits are visible to every strategy's EditRefs.
        for e in _children(root, "Edit"):
            if e.get("id"):
                self.named_edits[e.get("id")] = e

        strategies = [self._strategy(s) for s in _children(root, "Strategy")]
        if not strategies:
            raise FixatdlError("document defines no <Strategy>")

        if _bool(root.get("tag957Support")) is not True:
            for st in strategies:
                for param in st.parameters:
                    if parameter_transport(param) == "957-group":
                        raise FixatdlError(
                            f"Strategy[@name='{st.name}']/Parameter[@name='{param.name}']: "
                            'expected @fixTag, or tag957Support="true" on <Strategies> '
                            "so the parameter can travel in the StrategyParameters group"
                        )
        # Strategies/@imageLocation is UI-only (a logo path), so it is dropped on purpose.
        providers = {s.provider_id for s in strategies if s.provider_id}
        try:
            spec = AlgoSpec(
                provider=providers.pop() if len(providers) == 1 else None,
                strategy_identifier_tag=tag,
                version_identifier_tag=_int(
                    root.get("versionIdentifierTag"), "Strategies/@versionIdentifierTag"
                ),
                tag957_support=_bool(root.get("tag957Support")),
                change_strategy_on_cxl_rpl=_bool(root.get("changeStrategyOnCxlRpl")),
                draft_flag_identifier_tag=_int(
                    root.get("draftFlagIdentifierTag"), "Strategies/@draftFlagIdentifierTag"
                ),
                description=_description(root),
                strategies=strategies,
                sources=[self.source] if self.source else [],
            )
        except ValidationError as exc:
            raise FixatdlError(f"Strategies: {_first_error(exc)}") from exc
        return ReadResult(spec=spec, warnings=self.warnings)

    # -- strategy -----------------------------------------------------------

    def _strategy(self, el: etree._Element) -> Strategy:
        name = el.get("name")
        if not name:
            raise FixatdlError("Strategy without @name")
        where = f"Strategy[@name='{name}']"
        wire = el.get("wireValue")
        if wire is None:
            raise FixatdlError(f"{where}: @wireValue is required")

        if _child(el, "RepeatingGroup") is not None:
            self.warnings.append(
                f"{where}: RepeatingGroup is not supported by IR {AlgoSpec().ir_version}; skipped"
            )

        local_edits = dict(self.named_edits)
        for e in _children(el, "Edit"):
            if e.get("id"):
                local_edits[e.get("id")] = e

        try:
            params = [self._parameter(p, where) for p in _children(el, "Parameter")]
        except ValidationError as exc:
            raise FixatdlError(f"{where}: {_first_error(exc)}") from exc
        by_name = {p.name: p for p in params}

        layout = _child(el, "StrategyLayout")
        if layout is not None:
            self._merge_layout(layout, by_name, where)

        edits = [
            self._strategy_edit(se, local_edits, f"{where}/StrategyEdit[{i}]")
            for i, se in enumerate(_children(el, "StrategyEdit"), start=1)
        ]

        try:
            strategy = self._build_strategy(el, name, wire, params, edits, where)
        except ValidationError as exc:
            raise FixatdlError(f"{where}: {_first_error(exc)}") from exc
        for f in sorted(strategy.dangling_edit_fields()):
            self.warnings.append(f"{where}: validation rule refers to unknown field {f!r}")
        return strategy

    def _build_strategy(
        self,
        el: etree._Element,
        name: str,
        wire: str,
        params: list[Parameter],
        edits: list[StrategyEdit],
        where: str,
    ) -> Strategy:
        return Strategy(
            name=name,
            wire_value=wire,
            version=el.get("version") or "1",
            label=el.get("uiRep"),
            description=_description(el),
            fix_msg_type=el.get("fixMsgType"),
            provider_id=el.get("providerID"),
            provider_sub_id=el.get("providerSubID"),
            applicability=self._applicability(el),
            parameters=params,  # not by_name: duplicates must reach the validator
            edits=edits,
            citations=self._cite(where),
        )

    def _applicability(self, el: etree._Element) -> Applicability:
        def inc(node: etree._Element, code_attr: str) -> Inclusion:
            return Inclusion(
                code=node.get(code_attr, ""), include=node.get("inclusion") != "Exclude"
            )

        regions = []
        if (r := _child(el, "Regions")) is not None:
            for region in _children(r, "Region"):
                regions.append(
                    RegionInclusion(
                        code=region.get("name", ""),
                        include=region.get("inclusion") != "Exclude",
                        countries=[inc(c, "CountryCode") for c in _children(region, "Country")],
                    )
                )
        markets = []
        if (m := _child(el, "Markets")) is not None:
            markets = [inc(x, "MICCode") for x in _children(m, "Market")]
        sectypes = []
        if (s := _child(el, "SecurityTypes")) is not None:
            sectypes = [inc(x, "name") for x in _children(s, "SecurityType")]
        return Applicability(regions=regions, markets=markets, security_types=sectypes)

    # -- parameter ----------------------------------------------------------

    def _parameter(self, el: etree._Element, strategy_where: str) -> Parameter:
        name = el.get("name")
        if not name:
            raise FixatdlError(f"{strategy_where}: Parameter without @name")
        where = f"{strategy_where}/Parameter[@name='{name}']"
        xsi = el.get(_XSI_TYPE)
        if not xsi:
            raise FixatdlError(f"{where}: missing xsi:type")
        try:
            ptype = type_from_xsi(xsi)
        except ValueError as exc:
            raise FixatdlError(f"{where}: unknown parameter type {xsi!r}") from exc

        enums = []
        for i, ep in enumerate(_children(el, "EnumPair"), start=1):
            wire = ep.get("wireValue")
            if wire is None:
                raise FixatdlError(f"{where}/EnumPair[{i}]: @wireValue is required")
            enums.append(
                EnumValue(
                    wire_value=wire,
                    enum_id=ep.get("enumID"),
                    description=_description(ep),
                    citations=self._cite(f"{where}/EnumPair[@enumID='{ep.get('enumID')}']"),
                )
            )

        is_pct = ptype is ParamType.PERCENTAGE
        is_bool = ptype is ParamType.BOOLEAN
        return Parameter(
            name=name,
            type=ptype,
            fix_tag=_int(el.get("fixTag"), f"{where}/@fixTag"),
            required=el.get("use") == "required",
            description=_description(el),
            enum_values=enums,
            min_value=el.get("minValue"),
            max_value=el.get("maxValue"),
            const_value=el.get("constValue"),
            precision=_int(el.get("precision"), f"{where}/@precision"),
            min_length=_int(el.get("minLength"), f"{where}/@minLength"),
            max_length=_int(el.get("maxLength"), f"{where}/@maxLength"),
            multiply_by_100=_bool(el.get("multiplyBy100")) if is_pct else None,
            true_wire_value=el.get("trueWireValue") if is_bool else None,
            false_wire_value=el.get("falseWireValue") if is_bool else None,
            invert_on_wire=_bool(el.get("invertOnWire")),
            local_mkt_tz=el.get("localMktTz"),
            mutable_on_cxl_rpl=_bool(el.get("mutableOnCxlRpl")),
            revert_on_cxl_rpl=_bool(el.get("revertOnCxlRpl")),
            defined_by_fix=_bool(el.get("definedByFIX")),
            citations=self._cite(where),
        )

    # -- layout -------------------------------------------------------------

    def _merge_layout(
        self, layout: etree._Element, params: dict[str, Parameter], where: str
    ) -> None:
        """Pull enum labels and defaults out of the layout into the parameters.

        FIXatdl keeps an enum's human label on the layout's ListItem, not on the
        parameter's EnumPair, and keeps defaults on the control's initValue. The
        IR holds both on the parameter itself.
        """
        for ctrl in layout.iter():
            if not isinstance(ctrl.tag, str) or _local(ctrl) != "Control":
                continue
            ref = ctrl.get("parameterRef")
            if not ref:
                continue
            param = params.get(ref)
            if param is None:
                self.warnings.append(
                    f"{where}: control {ctrl.get('ID')!r} refers to unknown parameter {ref!r}"
                )
                continue
            ctype = (ctrl.get(_XSI_TYPE) or "").rsplit(":", 1)[-1]

            by_id = {e.enum_id: e for e in param.enum_values if e.enum_id}
            for item in _children(ctrl, "ListItem"):
                enum = by_id.get(item.get("enumID"))
                if enum is not None and enum.label is None and item.get("uiRep"):
                    enum.label = item.get("uiRep")

            init = ctrl.get("initValue")
            if init is None or param.default_value is not None:
                continue
            if ctype in ENUM_CONTROLS:
                # Multi-select controls may list several enumIDs; a single default
                # wire value is only meaningful when exactly one is named.
                ids = init.split()
                if len(ids) == 1 and ids[0] in by_id:
                    param.default_value = by_id[ids[0]].wire_value
            elif ctype in BOOLEAN_CONTROLS:
                checked = _bool(init)
                enum_ref = ctrl.get("checkedEnumRef" if checked else "uncheckedEnumRef")
                if enum_ref and enum_ref in by_id:
                    param.default_value = by_id[enum_ref].wire_value
                elif param.type is ParamType.BOOLEAN:
                    if checked:
                        param.default_value = param.true_wire_value or "Y"
                    else:
                        param.default_value = param.false_wire_value or "N"
            else:
                param.default_value = init

    # -- validation ---------------------------------------------------------

    def _strategy_edit(
        self, el: etree._Element, named: dict[str, etree._Element], where: str
    ) -> StrategyEdit:
        message = el.get("errorMessage")
        if message is None:
            raise FixatdlError(f"{where}: @errorMessage is required")
        body = _child(el, "Edit")
        if body is None and (ref := _child(el, "EditRef")) is not None:
            body = self._resolve(ref, named, where)
        if body is None:
            raise FixatdlError(f"{where}: StrategyEdit has no Edit or EditRef")
        return StrategyEdit(
            message=message, edit=self._edit(body, named, where), citations=self._cite(where)
        )

    def _resolve(
        self, ref: etree._Element, named: dict[str, etree._Element], where: str
    ) -> etree._Element:
        target = named.get(ref.get("id", ""))
        if target is None:
            raise FixatdlError(f"{where}: EditRef to undefined edit {ref.get('id')!r}")
        return target

    def _edit(
        self,
        el: etree._Element,
        named: dict[str, etree._Element],
        where: str,
        depth: int = 0,
    ) -> Edit:
        if depth > 64:
            raise FixatdlError(f"{where}: edits nested too deeply (circular EditRef?)")
        logic = el.get("logicOperator")
        if logic:
            kids: list[Edit] = []
            for c in el:
                if not isinstance(c.tag, str):
                    continue
                if _local(c) == "Edit":
                    kids.append(self._edit(c, named, where, depth + 1))
                elif _local(c) == "EditRef":
                    kids.append(self._edit(self._resolve(c, named, where), named, where, depth + 1))
            return Edit(logic=logic, children=kids)
        return Edit(
            field=el.get("field"),
            operator=el.get("operator"),
            value=el.get("value"),
            field2=el.get("field2"),
        )
