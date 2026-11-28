"""Read-only tools behind ``concord mcp`` (item 17a): plain functions, no MCP SDK needed.

Each handler returns ``{"summary": <short text>, "data": <JSON-able>}`` or raises
:class:`ToolError` with a message that says what was expected. Paths are files the caller names;
they are read with the existing hardened readers. Nothing is written, nothing is fetched here
(the FIX dictionaries are read from disk, as for ``concord lint``).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from concord.diff import diff_specs
from concord.fixatdl import FixatdlError, read_fixatdl_file
from concord.fixdict import DictionaryError, FixDictionary, dictionary_path, load_dictionary
from concord.ir import AlgoSpec
from concord.lint import lint_spec

MAX_BYTES = 20_000_000
MAX_CODES = 200  # code-set values returned for one field, so an answer stays small
VERSIONS = ("4.2", "4.4", "latest")


class ToolError(ValueError):
    """A tool call that cannot be answered; the message is shown to the caller."""


def _version(version: str) -> str:
    if version not in VERSIONS:
        raise ToolError(f"fix_version {version!r}: expected one of {list(VERSIONS)}")
    return version


def _dictionary(version: str, dict_dir: str | Path | None) -> FixDictionary:
    try:
        return load_dictionary(dictionary_path(_version(version), dict_dir))
    except DictionaryError as exc:
        raise ToolError(str(exc)) from exc


def load_spec(path: str) -> tuple[AlgoSpec, list[str]]:
    """Read an IR JSON file or a FIXatdl file. Returns the spec and the reader's warnings."""
    p = Path(path).expanduser()
    if not p.is_file():
        raise ToolError(f"{path}: not a file; expected a FIXatdl XML or IR JSON file")
    if p.stat().st_size > MAX_BYTES:
        raise ToolError(f"{path}: larger than {MAX_BYTES} bytes")
    try:
        if p.suffix.lower() == ".json":
            return AlgoSpec.model_validate_json(p.read_text(encoding="utf-8")), []
        result = read_fixatdl_file(p)
        return result.spec, list(result.warnings)
    except (FixatdlError, ValueError, OSError) as exc:
        raise ToolError(f"{path}: {exc}") from exc


def fix_field(
    tag: int, fix_version: str = "latest", dict_dir: str | Path | None = None
) -> dict[str, Any]:
    """What a FIX tag is: name, type, code set values and union data type."""
    d = _dictionary(fix_version, dict_dir)
    f = d.fields.get(tag)
    if f is None:
        raise ToolError(f"tag {tag} is not defined in {d.label}; expected a tag from that version")
    codes = d.codes(tag)
    values = [{"value": v, "name": n} for v, n in (codes.values.items() if codes else [])]
    data = {
        "tag": tag,
        "name": f.name,
        "type": d.base_type(tag),
        "code_set": codes.name if codes else None,
        "union_data_type": f.union,
        "values": values[:MAX_CODES],
        "values_truncated": len(values) > MAX_CODES,
        "dictionary": d.label,
    }
    kind = f"code set {codes.name} ({len(values)} values)" if codes else "no code set"
    return {"summary": f"{tag} {f.name}: {data['type']}, {kind} [{d.label}]", "data": data}


def lint_spec_tool(
    path: str, fix_version: str = "latest", dict_dir: str | Path | None = None
) -> dict[str, Any]:
    """``concord lint``: standard-tag findings for a spec file."""
    spec, warnings = load_spec(path)
    wanted = _dictionary(fix_version, dict_dir)
    latest = None if fix_version == "latest" else _dictionary("latest", dict_dir)
    findings = [f.to_dict() for f in lint_spec(spec, wanted, latest)]
    errors = sum(1 for f in findings if f["severity"] == "error")
    summary = f"{errors} errors, {len(findings) - errors} warnings against {wanted.label}"
    return {"summary": summary, "data": {"findings": findings, "reader_warnings": warnings}}


def diff_specs_tool(old_path: str, new_path: str) -> dict[str, Any]:
    """``concord diff``: classified changes between two spec files."""
    old, _ = load_spec(old_path)
    new, _ = load_spec(new_path)
    report = diff_specs(old, new)
    counts = report.to_dict()["summary"]
    summary = ", ".join(f"{n} {sev}" for sev, n in counts.items())
    return {"summary": summary, "data": report.to_dict()}


def describe_spec(path: str) -> dict[str, Any]:
    """Strategies, parameters, tags and citation counts of a spec file, structured."""
    spec, warnings = load_spec(path)
    strategies = []
    for s in spec.strategies:
        strategies.append(
            {
                "name": s.name,
                "label": s.label,
                "wire_value": s.wire_value,
                "version": s.version,
                "citations": len(s.citations),
                "edits": len(s.edits),
                "parameters": [
                    {
                        "name": p.name,
                        "type": p.type.value,
                        "fix_tag": p.fix_tag,
                        "required": p.required,
                        "enum_values": [e.wire_value for e in p.enum_values],
                        "min_value": p.min_value,
                        "max_value": p.max_value,
                        "mutable_on_cxl_rpl": p.mutable_on_cxl_rpl,
                        "citations": [
                            {"source_id": c.source_id, "page": c.page, "locator": c.locator}
                            for c in p.citations
                        ],
                    }
                    for p in s.parameters
                ],
            }
        )
    data = {
        "provider": spec.provider,
        "strategy_identifier_tag": spec.strategy_identifier_tag,
        "sources": [{"id": src.id, "title": src.title, "url": src.url} for src in spec.sources],
        "strategies": strategies,
        "reader_warnings": warnings,
    }
    nparams = sum(len(s["parameters"]) for s in strategies)
    who = spec.provider or "unknown provider"
    summary = f"{who}: {len(strategies)} strategies, {nparams} parameters"
    return {"summary": summary, "data": data}
