"""Dictionary reader and standard-tag lint (item 24, D21), on a tiny synthetic dictionary."""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from concord.cli import main
from concord.fixatdl import FixatdlError, read_fixatdl_file
from concord.fixdict import (
    NS,
    DictionaryError,
    dictionary_path,
    load_dictionary,
)
from concord.ir import AlgoSpec, EnumValue, Parameter, ParamType, Strategy
from concord.lint import lint_spec, types_conflict, value_allowed

# Written for this test suite; tags and names mimic FIX but the file is synthetic.
LATEST = f"""<?xml version="1.0" encoding="UTF-8"?>
<fixr:repository xmlns:fixr="{NS}" name="FIX.Latest" version="FIX.Latest_EP312">
  <fixr:datatypes><fixr:datatype name="int"/></fixr:datatypes>
  <fixr:codeSets>
    <fixr:codeSet id="40" name="OrdTypeCodeSet" type="char">
      <fixr:code id="40001" name="Market" value="1"/><fixr:code id="40002" name="Limit" value="2"/>
    </fixr:codeSet>
    <fixr:codeSet id="847" name="TargetStrategyCodeSet" type="int">
      <fixr:code id="847001" name="VWAP" value="1"/><fixr:code id="847002" name="TWAP" value="2"/>
    </fixr:codeSet>
    <fixr:codeSet id="100" name="ExDestCodeSet" type="String">
      <fixr:code id="100001" name="Nyse" value="N"/>
    </fixr:codeSet>
  </fixr:codeSets>
  <fixr:fields>
    <fixr:field id="38" name="OrderQty" type="Qty"/>
    <fixr:field id="40" name="OrdType" type="OrdTypeCodeSet"/>
    <fixr:field id="126" name="ExpireTime" type="UTCTimestamp"/>
    <fixr:field id="847" name="TargetStrategy" type="TargetStrategyCodeSet"
        unionDataType="Reserved1000Plus"/>
    <fixr:field id="100" name="ExDestination" type="ExDestCodeSet"
        unionDataType="Qty"/>
    <fixr:field id="9" name="Probe100" type="int"/>
  </fixr:fields>
  <fixr:messages>
    <fixr:message id="1" name="M" msgType="X"><fixr:structure/></fixr:message>
  </fixr:messages>
</fixr:repository>
"""
FIX42 = re.sub(r'<fixr:field id="847".*?/>\s*', "", LATEST, flags=re.S).replace(
    "FIX.Latest", "FIX.4.2"
)


@pytest.fixture
def dicts(tmp_path: Path) -> Path:
    (tmp_path / "OrchestraFIXLatest.xml").write_text(LATEST)
    (tmp_path / "OrchestraFIX42.xml").write_text(FIX42)
    return tmp_path


def _spec(*params: Parameter, ident: int = 7620, wires=("1",)) -> AlgoSpec:
    return AlgoSpec(
        strategy_identifier_tag=ident,
        strategies=[
            Strategy(name=f"S{w}", wire_value=w, parameters=list(params) if i == 0 else [])
            for i, w in enumerate(wires)
        ],
    )


def _p(name, ptype, tag, *values):
    return Parameter(
        name=name,
        type=ptype,
        fix_tag=tag,
        enum_values=[EnumValue(wire_value=v) for v in values],
    )


def _lint(spec, dicts, version="latest"):
    latest = load_dictionary(dictionary_path("latest", dicts))
    chosen = latest if version == "latest" else load_dictionary(dictionary_path(version, dicts))
    return lint_spec(spec, chosen, None if version == "latest" else latest)


def _msgs(findings, severity):
    return [f.message for f in findings if f.severity == severity]


def test_reader_keeps_fields_code_sets_and_union_types(dicts) -> None:
    d = load_dictionary(dicts / "OrchestraFIXLatest.xml")
    assert d.label == "FIX.Latest" and len(d.fields) == 6
    assert d.fields[847].union == "Reserved1000Plus"
    assert d.base_type(847) == "int" and d.base_type(126) == "UTCTimestamp"
    assert d.codes(40).values == {"1": "Market", "2": "Limit"}
    assert d.codes(38) is None


def test_reader_errors_are_clear(tmp_path: Path) -> None:
    with pytest.raises(DictionaryError, match=r"not found.*git fetch"):
        load_dictionary(tmp_path / "nope.xml")
    bad = tmp_path / "bad.xml"
    bad.write_text("<a><b></a>")
    with pytest.raises(DictionaryError, match="not well-formed"):
        load_dictionary(bad)
    other = tmp_path / "other.xml"
    other.write_text("<root/>")
    with pytest.raises(DictionaryError, match="no <fixr:field>"):
        load_dictionary(other)
    with pytest.raises(DictionaryError, match="unknown FIX version"):
        dictionary_path("5.0")


def test_reader_does_not_resolve_entities(tmp_path: Path) -> None:
    secret = tmp_path / "secret.txt"
    secret.write_text("TOP-SECRET")
    evil = LATEST.replace(
        "<fixr:repository",
        f'<!DOCTYPE r [<!ENTITY x SYSTEM "{secret}">]><fixr:repository',
        1,
    ).replace('name="OrderQty"', 'name="&x;"')
    (tmp_path / "e.xml").write_text(evil)
    try:
        d = load_dictionary(tmp_path / "e.xml")
    except DictionaryError:
        return  # refusing the file is also safe
    assert "TOP-SECRET" not in d.fields[38].name


def test_clean_spec_has_no_findings(dicts) -> None:
    spec = _spec(
        _p("OrderQty", ParamType.QTY, 38),
        _p("OrdType", ParamType.CHAR, 40, "1", "2"),
        _p("Mine", ParamType.INT, 7001),
        ident=847,
        wires=("1", "2"),
    )
    assert _lint(spec, dicts) == []


def test_undefined_standard_tag_is_an_error_but_user_ranges_are_not(dicts) -> None:
    spec = _spec(
        _p("Bogus", ParamType.INT, 4321),
        _p("User", ParamType.INT, 5000),
        _p("User2", ParamType.INT, 25000),
    )
    errors = _msgs(_lint(spec, dicts), "error")
    assert len(errors) == 1 and "tag 4321 is in the standard range" in errors[0]


def test_type_conflict_is_an_error_and_close_types_are_not(dicts) -> None:
    spec = _spec(
        _p("ExpireTime", ParamType.INT, 126),  # time vs integer: conflict
        _p("OrderQty", ParamType.FLOAT, 38),  # Qty vs float: compatible
        _p("Probe100", ParamType.QTY, 9),  # int vs Qty: compatible
    )
    errors = _msgs(_lint(spec, dicts), "error")
    assert errors == ["type int conflicts with UTCTimestamp for tag 126 (ExpireTime)"]
    assert types_conflict("UTCTimestamp", "UTCTimeOnly") == "warning"
    assert types_conflict("Boolean", "char") is None
    assert types_conflict("String", "int") == "error"
    assert types_conflict("Mystery", "int") is None


def test_enum_value_outside_a_standard_code_set_is_an_error(dicts) -> None:
    spec = _spec(_p("OrdType", ParamType.CHAR, 40, "1", "Z"))
    findings = _lint(spec, dicts)
    (err,) = [f for f in findings if f.severity == "error"]
    assert "EnumPair[@wireValue='Z']" in err.location and "OrdTypeCodeSet" in err.message


@pytest.mark.parametrize(
    ("union", "value", "allowed"),
    [
        ("Reserved100Plus", "100", True),
        ("Reserved100Plus", "99", False),
        ("Reserved1000Plus", "1014", True),
        ("Reserved1000Plus", "999", False),
        ("Reserved1000Plus", "T", False),
        ("Reserved4000Plus", "4000", True),
        ("Reserved4000Plus", "3999", False),
        ("Qty", "250", True),
        ("Qty", "1.5", True),
        ("Qty", "abc", False),
        ("Tenor", "D5", True),
        ("Tenor", "5D", False),
        (None, "1014", False),
    ],
)
def test_union_data_type_rules(union, value, allowed) -> None:
    assert value_allowed(value, union) is allowed


def test_union_type_admits_extra_values_in_a_field(dicts) -> None:
    ok = _spec(_p("ExDestination", ParamType.STRING, 100, "N", "250"))  # Qty union
    assert _msgs(_lint(ok, dicts), "error") == []
    bad = _spec(_p("ExDestination", ParamType.STRING, 100, "N", "XX"))
    assert len(_msgs(_lint(bad, dicts), "error")) == 1


def test_renamed_field_is_a_warning_showing_both_names(dicts) -> None:
    spec = _spec(_p("Quantity", ParamType.QTY, 38))
    assert _msgs(_lint(spec, dicts), "warning") == [
        "name 'Quantity' differs from the dictionary name 'OrderQty' for tag 38"
    ]


def test_tag_newer_than_the_chosen_version_is_a_warning(dicts) -> None:
    spec = _spec(ident=847, wires=("1",))
    (finding,) = _lint(spec, dicts, "4.2")
    assert (
        finding.severity == "warning"
        and "not in FIX.4.2; it exists in FIX.Latest" in finding.message
    )
    assert _lint(spec, dicts, "latest") == []
    # a tag in neither dictionary stays an error in 4.2
    assert _msgs(_lint(_spec(_p("X", ParamType.INT, 4321)), dicts, "4.2"), "error")


def test_identifier_values_outside_the_code_set_warn(dicts) -> None:
    spec = _spec(ident=847, wires=("1", "T", "1014", "7"))
    msgs = _msgs(_lint(spec, dicts), "warning")
    assert (
        len(msgs) == 2 and "'T'" in msgs[0] and "'7'" in msgs[1]
    )  # 1014 is legal (Reserved1000Plus)


def test_findings_name_the_location(dicts) -> None:
    (f,) = _lint(_spec(_p("Quantity", ParamType.QTY, 38)), dicts)
    assert f.location == "Strategy[@name='S1']/Parameter[@name='Quantity']"


def test_cli_exit_codes_and_formats(dicts, tmp_path: Path, capsys) -> None:
    good = tmp_path / "good.json"
    good.write_text(_spec(_p("Quantity", ParamType.QTY, 38)).model_dump_json(exclude_none=True))
    assert main(["lint", str(good), "--dict-dir", str(dicts)]) == 0  # warning only
    assert "warning:" in capsys.readouterr().out
    bad = tmp_path / "bad.json"
    bad.write_text(_spec(_p("Bogus", ParamType.INT, 4321)).model_dump_json(exclude_none=True))
    assert main(["lint", str(bad), "--dict-dir", str(dicts), "--format", "json"]) == 2
    assert '"severity": "error"' in capsys.readouterr().out
    assert main(["lint", str(good), "--dict-dir", str(tmp_path / "missing")]) == 1
    assert "not found" in capsys.readouterr().err
    assert main(["lint", str(good), "--dict-dir", str(dicts), "--fix-version", "4.2"]) == 0


# ------------------------------------------------------------ real dictionary (opt-in)

_DICT_URL = "https://github.com/FIXTradingCommunity/orchestrations.git"
_DICT_SHA = "cd24169a2abd8daba7c360987c7a46ca11873a12"


@pytest.mark.skipif(
    os.environ.get("CONCORD_PUBLIC_SAMPLES") != "1", reason="CONCORD_PUBLIC_SAMPLES not set"
)
def test_real_dictionary_lints_the_fixture_and_public_samples() -> None:
    from test_public_samples import CACHE, REPOS, _fetch

    root = _fetch("fix-orchestra-dictionaries", _DICT_URL, _DICT_SHA)
    if root is None:
        pytest.skip("cannot fetch the FIX dictionaries")
    directory = root / "FIX Standard"
    latest = load_dictionary(dictionary_path("latest", directory))
    assert latest.label == "FIX.Latest" and len(latest.fields) > 6000
    assert (
        latest.fields[847].union == "Reserved1000Plus" and latest.base_type(126) == "UTCTimestamp"
    )
    fix42 = load_dictionary(dictionary_path("4.2", directory))
    assert 847 not in fix42.fields  # the 847-in-FIX-4.2 case

    fixture = read_fixatdl_file(Path(__file__).parent / "fixtures/fixatdl/example_broker.xml").spec
    assert [f for f in lint_spec(fixture, latest) if f.severity == "error"] == []

    counts = {"files": 0, "error": 0, "warning": 0}
    for corpus_id, (_, _, pattern) in REPOS.items():
        for path in sorted((CACHE / corpus_id).glob(pattern)):
            try:
                spec = read_fixatdl_file(path).spec
            except FixatdlError:
                continue  # deliberate negatives
            counts["files"] += 1
            for finding in lint_spec(spec, latest):
                counts[finding.severity] += 1
    assert counts["files"] > 20  # the counts are reported in STATUS, not asserted
