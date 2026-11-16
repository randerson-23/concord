"""Check a spec's standard FIX tags against the FIX dictionary (item 24, D21).

Brokers get standard tags wrong, and extraction would repeat their mistakes. This is a
deterministic check, so it needs no API key. Only tags 1-4999 are standard: 5000 and
above are user-defined in every FIX version, and are never findings.

Errors (exit 2): a standard-range tag the dictionary does not define; a type that
conflicts with the dictionary's; an enum value outside a standard code set whose
``unionDataType`` does not allow it. Warnings: a name that differs from the dictionary's;
a tag that exists in FIX Latest but not in the chosen version; a strategy identifier
value outside the identifier's code set.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Literal

from concord.fixdict import FixDictionary
from concord.ir import AlgoSpec, Parameter, Strategy
from concord.orchestra import datatype_name

STANDARD_TAGS = range(1, 5000)

Severity = Literal["error", "warning"]

# Datatype families. Types of different families conflict; integers and decimals, and
# booleans and strings, are close enough to be compatible. Differing types inside the
# time family are a warning.
_FAMILY = {
    **dict.fromkeys(["int", "Length", "NumInGroup", "SeqNum", "TagNum", "DayOfMonth"], "int"),
    **dict.fromkeys(["float", "Qty", "Price", "PriceOffset", "Amt", "Percentage"], "decimal"),
    **dict.fromkeys(
        [
            "char",
            "String",
            "MultipleCharValue",
            "MultipleStringValue",
            "Currency",
            "Exchange",
            "Country",
            "Language",
            "data",
            "XMLData",
            "Pattern",
            "XID",
            "XIDREF",
        ],
        "string",
    ),
    "Boolean": "boolean",
    **dict.fromkeys(
        [
            "UTCTimestamp",
            "UTCTimeOnly",
            "UTCDateOnly",
            "LocalMktDate",
            "LocalMktTime",
            "MonthYear",
            "TZTimestamp",
            "TZTimeOnly",
            "Tenor",
        ],
        "time",
    ),
}
_COMPATIBLE = {frozenset(p) for p in (("int", "decimal"), ("boolean", "string"))}
_RESERVED = re.compile(r"Reserved(\d+)Plus")
_INT = re.compile(r"\d+")
_NUMBER = re.compile(r"-?\d+(\.\d+)?")
_TENOR = re.compile(r"[DWMY]\d+")


@dataclass(frozen=True)
class Finding:
    severity: Severity
    location: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    def to_text(self) -> str:
        return f"{self.severity}: {self.location}: {self.message}"


def value_allowed(value: str, union: str | None) -> bool:
    """Does a ``unionDataType`` admit ``value`` in addition to the listed codes?"""
    if union is None:
        return False
    reserved = _RESERVED.fullmatch(union)
    if reserved:
        return bool(_INT.fullmatch(value)) and int(value) >= int(reserved.group(1))
    if union == "Qty":
        return bool(_NUMBER.fullmatch(value))
    if union == "Tenor":
        return bool(_TENOR.fullmatch(value))
    return False


def types_conflict(ours: str, theirs: str) -> Literal["error", "warning", None]:
    a, b = _FAMILY.get(ours), _FAMILY.get(theirs)
    if a is None or b is None or ours == theirs:
        return None
    if a == b:
        return "warning" if a == "time" else None
    return None if frozenset((a, b)) in _COMPATIBLE else "error"


def lint_spec(
    spec: AlgoSpec, dictionary: FixDictionary, latest: FixDictionary | None = None
) -> list[Finding]:
    """Findings for every standard-range tag the spec uses, in a stable order.

    ``latest`` is FIX Latest, used to tell "newer than this FIX version" (a warning)
    from "not a FIX tag at all" (an error). Omit it when ``dictionary`` is Latest.
    """
    findings: list[Finding] = []

    def undefined(location: str, tag: int) -> None:
        if latest is not None and tag in latest.fields:
            name = latest.fields[tag].name
            findings.append(
                Finding(
                    "warning",
                    location,
                    f"tag {tag} ({name}) is not in {dictionary.label}; it exists in {latest.label}",
                )
            )
        else:
            findings.append(
                Finding(
                    "error",
                    location,
                    f"tag {tag} is in the standard range (1-4999) but {dictionary.label} "
                    "does not define it; expected a defined FIX tag, or a user-defined tag "
                    "of 5000 or above",
                )
            )

    ident = spec.strategy_identifier_tag
    for label, tag in (
        ("Strategies/@strategyIdentifierTag", ident),
        ("Strategies/@versionIdentifierTag", spec.version_identifier_tag),
        ("Strategies/@draftFlagIdentifierTag", spec.draft_flag_identifier_tag),
    ):
        if tag in STANDARD_TAGS and tag not in dictionary.fields:
            undefined(label, tag)

    codes = dictionary.codes(ident) if ident in STANDARD_TAGS else None
    if codes is not None:
        union = dictionary.fields[ident].union
        for strategy in spec.strategies:
            if strategy.wire_value not in codes.values and not value_allowed(
                strategy.wire_value, union
            ):
                findings.append(
                    Finding(
                        "warning",
                        f"Strategy[@name='{strategy.name}']",
                        f"wire value {strategy.wire_value!r} is outside the {codes.name} "
                        f"code set for tag {ident} ({dictionary.fields[ident].name})",
                    )
                )

    for strategy in spec.strategies:
        for param in strategy.parameters:
            _lint_parameter(strategy, param, dictionary, undefined, findings)
    return findings


def _lint_parameter(
    strategy: Strategy, param: Parameter, dictionary: FixDictionary, undefined, findings
) -> None:
    tag = param.fix_tag
    if tag is None or tag not in STANDARD_TAGS:
        return
    where = f"Strategy[@name='{strategy.name}']/Parameter[@name='{param.name}']"
    if tag not in dictionary.fields:
        undefined(where, tag)
        return
    entry = dictionary.fields[tag]
    if param.name != entry.name:
        findings.append(
            Finding(
                "warning",
                where,
                f"name {param.name!r} differs from the dictionary name {entry.name!r} "
                f"for tag {tag}",
            )
        )
    theirs = dictionary.base_type(tag) or ""
    ours = datatype_name(param.type)
    verdict = types_conflict(ours, theirs)
    if verdict is not None:
        findings.append(
            Finding(
                verdict,
                where,
                f"type {ours} conflicts with {theirs} for tag {tag} ({entry.name})",
            )
        )
    code_set = dictionary.codes(tag)
    if code_set is None:
        return
    for enum in param.enum_values:
        if enum.wire_value not in code_set.values and not value_allowed(
            enum.wire_value, entry.union
        ):
            suffix = f", union type {entry.union}" if entry.union else ""
            findings.append(
                Finding(
                    "error",
                    f"{where}/EnumPair[@wireValue='{enum.wire_value}']",
                    f"value {enum.wire_value!r} is outside the standard code set "
                    f"{code_set.name} for tag {tag}{suffix}",
                )
            )
