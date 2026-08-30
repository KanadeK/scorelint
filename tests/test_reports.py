from __future__ import annotations

import csv
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from scorelint.audit import Thresholds, audit_document
from scorelint.geometry import Point
from scorelint.reports import render_annotated_svg, render_html, write_reports
from scorelint.svg import Piece, SvgDocument


def risky_report() -> object:
    document = SvgDocument(
        source_name="private-panel.svg",
        width_mm=20,
        height_mm=10,
        flatness_mm=0.1,
        scale_description="viewBox to 20x10 mm viewport",
        pieces=(
            Piece(
                piece_id='<pane&"one">',
                has_explicit_id=True,
                source_tag="path",
                points=(Point(0, 0), Point(20, 0), Point(20, 2), Point(0, 2)),
            ),
        ),
    )
    return audit_document(document, Thresholds(min_separation_mm=3, min_area_mm2=50))


def test_write_reports_creates_deterministic_schema_csv_svg_and_html(tmp_path: Path) -> None:
    report = risky_report()
    output = tmp_path / "audit"

    paths = write_reports(report, output)  # type: ignore[arg-type]

    assert tuple(path.name for path in paths) == (
        "report.json",
        "findings.csv",
        "annotated.svg",
        "report.html",
    )
    payload = json.loads((output / "report.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == "1.0"
    assert payload["tool"] == {"name": "scorelint", "version": "0.1.0"}
    assert payload["source"]["name"] == "private-panel.svg"
    assert payload["summary"] == {"errors": 0, "warnings": 2, "notices": 0, "pieces": 1}
    assert payload["findings"][0]["code"] == "SL202"
    assert payload["findings"][0]["measured"] == 2.0
    assert "absolute" not in (output / "report.json").read_text(encoding="utf-8")

    with (output / "findings.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert [row["code"] for row in rows] == ["SL202", "SL203"]
    assert rows[0]["piece_ids"] == '<pane&"one">'

    annotated = (output / "annotated.svg").read_text(encoding="utf-8")
    ET.fromstring(annotated)
    assert "&lt;pane&amp;&quot;" in annotated
    html = (output / "report.html").read_text(encoding="utf-8")
    assert "<script>" not in html
    assert "&lt;pane&amp;&quot;" in html

    first = {path.name: path.read_bytes() for path in paths}
    second = {path.name: path.read_bytes() for path in write_reports(report, output)}  # type: ignore[arg-type]
    assert second == first


def test_renderers_return_utf8_safe_standalone_documents() -> None:
    report = risky_report()

    svg = render_annotated_svg(report)  # type: ignore[arg-type]
    html = render_html(report)  # type: ignore[arg-type]

    assert svg.startswith('<?xml version="1.0" encoding="UTF-8"?>')
    assert "ScoreLint audit" in svg
    assert html.startswith("<!doctype html>")
    assert "Cut-risk indicators require human review" in html
