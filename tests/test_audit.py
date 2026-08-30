from __future__ import annotations

import pytest

from scorelint.audit import Thresholds, audit_document
from scorelint.geometry import Point
from scorelint.svg import Piece, SvgDocument


def document(*pieces: Piece) -> SvgDocument:
    return SvgDocument(
        source_name="panel.svg",
        width_mm=100,
        height_mm=100,
        flatness_mm=0.1,
        scale_description="test scale",
        pieces=pieces,
    )


def piece(piece_id: str, coordinates: list[tuple[float, float]], *, explicit: bool = True) -> Piece:
    return Piece(
        piece_id=piece_id,
        has_explicit_id=explicit,
        source_tag="path",
        points=tuple(Point(x, y) for x, y in coordinates),
    )


def codes(report: object) -> list[str]:
    return [finding.code for finding in report.findings]  # type: ignore[attr-defined]


def test_clean_rectangle_has_measured_piece_and_no_findings() -> None:
    report = audit_document(
        document(piece("pane", [(0, 0), (20, 0), (20, 10), (0, 10)])),
        Thresholds(
            tip_angle_deg=20,
            concave_opening_deg=20,
            min_separation_mm=2,
            min_area_mm2=50,
        ),
    )

    assert report.has_risk_findings is False
    assert report.pieces[0].piece_id == "pane"
    assert report.pieces[0].area_mm2 == pytest.approx(200)
    assert report.pieces[0].perimeter_mm == pytest.approx(60)
    assert report.pieces[0].minimum_separation_mm == pytest.approx(10)
    assert report.findings == ()


def test_self_intersection_is_an_error_with_edge_evidence() -> None:
    report = audit_document(document(piece("bow", [(0, 0), (10, 10), (0, 10), (10, 0)])))

    finding = next(finding for finding in report.findings if finding.code == "SL100")
    assert finding.level == "error"
    assert finding.piece_ids == ("bow",)
    assert finding.measured == pytest.approx(0)
    assert finding.unit == "mm"
    assert finding.edge_indices == (0, 2)


def test_degenerate_contour_is_reported_instead_of_crashing() -> None:
    report = audit_document(document(piece("line", [(0, 0), (10, 0), (20, 0)])))

    assert codes(report) == ["SL100"]
    assert report.pieces[0].valid is False


def test_piece_overlap_is_an_error_for_each_pair() -> None:
    report = audit_document(
        document(
            piece("a", [(0, 0), (10, 0), (10, 10), (0, 10)]),
            piece("b", [(5, 5), (15, 5), (15, 15), (5, 15)]),
        )
    )

    finding = next(finding for finding in report.findings if finding.code == "SL101")
    assert finding.level == "error"
    assert finding.piece_ids == ("a", "b")
    assert finding.measured is None


def test_tip_notch_width_area_and_missing_id_rules() -> None:
    report = audit_document(
        document(
            piece("tip", [(0, 0), (20, 0), (10, 1)]),
            piece(
                "notch",
                [(30, 0), (50, 0), (50, 20), (41, 20), (40, 19), (39, 20), (30, 20)],
            ),
            piece("thin", [(60, 0), (80, 0), (80, 2), (60, 2)]),
            piece("piece-0004", [(90, 0), (91, 0), (91, 1), (90, 1)], explicit=False),
        ),
        Thresholds(
            tip_angle_deg=30,
            concave_opening_deg=100,
            min_separation_mm=3,
            min_area_mm2=50,
        ),
    )

    assert {"SL200", "SL201", "SL202", "SL203", "SL204"} <= set(codes(report))
    tip = next(finding for finding in report.findings if finding.code == "SL200")
    assert tip.level == "warning"
    assert tip.measured is not None and tip.measured < 30
    assert tip.threshold == 30
    assert tip.unit == "deg"
    notch = next(finding for finding in report.findings if finding.code == "SL201")
    assert notch.measured == pytest.approx(90)
    width = next(
        finding
        for finding in report.findings
        if finding.code == "SL202" and finding.piece_ids == ("thin",)
    )
    assert width.measured == pytest.approx(2)
    missing_id = next(finding for finding in report.findings if finding.code == "SL204")
    assert missing_id.level == "notice"
    assert missing_id.piece_ids == ("piece-0004",)


def test_findings_have_stable_code_piece_and_location_order() -> None:
    source = document(
        piece("z", [(0, 0), (2, 0), (1, 0.1)]),
        piece("a", [(10, 0), (12, 0), (11, 0.1)]),
    )

    first = audit_document(source).findings
    second = audit_document(source).findings

    assert first == second
    assert list(first) == sorted(
        first,
        key=lambda finding: (
            finding.code,
            finding.piece_ids,
            finding.location.x if finding.location else float("-inf"),
            finding.location.y if finding.location else float("-inf"),
        ),
    )


@pytest.mark.parametrize(
    ("keyword", "value"),
    [
        ("tip_angle_deg", 0),
        ("tip_angle_deg", 180),
        ("concave_opening_deg", -1),
        ("concave_opening_deg", 181),
        ("min_separation_mm", 0),
        ("min_area_mm2", -1),
        ("min_area_mm2", float("nan")),
        ("min_separation_mm", float("inf")),
    ],
)
def test_thresholds_reject_invalid_configuration(keyword: str, value: float) -> None:
    with pytest.raises(ValueError, match=keyword):
        Thresholds(**{keyword: value})
