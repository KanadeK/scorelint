"""Command-line entry point for ScoreLint."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from scorelint import __version__
from scorelint.audit import Thresholds, audit_document
from scorelint.reports import report_payload, write_reports
from scorelint.svg import SvgInputError, read_svg


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scorelint",
        description="Audit measurable cut-risk geometry in stained-glass SVG patterns.",
    )
    parser.add_argument("--version", action="version", version=f"scorelint {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    audit = commands.add_parser("audit", help="audit one local SVG and write evidence reports")
    audit.add_argument("input", type=Path, help="UTF-8 SVG pattern")
    audit.add_argument("--output", type=Path, required=True, help="report output directory")
    audit.add_argument("--scale-mm-per-unit", type=float)
    audit.add_argument("--flatness-mm", type=float, default=0.25)
    audit.add_argument("--tip-angle-deg", type=float, default=35.0)
    audit.add_argument("--concave-opening-deg", type=float, default=75.0)
    audit.add_argument("--min-separation-mm", type=float, default=3.0)
    audit.add_argument("--min-area-mm2", type=float, default=50.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        thresholds = Thresholds(
            tip_angle_deg=arguments.tip_angle_deg,
            concave_opening_deg=arguments.concave_opening_deg,
            min_separation_mm=arguments.min_separation_mm,
            min_area_mm2=arguments.min_area_mm2,
        )
        document = read_svg(
            arguments.input,
            flatness_mm=arguments.flatness_mm,
            scale_mm_per_unit=arguments.scale_mm_per_unit,
        )
        report = audit_document(document, thresholds)
        paths = write_reports(report, arguments.output)
    except (OSError, SvgInputError, ValueError) as error:
        print(f"scorelint: error: {error}", file=sys.stderr)
        return 2

    summary = report_payload(report)["summary"]
    assert isinstance(summary, dict)
    print(
        f"{summary['errors']} errors, {summary['warnings']} warnings, "
        f"{summary['notices']} notices across {summary['pieces']} pieces"
    )
    print(f"wrote {len(paths)} reports to {arguments.output}")
    return 1 if report.has_risk_findings else 0
