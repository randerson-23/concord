"""MCP tools: handlers called directly (no transport), plus one stdio smoke test."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest
from test_lint import FIX42, LATEST

from concord.ir import AlgoSpec, Parameter, ParamType, Strategy
from concord.mcp_tools import (
    ToolError,
    describe_spec,
    diff_specs_tool,
    fix_field,
    lint_spec_tool,
    load_spec,
)

FIXTURE = Path(__file__).parent / "fixtures" / "fixatdl" / "example_broker.xml"


@pytest.fixture
def dicts(tmp_path: Path) -> Path:
    d = tmp_path / "dicts"
    d.mkdir()
    (d / "OrchestraFIXLatest.xml").write_text(LATEST)
    (d / "OrchestraFIX42.xml").write_text(FIX42)
    return d


def _v1(tmp_path: Path) -> Path:
    spec = AlgoSpec(
        provider="Acme",
        strategy_identifier_tag=847,
        strategies=[
            Strategy(
                name="VWAP",
                wire_value="1",
                parameters=[
                    Parameter(name="Qty", type=ParamType.INT, fix_tag=38, required=True),
                    Parameter(name="Odd", type=ParamType.INT, fix_tag=99),  # not a FIX tag
                ],
            )
        ],
    )
    p = tmp_path / "v1.json"
    p.write_text(spec.model_dump_json(exclude_none=True))
    return p


def _v2(tmp_path: Path) -> Path:
    spec = AlgoSpec.model_validate_json(_v1(tmp_path).read_text())
    spec.strategies[0].parameters = spec.strategies[0].parameters[1:]  # Qty removed: breaking
    p = tmp_path / "v2.json"
    p.write_text(spec.model_dump_json(exclude_none=True))
    return p


def test_fix_field_code_set_and_union(dicts: Path) -> None:
    out = fix_field(847, "latest", dicts)
    assert out["data"]["name"] == "TargetStrategy"
    assert out["data"]["code_set"] == "TargetStrategyCodeSet"
    assert out["data"]["union_data_type"] == "Reserved1000Plus"
    assert {"value": "1", "name": "VWAP"} in out["data"]["values"]
    assert out["summary"].startswith("847 TargetStrategy")
    plain = fix_field(38, "4.2", dicts)["data"]
    assert plain["name"] == "OrderQty" and plain["code_set"] is None and plain["values"] == []


def test_fix_field_errors_say_what_to_do(dicts: Path, tmp_path: Path) -> None:
    with pytest.raises(ToolError, match=r"tag 847 is not defined in FIX\.4\.2"):
        fix_field(847, "4.2", dicts)
    with pytest.raises(ToolError, match="expected one of"):
        fix_field(38, "9.9", dicts)
    with pytest.raises(ToolError, match=r"dictionary file not found.*fetch it with"):
        fix_field(38, "latest", tmp_path / "missing")


def test_lint_reports_an_undefined_standard_tag(dicts: Path, tmp_path: Path) -> None:
    out = lint_spec_tool(str(_v1(tmp_path)), "latest", dicts)
    errors = [f for f in out["data"]["findings"] if f["severity"] == "error"]
    assert [f["location"] for f in errors] == ["Strategy[@name='VWAP']/Parameter[@name='Odd']"]
    assert out["summary"].startswith("1 errors")


def test_diff_finds_the_breaking_change(tmp_path: Path) -> None:
    out = diff_specs_tool(str(_v1(tmp_path)), str(_v2(tmp_path)))
    assert out["data"]["summary"]["breaking"] >= 1
    assert any(c["severity"] == "breaking" for c in out["data"]["changes"])
    assert "breaking" in out["summary"]


def test_describe_spec_shape_for_json_and_fixatdl(tmp_path: Path) -> None:
    data = describe_spec(str(_v1(tmp_path)))["data"]
    assert data["provider"] == "Acme" and data["strategy_identifier_tag"] == 847
    (s,) = data["strategies"]
    assert s["name"] == "VWAP" and s["wire_value"] == "1"
    assert [(p["name"], p["fix_tag"], p["type"], p["required"]) for p in s["parameters"]] == [
        ("Qty", 38, "Int", True),
        ("Odd", 99, "Int", False),
    ]
    fixatdl = describe_spec(str(FIXTURE))
    assert fixatdl["data"]["strategies"] and "strategies" in fixatdl["summary"]


def test_bad_paths_give_errors_not_tracebacks(tmp_path: Path) -> None:
    with pytest.raises(ToolError, match="not a file"):
        load_spec(str(tmp_path / "nope.json"))
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    with pytest.raises(ToolError, match=r"bad\.json"):
        load_spec(str(bad))
    xxe = tmp_path / "x.xml"
    xxe.write_text("<not-fixatdl/>")
    with pytest.raises(ToolError, match=r"x\.xml"):
        load_spec(str(xxe))


def test_stdio_smoke_lists_the_four_tools(dicts: Path, tmp_path: Path) -> None:
    pytest.importorskip("mcp")
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    params = StdioServerParameters(
        command=sys.executable,
        args=["-c", "from concord.cli import main; raise SystemExit(main(['mcp']))"],
        env={"CONCORD_FIX_DICT_DIR": str(dicts)},
    )

    async def go() -> tuple[list[str], str]:
        async with Client(params) as client:
            tools = await client.list_tools()
            res = await client.call_tool("fix_field", {"tag": 847})
            return sorted(t.name for t in tools.tools), json.dumps(res.model_dump(mode="json"))

    names, text = asyncio.run(asyncio.wait_for(go(), 60))
    assert names == ["describe_spec", "diff_specs", "fix_field", "lint_spec"]
    assert "TargetStrategy" in text
