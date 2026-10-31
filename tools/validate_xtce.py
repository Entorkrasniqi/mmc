#!/usr/bin/env python3
"""Check an XTCE file against the official XTCE 1.2 XML schema (XSD).

    python tools/validate_xtce.py yamcs/src/main/yamcs/mdb/minisat.xml                 # downloads the XSD
    python tools/validate_xtce.py yamcs/src/main/yamcs/mdb/minisat.xml --xsd SpaceSystemV1.2.xsd

An XSD check proves the file is *structurally* valid XTCE (right elements, right order, right attribute types). It does not
prove Yamcs interprets it as intended - tests/test_xtce.py complements it with an interpreter that checks the meaning.

The schema comes from the Yamcs repository (it is the OMG schema, vendored there). It imports the standard ``xml.xsd`` from
w3.org; to avoid needing that site, a tiny stand-in with the three attributes XTCE uses is written next to a patched copy.
"""
from __future__ import annotations

import argparse
import sys
import tempfile
import urllib.request
from pathlib import Path

from lxml import etree

XSD_URL = "https://raw.githubusercontent.com/yamcs/yamcs/yamcs-5.13.7/yamcs-xtce/SpaceSystemV1.2.xsd"
W3C_XML_XSD = "http://www.w3.org/2001/03/xml.xsd"
XML_XSD_STUB = """<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" targetNamespace="http://www.w3.org/XML/1998/namespace">
  <xs:attribute name="base" type="xs:anyURI"/>
  <xs:attribute name="lang" type="xs:language"/>
  <xs:attribute name="id" type="xs:ID"/>
</xs:schema>
"""


def validate(xml_path, xsd_path=None) -> list:
    """Return a list of error strings (empty = valid)."""
    if xsd_path is None:
        with urllib.request.urlopen(XSD_URL, timeout=30) as response:   # noqa: S310 - fixed https URL
            xsd_text = response.read().decode("utf-8")
    else:
        xsd_text = Path(xsd_path).read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "xml.xsd").write_text(XML_XSD_STUB, encoding="utf-8")
        patched = Path(tmp) / "SpaceSystem.xsd"
        patched.write_text(xsd_text.replace(W3C_XML_XSD, "xml.xsd"), encoding="utf-8")
        schema = etree.XMLSchema(etree.parse(str(patched)))
    document = etree.parse(str(xml_path))
    if schema.validate(document):
        return []
    return [f"line {e.line}: {e.message}" for e in schema.error_log]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("xml")
    parser.add_argument("--xsd", help="local copy of SpaceSystemV1.2.xsd (default: download from the Yamcs repository)")
    args = parser.parse_args()
    errors = validate(args.xml, args.xsd)
    if errors:
        print(f"{args.xml}: INVALID")
        for e in errors:
            print("  ", e)
        return 1
    print(f"{args.xml}: valid XTCE 1.2")
    return 0


if __name__ == "__main__":
    sys.exit(main())
