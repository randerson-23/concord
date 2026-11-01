from __future__ import annotations

import os
from pathlib import Path

import pytest
from lxml import etree

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def example_broker_bytes() -> bytes:
    return (FIXTURES / "fixatdl" / "example_broker.xml").read_bytes()


@pytest.fixture(scope="session")
def fixatdl_schema() -> etree.XMLSchema:
    """The official FIXatdl 1.1 schema, if available locally.

    The XSDs are not committed until their license is confirmed (see
    docs/DECISIONS.md). Point CONCORD_FIXATDL_XSD_DIR at a directory holding
    fixatdl-core-1-1.xsd and its siblings to enable schema-validation tests.
    """
    xsd_dir = os.environ.get("CONCORD_FIXATDL_XSD_DIR")
    if not xsd_dir:
        pytest.skip("CONCORD_FIXATDL_XSD_DIR not set")
    core = Path(xsd_dir) / "fixatdl-core-1-1.xsd"
    if not core.exists():
        pytest.skip(f"{core} not found")
    parser = etree.XMLParser(no_network=True, resolve_entities=False)
    return etree.XMLSchema(etree.parse(str(core), parser))
