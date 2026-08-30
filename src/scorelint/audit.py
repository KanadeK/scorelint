"""Deterministic, measured findings for parsed stained-glass pieces."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Literal

from scorelint.geometry import BoundingBox, Point, PolygonMetrics, analyze_polygon, polygons_overlap
from scorelint.svg import SvgDocument

Level = Literal["error", "warning", "notice"]


@dataclass(frozen=True, slots=True)
class Thresholds:
    tip_angle_deg: float = 35.0
    concave_opening_deg: float = 75.0
    min_separation_mm: float = 3.0
    min_area_mm2: float = 50.0

    def __post_init__(self) -> None:
        for name in ("tip_angle_deg", "concave_opening_deg"):
            value = getattr(self, name)
            if not isfinite(value):
                raise ValueError(f"{name} must be finite")
            if not 0 < value < 180:
                raise ValueError(f"{name} must be greater than 0 and less than 180")
        for name in ("min_separation_mm", "min_area_mm2"):
            value = getattr(self, name)
            if not isfinite(value):
                raise ValueError(f"{name} must be finite")
            if value <= 0:
                raise ValueError(f"{name} must be greater than 0")


@dataclass(frozen=True, slots=True)
class Finding:
    code: str
    level: Level
    message: str
    piece_ids: tuple[str, ...]
    location: Point | None = None
    measured: float | None = None
    threshold: float | None = None
    unit: str | None = None
    edge_indices: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class PieceAudit:
    piece_id: str
    source_tag: str
    valid: bool
    point_count: int
    area_mm2: float | None
    perimeter_mm: float | None
    bbox_mm: BoundingBox | None
    minimum_separation_mm: float | None


@dataclass(frozen=True, slots=True)
class AuditReport:
    document: SvgDocument
    thresholds: Thresholds
    pieces: tuple[PieceAudit, ...]
    findings: tuple[Finding, ...]

    @property
    def has_risk_findings(self) -> bool:
        return any(finding.level in {"error", "warning"} for finding in self.findings)


def _finding_sort_key(finding: Finding) -> tuple[object, ...]:
    return (
        finding.code,
        finding.piece_ids,
        finding.location.x if finding.location else float("-inf"),
        finding.location.y if finding.location else float("-inf"),
        finding.edge_indices,
    )


def _piece_findings(
    piece_id: str,
    has_explicit_id: bool,
    metrics: PolygonMetrics,
    thresholds: Thresholds,
) -> list[Finding]:
    findings: list[Finding] = []
    if metrics.intersections:
        for intersection in metrics.intersections:
            findings.append(
                Finding(
                    code="SL100",
                    level="error",
                    message=(
                        f"{piece_id}: contour edges {intersection.first_edge} and "
                        f"{intersection.second_edge} intersect"
                    ),
                    piece_ids=(piece_id,),
                    location=intersection.point,
                    measured=0.0,
                    threshold=None,
                    unit="mm",
                    edge_indices=(intersection.first_edge, intersection.second_edge),
                )
            )
    elif metrics.area <= 1e-9:
        findings.append(
            Finding(
                code="SL100",
                level="error",
                message=f"{piece_id}: contour has zero area",
                piece_ids=(piece_id,),
                measured=metrics.area,
                threshold=0.0,
                unit="mm2",
            )
        )

    if metrics.intersections or metrics.area <= 1e-9:
        if not has_explicit_id:
            findings.append(
                Finding(
                    code="SL204",
                    level="notice",
                    message=f"{piece_id}: generated ID; add an explicit SVG id for stable tracking",
                    piece_ids=(piece_id,),
                )
            )
        return findings

    for angle in metrics.angles:
        if not angle.concave and angle.degrees < thresholds.tip_angle_deg:
            findings.append(
                Finding(
                    code="SL200",
                    level="warning",
                    message=(
                        f"{piece_id}: {angle.degrees:.3f} deg internal tip is below "
                        f"{thresholds.tip_angle_deg:g} deg"
                    ),
                    piece_ids=(piece_id,),
                    location=angle.point,
                    measured=angle.degrees,
                    threshold=thresholds.tip_angle_deg,
                    unit="deg",
                )
            )
        if angle.concave and angle.opening_degrees < thresholds.concave_opening_deg:
            findings.append(
                Finding(
                    code="SL201",
                    level="warning",
                    message=(
                        f"{piece_id}: {angle.opening_degrees:.3f} deg concave opening is below "
                        f"{thresholds.concave_opening_deg:g} deg"
                    ),
                    piece_ids=(piece_id,),
                    location=angle.point,
                    measured=angle.opening_degrees,
                    threshold=thresholds.concave_opening_deg,
                    unit="deg",
                )
            )

    separation = metrics.minimum_separation
    if separation is not None and separation.distance < thresholds.min_separation_mm:
        location = Point(
            (separation.first_point.x + separation.second_point.x) / 2,
            (separation.first_point.y + separation.second_point.y) / 2,
        )
        findings.append(
            Finding(
                code="SL202",
                level="warning",
                message=(
                    f"{piece_id}: {separation.distance:.3f} mm non-adjacent edge separation "
                    f"is below {thresholds.min_separation_mm:g} mm"
                ),
                piece_ids=(piece_id,),
                location=location,
                measured=separation.distance,
                threshold=thresholds.min_separation_mm,
                unit="mm",
                edge_indices=(separation.first_edge, separation.second_edge),
            )
        )
    if metrics.area < thresholds.min_area_mm2:
        findings.append(
            Finding(
                code="SL203",
                level="warning",
                message=(
                    f"{piece_id}: {metrics.area:.3f} mm2 area is below "
                    f"{thresholds.min_area_mm2:g} mm2"
                ),
                piece_ids=(piece_id,),
                measured=metrics.area,
                threshold=thresholds.min_area_mm2,
                unit="mm2",
            )
        )
    if not has_explicit_id:
        findings.append(
            Finding(
                code="SL204",
                level="notice",
                message=f"{piece_id}: generated ID; add an explicit SVG id for stable tracking",
                piece_ids=(piece_id,),
            )
        )
    return findings


def audit_document(document: SvgDocument, thresholds: Thresholds | None = None) -> AuditReport:
    """Apply all v0.1 rules and retain the measurements behind each finding."""

    active_thresholds = thresholds or Thresholds()
    findings: list[Finding] = []
    piece_audits: list[PieceAudit] = []
    valid_metrics: list[tuple[str, PolygonMetrics]] = []

    for piece in document.pieces:
        try:
            metrics = analyze_polygon(piece.points)
        except ValueError:
            findings.append(
                Finding(
                    code="SL100",
                    level="error",
                    message=f"{piece.piece_id}: contour needs at least three distinct vertices",
                    piece_ids=(piece.piece_id,),
                )
            )
            piece_audits.append(
                PieceAudit(
                    piece_id=piece.piece_id,
                    source_tag=piece.source_tag,
                    valid=False,
                    point_count=len(piece.points),
                    area_mm2=None,
                    perimeter_mm=None,
                    bbox_mm=None,
                    minimum_separation_mm=None,
                )
            )
            continue

        valid = not metrics.intersections and metrics.area > 1e-9
        if valid:
            valid_metrics.append((piece.piece_id, metrics))
        piece_audits.append(
            PieceAudit(
                piece_id=piece.piece_id,
                source_tag=piece.source_tag,
                valid=valid,
                point_count=len(metrics.points),
                area_mm2=metrics.area,
                perimeter_mm=metrics.perimeter,
                bbox_mm=metrics.bbox,
                minimum_separation_mm=(
                    metrics.minimum_separation.distance if metrics.minimum_separation else None
                ),
            )
        )
        findings.extend(
            _piece_findings(
                piece.piece_id,
                piece.has_explicit_id,
                metrics,
                active_thresholds,
            )
        )

    for first_index, (first_id, first_metrics) in enumerate(valid_metrics):
        for second_id, second_metrics in valid_metrics[first_index + 1 :]:
            if polygons_overlap(first_metrics.points, second_metrics.points):
                findings.append(
                    Finding(
                        code="SL101",
                        level="error",
                        message=f"{first_id} and {second_id}: declared piece areas overlap",
                        piece_ids=(first_id, second_id),
                    )
                )

    return AuditReport(
        document=document,
        thresholds=active_thresholds,
        pieces=tuple(piece_audits),
        findings=tuple(sorted(findings, key=_finding_sort_key)),
    )
