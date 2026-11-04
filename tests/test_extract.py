"""Extraction scaffold tests: recorded model responses, no API key, no network."""

from __future__ import annotations

import json
from pathlib import Path

from test_pdf import _make_pdf

from concord.cli import main
from concord.extract import ReplayBackend, extract_spec
from concord.ir import SourceDocument
from concord.pdf import Page

SRC = SourceDocument(id="doc", title="Synthetic algo guide", kind="pdf")
PAGES = [
    Page(1, "The VWAP strategy slices the order over the day. StrategyWireValue is 7.", ""),
    Page(2, "MaxPct (tag 9001) is a Percentage between 1 and 100. Style is Passive or Active.", ""),
]


def _cite(page: int, quote: str) -> dict:
    return {"source_id": "doc", "page": page, "quote": quote}


RESPONSES = {
    1: {
        "strategies": [
            {
                "name": "VWAP",
                "wire_value": "7",
                "citations": [_cite(1, "StrategyWireValue is 7")],
            },
            # invented: quote is not on the page
            {"name": "Ghost", "wire_value": "9", "citations": [_cite(1, "Ghost algo exists")]},
        ]
    },
    2: {
        "strategies": [
            {
                "name": "VWAP",
                "wire_value": "7",
                "parameters": [
                    {
                        "name": "MaxPct",
                        "type": "Percentage",
                        "fix_tag": 9001,
                        "min_value": "1",
                        "max_value": "100",
                        "citations": [
                            _cite(2, "MaxPct (tag 9001) is a Percentage between 1 and 100")
                        ],
                    },
                    {
                        "name": "Style",
                        "type": "String",
                        "fix_tag": 9002,
                        "citations": [_cite(2, "Style is Passive or Active")],
                        "enum_values": [
                            {"wire_value": "P", "citations": [_cite(2, "Passive")]},
                            # right quote, wrong page
                            {"wire_value": "X", "citations": [_cite(1, "Active")]},
                        ],
                    },
                    {"name": "NoCite", "type": "Int", "fix_tag": 9003},
                ],
            }
        ]
    },
}


class Recorded:
    def __init__(self, by_page: dict[int, str]) -> None:
        self.by_page = by_page

    def complete(self, system: str, user: str, schema: dict) -> str:
        assert "VERBATIM" in system and "properties" in schema
        n = int(user.split("\n", 1)[0].split()[1])
        return self.by_page.get(n, '{"strategies": []}')


def _run(responses: dict[int, str]):
    return extract_spec(PAGES, SRC, Recorded(responses), provider="Acme")


def test_verified_facts_merge_and_unverified_go_to_review() -> None:
    res = _run({n: json.dumps(r) for n, r in RESPONSES.items()})
    assert [s.name for s in res.spec.strategies] == ["VWAP"]
    vwap = res.spec.strategy("VWAP")
    assert [p.name for p in vwap.parameters] == ["MaxPct", "Style"]
    assert [e.wire_value for e in vwap.parameter("Style").enum_values] == ["P"]
    assert res.spec.provider == "Acme" and res.spec.sources == [SRC]
    rejected = {r.location for r in res.review if r.reason == "unverified"}
    assert rejected == {
        "Strategy[@name='Ghost']",
        "Strategy[@name='VWAP']/Parameter[@name='Style']/EnumValue[@wireValue='X']",
        "Strategy[@name='VWAP']/Parameter[@name='NoCite']",
    }


def test_every_kept_citation_verifies() -> None:
    from concord.verify import verify_spec

    res = _run({n: json.dumps(r) for n, r in RESPONSES.items()})
    assert verify_spec(res.spec, {"doc": PAGES}).ok


def test_conflicting_scalar_is_kept_first_and_reviewed() -> None:
    p2 = json.loads(json.dumps(RESPONSES[2]))
    p2["strategies"][0]["parameters"][0]["max_value"] = "50"
    p2["strategies"][0]["parameters"][0]["citations"] = [_cite(2, "MaxPct (tag 9001)")]
    again = {"strategies": [p2["strategies"][0]]}
    res = extract_spec(
        [PAGES[0], PAGES[1], Page(3, "MaxPct (tag 9001) again", "")],
        SRC,
        Recorded(
            {
                1: json.dumps(RESPONSES[1]),
                2: json.dumps(RESPONSES[2]),
                3: json.dumps(
                    {
                        "strategies": [
                            {
                                **again["strategies"][0],
                                "parameters": [
                                    {
                                        **p2["strategies"][0]["parameters"][0],
                                        "citations": [_cite(3, "MaxPct (tag 9001) again")],
                                    }
                                ],
                            }
                        ]
                    }
                ),
            }
        ),
    )
    assert res.spec.strategy("VWAP").parameter("MaxPct").max_value == "100"
    assert len(res.spec.strategy("VWAP").parameter("MaxPct").citations) == 2
    conflicts = [r for r in res.review if r.reason == "conflict"]
    assert len(conflicts) == 1 and "max_value" in conflicts[0].detail


def test_invalid_response_is_reviewed_not_fatal() -> None:
    res = _run({1: "not json", 2: json.dumps(RESPONSES[2])})
    assert any(r.reason == "invalid_response" and r.page == 1 for r in res.review)
    assert [p.name for p in res.spec.strategy("VWAP").parameters] == ["MaxPct", "Style"]


def test_cli_replay(tmp_path: Path) -> None:
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(_make_pdf([[(72, 700, "StrategyWireValue is 7")]]))
    rec = tmp_path / "rec"
    rec.mkdir()
    (rec / "page-1.json").write_text(
        json.dumps(
            {
                "strategies": [
                    {
                        "name": "VWAP",
                        "wire_value": "7",
                        "citations": [_cite(1, "StrategyWireValue is 7")],
                    }
                ]
            }
        )
    )
    out, rev = tmp_path / "spec.json", tmp_path / "review.json"
    rc = main(
        [
            "extract",
            str(pdf),
            "--id",
            "doc",
            "--title",
            "T",
            "--out",
            str(out),
            "--review-out",
            str(rev),
            "--replay",
            str(rec),
        ]
    )
    assert rc == 0
    assert json.loads(out.read_text())["strategies"][0]["name"] == "VWAP"
    assert json.loads(rev.read_text()) == []
    assert ReplayBackend(rec).complete("", "PAGE 5\n", {}) == '{"strategies": []}'
