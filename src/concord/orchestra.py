"""FIX Orchestra writer: fields, code sets and NewOrderSingle scenarios (items 9a/9b, D17/D18).

Writes an Orchestra 1.0 repository (namespace ``fixprotocol.io/2020``) that holds one
field per algo parameter tag, one code set per enumerated parameter and one for the
strategy identifier, and one ``NewOrderSingle`` message per strategy (the strategy is
the message ``scenario``). Deterministic: same IR in, same bytes out. No timestamps.

Parameters without a ``fix_tag`` travel in the StrategyParameters group (957-960): they
become entries of a code set on StrategyParameterName (958) and are also listed on the
result.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from lxml import etree

from concord.ir import AlgoSpec, Parameter, ParamType, Strategy, parameter_transport
from concord.score import ScoreError, presence_rule, to_score
from concord.site import edit_text

# One constant, so moving to Orchestra 1.1 (namespace .../2026/...) is a one-line change.
NS_REPOSITORY = "http://fixprotocol.io/2020/orchestra/repository"
NS_DCTERMS = "http://purl.org/dc/terms/"
REPOSITORY_VERSION = "1.0"  # Version_t needs a FIX version or "major.minor"; specs carry none.
STANDARD_TAG_LIMIT = 5000  # tags below this are standard FIX fields

_NSMAP = {"fixr": NS_REPOSITORY, "dcterms": NS_DCTERMS}
_NAME_OK = re.compile(r"[A-Za-z][A-Za-z0-9_]*")
_NOT_NAME = re.compile(r"[^A-Za-z0-9_]+")
_CODES_PER_SET = 1000  # code ids are tag * 1000 + position (1-based)
GROUP_NUM_TAG = 957  # NoStrategyParameters, the StrategyParameters group
_GROUP_NAME = "StrategyParametersGrp"

# Orchestra spells a few datatypes in lower case; the rest match the FIX name.
_DATATYPE_NAMES = {
    ParamType.INT: "int",
    ParamType.CHAR: "char",
    ParamType.FLOAT: "float",
    ParamType.DATA: "data",
}


class OrchestraError(ValueError):
    """The spec cannot be written as Orchestra without guessing. The message says where."""


@dataclass
class OrchestraResult:
    xml: bytes
    # (strategy name, parameter name) for parameters that travel in the 957 group.
    group_parameters: list[tuple[str, str]] = field(default_factory=list)
    # (strategy name, error message) for StrategyEdits Orchestra 1.0 cannot enforce; they are
    # kept as message annotations.
    unenforced: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class _Field:
    tag: int
    name: str
    datatype: str
    codes: list[tuple[str, str]] | None  # (wire value, display text) for an enum
    origin: str  # where this definition came from, for error messages


def _q(name: str) -> str:
    return f"{{{NS_REPOSITORY}}}{name}"


def datatype_name(ptype: ParamType) -> str:
    return _DATATYPE_NAMES.get(ptype, ptype.value)


def sanitize_name(text: str, fallback: str = "X") -> str:
    """A legal Orchestra Name_t: letters, digits and underscores, starting with a letter."""
    name = _NOT_NAME.sub("_", text).strip("_")
    if not name:
        name = fallback
    if not _NAME_OK.fullmatch(name):
        name = f"{fallback}_{name}"
    return name[:255]


def _identifier_datatype(spec: AlgoSpec) -> str:
    wires = [s.wire_value for s in spec.strategies]
    return "int" if wires and all(w.isdigit() for w in wires) else "String"


def _collect(spec: AlgoSpec) -> tuple[dict[int, _Field], list[tuple[str, str]]]:
    fields: dict[int, _Field] = {}
    group: list[tuple[str, str]] = []

    def register(new: _Field) -> None:
        old = fields.get(new.tag)
        if old is None:
            fields[new.tag] = new
            return
        if (old.name, old.datatype, old.codes) != (new.name, new.datatype, new.codes):
            raise OrchestraError(
                f"tag {new.tag} is defined differently by {old.origin} "
                f"({old.name}, {old.datatype}) and {new.origin} ({new.name}, {new.datatype}"
                f"{'' if old.codes == new.codes else ', different enum values'}); "
                "expected one definition per tag"
            )

    register(
        _Field(
            spec.strategy_identifier_tag,
            "TargetStrategy" if spec.strategy_identifier_tag == 847 else "StrategyIdentifier",
            _identifier_datatype(spec),
            [(s.wire_value, s.name) for s in spec.strategies],
            "the strategy identifier",
        )
    )
    if spec.version_identifier_tag is not None:
        register(
            _Field(
                spec.version_identifier_tag,
                "StrategyVersionIdentifier",
                "String",
                None,
                "the strategy version identifier",
            )
        )
    if spec.draft_flag_identifier_tag is not None:
        register(
            _Field(
                spec.draft_flag_identifier_tag,
                "StrategyDraftFlag",
                "Boolean",
                None,
                "the draft flag identifier",
            )
        )
    for strategy in spec.strategies:
        for param in strategy.parameters:
            if parameter_transport(param) == "957-group":
                group.append((strategy.name, param.name))
                continue
            assert param.fix_tag is not None
            register(_param_field(strategy, param))
    if group:
        names = list(dict.fromkeys(name for _, name in group))  # first-seen order
        origin = "the StrategyParameters group (957)"
        register(_Field(957, "NoStrategyParameters", "NumInGroup", None, origin))
        register(_Field(958, "StrategyParameterName", "String", [(n, n) for n in names], origin))
        register(_Field(959, "StrategyParameterType", "int", None, origin))
        register(_Field(960, "StrategyParameterValue", "String", None, origin))
    return fields, group


def _param_field(strategy: Strategy, param: Parameter) -> _Field:
    assert param.fix_tag is not None
    codes = (
        [(e.wire_value, e.label or e.enum_id or "") for e in param.enum_values]
        if param.enum_values
        else None
    )
    return _Field(
        param.fix_tag,
        sanitize_name(param.name, "P"),
        datatype_name(param.type),
        codes,
        f"Strategy[@name='{strategy.name}']/Parameter[@name='{param.name}']",
    )


def _check_unique_names(fields: dict[int, _Field]) -> None:
    seen: dict[str, _Field] = {}
    for f in sorted(fields.values(), key=lambda f: f.tag):
        other = seen.get(f.name)
        if other is not None:
            raise OrchestraError(
                f"field name {f.name!r} is used for tag {other.tag} ({other.origin}) and "
                f"tag {f.tag} ({f.origin}); expected unique field names"
            )
        seen[f.name] = f


def _code_names(codes: list[tuple[str, str]]) -> list[str]:
    """Unique, legal names for the codes of one code set, in order."""
    names: list[str] = []
    for wire, text in codes:
        base = sanitize_name(text or f"Code_{wire}", "C")
        name, n = base, 2
        while name in names:
            name, n = f"{base}_{n}", n + 1
        names.append(name)
    return names


def _scenario_names(spec: AlgoSpec) -> dict[str, str]:
    """Strategy name -> Orchestra scenario name (letters, digits, ``_`` and ``-``)."""
    names: dict[str, str] = {}
    used: dict[str, str] = {}
    for strategy in spec.strategies:
        scenario = sanitize_name(strategy.name, "S")
        if scenario in used:
            raise OrchestraError(
                f"strategies {used[scenario]!r} and {strategy.name!r} both map to scenario "
                f"{scenario!r}; expected distinct scenario names"
            )
        used[scenario] = strategy.name
        names[strategy.name] = scenario
    return names


def _annotate(parent: etree._Element, texts: list[str]) -> None:
    if not texts:
        return
    ann = etree.SubElement(parent, _q("annotation"))
    for text in texts:
        doc = etree.SubElement(ann, _q("documentation"), purpose="ELABORATION")
        doc.text = text


def _names_for(strategy: Strategy, code_names_by_tag: dict[int, dict[str, str]]):
    """Field-name and code-name lookups for rendering this strategy's edits as Score."""
    params = {p.name: p for p in strategy.parameters}

    def field_name(name: str) -> str:
        if name in params:
            return sanitize_name(name, "P")
        return sanitize_name(name.removeprefix("FIX_"), "F")  # FIX_OrderQty -> OrderQty

    def code_name(name: str, value: str) -> str | None:
        param = params.get(name)
        if param is None or param.fix_tag is None:
            return None
        return code_names_by_tag.get(param.fix_tag, {}).get(value)

    return field_name, code_name


def _message(
    parent: etree._Element,
    spec: AlgoSpec,
    strategy: Strategy,
    scenario: str,
    code_names_by_tag: dict[int, dict[str, str]],
) -> list[str]:
    """One NewOrderSingle for one strategy; returns the messages of edits it cannot enforce.

    The identifier is constant, parameters follow. Edits of the presence form become
    field rules; every other edit stays as an annotation (D19).
    """
    msg = etree.SubElement(
        parent, _q("message"), id="14", name="NewOrderSingle", msgType="D", scenario=scenario
    )
    structure = etree.SubElement(msg, _q("structure"))
    etree.SubElement(
        structure,
        _q("fieldRef"),
        id=str(spec.strategy_identifier_tag),
        presence="constant",
        value=strategy.wire_value,
    )
    refs: dict[str, etree._Element] = {}
    in_group = False
    for param in strategy.parameters:
        if parameter_transport(param) == "957-group":
            in_group = True
            continue
        ref = etree.SubElement(structure, _q("fieldRef"), id=str(param.fix_tag))
        refs[param.name] = ref
        if param.const_value is not None:
            ref.set("presence", "constant")
            ref.set("value", param.const_value)
        elif param.required:
            ref.set("presence", "required")
        if param.min_value is not None:
            ref.set("minInclusive", param.min_value)
        if param.max_value is not None:
            ref.set("maxInclusive", param.max_value)
    if in_group:
        etree.SubElement(structure, _q("groupRef"), id=str(GROUP_NUM_TAG))

    field_name, code_name = _names_for(strategy, code_names_by_tag)
    notes: list[str] = []
    unenforced: list[str] = []
    for edit in strategy.edits:
        rule = presence_rule(edit.edit)
        ref = refs.get(rule.field) if rule else None
        try:
            if rule is not None and ref is not None:
                when = f"!({to_score(rule.unless, field_name, code_name)})"
                el = etree.SubElement(
                    ref,
                    _q("rule"),
                    name=f"{field_name(rule.field)}_{rule.presence}",
                    presence=rule.presence,
                )
                etree.SubElement(el, _q("when")).text = when
                continue
            expr = to_score(edit.edit, field_name, code_name)
        except ScoreError:
            expr = f"(no Score form) {edit_text(edit.edit)}"
        notes.append(f"Not enforceable in Orchestra 1.0: {edit.message} Valid when: {expr}")
        unenforced.append(edit.message)
    _annotate(msg, notes)
    _cancel_replace(parent, spec, strategy, scenario)
    return unenforced


def _cancel_replace(
    parent: etree._Element, spec: AlgoSpec, strategy: Strategy, scenario: str
) -> None:
    """Parameters that are not amendable get a note on an OrderCancelReplaceRequest scenario."""
    fixed = [p for p in strategy.parameters if p.mutable_on_cxl_rpl is False]
    if not fixed:
        return
    msg = etree.SubElement(
        parent,
        _q("message"),
        id="17",
        name="OrderCancelReplaceRequest",
        msgType="G",
        scenario=scenario,
    )
    structure = etree.SubElement(msg, _q("structure"))
    etree.SubElement(
        structure,
        _q("fieldRef"),
        id=str(spec.strategy_identifier_tag),
        presence="constant",
        value=strategy.wire_value,
    )
    notes = []
    for param in fixed:
        if param.fix_tag is not None:
            etree.SubElement(structure, _q("fieldRef"), id=str(param.fix_tag))
        notes.append(
            f"{param.name} cannot be amended: it must equal its value in the order being "
            "replaced. Orchestra 1.0 has no rule for an unchanged value."
        )
    _annotate(msg, notes)


def write_orchestra(spec: AlgoSpec) -> OrchestraResult:
    """Serialise the spec's fields and code sets as an Orchestra 1.0 repository."""
    fields, group = _collect(spec)
    _check_unique_names(fields)
    by_tag = sorted(fields.values(), key=lambda f: f.tag)

    root = etree.Element(
        _q("repository"),
        nsmap=_NSMAP,
        name=spec.provider or "AlgoSpecification",
        version=REPOSITORY_VERSION,
    )
    meta = etree.SubElement(root, _q("metadata"))
    title = f"{spec.provider} algorithmic order parameters" if spec.provider else "Algo spec"
    etree.SubElement(meta, f"{{{NS_DCTERMS}}}title").text = title
    if spec.provider:
        etree.SubElement(meta, f"{{{NS_DCTERMS}}}publisher").text = spec.provider

    code_set_names = {f.tag: f"{f.name}CodeSet" for f in by_tag if f.codes is not None}
    base_types = sorted({f.datatype for f in by_tag})
    datatypes = etree.SubElement(root, _q("datatypes"))
    for dt in base_types:
        etree.SubElement(datatypes, _q("datatype"), name=dt)

    code_sets = etree.SubElement(root, _q("codeSets"))
    for f in by_tag:
        if f.codes is None:
            continue
        if len(f.codes) >= _CODES_PER_SET:
            raise OrchestraError(f"{f.origin}: too many enum values ({len(f.codes)})")
        cs = etree.SubElement(
            code_sets,
            _q("codeSet"),
            id=str(f.tag),
            name=code_set_names[f.tag],
            type=f.datatype,
        )
        for i, ((wire, _), name) in enumerate(zip(f.codes, _code_names(f.codes), strict=True), 1):
            # Code ids are tag * 1000 + position: stable, unique per code set.
            etree.SubElement(
                cs, _q("code"), id=str(f.tag * _CODES_PER_SET + i), name=name, value=wire
            )

    fields_el = etree.SubElement(root, _q("fields"))
    for f in by_tag:
        el = etree.SubElement(
            fields_el,
            _q("field"),
            id=str(f.tag),
            name=f.name,
            type=code_set_names.get(f.tag, f.datatype),
        )
        if f.tag < STANDARD_TAG_LIMIT:
            ann = etree.SubElement(etree.SubElement(el, _q("annotation")), _q("documentation"))
            ann.set("purpose", "ELABORATION")
            ann.text = "Standard FIX field (tag below 5000); name and type as given by the source."

    if group:
        groups = etree.SubElement(root, _q("groups"))
        grp = etree.SubElement(groups, _q("group"), id=str(GROUP_NUM_TAG), name=_GROUP_NAME)
        etree.SubElement(grp, _q("numInGroup"), id="957")
        for tag in (958, 959, 960):
            etree.SubElement(grp, _q("fieldRef"), id=str(tag))

    code_names_by_tag = {
        f.tag: dict(zip((w for w, _ in f.codes), _code_names(f.codes), strict=True))
        for f in by_tag
        if f.codes is not None
    }
    messages = etree.SubElement(root, _q("messages"))
    scenarios = _scenario_names(spec)
    unenforced: list[tuple[str, str]] = []
    for strategy in spec.strategies:
        skipped = _message(messages, spec, strategy, scenarios[strategy.name], code_names_by_tag)
        unenforced += [(strategy.name, text) for text in skipped]
    if not spec.strategies:  # the schema needs at least one message
        base = etree.SubElement(
            messages, _q("message"), id="14", name="NewOrderSingle", msgType="D"
        )
        structure = etree.SubElement(base, _q("structure"))
        etree.SubElement(structure, _q("fieldRef"), id=str(spec.strategy_identifier_tag))

    xml = etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)
    return OrchestraResult(xml=xml, group_parameters=group, unenforced=unenforced)
