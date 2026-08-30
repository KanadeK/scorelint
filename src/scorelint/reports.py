"""Deterministic local report artifacts for a ScoreLint audit."""

from __future__ import annotations

import csv
import html
import io
import json
import xml.etree.ElementTree as ET
from dataclasses import asdict
from pathlib import Path

from scorelint import __version__
from scorelint.audit import AuditReport, Finding

SVG_NAMESPACE = "http://www.w3.org/2000/svg"


def _finding_dict(finding: Finding) -> dict[str, object]:
    return {
        "code": finding.code,
        "level": finding.level,
        "message": finding.message,
        "piece_ids": list(finding.piece_ids),
        "location": asdict(finding.location) if finding.location else None,
        "measured": finding.measured,
        "threshold": finding.threshold,
        "unit": finding.unit,
        "edge_indices": list(finding.edge_indices),
    }


def report_payload(report: AuditReport) -> dict[str, object]:
    counts = {
        level: sum(finding.level == level for finding in report.findings)
        for level in ("error", "warning", "notice")
    }
    return {
        "schema_version": "1.0",
        "tool": {"name": "scorelint", "version": __version__},
        "source": {
            "name": report.document.source_name,
            "width_mm": report.document.width_mm,
            "height_mm": report.document.height_mm,
            "scale_description": report.document.scale_description,
            "flatness_mm": report.document.flatness_mm,
        },
        "thresholds": asdict(report.thresholds),
        "summary": {
            "errors": counts["error"],
            "warnings": counts["warning"],
            "notices": counts["notice"],
            "pieces": len(report.pieces),
        },
        "pieces": [
            {
                "piece_id": piece.piece_id,
                "source_tag": piece.source_tag,
                "valid": piece.valid,
                "point_count": piece.point_count,
                "area_mm2": piece.area_mm2,
                "perimeter_mm": piece.perimeter_mm,
                "bbox_mm": asdict(piece.bbox_mm) if piece.bbox_mm else None,
                "minimum_separation_mm": piece.minimum_separation_mm,
            }
            for piece in report.pieces
        ],
        "findings": [_finding_dict(finding) for finding in report.findings],
    }


def render_csv(report: AuditReport) -> str:
    output = io.StringIO(newline="")
    fieldnames = [
        "code",
        "level",
        "piece_ids",
        "message",
        "measured",
        "threshold",
        "unit",
        "x_mm",
        "y_mm",
        "edge_indices",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for finding in report.findings:
        writer.writerow(
            {
                "code": finding.code,
                "level": finding.level,
                "piece_ids": "|".join(finding.piece_ids),
                "message": finding.message,
                "measured": "" if finding.measured is None else f"{finding.measured:.6g}",
                "threshold": "" if finding.threshold is None else f"{finding.threshold:.6g}",
                "unit": finding.unit or "",
                "x_mm": "" if finding.location is None else f"{finding.location.x:.6g}",
                "y_mm": "" if finding.location is None else f"{finding.location.y:.6g}",
                "edge_indices": "|".join(str(index) for index in finding.edge_indices),
            }
        )
    return output.getvalue()


def render_annotated_svg(report: AuditReport) -> str:
    ET.register_namespace("", SVG_NAMESPACE)
    root = ET.Element(
        f"{{{SVG_NAMESPACE}}}svg",
        {
            "width": f"{report.document.width_mm:g}mm",
            "height": f"{report.document.height_mm:g}mm",
            "viewBox": (f"0 0 {report.document.width_mm:g} {report.document.height_mm:g}"),
            "role": "img",
            "aria-label": "ScoreLint audit",
        },
    )
    title = ET.SubElement(root, f"{{{SVG_NAMESPACE}}}title")
    title.text = f"ScoreLint audit: {report.document.source_name}"
    style = ET.SubElement(root, f"{{{SVG_NAMESPACE}}}style")
    style.text = (
        ".piece{fill:#d8e7f0;stroke:#243447;stroke-width:.35}"
        ".piece-risk{fill:#ffd9d2;stroke:#922b21}"
        ".marker{fill:#c0392b;stroke:#fff;stroke-width:.3}"
        ".label{font:2.5px sans-serif;fill:#17202a}"
    )
    codes_by_piece: dict[str, list[str]] = {}
    for finding in report.findings:
        for piece_id in finding.piece_ids:
            codes_by_piece.setdefault(piece_id, []).append(finding.code)
    for piece in report.document.pieces:
        codes = codes_by_piece.get(piece.piece_id, [])
        polygon = ET.SubElement(
            root,
            f"{{{SVG_NAMESPACE}}}polygon",
            {
                "class": "piece-risk" if codes else "piece",
                "points": " ".join(f"{point.x:.6g},{point.y:.6g}" for point in piece.points),
                "data-piece-id": piece.piece_id,
                "data-findings": " ".join(sorted(set(codes))),
            },
        )
        polygon.set("vector-effect", "non-scaling-stroke")
    for finding in report.findings:
        if finding.location is None:
            continue
        ET.SubElement(
            root,
            f"{{{SVG_NAMESPACE}}}circle",
            {
                "class": "marker",
                "cx": f"{finding.location.x:.6g}",
                "cy": f"{finding.location.y:.6g}",
                "r": "1.2",
                "data-code": finding.code,
            },
        )
        label = ET.SubElement(
            root,
            f"{{{SVG_NAMESPACE}}}text",
            {
                "class": "label",
                "x": f"{finding.location.x + 1.6:.6g}",
                "y": f"{finding.location.y - 1.2:.6g}",
            },
        )
        label.text = finding.code
    body = ET.tostring(root, encoding="unicode", short_empty_elements=True)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n{body}\n'


def render_html(report: AuditReport) -> str:
    payload = report_payload(report)
    summary = payload["summary"]
    assert isinstance(summary, dict)
    rows = "\n".join(
        "<tr>"
        f"<td><code>{html.escape(finding.code)}</code></td>"
        f"<td>{html.escape(finding.level)}</td>"
        f"<td>{html.escape(', '.join(finding.piece_ids))}</td>"
        f"<td>{html.escape(finding.message)}</td>"
        "</tr>"
        for finding in report.findings
    )
    if not rows:
        rows = '<tr><td colspan="4">No findings.</td></tr>'
    svg = render_annotated_svg(report).split("\n", 1)[1]
    source = html.escape(report.document.source_name)
    disclaimer = (
        "Cut-risk indicators require human review; this report does not certify cuttability."
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ScoreLint audit - {source}</title>
<style>
:root {{ color-scheme: light; font-family: system-ui, sans-serif; color: #17202a; }}
body {{ max-width: 72rem; margin: 0 auto; padding: 2rem; background: #f7f4ed; }}
h1 {{ margin-bottom: .25rem; }}
.summary {{ display: flex; gap: 1rem; flex-wrap: wrap; }}
.summary strong {{ padding: .4rem .7rem; background: #fff; border: 1px solid #d6d0c4; }}
.canvas {{ margin: 1.5rem 0; padding: 1rem; background: #fff; border: 1px solid #d6d0c4; }}
.canvas svg {{ display: block; width: 100%; height: auto; max-height: 34rem; }}
table {{ width: 100%; border-collapse: collapse; background: #fff; }}
th, td {{ padding: .65rem; text-align: left; vertical-align: top; border: 1px solid #d6d0c4; }}
caption {{ text-align: left; font-weight: 700; margin-bottom: .5rem; }}
</style>
</head>
<body>
<main>
<h1>ScoreLint audit</h1>
<p><code>{source}</code> - {len(report.pieces)} pieces</p>
<p><strong>{disclaimer}</strong></p>
<div class="summary">
<strong>{summary["errors"]} errors</strong>
<strong>{summary["warnings"]} warnings</strong>
<strong>{summary["notices"]} notices</strong>
</div>
<div class="canvas">{svg}</div>
<table>
<caption>Measured findings</caption>
<thead><tr><th>Code</th><th>Level</th><th>Piece</th><th>Evidence</th></tr></thead>
<tbody>{rows}</tbody>
</table>
</main>
</body>
</html>
"""


def write_reports(report: AuditReport, output_directory: Path) -> tuple[Path, ...]:
    output_directory.mkdir(parents=True, exist_ok=True)
    paths = tuple(
        output_directory / name
        for name in ("report.json", "findings.csv", "annotated.svg", "report.html")
    )
    paths[0].write_text(
        json.dumps(report_payload(report), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    paths[1].write_text(render_csv(report), encoding="utf-8", newline="")
    paths[2].write_text(render_annotated_svg(report), encoding="utf-8", newline="\n")
    paths[3].write_text(render_html(report), encoding="utf-8", newline="\n")
    return paths
