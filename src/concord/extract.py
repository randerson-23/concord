"""LLM extraction scaffold: PDF pages in, verified ``AlgoSpec`` plus a review list out.

Pipeline: for each page ask a *backend* for an IR fragment (strategies with
mandatory page+quote citations), verify every fact's citations against the real
page text, keep only facts with at least one verified citation, merge the kept
facts into one ``AlgoSpec``, and route everything else (unverified facts, merge
conflicts, unparseable responses) to a review list. Nothing unverified reaches
the spec.

The backend is a small protocol, so tests run on recorded responses and need
no API key. :class:`AnthropicBackend` is the live implementation; it imports
the ``anthropic`` SDK lazily and reads ``ANTHROPIC_API_KEY`` from the
environment.
"""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol

from pydantic import Field, ValidationError

from concord.ir import (
    AlgoSpec,
    Citation,
    EnumValue,
    Parameter,
    SourceDocument,
    Strategy,
    StrategyEdit,
    _Model,
)
from concord.pdf import Page
from concord.verify import Status, verify_citation

DEFAULT_MODEL = "claude-opus-5-5"

SYSTEM_PROMPT = """\
You extract machine-readable algorithmic-order specifications from broker
documents into a JSON structure. Rules:
- Extract only what the page states. Never infer or fill in from general knowledge.
- Every strategy, parameter, enum value and rule MUST carry at least one citation:
  source_id (given), the page number (given), and `quote`: a short passage copied
  VERBATIM from the `--- page text ---` section. Do not quote the layout text: its
  words can carry stray spaces. Do not paraphrase the quote.
- Wire values, tags, defaults and bounds are strings exactly as printed.
- If the page contains no algo specification content, return {"strategies": []}.
"""


class Fragment(_Model):
    """What the model returns for one page: the strategies (or parts) seen there."""

    strategies: list[Strategy] = Field(default_factory=list)


TOKEN_CHARS = 4  # rough characters per token, for estimates only


@dataclass(frozen=True)
class Usage:
    """Token counts for one API call (cache fields are zero when the API reports none)."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0

    @property
    def total_input(self) -> int:
        return self.input_tokens + self.cache_creation_input_tokens + self.cache_read_input_tokens

    def __add__(self, other: Usage) -> Usage:
        return Usage(
            self.input_tokens + other.input_tokens,
            self.output_tokens + other.output_tokens,
            self.cache_creation_input_tokens + other.cache_creation_input_tokens,
            self.cache_read_input_tokens + other.cache_read_input_tokens,
        )

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


def usage_from_response(raw: Any) -> Usage:
    """Read an Anthropic ``usage`` object; absent or None counts become zero."""

    def count(name: str) -> int:
        return int(getattr(raw, name, 0) or 0)

    return Usage(
        count("input_tokens"),
        count("output_tokens"),
        count("cache_creation_input_tokens"),
        count("cache_read_input_tokens"),
    )


def estimate_tokens(text: str) -> int:
    return len(text) // TOKEN_CHARS


class Backend(Protocol):
    """Anything that can turn a prompt into a JSON string matching ``Fragment``.

    A backend may also expose ``last_usage`` (a :class:`Usage`) describing its latest call.
    """

    def complete(self, system: str, user: str, schema: dict[str, Any]) -> str: ...


class ReplayBackend:
    """Serves recorded responses, one JSON file per page: ``page-<n>.json``.

    The user prompt carries the page number on its first line (``PAGE n``).
    """

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)
        self.last_usage: Usage | None = None

    def complete(self, system: str, user: str, schema: dict[str, Any]) -> str:
        n = int(user.split("\n", 1)[0].removeprefix("PAGE ").split()[0])
        usage_file = self.directory / f"page-{n}.usage.json"
        self.last_usage = (
            Usage(**json.loads(usage_file.read_text())) if usage_file.exists() else None
        )
        path = self.directory / f"page-{n}.json"
        return path.read_text() if path.exists() else '{"strategies": []}'


class AnthropicBackend:
    """Live backend using the Anthropic Messages API with a forced tool call."""

    def __init__(self, model: str = DEFAULT_MODEL, max_tokens: int = 8192) -> None:
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set; expected it in the environment")
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            raise RuntimeError("the 'anthropic' package is needed: uv sync --extra llm") from exc
        self._client = anthropic.Anthropic(api_key=key)
        self.model = model
        self.max_tokens = max_tokens
        self.last_usage: Usage | None = None

    def complete(self, system: str, user: str, schema: dict[str, Any]) -> str:  # pragma: no cover
        resp = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            tools=[
                {
                    "name": "record_fragment",
                    "description": "Record the extraction.",
                    "input_schema": schema,
                }
            ],
            tool_choice={"type": "tool", "name": "record_fragment"},
        )
        self.last_usage = usage_from_response(getattr(resp, "usage", None))
        for block in resp.content:
            if block.type == "tool_use":
                return json.dumps(block.input)
        return '{"strategies": []}'


class RecordingBackend:
    """Wraps a backend and saves every raw response (``page-N.json``) and its usage
    (``page-N.usage.json``), so a live run can be replayed later without the API."""

    def __init__(self, inner: Backend, directory: str | Path) -> None:
        self.inner = inner
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.last_usage: Usage | None = None

    def complete(self, system: str, user: str, schema: dict[str, Any]) -> str:
        n = int(user.split("\n", 1)[0].removeprefix("PAGE ").split()[0])
        raw = self.inner.complete(system, user, schema)
        self.last_usage = getattr(self.inner, "last_usage", None)
        (self.directory / f"page-{n}.json").write_text(raw)
        if self.last_usage is not None:
            usage_json = json.dumps(self.last_usage.to_dict())
            (self.directory / f"page-{n}.usage.json").write_text(usage_json)
        return raw


@dataclass(frozen=True)
class ReviewItem:
    page: int | None
    location: str
    reason: str  # unverified | conflict | invalid_response
    detail: str
    quotes: tuple[tuple[int | None, str], ...] = ()  # (page, quote) the model gave, for review

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "page": self.page,
            "location": self.location,
            "reason": self.reason,
            "detail": self.detail,
        }
        if self.quotes:  # only when present, so older review files keep their shape
            out["quotes"] = [{"page": p, "quote": q} for p, q in self.quotes]
        return out


@dataclass(frozen=True)
class PageUsage:
    page: int
    usage: Usage
    estimated: bool  # True when the backend reported no usage and this is characters / 4

    def to_dict(self) -> dict[str, Any]:
        return {"page": self.page, "estimated": self.estimated, **self.usage.to_dict()}


@dataclass
class ExtractionResult:
    spec: AlgoSpec
    review: list[ReviewItem] = field(default_factory=list)
    usage: list[PageUsage] = field(default_factory=list)
    stopped_at_page: int | None = None  # set when the input-token cap ended the run early

    @property
    def total_usage(self) -> Usage:
        return sum((p.usage for p in self.usage), Usage())

    def usage_dict(self, max_input_tokens: int | None) -> dict[str, Any]:
        return {
            "max_input_tokens": max_input_tokens,
            "stopped_at_page": self.stopped_at_page,
            "pages": [p.to_dict() for p in self.usage],
            "total": {**self.total_usage.to_dict(), "total_input": self.total_usage.total_input},
        }

    def usage_text(self) -> str:
        lines = [
            f"page {p.page}: input {p.usage.total_input}, output {p.usage.output_tokens}"
            + (" (estimated)" if p.estimated else "")
            for p in self.usage
        ]
        total = self.total_usage
        lines.append(f"total: input {total.total_input}, output {total.output_tokens}")
        if self.stopped_at_page is not None:
            lines.append(f"stopped before page {self.stopped_at_page}: input-token cap reached")
        return "\n".join(lines)

    def review_text(self) -> str:
        if not self.review:
            return "no items need review"
        lines = [f"{len(self.review)} items need review:"]
        lines += [f"  p.{r.page} {r.location}: {r.reason} - {r.detail}" for r in self.review]
        return "\n".join(lines)


def build_prompt(source: SourceDocument, page: Page) -> str:
    where = f'section "{page.locator}"' if page.locator else f"page {page.number}"
    return (
        f"PAGE {page.number}\n"
        f"source_id: {source.id}  (title: {source.title})\n"
        f"Extract from {where} only. Cite page={page.number}"
        + (f' and locator="{page.locator}"' if page.locator else "")
        + ".\n"
        f"--- page text ---\n{page.text}\n--- layout text ---\n{page.layout_text}\n"
    )


# --------------------------------------------------------------------------- filtering


def _good(cites: list[Citation], pages: Sequence[Page], source_id: str) -> list[Citation]:
    """Citations for this source that verify against the real pages."""
    return [
        c
        for c in cites
        if c.source_id == source_id and verify_citation(c, pages)[0] is Status.VERIFIED
    ]


def _filter_fragment(
    frag: Fragment, pages: Sequence[Page], source_id: str, page_no: int, review: list[ReviewItem]
) -> list[Strategy]:
    """Drop facts without a verified citation (recording them); strip failed citations."""

    def reject(loc: str, citations: list[Citation], what: str) -> None:
        quotes = "; ".join(f'p.{c.page} "{c.quote}"' for c in citations) or "no citations"
        given = tuple((c.page, c.quote) for c in citations if c.quote)
        review.append(ReviewItem(page_no, loc, "unverified", f"{what}: {quotes}", given))

    out: list[Strategy] = []
    for s in frag.strategies:
        sloc = f"Strategy[@name='{s.name}']"
        params: list[Parameter] = []
        for p in s.parameters:
            ploc = f"{sloc}/Parameter[@name='{p.name}']"
            enums: list[EnumValue] = []
            for e in p.enum_values:
                good = _good(e.citations, pages, source_id)
                if good:
                    enums.append(e.model_copy(update={"citations": good}))
                else:
                    reject(f"{ploc}/EnumValue[@wireValue='{e.wire_value}']", e.citations, "enum")
            good = _good(p.citations, pages, source_id)
            if good:
                params.append(p.model_copy(update={"citations": good, "enum_values": enums}))
            else:
                reject(ploc, p.citations, "parameter")
        edits: list[StrategyEdit] = []
        for i, se in enumerate(s.edits, start=1):
            good = _good(se.citations, pages, source_id)
            if good:
                edits.append(se.model_copy(update={"citations": good}))
            else:
                reject(f"{sloc}/StrategyEdit[{i}]", se.citations, "rule")
        good = _good(s.citations, pages, source_id)
        if not good and not params and not edits:
            reject(sloc, s.citations, "strategy")
            continue
        out.append(
            s.model_copy(
                update={"citations": good, "parameters": params, "edits": edits},
            )
        )
    return out


# --------------------------------------------------------------------------- merging

_STRATEGY_SKIP = {"citations", "parameters", "edits"}
_PARAM_SKIP = {"citations", "enum_values"}


def _merge_scalars(
    base: Any, new: Any, skip: set[str], loc: str, page: int, review: list[ReviewItem]
) -> dict[str, Any]:
    """Fill gaps in ``base`` from ``new``; a disagreement is kept as base and reviewed."""
    updates: dict[str, Any] = {}
    for name in type(base).model_fields:
        if name in skip or name not in new.model_fields_set:
            continue
        old, val = getattr(base, name), getattr(new, name)
        if val == old:
            continue
        if name not in base.model_fields_set or old is None:
            updates[name] = val
        else:
            review.append(
                ReviewItem(page, loc, "conflict", f"{name}: kept {old!r}, page {page} says {val!r}")
            )
    return updates


def _merge_param(base: Parameter, new: Parameter, loc: str, page: int, review) -> Parameter:
    upd = _merge_scalars(base, new, _PARAM_SKIP, loc, page, review)
    enums = list(base.enum_values)
    for e in new.enum_values:
        have = base.enum_by_wire(e.wire_value)
        if have is None:
            enums.append(e)
        else:
            enums[enums.index(have)] = have.model_copy(
                update={"citations": [*have.citations, *e.citations]}
            )
    return base.model_copy(
        update={**upd, "citations": [*base.citations, *new.citations], "enum_values": enums}
    )


def _merge_strategy(base: Strategy, new: Strategy, page: int, review: list[ReviewItem]) -> Strategy:
    sloc = f"Strategy[@name='{base.name}']"
    upd = _merge_scalars(base, new, _STRATEGY_SKIP, sloc, page, review)
    params = list(base.parameters)
    for p in new.parameters:
        ploc = f"{sloc}/Parameter[@name='{p.name}']"
        have = next((q for q in params if q.name == p.name), None)
        if have is not None:
            params[params.index(have)] = _merge_param(have, p, ploc, page, review)
        elif p.fix_tag is not None and any(q.fix_tag == p.fix_tag for q in params):
            review.append(ReviewItem(page, ploc, "conflict", f"tag {p.fix_tag} already used"))
        else:
            params.append(p)
    edits = list(base.edits)
    for se in new.edits:
        have = next((e for e in edits if e.message == se.message), None)
        if have is None:
            edits.append(se)
        else:
            edits[edits.index(have)] = have.model_copy(
                update={"citations": [*have.citations, *se.citations]}
            )
    return base.model_copy(
        update={
            **upd,
            "citations": [*base.citations, *new.citations],
            "parameters": params,
            "edits": edits,
        }
    )


def _merge(
    strategies: list[Strategy], new: list[Strategy], page: int, review: list[ReviewItem]
) -> list[Strategy]:
    for s in new:
        have = next((b for b in strategies if b.name == s.name), None)
        if have is not None:
            strategies[strategies.index(have)] = _merge_strategy(have, s, page, review)
        elif any(b.wire_value == s.wire_value for b in strategies):
            loc = f"Strategy[@name='{s.name}']"
            review.append(ReviewItem(page, loc, "conflict", f"wire value {s.wire_value!r} in use"))
        else:
            strategies.append(s)
    return strategies


# --------------------------------------------------------------------------- driver


def extract_spec(
    pages: Sequence[Page],
    source: SourceDocument,
    backend: Backend,
    *,
    provider: str | None = None,
    max_input_tokens: int | None = None,
) -> ExtractionResult:
    """Run the pipeline over every page of ``pages``.

    ``max_input_tokens`` stops the run before the call that would pass the cap, keeping
    everything extracted so far; the pages that were not read go to the review list.
    """
    schema = Fragment.model_json_schema()
    review: list[ReviewItem] = []
    strategies: list[Strategy] = []
    page_usage: list[PageUsage] = []
    used_input = 0
    stopped_at: int | None = None
    for page in pages:
        prompt = build_prompt(source, page)
        estimate = estimate_tokens(SYSTEM_PROMPT + prompt)
        if max_input_tokens is not None and used_input + estimate > max_input_tokens:
            stopped_at = page.number
            review.append(
                ReviewItem(
                    page.number,
                    "Extraction",
                    "token_cap",
                    f"stopped before page {page.number}: {used_input} input tokens used, "
                    f"next page needs about {estimate}, cap is {max_input_tokens}",
                )
            )
            break
        raw = backend.complete(SYSTEM_PROMPT, prompt, schema)
        reported = getattr(backend, "last_usage", None)
        page_usage.append(
            PageUsage(page.number, reported or Usage(input_tokens=estimate), reported is None)
        )
        used_input = sum(p.usage.total_input for p in page_usage)
        try:
            frag = Fragment.model_validate_json(raw)
        except ValidationError as exc:
            first = exc.errors()[0]
            detail = f"{'.'.join(map(str, first['loc']))}: {first['msg']}"
            review.append(ReviewItem(page.number, "Fragment", "invalid_response", detail))
            continue
        kept = _filter_fragment(frag, pages, source.id, page.number, review)
        strategies = _merge(strategies, kept, page.number, review)
    spec = AlgoSpec(provider=provider, sources=[source], strategies=strategies)
    return ExtractionResult(spec, review, page_usage, stopped_at)
