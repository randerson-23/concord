"""``concord mcp``: a stdio MCP server over Concord's read-only tools (item 17a).

Needs the optional ``mcp`` extra (``uv sync --extra mcp``). The tool logic lives in
:mod:`concord.mcp_tools` so it is testable without the SDK.
"""

from __future__ import annotations

import json
from typing import Any

from concord import mcp_tools
from concord.mcp_tools import ToolError

INSTRUCTIONS = (
    "Concord answers questions about FIX rules of engagement deterministically: what a tag is, "
    "whether a broker algo spec uses standard tags correctly, what changed between two spec "
    "versions, and what a spec contains. Tools only read the files you name."
)


def _run(fn: Any, *args: Any) -> str:
    try:
        result = fn(*args)
    except ToolError as exc:
        raise ValueError(str(exc)) from exc
    return result["summary"] + "\n" + json.dumps(result["data"], indent=2, ensure_ascii=False)


def build_server() -> Any:
    try:
        from mcp.server.mcpserver import MCPServer
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise RuntimeError(
            "the MCP SDK is not installed; expected `uv sync --extra mcp` (or pip install "
            "'concord[mcp]')"
        ) from exc
    server = MCPServer("concord", instructions=INSTRUCTIONS)

    @server.tool()
    def fix_field(tag: int, fix_version: str = "latest") -> str:
        """Look up a FIX tag: name, type, code set values. fix_version: 4.2, 4.4 or latest."""
        return _run(mcp_tools.fix_field, tag, fix_version)

    @server.tool()
    def lint_spec(path: str, fix_version: str = "latest") -> str:
        """Check a spec file's standard FIX tags against the FIX dictionary."""
        return _run(mcp_tools.lint_spec_tool, path, fix_version)

    @server.tool()
    def diff_specs(old_path: str, new_path: str) -> str:
        """Classify the changes between two spec files as breaking, additive or cosmetic."""
        return _run(mcp_tools.diff_specs_tool, old_path, new_path)

    @server.tool()
    def describe_spec(path: str) -> str:
        """List a spec file's strategies, parameters, FIX tags and citations."""
        return _run(mcp_tools.describe_spec, path)

    return server


def serve() -> None:
    build_server().run("stdio")
