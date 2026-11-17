"""Corpus pipeline, part 1: fetch the public sources and plan the extraction (item 25a, D22).

``fetch`` reads ``corpus/sources.yaml`` and downloads only entries marked ``use: ok`` whose
kind is ``pdf`` or ``html`` into the git-ignored ``corpus/cache/<id>/`` (hard rule 2: nothing
is written into the repo outside the cache). One request per source per run, no retry, no
header tricks: a refusal or a bot-challenge page is reported as ``blocked`` and skipped.
``plan`` sizes what was fetched and estimates the extraction cost.

The network sits behind one function, :func:`http_get`, so tests replace it.
"""

from __future__ import annotations

import hashlib
import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import yaml

DEFAULT_SOURCES = Path("corpus/sources.yaml")
DEFAULT_CACHE = Path("corpus/cache")
USER_AGENT = "concord-corpus-fetch/0.1"
FETCHABLE_KINDS = ("pdf", "html")
TOKEN_CHARS = 4  # the rough chars-per-token used for estimates; stated as an estimate
_CHALLENGE = re.compile(
    r"<title>[^<]*(attention required|just a moment|access denied|pardon our interruption|"
    r"request unsuccessful|are you a robot)[^<]*</title>",
    re.I,
)


class CorpusError(ValueError):
    """A bad corpus request, such as an unknown source id."""


def http_get(url: str, timeout: float = 60.0) -> tuple[int, str, bytes]:
    """One GET: (status, content type, body). The only place the network is touched."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            return resp.status, resp.headers.get("Content-Type", ""), resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers.get("Content-Type", "") if exc.headers else "", b""


@dataclass(frozen=True)
class FetchResult:
    id: str
    status: str  # fetched | cached | blocked | skipped
    detail: str = ""

    def to_text(self) -> str:
        return f"{self.status:8} {self.id}" + (f"  {self.detail}" if self.detail else "")


def load_sources(path: str | Path = DEFAULT_SOURCES) -> list[dict[str, Any]]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    sources = (data or {}).get("sources")
    if not isinstance(sources, list):
        raise CorpusError(f"{path}: expected a top-level 'sources' list")
    return sources


def _select(sources: list[dict[str, Any]], ids: list[str] | None) -> list[dict[str, Any]]:
    if not ids:
        return sources
    known = {s["id"] for s in sources}
    missing = [i for i in ids if i not in known]
    if missing:
        raise CorpusError(f"unknown source id(s) {missing}; expected ids from the sources file")
    return [s for s in sources if s["id"] in ids]


def doc_path(cache: Path, entry: dict[str, Any]) -> Path:
    return cache / entry["id"] / f"doc.{'pdf' if entry['kind'] == 'pdf' else 'html'}"


def _check(kind: str, status: int, body: bytes) -> str | None:
    """Why a response is unusable, or None when it is the document we asked for."""
    if status != 200:
        return f"HTTP {status}"
    if not body:
        return "empty response"
    if kind == "pdf":
        return None if body.startswith(b"%PDF") else "response is not a PDF (bot challenge?)"
    text = body[:200_000].decode("utf-8", errors="replace")
    if _CHALLENGE.search(text):
        return "bot-challenge page"
    return None


def _write_meta(directory: Path, entry: dict[str, Any], body: bytes, fetched_at: str) -> None:
    meta = {
        "id": entry["id"],
        "url": entry["url"],
        "kind": entry["kind"],
        "fetched_at": fetched_at,
        "sha256": hashlib.sha256(body).hexdigest(),
        "bytes": len(body),
    }
    (directory / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")


def fetch_sources(
    sources: list[dict[str, Any]],
    cache: str | Path = DEFAULT_CACHE,
    ids: list[str] | None = None,
) -> list[FetchResult]:
    """Fetch every eligible source once; reuse the cache when the document is already there."""
    cache = Path(cache)
    results: list[FetchResult] = []
    for entry in _select(sources, ids):
        sid = entry["id"]
        if entry.get("use") != "ok" or entry.get("kind") not in FETCHABLE_KINDS:
            reason = f"use: {entry.get('use', 'unset')}, kind: {entry.get('kind')}"
            results.append(FetchResult(sid, "skipped", reason))
            continue
        target = doc_path(cache, entry)
        if target.is_file():
            if not (target.parent / "meta.json").is_file():  # fetched before meta existed
                stamp = datetime.fromtimestamp(target.stat().st_mtime, UTC).isoformat()
                _write_meta(target.parent, entry, target.read_bytes(), stamp)
            results.append(FetchResult(sid, "cached"))
            continue
        status, _content_type, body = http_get(entry["url"])
        problem = _check(entry["kind"], status, body)
        if problem:
            results.append(FetchResult(sid, "blocked", problem))
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
        _write_meta(target.parent, entry, body, datetime.now(UTC).isoformat(timespec="seconds"))
        results.append(FetchResult(sid, "fetched", f"{len(body)} bytes"))
    return results


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag in ("script", "style"):
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)


@dataclass(frozen=True)
class PlanRow:
    id: str
    kind: str
    units: str  # "12 pages" or "- (html)"
    chars: int
    tokens: int


def plan_sources(
    sources: list[dict[str, Any]],
    cache: str | Path = DEFAULT_CACHE,
    ids: list[str] | None = None,
) -> list[PlanRow]:
    """Size every cached source: pages (PDF) or text length (HTML), and estimated tokens."""
    from concord.pdf import read_pdf

    cache = Path(cache)
    rows: list[PlanRow] = []
    for entry in _select(sources, ids):
        if entry.get("kind") not in FETCHABLE_KINDS:
            continue
        path = doc_path(cache, entry)
        if not path.is_file():
            continue
        if entry["kind"] == "pdf":
            pages = read_pdf(path)
            chars = sum(len(p.text) for p in pages)
            units = f"{len(pages)} pages"
        else:
            parser = _Text()
            parser.feed(path.read_text(encoding="utf-8", errors="replace"))
            chars = len(re.sub(r"\s+", " ", " ".join(parser.parts)).strip())
            units = "html"
        rows.append(PlanRow(entry["id"], entry["kind"], units, chars, chars // TOKEN_CHARS))
    return rows


def plan_text(rows: list[PlanRow], price_per_mtok: float | None = None) -> str:
    if not rows:
        return "no fetched sources; run `concord corpus fetch` first"
    width = max(len(r.id) for r in rows)
    lines = [f"{'source':{width}}  {'kind':4}  {'size':>10}  {'chars':>9}  {'~tokens':>8}"]
    for r in rows:
        lines.append(f"{r.id:{width}}  {r.kind:4}  {r.units:>10}  {r.chars:>9}  {r.tokens:>8}")
    tokens = sum(r.tokens for r in rows)
    lines.append(
        f"{'total':{width}}  {'':4}  {'':>10}  {sum(r.chars for r in rows):>9}  {tokens:>8}"
    )
    lines.append(f"(~tokens is an estimate: characters / {TOKEN_CHARS})")
    if price_per_mtok is not None:
        lines.append(
            f"estimated input cost at {price_per_mtok} per million tokens: "
            f"{tokens / 1_000_000 * price_per_mtok:.2f}"
        )
    return "\n".join(lines)
