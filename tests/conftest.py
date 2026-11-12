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


@pytest.fixture(scope="session")
def orchestra_schema() -> etree.XMLSchema:
    """The Orchestra 1.0 repository schema (tag v1.6), if available locally.

    Point CONCORD_ORCHESTRA_XSD_DIR at a directory holding repository.xsd and its
    siblings (see D15 for fetching them). The XSD imports xml.xsd from w3.org; that
    one import is redirected to the local copy so no network access is needed.
    """
    xsd_dir = os.environ.get("CONCORD_ORCHESTRA_XSD_DIR")
    if not xsd_dir:
        pytest.skip("CONCORD_ORCHESTRA_XSD_DIR not set")
    repo = Path(xsd_dir) / "repository.xsd"
    if not repo.exists():
        pytest.skip(f"{repo} not found")
    text = repo.read_text(encoding="utf-8").replace("http://www.w3.org/2001/03/xml.xsd", "xml.xsd")
    parser = etree.XMLParser(no_network=True, resolve_entities=False)
    doc = etree.fromstring(text.encode(), parser, base_url=str(repo))
    return etree.XMLSchema(doc)
