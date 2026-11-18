"""Extraction scaffold tests: recorded model responses, no API key, no network."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from test_pdf import _make_pdf

from concord.cli import main
from concord.extract import (
    RecordingBackend,
    ReplayBackend,
    Usage,
    extract_spec,
    usage_from_response,
)
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


# --------------------------------------------------------------------------- usage accounting


class Metered(Recorded):
    """A recorded backend that reports usage, as the live backend does."""

    def __init__(self, by_page: dict[int, str], usage: dict[int, Usage]) -> None:
        super().__init__(by_page)
        self.usage = usage
        self.last_usage: Usage | None = None

    def complete(self, system: str, user: str, schema: dict) -> str:
        n = int(user.split("\n", 1)[0].split()[1])
        self.last_usage = self.usage.get(n)
        return super().complete(system, user, schema)


def _responses() -> dict[int, str]:
    return {n: json.dumps(r) for n, r in RESPONSES.items()}


def test_usage_is_captured_per_page_and_in_total() -> None:
    usage = {
        1: Usage(input_tokens=100, output_tokens=20),
        2: Usage(input_tokens=50, output_tokens=10, cache_read_input_tokens=400),
    }
    res = extract_spec(PAGES, SRC, Metered(_responses(), usage))
    assert [(p.page, p.estimated) for p in res.usage] == [(1, False), (2, False)]
    assert res.total_usage == Usage(150, 30, 0, 400) and res.total_usage.total_input == 550
    text = res.usage_text()
    assert "page 2: input 450, output 10" in text and "total: input 550, output 30" in text
    d = res.usage_dict(150_000)
    assert d["total"]["total_input"] == 550 and d["pages"][1]["cache_read_input_tokens"] == 400
    assert d["max_input_tokens"] == 150_000 and d["stopped_at_page"] is None


def test_a_backend_that_reports_no_usage_gets_an_estimate() -> None:
    res = extract_spec(PAGES, SRC, Recorded(_responses()))
    assert all(p.estimated for p in res.usage)
    assert all(p.usage.input_tokens > 0 and p.usage.output_tokens == 0 for p in res.usage)
    assert "(estimated)" in res.usage_text()


def test_usage_from_response_treats_missing_counts_as_zero() -> None:
    raw = SimpleNamespace(input_tokens=7, output_tokens=3, cache_creation_input_tokens=None)
    assert usage_from_response(raw) == Usage(7, 3, 0, 0)
    assert usage_from_response(None) == Usage()


def test_the_input_token_cap_stops_before_the_call_that_would_exceed_it() -> None:
    backend = Metered(_responses(), {1: Usage(input_tokens=1000, output_tokens=5)})
    res = extract_spec(PAGES, SRC, backend, max_input_tokens=1000)
    assert res.stopped_at_page == 2 and [p.page for p in res.usage] == [1]
    assert [s.name for s in res.spec.strategies] == ["VWAP"]  # page 1's facts are kept
    (cap,) = [r for r in res.review if r.reason == "token_cap"]
    assert cap.page == 2 and "cap is 1000" in cap.detail
    assert "stopped before page 2" in res.usage_text()


def test_a_cap_too_small_for_even_the_first_page_reads_nothing() -> None:
    res = extract_spec(PAGES, SRC, Metered(_responses(), {}), max_input_tokens=1)
    assert res.stopped_at_page == 1 and res.usage == [] and res.spec.strategies == []


def test_no_cap_reads_every_page() -> None:
    res = extract_spec(PAGES, SRC, Metered(_responses(), {}), max_input_tokens=None)
    assert res.stopped_at_page is None and len(res.usage) == len(PAGES)


def test_recording_backend_saves_responses_and_usage_for_replay(tmp_path: Path) -> None:
    usage = {1: Usage(11, 2), 2: Usage(13, 4, 1, 2)}
    live = RecordingBackend(Metered(_responses(), usage), tmp_path / "run")
    first = extract_spec(PAGES, SRC, live)
    assert (tmp_path / "run" / "page-1.json").read_text() == _responses()[1]
    replay = extract_spec(PAGES, SRC, ReplayBackend(tmp_path / "run"))
    assert replay.spec == first.spec
    assert [p.usage for p in replay.usage] == [Usage(11, 2), Usage(13, 4, 1, 2)]
    assert not any(p.estimated for p in replay.usage)


def test_cli_writes_usage_json_and_prints_totals(tmp_path: Path, capsys) -> None:
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(_make_pdf([[(72, 700, "StrategyWireValue is 7")]]))
    rec = tmp_path / "rec"
    rec.mkdir()
    (rec / "page-1.json").write_text('{"strategies": []}')
    (rec / "page-1.usage.json").write_text(json.dumps(Usage(120, 9).to_dict()))
    out = tmp_path / "spec.json"
    args = ["extract", str(pdf), "--id", "doc", "--title", "T", "--out", str(out)]
    assert main([*args, "--replay", str(rec)]) == 0
    usage = json.loads(Path(f"{out}.usage.json").read_text())
    assert usage["total"]["input_tokens"] == 120 and usage["max_input_tokens"] == 150_000
    assert "total: input 120, output 9" in capsys.readouterr().err
    # a tiny cap stops the run, writes usage, and exits 2 because the review list is not empty
    assert main([*args, "--replay", str(rec), "--max-input-tokens", "1"]) == 2
    assert json.loads(Path(f"{out}.usage.json").read_text())["stopped_at_page"] == 1
    rec_out = tmp_path / "saved"
    assert main([*args, "--replay", str(rec), "--record", str(rec_out)]) == 0
    assert (rec_out / "page-1.usage.json").exists()
