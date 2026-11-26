"""Human decisions on review cards, applied to a spec (item 16b, D31).

``decisions.json`` in a ``corpus convert`` folder maps a review card id to a decision::

    {"<card id>": {"decision": "accept" | "reject" | "correct", "reviewer": "...",
                   "at": "YYYY-MM-DD", "note": "...", "corrections": {"max_value": "100"}}}

``apply_to_folder`` starts from ``spec.extracted.json`` (a copy of the first ``spec.json``, so
applying twice gives the same result), records an accept or correction as a :class:`Review` on the
fact, drops a rejected fact, rewrites ``spec.json``, ``strategies.xml``, ``orchestra.xml`` and
``site/``, and writes ``applied.json``. It never calls a model and is deterministic.
A decision about a fact that is not in the spec (a fact the extractor already dropped, an edit, a
run-level item) cannot be applied; it is listed as unapplied with the reason.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from concord.fixatdl import write_fixatdl
from concord.ir import AlgoSpec, EnumValue, Parameter, Review, Strategy
from concord.orchestra import write_orchestra
from concord.review import card_ids, load_items
from concord.site import write_site

DECISIONS = ("accept", "reject", "correct")
_SEG = re.compile(r"(Strategy|Parameter|EnumValue)\[@(?:name|wireValue)='([^']*)'\]")
_PROTECTED = {"citations", "review"}  # a correction never rewrites provenance


@dataclass
class ApplyResult:
    spec: AlgoSpec
    applied: list[dict[str, str]] = field(default_factory=list)
    unapplied: list[dict[str, str]] = field(default_factory=list)
    open_cards: list[str] = field(default_factory=list)

    @property
    def resolved(self) -> bool:
        return not self.unapplied and not self.open_cards

    def to_dict(self) -> dict[str, Any]:
        return {"applied": self.applied, "unapplied": self.unapplied, "open": self.open_cards}


def load_decisions(path: Path) -> dict[str, dict[str, Any]]:
    """Read and validate ``decisions.json``; errors name the card id."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"{path}: could not read ({exc}); expected a JSON object") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a JSON object keyed by card id")
    for cid, d in data.items():
        if not isinstance(d, dict) or d.get("decision") not in DECISIONS:
            raise ValueError(f"{path}: card {cid}: decision must be one of {list(DECISIONS)}")
        if not isinstance(d.get("reviewer"), str) or not d["reviewer"].strip():
            raise ValueError(f"{path}: card {cid}: reviewer is required")
        try:
            date.fromisoformat(str(d.get("at")))
        except ValueError as exc:
            raise ValueError(f"{path}: card {cid}: 'at' must be an ISO date, YYYY-MM-DD") from exc
        corr = d.get("corrections")
        if d["decision"] == "correct" and not (isinstance(corr, dict) and corr):
            raise ValueError(f"{path}: card {cid}: a correction needs a non-empty 'corrections'")
        if corr and (not isinstance(corr, dict) or _PROTECTED & set(corr)):
            raise ValueError(f"{path}: card {cid}: corrections may not touch {sorted(_PROTECTED)}")
    return data


class Absent(LookupError):
    """The fact is not in the spec because it was dropped before review."""


def _find(spec: AlgoSpec, location: str) -> tuple[Strategy, Parameter | None, EnumValue | None]:
    segs = _SEG.findall(location)
    if not segs or segs[0][0] != "Strategy" or location.count("/") != len(segs) - 1:
        raise LookupError("not a fact in the spec")
    strategy = next((s for s in spec.strategies if s.name == segs[0][1]), None)
    if strategy is None:
        raise Absent("fact is not in the spec (dropped earlier)")
    if len(segs) == 1:
        return strategy, None, None
    param = next((p for p in strategy.parameters if p.name == segs[1][1]), None)
    if param is None:
        raise Absent("fact is not in the spec (dropped earlier)")
    if len(segs) == 2:
        return strategy, param, None
    enum = next((e for e in param.enum_values if e.wire_value == segs[2][1]), None)
    if enum is None:
        raise Absent("fact is not in the spec (dropped earlier)")
    return strategy, param, enum


def _replace(items: list[Any], old: Any, new: Any) -> None:
    items[next(i for i, x in enumerate(items) if x is old)] = new


def apply_decisions(
    spec: AlgoSpec, items: list[dict[str, Any]], decisions: dict[str, dict[str, Any]]
) -> ApplyResult:
    """Apply ``decisions`` (keyed by card id) to a copy of ``spec``."""
    out = spec.model_copy(deep=True)
    result = ApplyResult(out)
    ids = card_ids(items)
    by_id = dict(zip(ids, items, strict=True))
    for cid in sorted(set(decisions) - set(by_id)):
        result.unapplied.append({"card_id": cid, "location": "", "reason": "unknown card id"})
    for cid in ids:
        d = decisions.get(cid)
        loc = by_id[cid].get("location", "")
        if d is None:
            if by_id[cid].get("reason") != "lint_warning":  # warnings never block
                result.open_cards.append(cid)
            continue
        try:
            strategy, param, enum = _find(out, loc)
            fact = enum or param or strategy
            if d["decision"] == "reject":
                if enum is not None and param is not None:
                    param.enum_values.remove(enum)
                elif param is not None:
                    strategy.parameters.remove(param)
                else:
                    out.strategies.remove(strategy)
            else:
                if d["decision"] == "correct":
                    data = {**fact.model_dump(), **d["corrections"]}
                    new = type(fact).model_validate(data)
                    if enum is not None and param is not None:
                        _replace(param.enum_values, enum, new)
                    elif param is not None:
                        _replace(strategy.parameters, param, new)
                    else:
                        _replace(out.strategies, strategy, new)
                    fact = new
                verdict = "accepted" if d["decision"] == "accept" else "corrected"
                fact.review = Review(
                    decision=verdict,
                    reviewer=d["reviewer"],
                    at=date.fromisoformat(str(d["at"])),
                    note=d.get("note"),
                    card_id=cid,
                )
        except Absent as exc:
            if d["decision"] == "reject":  # nothing to drop: the fact is already absent
                result.applied.append({"card_id": cid, "decision": "reject", "location": loc})
            else:
                reason = f"{exc}; restoring a dropped fact is not supported yet"
                result.unapplied.append({"card_id": cid, "location": loc, "reason": reason})
            continue
        except LookupError as exc:
            result.unapplied.append({"card_id": cid, "location": loc, "reason": str(exc)})
            continue
        except (ValidationError, ValueError) as exc:
            reason = f"correction rejected: {str(exc).splitlines()[0]}"
            result.unapplied.append({"card_id": cid, "location": loc, "reason": reason})
            continue
        result.applied.append({"card_id": cid, "decision": d["decision"], "location": loc})
    return result


def _atomic_write(path: Path, data: bytes) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def write_outputs(root: Path, spec: AlgoSpec) -> None:
    """Rewrite the spec-derived outputs of a convert folder."""
    _atomic_write(
        root / "spec.json", (spec.model_dump_json(indent=2, exclude_none=True) + "\n").encode()
    )
    _atomic_write(root / "strategies.xml", write_fixatdl(spec))
    _atomic_write(root / "orchestra.xml", write_orchestra(spec).xml)
    write_site(spec, root / "site")


def apply_to_folder(out_dir: str | Path) -> ApplyResult:
    """Apply ``decisions.json`` in a convert folder and rewrite its outputs."""
    root = Path(out_dir)
    extracted = root / "spec.extracted.json"
    if not extracted.is_file():
        source = root / "spec.json"
        if not source.is_file():
            raise ValueError(f"{source}: not found; expected a `concord corpus convert` folder")
        _atomic_write(extracted, source.read_bytes())
    spec = AlgoSpec.model_validate_json(extracted.read_text(encoding="utf-8"))
    decisions_path = root / "decisions.json"
    decisions = load_decisions(decisions_path) if decisions_path.is_file() else {}
    result = apply_decisions(spec, load_items(root), decisions)
    write_outputs(root, result.spec)
    report = json.dumps(result.to_dict(), indent=2) + "\n"
    _atomic_write(root / "applied.json", report.encode())
    return result
