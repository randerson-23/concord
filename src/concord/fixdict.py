"""Minimal FIX Orchestra dictionary reader: fields and code sets only (item 24, D21).

The FIX Trading Community publishes the whole FIX dictionary as Orchestra XML. Concord
reads just the two parts it needs to check a broker's standard tags: ``fixr:fields`` and
``fixr:codeSets``. The files are large (FIX Latest is 8.6 MB), so they are streamed with
``iterparse`` and every element is freed once read. Parsing is hardened like the FIXatdl
reader: no entity resolution, no network access, no DTD loading.

The dictionaries are NOT committed (D21): fetch them into ``corpus/cache/`` first.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from lxml import etree

NS = "http://fixprotocol.io/2020/orchestra/repository"
_FIELD, _FIELDS = f"{{{NS}}}field", f"{{{NS}}}fields"
_CODESET, _CODESETS = f"{{{NS}}}codeSet", f"{{{NS}}}codeSets"
_CODE = f"{{{NS}}}code"

DICTIONARY_FILES = {
    "4.2": "OrchestraFIX42.xml",
    "4.4": "OrchestraFIX44.xml",
    "latest": "OrchestraFIXLatest.xml",
}
DEFAULT_DIR = Path("corpus/cache/fix-orchestra-dictionaries/FIX Standard")
ENV_DIR = "CONCORD_FIX_DICT_DIR"
FETCH_HELP = (
    "fetch it with: mkdir -p corpus/cache/fix-orchestra-dictionaries && cd "
    "corpus/cache/fix-orchestra-dictionaries && git init -q && git fetch --depth 1 "
    "https://github.com/FIXTradingCommunity/orchestrations.git "
    "cd24169a2abd8daba7c360987c7a46ca11873a12 && git checkout -q FETCH_HEAD, "
    f"or point {ENV_DIR} or --dict-dir at a directory holding the files"
)


class DictionaryError(ValueError):
    """The dictionary file is missing or not an Orchestra repository."""


@dataclass(frozen=True)
class DictField:
    tag: int
    name: str
    type: str  # a datatype name, or a code set name
    union: str | None = None  # unionDataType: extra values allowed beyond the code set


@dataclass(frozen=True)
class DictCodeSet:
    name: str
    type: str  # underlying datatype of the codes
    values: dict[str, str] = field(default_factory=dict)  # value -> code name


@dataclass
class FixDictionary:
    label: str  # repository name, for example "FIX.4.2"
    fields: dict[int, DictField] = field(default_factory=dict)
    code_sets: dict[str, DictCodeSet] = field(default_factory=dict)

    def base_type(self, tag: int) -> str | None:
        """The datatype a tag carries; for a code-set field, the code set's datatype."""
        f = self.fields.get(tag)
        if f is None:
            return None
        cs = self.code_sets.get(f.type)
        return cs.type if cs is not None else f.type

    def codes(self, tag: int) -> DictCodeSet | None:
        f = self.fields.get(tag)
        return self.code_sets.get(f.type) if f is not None else None


def dictionary_path(version: str, directory: str | Path | None = None) -> Path:
    """A version's file: in ``directory``, else ``$CONCORD_FIX_DICT_DIR``, else the cache."""
    if version not in DICTIONARY_FILES:
        raise DictionaryError(
            f"unknown FIX version {version!r}; expected one of {sorted(DICTIONARY_FILES)}"
        )
    base = Path(directory or os.environ.get(ENV_DIR) or DEFAULT_DIR)
    return base / DICTIONARY_FILES[version]


def load_dictionary(path: str | Path) -> FixDictionary:
    """Stream an Orchestra repository file, keeping only fields and code sets."""
    p = Path(path)
    if not p.is_file():
        raise DictionaryError(f"{p}: dictionary file not found; {FETCH_HELP}")
    result = FixDictionary(label=p.stem)
    try:
        context = etree.iterparse(
            str(p),
            events=("start", "end"),
            tag=(_FIELD, _CODESET, f"{{{NS}}}repository"),
            resolve_entities=False,
            no_network=True,
            load_dtd=False,
        )
        for event, el in context:
            if event == "start":
                if el.tag == f"{{{NS}}}repository":
                    result.label = el.get("name") or result.label
                continue
            parent = el.getparent()
            if el.tag == _FIELD and parent is not None and parent.tag == _FIELDS:
                tag = int(el.get("id", "0"))
                result.fields[tag] = DictField(
                    tag, el.get("name", ""), el.get("type", ""), el.get("unionDataType")
                )
            elif el.tag == _CODESET and parent is not None and parent.tag == _CODESETS:
                values = {c.get("value", ""): c.get("name", "") for c in el.iter(_CODE)}
                result.code_sets[el.get("name", "")] = DictCodeSet(
                    el.get("name", ""), el.get("type", ""), values
                )
            else:
                continue
            el.clear()  # free memory: the file is large
            while el.getprevious() is not None:
                del el.getparent()[0]
    except etree.XMLSyntaxError as exc:
        raise DictionaryError(f"{p}: not well-formed XML: {exc}") from exc
    if not result.fields:
        raise DictionaryError(
            f"{p}: no <fixr:field> elements found; expected an Orchestra repository"
        )
    return result
