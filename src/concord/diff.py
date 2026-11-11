"""Spec diff engine: compare two ``AlgoSpec`` values and classify every change.

Severity reflects the impact on a client that already integrated the old spec:

* **breaking** - orders that were valid may now be rejected, or mean something
  different on the wire.
* **additive** - the old integration keeps working; something new is available
  (or a restriction was relaxed).
* **cosmetic** - labels and descriptions; nothing on the wire changes.

The output is deterministic: same two specs in, same report out.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from concord.ir import AlgoSpec, Applicability, Parameter, Strategy

Severity = Literal["breaking", "additive", "cosmetic"]
SEVERITIES: tuple[Severity, ...] = ("breaking", "additive", "cosmetic")


@dataclass(frozen=True)
class Change:
    severity: Severity
    path: str
    kind: str
    message: str
    old: str | None = None
    new: str | None = None


@dataclass
class DiffReport:
    changes: list[Change]

    def by_severity(self, severity: Severity) -> list[Change]:
        return [c for c in self.changes if c.severity == severity]

    @property
    def has_breaking(self) -> bool:
        return any(c.severity == "breaking" for c in self.changes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": {s: len(self.by_severity(s)) for s in SEVERITIES},
            "changes": [asdict(c) for c in self.changes],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    def to_text(self) -> str:
        if not self.changes:
            return "No differences."
        counts = ", ".join(f"{len(self.by_severity(s))} {s}" for s in SEVERITIES)
        lines = [f"{len(self.changes)} change(s): {counts}"]
        for sev in SEVERITIES:
            group = self.by_severity(sev)
            if not group:
                continue
            lines += ["", sev.upper()]
            lines += [f"  {c.path}: {c.message}" for c in group]
        return "\n".join(lines)


def diff_specs(old: AlgoSpec, new: AlgoSpec) -> DiffReport:
    changes: list[Change] = []

    def add(sev: Severity, path: str, kind: str, msg: str, o: Any = None, n: Any = None) -> None:
        changes.append(
            Change(
                sev, path, kind, msg, None if o is None else str(o), None if n is None else str(n)
            )
        )

    def scalar(sev: Severity, path: str, label: str, o: Any, n: Any) -> None:
        if o != n:
            add(sev, path, f"{label}_changed", f"{label} changed {_show(o)} -> {_show(n)}", o, n)

    scalar("breaking", "spec", "provider", old.provider, new.provider)
    scalar("breaking", "spec", "strategy_identifier_tag", *_t(old, new, "strategy_identifier_tag"))
    scalar("breaking", "spec", "version_identifier_tag", *_t(old, new, "version_identifier_tag"))
    scalar("cosmetic", "spec", "description", old.description, new.description)
    _diff_wire_contract(old, new, add)

    old_s = {s.name: s for s in old.strategies}
    new_s = {s.name: s for s in new.strategies}
    gone, fresh = old_s.keys() - new_s.keys(), new_s.keys() - old_s.keys()
    # A strategy that changed name but kept its wire value is the same strategy.
    # Only an unambiguous pair counts: a wire value shared by several removed or
    # several added strategies is not matched.
    renamed_s: dict[str, str] = {}
    for rn in sorted(gone):
        wv = old_s[rn].wire_value
        if wv is None:
            continue
        gs = [g for g in gone if old_s[g].wire_value == wv]
        fs = [f for f in fresh if new_s[f].wire_value == wv]
        if len(gs) == 1 and len(fs) == 1:
            renamed_s[rn] = fs[0]
    gone -= renamed_s.keys()
    fresh -= set(renamed_s.values())
    for rn, an in sorted(renamed_s.items()):
        add(
            "cosmetic",
            _spath(an),
            "strategy_renamed",
            f"renamed {rn!r} -> {an!r} (wire value {old_s[rn].wire_value})",
            rn,
            an,
        )
        _diff_strategy(old_s[rn], new_s[an], add, scalar, sname=an)
    for name in sorted(gone):
        add(
            "breaking", _spath(name), "strategy_removed", "strategy removed", old_s[name].wire_value
        )
    for name in sorted(fresh):
        add(
            "additive",
            _spath(name),
            "strategy_added",
            "strategy added",
            None,
            new_s[name].wire_value,
        )
    for name in sorted(old_s.keys() & new_s.keys()):
        _diff_strategy(old_s[name], new_s[name], add, scalar)

    return DiffReport(changes)


def _diff_wire_contract(old: AlgoSpec, new: AlgoSpec, add) -> None:
    """D9 rules for the document-level wire-contract attributes (D16)."""
    for attr, what in (
        ("tag957_support", "StrategyParameters group (957) support"),
        ("change_strategy_on_cxl_rpl", "changing the strategy on cancel/replace"),
    ):
        was, now = getattr(old, attr) is True, getattr(new, attr) is True
        if was and not now:
            add("breaking", "spec", f"{attr}_changed", f"{what} withdrawn", was, now)
        elif now and not was:
            add("additive", "spec", f"{attr}_changed", f"{what} now supported", was, now)
    o, n = old.draft_flag_identifier_tag, new.draft_flag_identifier_tag
    if o != n:
        sev = "additive" if o is None else "breaking"
        add(
            sev,
            "spec",
            "draft_flag_identifier_tag_changed",
            f"draft flag tag {_show(o)} -> {_show(n)}",
            o,
            n,
        )


def _t(old: AlgoSpec, new: AlgoSpec, attr: str) -> tuple[Any, Any]:
    return getattr(old, attr), getattr(new, attr)


def _show(v: Any) -> str:
    return "(none)" if v is None else repr(v) if isinstance(v, str) else str(v)


def _spath(name: str) -> str:
    return f"Strategy[@name='{name}']"


def _ppath(strategy: str, param: str) -> str:
    return f"{_spath(strategy)}/Parameter[@name='{param}']"


def _diff_strategy(o: Strategy, n: Strategy, add, scalar, sname: str | None = None) -> None:
    sname = sname or o.name
    path = _spath(sname)
    scalar("breaking", path, "wire_value", o.wire_value, n.wire_value)
    scalar("breaking", path, "fix_msg_type", o.fix_msg_type, n.fix_msg_type)
    scalar("breaking", path, "provider_id", o.provider_id, n.provider_id)
    scalar("breaking", path, "provider_sub_id", o.provider_sub_id, n.provider_sub_id)
    scalar("cosmetic", path, "version", o.version, n.version)
    scalar("cosmetic", path, "label", o.label, n.label)
    scalar("cosmetic", path, "description", o.description, n.description)
    _diff_applicability(path, o.applicability, n.applicability, add)

    old_p = {p.name: p for p in o.parameters}
    new_p = {p.name: p for p in n.parameters}
    removed = old_p.keys() - new_p.keys()
    added = new_p.keys() - old_p.keys()

    # A parameter that changed name but kept its tag is the same wire parameter.
    renamed: dict[str, str] = {}
    for rn in sorted(removed):
        tag = old_p[rn].fix_tag
        if tag is None:
            continue
        match = next((an for an in sorted(added) if new_p[an].fix_tag == tag), None)
        if match:
            renamed[rn] = match
            added.discard(match)
    for rn, an in sorted(renamed.items()):
        add(
            "cosmetic",
            _ppath(sname, rn),
            "parameter_renamed",
            f"renamed to {an!r} (tag unchanged)",
            rn,
            an,
        )
        _diff_param(sname, old_p[rn], new_p[an], add, scalar, label=an)
    for name in sorted(removed - renamed.keys()):
        tag = old_p[name].fix_tag
        add(
            "breaking",
            _ppath(sname, name),
            "parameter_removed",
            f"parameter removed (tag {tag})" if tag else "parameter removed",
            tag,
        )
    for name in sorted(added):
        p = new_p[name]
        if p.required:
            add(
                "breaking",
                _ppath(sname, name),
                "parameter_added_required",
                f"new required parameter (tag {p.fix_tag})",
                None,
                p.fix_tag,
            )
        else:
            add(
                "additive",
                _ppath(sname, name),
                "parameter_added",
                f"new optional parameter (tag {p.fix_tag})",
                None,
                p.fix_tag,
            )
    for name in sorted(old_p.keys() & new_p.keys()):
        _diff_param(sname, old_p[name], new_p[name], add, scalar)

    _diff_edits(o, n, add, sname)


def _diff_applicability(path: str, o: Applicability, n: Applicability, add) -> None:
    def flat(a: Applicability) -> dict[tuple[str, str], bool]:
        out: dict[tuple[str, str], bool] = {}
        for r in a.regions:
            out[("region", r.code)] = r.include
            for c in r.countries:
                out[(f"country in {r.code}", c.code)] = c.include
        for m in a.markets:
            out[("market", m.code)] = m.include
        for s in a.security_types:
            out[("security type", s.code)] = s.include
        return out

    fo, fn = flat(o), flat(n)
    for key in sorted(fo.keys() | fn.keys()):
        kind, code = key
        before, after = fo.get(key), fn.get(key)
        if before == after:
            continue
        # Unlisted is treated as unrestricted; an explicit exclusion restricts.
        was = before is not False and not (before is None and _restricted(fo, kind))
        now = after is not False and not (after is None and _restricted(fn, kind))
        if was and not now:
            add(
                "breaking",
                path,
                "applicability_narrowed",
                f"{kind} {code} no longer allowed",
                before,
                after,
            )
        elif now and not was:
            add(
                "additive",
                path,
                "applicability_widened",
                f"{kind} {code} now allowed",
                before,
                after,
            )


def _restricted(flat: dict[tuple[str, str], bool], kind: str) -> bool:
    """True when the spec lists included items of this kind (so unlisted means excluded)."""
    return any(k[0] == kind and v for k, v in flat.items())


def _num(v: str | None) -> Decimal | None:
    if v is None:
        return None
    try:
        return Decimal(v)
    except InvalidOperation:
        return None


def _bound(path: str, label: str, o: Any, n: Any, add, *, lower: bool) -> None:
    """Compare a limit. ``lower`` bounds narrow when raised; upper bounds when lowered."""
    if o == n:
        return
    kind = f"{label}_changed"
    msg = f"{label} {_show(o)} -> {_show(n)}"
    if o is None:
        add("breaking", path, kind, f"{msg} (new restriction)", o, n)
        return
    if n is None:
        add("additive", path, kind, f"{msg} (restriction removed)", o, n)
        return
    a, b = (_num(o), _num(n)) if isinstance(o, str) else (Decimal(o), Decimal(n))
    if a is None or b is None:
        add("breaking", path, kind, msg, o, n)
        return
    narrowed = b > a if lower else b < a
    add(
        "breaking" if narrowed else "additive",
        path,
        kind,
        f"{msg} ({'narrowed' if narrowed else 'widened'})",
        o,
        n,
    )


def _diff_param(
    sname: str, o: Parameter, n: Parameter, add, scalar, label: str | None = None
) -> None:
    path = _ppath(sname, label or o.name)
    scalar("breaking", path, "fix_tag", o.fix_tag, n.fix_tag)
    if o.type != n.type:
        add(
            "breaking",
            path,
            "type_changed",
            f"type changed {o.type.value} -> {n.type.value}",
            o.type.value,
            n.type.value,
        )
    if o.required != n.required:
        if n.required:
            add("breaking", path, "became_required", "parameter became required", False, True)
        else:
            add("additive", path, "became_optional", "parameter became optional", True, False)

    ov, nv = {e.wire_value: e for e in o.enum_values}, {e.wire_value: e for e in n.enum_values}
    for w in sorted(ov.keys() - nv.keys()):
        add("breaking", path, "enum_removed", f"enum value {w!r} removed", w)
    for w in sorted(nv.keys() - ov.keys()):
        add("additive", path, "enum_added", f"enum value {w!r} added", None, w)
    for w in sorted(ov.keys() & nv.keys()):
        scalar("cosmetic", path, f"enum[{w}] label", ov[w].label, nv[w].label)
        scalar("cosmetic", path, f"enum[{w}] description", ov[w].description, nv[w].description)

    _bound(path, "min_value", o.min_value, n.min_value, add, lower=True)
    _bound(path, "max_value", o.max_value, n.max_value, add, lower=False)
    _bound(path, "min_length", o.min_length, n.min_length, add, lower=True)
    _bound(path, "max_length", o.max_length, n.max_length, add, lower=False)
    _bound(path, "precision", o.precision, n.precision, add, lower=False)

    scalar("breaking", path, "const_value", o.const_value, n.const_value)
    scalar("additive", path, "default_value", o.default_value, n.default_value)
    for attr in (
        "multiply_by_100",
        "true_wire_value",
        "false_wire_value",
        "invert_on_wire",
        "local_mkt_tz",
    ):
        scalar("breaking", path, attr, getattr(o, attr), getattr(n, attr))

    om, nm = o.mutable_on_cxl_rpl is not False, n.mutable_on_cxl_rpl is not False
    if om and not nm:
        add(
            "breaking",
            path,
            "mutable_changed",
            "no longer changeable on cancel/replace",
            True,
            False,
        )
    elif nm and not om:
        add("additive", path, "mutable_changed", "now changeable on cancel/replace", False, True)
    scalar("cosmetic", path, "revert_on_cxl_rpl", o.revert_on_cxl_rpl, n.revert_on_cxl_rpl)
    scalar("cosmetic", path, "defined_by_fix", o.defined_by_fix, n.defined_by_fix)
    scalar("cosmetic", path, "description", o.description, n.description)


def _diff_edits(o: Strategy, n: Strategy, add, name: str) -> None:
    path = _spath(name)
    oe = {se.edit.model_dump_json(exclude_none=True): se for se in o.edits}
    ne = {se.edit.model_dump_json(exclude_none=True): se for se in n.edits}
    for key in sorted(oe.keys() & ne.keys()):
        if oe[key].message != ne[key].message:
            add(
                "cosmetic",
                path,
                "rule_message_changed",
                f"rule message changed: {oe[key].message!r} -> {ne[key].message!r}",
                oe[key].message,
                ne[key].message,
            )
    for key in sorted(ne.keys() - oe.keys()):
        add(
            "breaking",
            path,
            "rule_added",
            f"rule added or changed: {ne[key].message}",
            None,
            ne[key].message,
        )
    for key in sorted(oe.keys() - ne.keys()):
        add(
            "additive",
            path,
            "rule_removed",
            f"rule removed or replaced: {oe[key].message}",
            oe[key].message,
        )
