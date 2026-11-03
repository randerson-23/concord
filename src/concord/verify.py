# ruff: noqa: RUF001  (typographic characters are the point of this table)
"""Citation verifier: does each quote really appear on its cited page?

The deterministic guard against an extractor (human or LLM) inventing a rule.
A citation passes only if it names a page and a quote, and that quote appears
on that page after whitespace, hyphenation and typographic-character folding.
Matching is otherwise exact (case-sensitive, no fuzzy scoring). A citation that
cannot be checked (no page, no quote, unknown source) is reported, never
silently passed.
"""

from __future__ import annotations

import json
import unicodedata
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from concord.ir import AlgoSpec, Citation
from concord.pdf import Page, normalize

_FOLD = str.maketrans(
    {
        "‘": "'",
        "’": "'",
        "“": '"',
        "”": '"',
        "‐": "-",
        "‑": "-",
        "‒": "-",
        "–": "-",
        "—": "-",
        "−": "-",
        "­": "",
        "​": "",
        " ": " ",
    }
)


def fold(text: str) -> str:
    """Canonical comparison form: NFKC, typographic characters, spacing, hyphenation."""
    text = unicodedata.normalize("NFKC", text).translate(_FOLD)
    return normalize(text)


class Status(StrEnum):
    VERIFIED = "verified"
    NOT_FOUND = "not_found"  # page exists, quote is not on it
    WRONG_PAGE = "wrong_page"  # quote is on a different page (see ``found_on``)
    PAGE_OUT_OF_RANGE = "page_out_of_range"
    NO_QUOTE = "no_quote"  # nothing to check
    NO_PAGE = "no_page"  # quote given but no page to check it on
    UNKNOWN_SOURCE = "unknown_source"  # no document supplied for this source_id


@dataclass(frozen=True)
class CitationResult:
    location: str  # e.g. Strategy[@name='X']/Parameter[@name='Y']
    citation: Citation
    status: Status
    found_on: tuple[int, ...] = ()

    @property
    def ok(self) -> bool:
        return self.status is Status.VERIFIED


@dataclass(frozen=True)
class VerifyReport:
    results: list[CitationResult]

    @property
    def failures(self) -> list[CitationResult]:
        return [r for r in self.results if not r.ok]

    @property
    def ok(self) -> bool:
        return not self.failures

    def to_text(self) -> str:
        bad = self.failures
        head = f"{len(self.results) - len(bad)}/{len(self.results)} citations verified"
        if not bad:
            return head
        lines = [head + f"; {len(bad)} need review:"]
        for r in bad:
            c = r.citation
            where = (
                f" (quote found on page {', '.join(map(str, r.found_on))})" if r.found_on else ""
            )
            q = f' "{c.quote}"' if c.quote else ""
            lines.append(f"  {r.location}: {r.status.value} [{c.source_id} p.{c.page}]{q}{where}")
        return "\n".join(lines)

    def to_json(self) -> str:
        return json.dumps(
            {
                "verified": len(self.results) - len(self.failures),
                "total": len(self.results),
                "failures": [
                    {
                        "location": r.location,
                        "status": r.status.value,
                        "source_id": r.citation.source_id,
                        "page": r.citation.page,
                        "quote": r.citation.quote,
                        "found_on": list(r.found_on),
                    }
                    for r in self.failures
                ],
            },
            indent=2,
        )


def verify_citation(
    citation: Citation, pages: Sequence[Page] | None
) -> tuple[Status, tuple[int, ...]]:
    """Check one citation against the pages of its source document."""
    if pages is None:
        return Status.UNKNOWN_SOURCE, ()
    if not citation.quote or not fold(citation.quote):
        return Status.NO_QUOTE, ()
    if citation.page is None:
        return Status.NO_PAGE, ()
    if citation.page > len(pages):
        return Status.PAGE_OUT_OF_RANGE, ()
    needle = fold(citation.quote)
    haystacks = [fold(p.text) for p in pages]
    if needle in haystacks[citation.page - 1]:
        return Status.VERIFIED, ()
    elsewhere = tuple(i for i, h in enumerate(haystacks, start=1) if needle in h)
    return (Status.WRONG_PAGE, elsewhere) if elsewhere else (Status.NOT_FOUND, ())


def _walk(spec: AlgoSpec) -> Iterator[tuple[str, Citation]]:
    for s in spec.strategies:
        sloc = f"Strategy[@name='{s.name}']"
        for c in s.citations:
            yield sloc, c
        for p in s.parameters:
            ploc = f"{sloc}/Parameter[@name='{p.name}']"
            for c in p.citations:
                yield ploc, c
            for e in p.enum_values:
                for c in e.citations:
                    yield f"{ploc}/EnumValue[@wireValue='{e.wire_value}']", c
        for i, se in enumerate(s.edits, start=1):
            for c in se.citations:
                yield f"{sloc}/StrategyEdit[{i}]", c


def verify_spec(spec: AlgoSpec, documents: Mapping[str, Sequence[Page]]) -> VerifyReport:
    """Verify every citation in ``spec`` against ``documents`` (keyed by source id)."""
    results = []
    for loc, c in _walk(spec):
        status, found = verify_citation(c, documents.get(c.source_id))
        results.append(CitationResult(loc, c, status, found))
    return VerifyReport(results)
