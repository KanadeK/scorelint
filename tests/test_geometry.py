from __future__ import annotations

import math

import pytest

from scorelint.geometry import (
    Point,
    analyze_polygon,
    point_in_polygon,
    polygons_overlap,
    segment_intersection,
)


def polygon(*coordinates: tuple[float, float]) -> tuple[Point, ...]:
    return tuple(Point(x, y) for x, y in coordinates)


def test_rectangle_metrics_are_orientation_independent() -> None:
    clockwise = polygon((0, 0), (0, 10), (20, 10), (20, 0))
    counter_clockwise = tuple(reversed(clockwise))

    first = analyze_polygon(clockwise)
    second = analyze_polygon(counter_clockwise)

    assert first.area == pytest.approx(200)
    assert first.perimeter == pytest.approx(60)
    assert first.bbox.width == pytest.approx(20)
    assert first.bbox.height == pytest.approx(10)
    assert [angle.degrees for angle in first.angles] == pytest.approx([90, 90, 90, 90])
    assert [angle.degrees for angle in second.angles] == pytest.approx([90, 90, 90, 90])
    assert first.minimum_separation is not None
    assert first.minimum_separation.distance == pytest.approx(10)
    assert first.intersections == ()


def test_concave_notch_reports_reflex_vertices_and_opening() -> None:
    notched = polygon(
        (0, 0),
        (10, 0),
        (10, 10),
        (6, 10),
        (6, 4),
        (4, 4),
        (4, 10),
        (0, 10),
    )

    metrics = analyze_polygon(notched)
    reflex = [angle for angle in metrics.angles if angle.concave]

    assert len(reflex) == 2
    assert [angle.degrees for angle in reflex] == pytest.approx([270, 270])
    assert [angle.opening_degrees for angle in reflex] == pytest.approx([90, 90])
    assert metrics.minimum_separation is not None
    assert metrics.minimum_separation.distance == pytest.approx(2)


def test_sharp_triangle_tip_is_measured_without_rounding() -> None:
    triangle = polygon((0, 0), (10, 1), (10, -1))

    metrics = analyze_polygon(triangle)

    assert metrics.angles[0].degrees == pytest.approx(math.degrees(2 * math.atan(0.1)))
    assert metrics.angles[0].concave is False


def test_bow_tie_exposes_proper_self_intersection() -> None:
    bow_tie = polygon((0, 0), (10, 10), (0, 10), (10, 0))

    metrics = analyze_polygon(bow_tie)

    assert metrics.area == pytest.approx(0)
    assert len(metrics.intersections) == 1
    assert metrics.intersections[0].kind == "proper"
    assert metrics.intersections[0].point == Point(5, 5)


@pytest.mark.parametrize(
    ("a", "b", "c", "d", "kind"),
    [
        ((0, 0), (10, 10), (0, 10), (10, 0), "proper"),
        ((0, 0), (10, 0), (10, 0), (10, 10), "touch"),
        ((0, 0), (10, 0), (5, 0), (15, 0), "overlap"),
        ((0, 0), (4, 0), (5, 0), (10, 0), None),
    ],
)
def test_segment_intersection_classifies_contact(
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
    d: tuple[float, float],
    kind: str | None,
) -> None:
    result = segment_intersection(Point(*a), Point(*b), Point(*c), Point(*d))

    assert (result.kind if result else None) == kind


def test_point_in_polygon_distinguishes_inside_boundary_and_outside() -> None:
    square = polygon((0, 0), (10, 0), (10, 10), (0, 10))

    assert point_in_polygon(Point(5, 5), square) == "inside"
    assert point_in_polygon(Point(0, 5), square) == "boundary"
    assert point_in_polygon(Point(20, 5), square) == "outside"


def test_polygon_overlap_requires_shared_area_not_shared_edge() -> None:
    base = polygon((0, 0), (10, 0), (10, 10), (0, 10))
    overlapping = polygon((8, 2), (12, 2), (12, 8), (8, 8))
    touching = polygon((10, 2), (12, 2), (12, 8), (10, 8))
    contained = polygon((2, 2), (4, 2), (4, 4), (2, 4))

    assert polygons_overlap(base, overlapping) is True
    assert polygons_overlap(base, touching) is False
    assert polygons_overlap(base, contained) is True


def test_repeated_closing_vertex_is_normalized() -> None:
    closed = polygon((0, 0), (10, 0), (10, 10), (0, 10), (0, 0))

    metrics = analyze_polygon(closed)

    assert metrics.area == pytest.approx(100)
    assert len(metrics.points) == 4


def test_polygon_requires_three_distinct_vertices() -> None:
    with pytest.raises(ValueError, match="at least three distinct vertices"):
        analyze_polygon(polygon((0, 0), (1, 0), (0, 0)))
