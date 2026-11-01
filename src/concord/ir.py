"""Concord intermediate representation (IR) for algorithmic-order specifications.

The IR is the contract at the centre of Concord. Every input produces it (PDF
rules-of-engagement extraction, FIXatdl, Orchestra) and every output consumes it
(FIXatdl, Orchestra, engine dictionaries, docs, certification tests).

Design rules:

* **Format-neutral.** Nothing here is FIXatdl-specific unless FIX semantics
  themselves demand it. FIXatdl's split of enum labels into the layout section,
  for example, is resolved away by the FIXatdl reader.
* **Wire-level values.** Defaults, constants and bounds are stored as the
  strings that would appear on the wire, so no precision or formatting is lost
  in transit between formats.
* **Every fact can cite its source.** Extraction from prose is only trustworthy
  when each extracted rule points back at the page and quote it came from.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

IR_VERSION = "0.1"


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class ParamType(StrEnum):
    """FIX data types an algo parameter can take.

    Names match the FIX datatype names. FIXatdl spells these with a ``_t``
    suffix (``Qty_t``); readers and writers translate.
    """

    INT = "Int"
    LENGTH = "Length"
    NUM_IN_GROUP = "NumInGroup"
    SEQ_NUM = "SeqNum"
    TAG_NUM = "TagNum"
    FLOAT = "Float"
    QTY = "Qty"
    PRICE = "Price"
    PRICE_OFFSET = "PriceOffset"
    AMT = "Amt"
    PERCENTAGE = "Percentage"
    CHAR = "Char"
    BOOLEAN = "Boolean"
    STRING = "String"
    MULTIPLE_CHAR_VALUE = "MultipleCharValue"
    MULTIPLE_STRING_VALUE = "MultipleStringValue"
    CURRENCY = "Currency"
    EXCHANGE = "Exchange"
    MONTH_YEAR = "MonthYear"
    UTC_TIMESTAMP = "UTCTimestamp"
    UTC_TIME_ONLY = "UTCTimeOnly"
    UTC_DATE_ONLY = "UTCDateOnly"
    LOCAL_MKT_DATE = "LocalMktDate"
    TZ_TIMESTAMP = "TZTimestamp"
    TZ_TIME_ONLY = "TZTimeOnly"
    TENOR = "Tenor"
    COUNTRY = "Country"
    LANGUAGE = "Language"
    DATA = "Data"

    @property
    def is_numeric(self) -> bool:
        return self in _NUMERIC

    @property
    def is_temporal(self) -> bool:
        return self in _TEMPORAL


_NUMERIC = frozenset(
    {
        ParamType.INT,
        ParamType.LENGTH,
        ParamType.NUM_IN_GROUP,
        ParamType.SEQ_NUM,
        ParamType.TAG_NUM,
        ParamType.FLOAT,
        ParamType.QTY,
        ParamType.PRICE,
        ParamType.PRICE_OFFSET,
        ParamType.AMT,
        ParamType.PERCENTAGE,
    }
)
_TEMPORAL = frozenset(
    {
        ParamType.UTC_TIMESTAMP,
        ParamType.UTC_TIME_ONLY,
        ParamType.TZ_TIMESTAMP,
        ParamType.TZ_TIME_ONLY,
    }
)


# --------------------------------------------------------------------------- provenance


class SourceDocument(_Model):
    """A document that facts in the spec were taken from."""

    id: str = Field(description="Short key that citations refer to, e.g. 'acme-algo-v3'.")
    title: str
    kind: Literal["pdf", "fixatdl", "orchestra", "docx", "xlsx", "html", "other"]
    url: str | None = Field(default=None, description="Public URL the document was retrieved from.")
    publisher: str | None = None
    retrieved: date | None = None
    sha256: str | None = Field(default=None, description="Hash of the exact bytes processed.")


class Citation(_Model):
    """Points a fact back at the place in a source document that supports it."""

    source_id: str
    page: int | None = Field(default=None, ge=1)
    quote: str | None = Field(default=None, description="Verbatim supporting text.")
    locator: str | None = Field(
        default=None, description="Finer position: an XPath, 'table 4.2 row 3', etc."
    )


class _Cited(_Model):
    citations: list[Citation] = Field(default_factory=list)


# --------------------------------------------------------------------------- parameters


class EnumValue(_Cited):
    """One permitted value of an enumerated parameter."""

    wire_value: str
    label: str | None = Field(default=None, description="Human-facing name, e.g. 'Passive'.")
    enum_id: str | None = Field(
        default=None, description="Stable identifier within the parameter (FIXatdl enumID)."
    )
    description: str | None = None


class Parameter(_Cited):
    """A single algo parameter, typically carried in its own FIX tag."""

    name: str
    type: ParamType
    fix_tag: int | None = Field(
        default=None, gt=0, description="Absent for parameters that never go on the wire."
    )
    required: bool = False
    description: str | None = None
    enum_values: list[EnumValue] = Field(default_factory=list)

    min_value: str | None = None
    max_value: str | None = None
    const_value: str | None = None
    default_value: str | None = Field(
        default=None, description="Wire value pre-selected for the user, if the spec gives one."
    )

    precision: int | None = Field(default=None, ge=0)
    min_length: int | None = Field(default=None, ge=0)
    max_length: int | None = Field(default=None, ge=0)
    multiply_by_100: bool | None = Field(
        default=None, description="Percentage: user enters 5 meaning 5%, wire carries 0.05."
    )
    true_wire_value: str | None = None
    false_wire_value: str | None = None
    invert_on_wire: bool | None = Field(
        default=None, description="Multiple-value types: values listed are the ones NOT selected."
    )
    local_mkt_tz: str | None = Field(
        default=None,
        description="Times are entered in this market time zone (e.g. 'America/Chicago').",
    )

    mutable_on_cxl_rpl: bool | None = Field(
        default=None, description="May be changed on a cancel/replace. FIXatdl default: true."
    )
    revert_on_cxl_rpl: bool | None = None
    defined_by_fix: bool | None = Field(
        default=None, description="Tag is a standard FIX field rather than a custom one."
    )

    @model_validator(mode="after")
    def _check(self) -> Parameter:
        wires = [e.wire_value for e in self.enum_values]
        dupes = {w for w in wires if wires.count(w) > 1}
        if dupes:
            raise ValueError(f"parameter {self.name!r}: duplicate enum wire values {sorted(dupes)}")
        ids = [e.enum_id for e in self.enum_values if e.enum_id is not None]
        if len(ids) != len(set(ids)):
            raise ValueError(f"parameter {self.name!r}: duplicate enum_id values")
        if self.multiply_by_100 is not None and self.type is not ParamType.PERCENTAGE:
            raise ValueError(f"parameter {self.name!r}: multiply_by_100 only applies to Percentage")
        if (
            self.true_wire_value is not None or self.false_wire_value is not None
        ) and self.type is not ParamType.BOOLEAN:
            raise ValueError(f"parameter {self.name!r}: true/false wire values need Boolean type")
        return self

    def enum_by_wire(self, wire_value: str) -> EnumValue | None:
        return next((e for e in self.enum_values if e.wire_value == wire_value), None)


# --------------------------------------------------------------------------- validation rules

Operator = Literal["EX", "NX", "EQ", "NE", "LT", "LE", "GT", "GE"]
LogicOperator = Literal["AND", "OR", "XOR", "NOT"]


class Edit(_Model):
    """A validation condition: either a comparison or a logical combination.

    A comparison names a ``field`` (a parameter name, or ``FIX_<FieldName>`` for
    a standard order field such as ``FIX_OrderQty``) and an ``operator``, with
    either a literal ``value`` or a second ``field2``. EX and NX test presence
    and take neither.
    """

    field: str | None = None
    operator: Operator | None = None
    value: str | None = None
    field2: str | None = None
    logic: LogicOperator | None = None
    children: list[Edit] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check(self) -> Edit:
        if self.logic is not None:
            if self.field or self.operator:
                raise ValueError("an Edit is either a comparison or a logical group, not both")
            if self.logic == "NOT" and len(self.children) != 1:
                raise ValueError("NOT takes exactly one child")
            if self.logic != "NOT" and len(self.children) < 2:
                raise ValueError(f"{self.logic} takes at least two children")
        else:
            if not (self.field and self.operator):
                raise ValueError("a comparison Edit needs field and operator")
            if self.children:
                raise ValueError("a comparison Edit cannot have children")
            if self.operator in ("EX", "NX") and (self.value is not None or self.field2):
                raise ValueError(f"{self.operator} tests presence and takes no value")
            if self.operator not in ("EX", "NX") and (self.value is None) == (self.field2 is None):
                raise ValueError(f"{self.operator} needs exactly one of value or field2")
        return self

    def fields(self) -> set[str]:
        """Every field name this condition reads, recursively."""
        out = {f for f in (self.field, self.field2) if f}
        for child in self.children:
            out |= child.fields()
        return out


class StrategyEdit(_Cited):
    """A rule the order must satisfy.

    ``edit`` describes the *valid* state. ``message`` is the error shown when
    ``edit`` evaluates false. This matches FIXatdl StrategyEdit semantics.
    """

    message: str
    edit: Edit


# --------------------------------------------------------------------------- strategies


class Inclusion(_Model):
    code: str
    include: bool = True


class RegionInclusion(Inclusion):
    """A region (FIXatdl: TheAmericas, EuropeMiddleEastAfrica, AsiaPacificJapan)
    with optional per-country overrides, by ISO 3166 code."""

    countries: list[Inclusion] = Field(default_factory=list)


class Applicability(_Model):
    """Where a strategy may be used. Empty lists mean unrestricted."""

    regions: list[RegionInclusion] = Field(default_factory=list)
    markets: list[Inclusion] = Field(default_factory=list, description="By MIC code.")
    security_types: list[Inclusion] = Field(default_factory=list, description="FIX SecurityType.")


class Strategy(_Cited):
    """One algorithm offered by a provider: VWAP, TWAP, Implementation Shortfall..."""

    name: str = Field(description="Unique identifier within the spec.")
    wire_value: str = Field(description="Value sent in the strategy identifier tag (847).")
    version: str = "1"
    label: str | None = Field(default=None, description="Name shown to traders.")
    description: str | None = None
    fix_msg_type: str | None = Field(default=None, description="FIXatdl default when absent: D.")
    provider_id: str | None = None
    provider_sub_id: str | None = None
    applicability: Applicability = Field(default_factory=Applicability)
    parameters: list[Parameter] = Field(default_factory=list)
    edits: list[StrategyEdit] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check(self) -> Strategy:
        names = [p.name for p in self.parameters]
        dupes = {n for n in names if names.count(n) > 1}
        if dupes:
            raise ValueError(f"strategy {self.name!r}: duplicate parameter names {sorted(dupes)}")
        tags = [p.fix_tag for p in self.parameters if p.fix_tag is not None]
        dupe_tags = {t for t in tags if tags.count(t) > 1}
        if dupe_tags:
            raise ValueError(f"strategy {self.name!r}: tag used twice {sorted(dupe_tags)}")
        return self

    def parameter(self, name: str) -> Parameter:
        for p in self.parameters:
            if p.name == name:
                return p
        raise KeyError(f"strategy {self.name!r} has no parameter {name!r}")

    def dangling_edit_fields(self) -> set[str]:
        """Edit fields that name neither a parameter nor a standard FIX_ field."""
        known = {p.name for p in self.parameters}
        used: set[str] = set()
        for se in self.edits:
            used |= se.edit.fields()
        return {f for f in used if f not in known and not f.startswith("FIX_")}


class AlgoSpec(_Model):
    """A provider's complete algo offering: the unit Concord converts and diffs."""

    ir_version: str = IR_VERSION
    provider: str | None = None
    strategy_identifier_tag: int = Field(default=847, gt=0)
    version_identifier_tag: int | None = Field(default=None, gt=0)
    description: str | None = None
    strategies: list[Strategy] = Field(default_factory=list)
    sources: list[SourceDocument] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check(self) -> AlgoSpec:
        names = [s.name for s in self.strategies]
        if len(names) != len(set(names)):
            raise ValueError("duplicate strategy names")
        wires = [s.wire_value for s in self.strategies]
        if len(wires) != len(set(wires)):
            raise ValueError("duplicate strategy wire values")
        source_ids = {s.id for s in self.sources}
        missing = {c.source_id for c in self.iter_citations()} - source_ids
        if missing:
            raise ValueError(f"citations refer to unknown sources: {sorted(missing)}")
        return self

    def strategy(self, name: str) -> Strategy:
        for s in self.strategies:
            if s.name == name:
                return s
        raise KeyError(f"no strategy {name!r}")

    def iter_citations(self):
        for s in self.strategies:
            yield from s.citations
            for p in s.parameters:
                yield from p.citations
                for e in p.enum_values:
                    yield from e.citations
            for se in s.edits:
                yield from se.citations
