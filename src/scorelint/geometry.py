"""Dependency-free polygon evidence used by ScoreLint.

The routines deliberately report measurable geometry. They do not classify a
physical glass cut as possible or impossible.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import acos, degrees, hypot
from typing import Literal

EPSILON = 1e-9


@dataclass(frozen=True, slots=True)
class Point:
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class BoundingBox:
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    @property
    def width(self) -> float:
        return self.max_x - self.min_x

    @property
    def height(self) -> float:
        return self.max_y - self.min_y


@dataclass(frozen=True, slots=True)
class SegmentIntersection:
    kind: Literal["proper", "touch", "overlap"]
    point: Point


@dataclass(frozen=True, slots=True)
class PolygonIntersection:
    first_edge: int
    second_edge: int
    kind: Literal["proper", "touch", "overlap"]
    point: Point


@dataclass(frozen=True, slots=True)
class VertexAngle:
    index: int
    point: Point
    degrees: float
    concave: bool
    opening_degrees: float


@dataclass(frozen=True, slots=True)
class SeparationWitness:
    first_edge: int
    second_edge: int
    distance: float
    first_point: Point
    second_point: Point


@dataclass(frozen=True, slots=True)
class PolygonMetrics:
    points: tuple[Point, ...]
    area: float
    perimeter: float
    bbox: BoundingBox
    angles: tuple[VertexAngle, ...]
    intersections: tuple[PolygonIntersection, ...]
    minimum_separation: SeparationWitness | None


def _cross(a: Point, b: Point, c: Point) -> float:
    return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)


def _same_point(a: Point, b: Point) -> bool:
    return hypot(a.x - b.x, a.y - b.y) <= EPSILON


def _point_on_segment(point: Point, start: Point, end: Point) -> bool:
    if abs(_cross(start, end, point)) > EPSILON:
        return False
    return (
        min(start.x, end.x) - EPSILON <= point.x <= max(start.x, end.x) + EPSILON
        and min(start.y, end.y) - EPSILON <= point.y <= max(start.y, end.y) + EPSILON
    )


def _line_intersection(a: Point, b: Point, c: Point, d: Point) -> Point:
    denominator = (a.x - b.x) * (c.y - d.y) - (a.y - b.y) * (c.x - d.x)
    determinant_ab = a.x * b.y - a.y * b.x
    determinant_cd = c.x * d.y - c.y * d.x
    return Point(
        (determinant_ab * (c.x - d.x) - (a.x - b.x) * determinant_cd) / denominator,
        (determinant_ab * (c.y - d.y) - (a.y - b.y) * determinant_cd) / denominator,
    )


def segment_intersection(a: Point, b: Point, c: Point, d: Point) -> SegmentIntersection | None:
    """Classify how two closed segments meet."""

    ab_c = _cross(a, b, c)
    ab_d = _cross(a, b, d)
    cd_a = _cross(c, d, a)
    cd_b = _cross(c, d, b)

    if ab_c * ab_d < -EPSILON and cd_a * cd_b < -EPSILON:
        return SegmentIntersection("proper", _line_intersection(a, b, c, d))

    if all(abs(value) <= EPSILON for value in (ab_c, ab_d, cd_a, cd_b)):
        candidates: list[Point] = []
        for point in (a, b, c, d):
            if (
                _point_on_segment(point, a, b)
                and _point_on_segment(point, c, d)
                and not any(_same_point(point, existing) for existing in candidates)
            ):
                candidates.append(point)
        if not candidates:
            return None
        if len(candidates) == 1:
            return SegmentIntersection("touch", candidates[0])
        midpoint = Point(
            sum(point.x for point in candidates) / len(candidates),
            sum(point.y for point in candidates) / len(candidates),
        )
        return SegmentIntersection("overlap", midpoint)

    for point, start, end in ((a, c, d), (b, c, d), (c, a, b), (d, a, b)):
        if _point_on_segment(point, start, end):
            return SegmentIntersection("touch", point)
    return None


def _normalize_points(points: tuple[Point, ...]) -> tuple[Point, ...]:
    normalized: list[Point] = []
    for point in points:
        if not normalized or not _same_point(point, normalized[-1]):
            normalized.append(point)
    if len(normalized) > 1 and _same_point(normalized[0], normalized[-1]):
        normalized.pop()
    if len(normalized) < 3 or len({(point.x, point.y) for point in normalized}) < 3:
        raise ValueError("a polygon needs at least three distinct vertices")
    return tuple(normalized)


def _signed_area(points: tuple[Point, ...]) -> float:
    return (
        sum(
            point.x * points[(index + 1) % len(points)].y
            - points[(index + 1) % len(points)].x * point.y
            for index, point in enumerate(points)
        )
        / 2
    )


def _vertex_angles(points: tuple[Point, ...], orientation: float) -> tuple[VertexAngle, ...]:
    result: list[VertexAngle] = []
    for index, current in enumerate(points):
        previous = points[index - 1]
        following = points[(index + 1) % len(points)]
        incoming = Point(previous.x - current.x, previous.y - current.y)
        outgoing = Point(following.x - current.x, following.y - current.y)
        incoming_length = hypot(incoming.x, incoming.y)
        outgoing_length = hypot(outgoing.x, outgoing.y)
        cosine = (incoming.x * outgoing.x + incoming.y * outgoing.y) / (
            incoming_length * outgoing_length
        )
        smaller_angle = degrees(acos(max(-1.0, min(1.0, cosine))))
        turn = _cross(previous, current, following)
        concave = turn * orientation < -EPSILON
        internal_angle = 360 - smaller_angle if concave else smaller_angle
        result.append(
            VertexAngle(
                index=index,
                point=current,
                degrees=internal_angle,
                concave=concave,
                opening_degrees=360 - internal_angle if concave else internal_angle,
            )
        )
    return tuple(result)


def _self_intersections(points: tuple[Point, ...]) -> tuple[PolygonIntersection, ...]:
    count = len(points)
    result: list[PolygonIntersection] = []
    for first in range(count):
        first_end = (first + 1) % count
        for second in range(first + 1, count):
            second_end = (second + 1) % count
            if first == second or first_end == second or second_end == first:
                continue
            contact = segment_intersection(
                points[first], points[first_end], points[second], points[second_end]
            )
            if contact is not None:
                result.append(PolygonIntersection(first, second, contact.kind, contact.point))
    return tuple(result)


def _point_segment_distance(point: Point, start: Point, end: Point) -> tuple[float, Point]:
    dx = end.x - start.x
    dy = end.y - start.y
    squared_length = dx * dx + dy * dy
    if squared_length <= EPSILON:
        return hypot(point.x - start.x, point.y - start.y), start
    fraction = ((point.x - start.x) * dx + (point.y - start.y) * dy) / squared_length
    fraction = max(0.0, min(1.0, fraction))
    projection = Point(start.x + fraction * dx, start.y + fraction * dy)
    return hypot(point.x - projection.x, point.y - projection.y), projection


def _segment_distance(a: Point, b: Point, c: Point, d: Point) -> tuple[float, Point, Point]:
    contact = segment_intersection(a, b, c, d)
    if contact is not None:
        return 0.0, contact.point, contact.point
    choices: list[tuple[float, Point, Point]] = []
    for point, start, end, reverse in (
        (a, c, d, False),
        (b, c, d, False),
        (c, a, b, True),
        (d, a, b, True),
    ):
        distance, projection = _point_segment_distance(point, start, end)
        choices.append((distance, projection, point) if reverse else (distance, point, projection))
    return min(choices, key=lambda item: item[0])


def _minimum_separation(points: tuple[Point, ...]) -> SeparationWitness | None:
    count = len(points)
    candidates: list[SeparationWitness] = []
    for first in range(count):
        for second in range(first + 1, count):
            if second == first + 1 or (first == 0 and second == count - 1):
                continue
            distance, first_point, second_point = _segment_distance(
                points[first],
                points[(first + 1) % count],
                points[second],
                points[(second + 1) % count],
            )
            candidates.append(SeparationWitness(first, second, distance, first_point, second_point))
    return min(candidates, key=lambda item: item.distance) if candidates else None


def analyze_polygon(points: tuple[Point, ...]) -> PolygonMetrics:
    normalized = _normalize_points(points)
    signed_area = _signed_area(normalized)
    orientation = 1.0 if signed_area >= 0 else -1.0
    perimeter = sum(
        hypot(
            point.x - normalized[(index + 1) % len(normalized)].x,
            point.y - normalized[(index + 1) % len(normalized)].y,
        )
        for index, point in enumerate(normalized)
    )
    return PolygonMetrics(
        points=normalized,
        area=abs(signed_area),
        perimeter=perimeter,
        bbox=BoundingBox(
            min(point.x for point in normalized),
            min(point.y for point in normalized),
            max(point.x for point in normalized),
            max(point.y for point in normalized),
        ),
        angles=_vertex_angles(normalized, orientation),
        intersections=_self_intersections(normalized),
        minimum_separation=_minimum_separation(normalized),
    )


def point_in_polygon(
    point: Point, polygon: tuple[Point, ...]
) -> Literal["inside", "boundary", "outside"]:
    points = _normalize_points(polygon)
    inside = False
    for index, start in enumerate(points):
        end = points[(index + 1) % len(points)]
        if _point_on_segment(point, start, end):
            return "boundary"
        crosses = (start.y > point.y) != (end.y > point.y)
        if crosses:
            crossing_x = start.x + (point.y - start.y) * (end.x - start.x) / (end.y - start.y)
            if crossing_x > point.x:
                inside = not inside
    return "inside" if inside else "outside"


def polygons_overlap(first: tuple[Point, ...], second: tuple[Point, ...]) -> bool:
    left = _normalize_points(first)
    right = _normalize_points(second)
    for left_index, left_start in enumerate(left):
        left_end = left[(left_index + 1) % len(left)]
        for right_index, right_start in enumerate(right):
            right_end = right[(right_index + 1) % len(right)]
            contact = segment_intersection(left_start, left_end, right_start, right_end)
            if contact is not None and contact.kind == "proper":
                return True
    if any(point_in_polygon(point, right) == "inside" for point in left):
        return True
    if any(point_in_polygon(point, left) == "inside" for point in right):
        return True
    return left == right or left == tuple(reversed(right))
