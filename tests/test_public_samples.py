"""Read publicly published FIXatdl files we did not write (backlog item 2, D15).

Opt-in: set ``CONCORD_PUBLIC_SAMPLES=1``. The sample repos are fetched into the
git-ignored ``corpus/cache/<id>/`` at the commit pinned in ``corpus/sources.yaml``
and are never committed (hard rule 2). The module skips when offline.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

from concord.fixatdl import FixatdlError, read_fixatdl_file, write_fixatdl
from concord.fixatdl.write import IDENTIFIER
from concord.ir import AlgoSpec

CACHE = Path(__file__).resolve().parents[1] / "corpus" / "cache"
ENABLED = os.environ.get("CONCORD_PUBLIC_SAMPLES") == "1"

# corpus id -> (git URL, pinned commit, glob of sample files under the checkout)
REPOS = {
    "atdl4j-test-examples": (
        "https://github.com/atdl4j/atdl4j.git",
        "a11bea0d84a7a57c247a3586b4d53f00485de220",
        "src/test/resources/*.xml",
    ),
    "fixportal-fixatdl-fixtures": (
        "https://github.com/FixPortal/fixportal-fixatdl.git",
        "65c3293a3be71a11985c132c4c92a9b15c6fd8bc",
        "tests/*/Fixtures/**/*.xml",
    ),
}

# Deliberate negatives: must raise a FixatdlError that names the location.
NEGATIVE = {"invalid-schema.xml": "Strategy without @name"}

# Files the IR cannot hold yet. Strict: when a gap is fixed, the xfail must go.
_SHARED_WIRE = "several strategies share one wireValue (IR requires unique)"
KNOWN_GAPS = {
    "Example Strategy Filtering.xml": _SHARED_WIRE,
    "Example StrategyPanel Tests2.xml": _SHARED_WIRE,
    "tz-clock.xml": "two parameters of one strategy share a fixTag (IR requires unique)",
}


def _fetch(corpus_id: str, url: str, sha: str) -> Path | None:
    dest = CACHE / corpus_id
    try:
        if (dest / ".git").exists():
            head = subprocess.run(
                ["git", "-C", str(dest), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=False,
            ).stdout.strip()
            if head == sha:
                return dest
        dest.mkdir(parents=True, exist_ok=True)

        def git(*args: str) -> None:
            subprocess.run(["git", "-C", str(dest), *args], check=True, capture_output=True)

        if not (dest / ".git").exists():
            git("init", "-q")
        git("fetch", "-q", "--depth", "1", url, sha)
        git("checkout", "-q", "FETCH_HEAD")
        return dest
    except (subprocess.CalledProcessError, OSError):
        return None


def _samples() -> list:
    if not ENABLED:
        return [pytest.param(None, marks=pytest.mark.skip(reason="CONCORD_PUBLIC_SAMPLES not set"))]
    out: list = []
    for corpus_id, (url, sha, pattern) in REPOS.items():
        root = _fetch(corpus_id, url, sha)
        if root is None:
            out.append(
                pytest.param(None, marks=pytest.mark.skip(reason=f"cannot fetch {corpus_id}"))
            )
            continue
        for path in sorted(root.glob(pattern)):
            marks = []
            if path.name in KNOWN_GAPS:
                marks.append(
                    pytest.mark.xfail(
                        reason=KNOWN_GAPS[path.name], raises=FixatdlError, strict=True
                    )
                )
            out.append(pytest.param(path, id=f"{corpus_id}/{path.relative_to(root)}", marks=marks))
    return out


def _comparable(spec: AlgoSpec, written: AlgoSpec) -> tuple[dict, dict]:
    """Dump both specs, undoing the two documented writer normalisations (D15).

    * An ``enumID`` that is not a legal XML identifier is regenerated.
    * An enum value with no label is written with its wire value as ``uiRep``.
    """
    a, b = spec.model_dump(), written.model_dump()
    for sa, sb in zip(a["strategies"], b["strategies"], strict=True):
        for pa, pb in zip(sa["parameters"], sb["parameters"], strict=True):
            for ea, eb in zip(pa["enum_values"], pb["enum_values"], strict=True):
                if ea["enum_id"] and not IDENTIFIER.fullmatch(ea["enum_id"]):
                    ea["enum_id"] = eb["enum_id"] = None
                if ea["label"] is None and eb["label"] == ea["wire_value"]:
                    eb["label"] = None
    return a, b


@pytest.mark.parametrize("path", _samples())
def test_public_sample(path: Path, tmp_path: Path) -> None:
    if path.name in NEGATIVE:
        with pytest.raises(FixatdlError, match=re.escape(NEGATIVE[path.name])):
            read_fixatdl_file(path)
        return

    first = read_fixatdl_file(path)
    out = tmp_path / "roundtrip.xml"
    out.write_bytes(write_fixatdl(first.spec))
    second = read_fixatdl_file(out)
    a, b = _comparable(first.spec, second.spec)
    assert a == b
