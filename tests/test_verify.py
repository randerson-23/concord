# ruff: noqa: RUF001
"""Citation verifier tests: pages are built by hand; one CLI test uses a synthetic PDF."""

from __future__ import annotations

import json
from pathlib import Path

from test_pdf import _make_pdf

from concord.cli import main
from concord.ir import AlgoSpec, Citation, Parameter, ParamType, SourceDocument, Strategy
from concord.pdf import Page
from concord.verify import Status, fold, verify_citation, verify_spec

PAGES = [
    Page(1, "The VWAP strategy slices the order over the day.", ""),
    Page(
        2,
        "MaxPct must be between 1 and 100 and is\nrequired for par-\nticipation orders.",
        "",
    ),
]


def _c(page: int | None, quote: str | None, source: str = "doc") -> Citation:
    return Citation(source_id=source, page=page, quote=quote)


def test_fold_is_tolerant_but_case_sensitive() -> None:
    assert fold("it’s  a “quote”") == 'it\'s a "quote"'
    assert fold("par-\nticipation") == "participation"
    assert "vwap" not in fold("VWAP")


def test_each_status() -> None:
    assert verify_citation(_c(1, "slices the order"), PAGES)[0] is Status.VERIFIED
    assert verify_citation(_c(2, "required for participation"), PAGES)[0] is Status.VERIFIED
    assert verify_citation(_c(1, "invented rule"), PAGES)[0] is Status.NOT_FOUND
    assert verify_citation(_c(1, "slices the ORDER"), PAGES)[0] is Status.NOT_FOUND
    assert verify_citation(_c(2, "slices the order"), PAGES) == (Status.WRONG_PAGE, (1,))
    assert verify_citation(_c(9, "slices the order"), PAGES)[0] is Status.PAGE_OUT_OF_RANGE
    assert verify_citation(_c(1, None), PAGES)[0] is Status.NO_QUOTE
    assert verify_citation(_c(1, "  "), PAGES)[0] is Status.NO_QUOTE
    assert verify_citation(_c(None, "slices the order"), PAGES)[0] is Status.NO_PAGE
    assert verify_citation(_c(1, "x"), None)[0] is Status.UNKNOWN_SOURCE


def _spec() -> AlgoSpec:
    return AlgoSpec(
        sources=[SourceDocument(id="doc", title="Synthetic", kind="pdf")],
        strategies=[
            Strategy(
                name="VWAP",
                wire_value="1",
                citations=[_c(1, "The VWAP strategy")],
                parameters=[
                    Parameter(
                        name="MaxPct",
                        type=ParamType.PERCENTAGE,
                        fix_tag=7001,
                        citations=[_c(2, "MaxPct must be between 1 and 99")],
                    )
                ],
            )
        ],
    )


def test_spec_report_names_location() -> None:
    report = verify_spec(_spec(), {"doc": PAGES})
    assert not report.ok
    (bad,) = report.failures
    assert bad.location == "Strategy[@name='VWAP']/Parameter[@name='MaxPct']"
    assert bad.status is Status.NOT_FOUND
    assert "1/2 citations verified" in report.to_text()
    assert json.loads(report.to_json())["failures"][0]["status"] == "not_found"


def test_cli_verify(tmp_path: Path, capsys) -> None:
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(_make_pdf([[(72, 720, "The VWAP strategy slices the order.")]]))
    spec = _spec()
    spec.strategies[0].parameters.clear()
    f = tmp_path / "spec.json"
    f.write_text(spec.model_dump_json())
    assert main(["verify", str(f), "--source", f"doc={pdf}"]) == 0
    assert "1/1 citations verified" in capsys.readouterr().out
    assert main(["verify", str(f)]) == 2  # no document supplied for source
    assert "unknown_source" in capsys.readouterr().out
    assert main(["verify", str(f), "--source", "bogus"]) == 1


def test_locator_must_match_the_heading_of_a_page_that_has_one() -> None:
    pages = [
        Page(1, "Preamble text.", "", locator=None),
        Page(2, "Acme TWAP spreads the order.", "", locator="Overview"),
    ]

    def cite(page: int, locator: str | None) -> Citation:
        return Citation(source_id="doc", page=page, quote="spreads the order", locator=locator)

    ok = Citation(source_id="doc", page=2, quote="spreads the order", locator="  Overview ")
    assert verify_citation(ok, pages)[0] is Status.VERIFIED
    bad = cite(2, "Fields")
    assert verify_citation(bad, pages) == (Status.LOCATOR_MISMATCH, ())
    assert verify_citation(cite(2, None), pages)[0] is Status.VERIFIED  # no locator given
    # a page with no heading, or a PDF page, cannot check a free-form locator
    quote_on_1 = Citation(source_id="doc", page=1, quote="Preamble text", locator="table 4.2")
    assert verify_citation(quote_on_1, pages)[0] is Status.VERIFIED
    pdf_page = [Page(1, "Preamble text.", "")]
    assert verify_citation(quote_on_1, pdf_page)[0] is Status.VERIFIED


def test_quote_on_several_pages_is_flagged_but_still_verifies() -> None:
    pages = [
        Page(1, "Style is Passive or Active.", ""),
        Page(2, "Passive orders rest on the book.", ""),
        Page(3, "Nothing here.", ""),
    ]
    spec = AlgoSpec(
        sources=[SourceDocument(id="doc", title="S", kind="pdf")],
        strategies=[
            Strategy(
                name="A",
                wire_value="1",
                citations=[_c(1, "Passive"), _c(1, "Style is Passive")],
            )
        ],
    )
    report = verify_spec(spec, {"doc": pages})
    assert report.ok  # D10 strictness kept: ambiguity is a warning, not a failure
    (amb,) = report.ambiguous
    assert amb.citation.quote == "Passive" and amb.also_on == (2,)
    text = report.to_text()
    assert "2/2 citations verified" in text
    assert "1 quotes match several pages" in text and "also appears on page 2" in text
    assert json.loads(report.to_json())["ambiguous"][0]["also_on"] == [2]
    assert json.loads(report.to_json())["failures"] == []
