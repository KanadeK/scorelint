"""Strict SVG geometry ingestion for ScoreLint.

SVG path semantics follow the W3C SVG 2 path specification. Curves are
flattened after transforms so the requested tolerance is measured in physical
millimetres: https://www.w3.org/TR/SVG2/paths.html
"""

from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from scorelint.geometry import Point

MAX_INPUT_BYTES = 10 * 1024 * 1024
MAX_PIECES = 5_000
MAX_POINTS = 200_000
SVG_NAMESPACE = "http://www.w3.org/2000/svg"
NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
PATH_TOKEN = re.compile(rf"[AaCcHhLlMmQqSsTtVvZz]|{NUMBER}")
TRANSFORM = re.compile(r"([A-Za-z]+)\s*\(([^)]*)\)")
LENGTH = re.compile(rf"^\s*({NUMBER})\s*([A-Za-z%]*)\s*$")
IGNORED_SUBTREES = {"defs", "clipPath", "mask", "symbol", "marker", "pattern"}
IGNORED_ELEMENTS = {"title", "desc", "metadata", "style", "script"}
SHAPES = {"path", "polygon", "polyline", "rect", "circle", "ellipse"}
CONTAINERS = {"svg", "g", "a", "switch"}


class SvgInputError(ValueError):
    """The SVG cannot be audited without guessing."""


@dataclass(frozen=True, slots=True)
class Matrix:
    a: float = 1.0
    b: float = 0.0
    c: float = 0.0
    d: float = 1.0
    e: float = 0.0
    f: float = 0.0

    def __matmul__(self, other: Matrix) -> Matrix:
        """Compose transforms so ``left @ right`` applies right first."""

        return Matrix(
            a=self.a * other.a + self.c * other.b,
            b=self.b * other.a + self.d * other.b,
            c=self.a * other.c + self.c * other.d,
            d=self.b * other.c + self.d * other.d,
            e=self.a * other.e + self.c * other.f + self.e,
            f=self.b * other.e + self.d * other.f + self.f,
        )

    def apply(self, point: Point) -> Point:
        return Point(
            self.a * point.x + self.c * point.y + self.e,
            self.b * point.x + self.d * point.y + self.f,
        )

    @property
    def maximum_scale(self) -> float:
        return max(math.hypot(self.a, self.b), math.hypot(self.c, self.d))


@dataclass(frozen=True, slots=True)
class Piece:
    piece_id: str
    has_explicit_id: bool
    source_tag: str
    points: tuple[Point, ...]


@dataclass(frozen=True, slots=True)
class SvgDocument:
    source_name: str
    width_mm: float
    height_mm: float
    flatness_mm: float
    scale_description: str
    pieces: tuple[Piece, ...]


def _numbers(value: str, *, context: str) -> list[float]:
    tokens = re.findall(NUMBER, value)
    remainder = re.sub(NUMBER, "", value)
    if remainder.replace(",", " ").strip():
        raise SvgInputError(f"invalid numeric list in {context}")
    return [float(token) for token in tokens]


def _translation(x: float, y: float = 0.0) -> Matrix:
    return Matrix(e=x, f=y)


def _scale(x: float, y: float | None = None) -> Matrix:
    return Matrix(a=x, d=x if y is None else y)


def _rotation(angle_degrees: float) -> Matrix:
    angle = math.radians(angle_degrees)
    return Matrix(a=math.cos(angle), b=math.sin(angle), c=-math.sin(angle), d=math.cos(angle))


def parse_transform(value: str | None) -> Matrix:
    if not value:
        return Matrix()
    result = Matrix()
    position = 0
    for match in TRANSFORM.finditer(value):
        gap = value[position : match.start()].replace(",", " ").strip()
        if gap:
            raise SvgInputError(f"invalid transform syntax near {gap!r}")
        name = match.group(1)
        arguments = _numbers(match.group(2), context=f"{name} transform")
        if name == "matrix" and len(arguments) == 6:
            operation = Matrix(*arguments)
        elif name == "translate" and len(arguments) in {1, 2}:
            operation = _translation(arguments[0], arguments[1] if len(arguments) == 2 else 0)
        elif name == "scale" and len(arguments) in {1, 2}:
            operation = _scale(arguments[0], arguments[1] if len(arguments) == 2 else None)
        elif name == "rotate" and len(arguments) in {1, 3}:
            operation = _rotation(arguments[0])
            if len(arguments) == 3:
                cx, cy = arguments[1:]
                operation = _translation(cx, cy) @ operation @ _translation(-cx, -cy)
        elif name == "skewX" and len(arguments) == 1:
            operation = Matrix(c=math.tan(math.radians(arguments[0])))
        elif name == "skewY" and len(arguments) == 1:
            operation = Matrix(b=math.tan(math.radians(arguments[0])))
        else:
            raise SvgInputError(f"unsupported or malformed {name} transform")
        result = result @ operation
        position = match.end()
    if not value[:position] and position == 0:
        raise SvgInputError("invalid transform syntax")
    if value[position:].replace(",", " ").strip():
        raise SvgInputError("invalid transform syntax")
    return result


def _parse_length(value: str | None, *, field: str) -> tuple[float, str]:
    if value is None:
        raise SvgInputError(f"SVG root needs a physical {field} or --scale-mm-per-unit")
    match = LENGTH.match(value)
    if match is None:
        raise SvgInputError(f"unsupported SVG {field}: {value!r}")
    magnitude = float(match.group(1))
    unit = match.group(2)
    if magnitude <= 0:
        raise SvgInputError(f"SVG {field} must be positive")
    factors = {"mm": 1.0, "cm": 10.0, "in": 25.4, "pt": 25.4 / 72, "pc": 25.4 / 6, "Q": 0.25}
    if unit not in factors:
        raise SvgInputError(
            f"SVG {field} must use mm, cm, in, pt, pc, or Q; use --scale-mm-per-unit"
        )
    return magnitude * factors[unit], unit


def _viewbox(root: ET.Element) -> tuple[float, float, float, float] | None:
    raw = root.get("viewBox")
    if raw is None:
        return None
    values = _numbers(raw, context="viewBox")
    if len(values) != 4 or values[2] <= 0 or values[3] <= 0:
        raise SvgInputError("viewBox must contain min-x min-y positive-width positive-height")
    return values[0], values[1], values[2], values[3]


def _viewbox_matrix(
    viewbox: tuple[float, float, float, float],
    width_mm: float,
    height_mm: float,
    preserve: str | None,
) -> Matrix:
    min_x, min_y, box_width, box_height = viewbox
    scale_x = width_mm / box_width
    scale_y = height_mm / box_height
    specification = (preserve or "xMidYMid meet").strip().split()
    if specification and specification[0] == "defer":
        specification.pop(0)
    if specification and specification[0] == "none":
        return _scale(scale_x, scale_y) @ _translation(-min_x, -min_y)
    alignment = specification[0] if specification else "xMidYMid"
    mode = specification[1] if len(specification) > 1 else "meet"
    if alignment not in {
        "xMinYMin",
        "xMidYMin",
        "xMaxYMin",
        "xMinYMid",
        "xMidYMid",
        "xMaxYMid",
        "xMinYMax",
        "xMidYMax",
        "xMaxYMax",
    } or mode not in {"meet", "slice"}:
        raise SvgInputError("unsupported preserveAspectRatio value")
    scale = min(scale_x, scale_y) if mode == "meet" else max(scale_x, scale_y)
    rendered_width = box_width * scale
    rendered_height = box_height * scale
    x_factor = 0.0 if "xMin" in alignment else 1.0 if "xMax" in alignment else 0.5
    y_factor = 0.0 if "YMin" in alignment else 1.0 if "YMax" in alignment else 0.5
    offset_x = (width_mm - rendered_width) * x_factor
    offset_y = (height_mm - rendered_height) * y_factor
    return _translation(offset_x, offset_y) @ _scale(scale) @ _translation(-min_x, -min_y)


def _root_geometry(
    root: ET.Element, scale_mm_per_unit: float | None
) -> tuple[Matrix, float, float, str]:
    box = _viewbox(root)
    if scale_mm_per_unit is not None:
        if scale_mm_per_unit <= 0:
            raise SvgInputError("--scale-mm-per-unit must be positive")
        if box is not None:
            min_x, min_y, width, height = box
            return (
                _scale(scale_mm_per_unit) @ _translation(-min_x, -min_y),
                width * scale_mm_per_unit,
                height * scale_mm_per_unit,
                f"explicit {scale_mm_per_unit:g} mm per user unit",
            )
        return (
            _scale(scale_mm_per_unit),
            0,
            0,
            f"explicit {scale_mm_per_unit:g} mm per user unit",
        )

    width_mm, _ = _parse_length(root.get("width"), field="width")
    height_mm, _ = _parse_length(root.get("height"), field="height")
    if box is not None:
        return (
            _viewbox_matrix(box, width_mm, height_mm, root.get("preserveAspectRatio")),
            width_mm,
            height_mm,
            f"viewBox to {width_mm:g}x{height_mm:g} mm viewport",
        )
    css_px_to_mm = 25.4 / 96
    return (
        _scale(css_px_to_mm),
        width_mm,
        height_mm,
        "SVG user units at 96 CSS px per inch",
    )


def _local_name(tag: str) -> tuple[str | None, str]:
    if tag.startswith("{"):
        namespace, name = tag[1:].split("}", 1)
        return namespace, name
    return None, tag


def _is_hidden(element: ET.Element) -> bool:
    style = element.get("style", "").replace(" ", "").lower()
    return (
        element.get("display", "").lower() == "none"
        or element.get("visibility", "").lower() == "hidden"
        or "display:none" in style
        or "visibility:hidden" in style
        or element.get("data-scorelint", "").lower() == "ignore"
    )


def _shape_is_ignored(element: ET.Element) -> bool:
    style = element.get("style", "").replace(" ", "").lower()
    return element.get("fill", "").lower() == "none" or "fill:none" in style


def _float(element: ET.Element, name: str, *, default: float | None = None) -> float:
    raw = element.get(name)
    if raw is None:
        if default is None:
            raise SvgInputError(f"<{_local_name(element.tag)[1]}> needs {name}")
        return default
    values = _numbers(raw, context=f"{name} attribute")
    if len(values) != 1:
        raise SvgInputError(f"{name} must be one number")
    return values[0]


def _dedupe_closed(points: list[Point]) -> tuple[Point, ...]:
    deduplicated: list[Point] = []
    for point in points:
        if (
            not deduplicated
            or math.hypot(point.x - deduplicated[-1].x, point.y - deduplicated[-1].y) > 1e-9
        ):
            deduplicated.append(point)
    if (
        len(deduplicated) > 1
        and math.hypot(
            deduplicated[0].x - deduplicated[-1].x,
            deduplicated[0].y - deduplicated[-1].y,
        )
        <= 1e-9
    ):
        deduplicated.pop()
    if len(deduplicated) < 3:
        raise SvgInputError("closed SVG piece needs at least three distinct points")
    return tuple(deduplicated)


def _point_line_distance(point: Point, start: Point, end: Point) -> float:
    dx = end.x - start.x
    dy = end.y - start.y
    length = math.hypot(dx, dy)
    if length == 0:
        return math.hypot(point.x - start.x, point.y - start.y)
    return abs(dx * (start.y - point.y) - (start.x - point.x) * dy) / length


def _flatten_cubic(
    start: Point,
    first_control: Point,
    second_control: Point,
    end: Point,
    tolerance: float,
    depth: int = 0,
) -> list[Point]:
    if (
        depth >= 20
        or max(
            _point_line_distance(first_control, start, end),
            _point_line_distance(second_control, start, end),
        )
        <= tolerance
    ):
        return [end]
    p01 = Point((start.x + first_control.x) / 2, (start.y + first_control.y) / 2)
    p12 = Point((first_control.x + second_control.x) / 2, (first_control.y + second_control.y) / 2)
    p23 = Point((second_control.x + end.x) / 2, (second_control.y + end.y) / 2)
    p012 = Point((p01.x + p12.x) / 2, (p01.y + p12.y) / 2)
    p123 = Point((p12.x + p23.x) / 2, (p12.y + p23.y) / 2)
    midpoint = Point((p012.x + p123.x) / 2, (p012.y + p123.y) / 2)
    return _flatten_cubic(start, p01, p012, midpoint, tolerance, depth + 1) + _flatten_cubic(
        midpoint, p123, p23, end, tolerance, depth + 1
    )


def _flatten_quadratic(
    start: Point, control: Point, end: Point, tolerance: float, depth: int = 0
) -> list[Point]:
    if depth >= 20 or _point_line_distance(control, start, end) <= tolerance:
        return [end]
    p01 = Point((start.x + control.x) / 2, (start.y + control.y) / 2)
    p12 = Point((control.x + end.x) / 2, (control.y + end.y) / 2)
    midpoint = Point((p01.x + p12.x) / 2, (p01.y + p12.y) / 2)
    return _flatten_quadratic(start, p01, midpoint, tolerance, depth + 1) + _flatten_quadratic(
        midpoint, p12, end, tolerance, depth + 1
    )


def _vector_angle(ux: float, uy: float, vx: float, vy: float) -> float:
    dot = ux * vx + uy * vy
    lengths = math.hypot(ux, uy) * math.hypot(vx, vy)
    angle = math.acos(max(-1.0, min(1.0, dot / lengths)))
    return -angle if ux * vy - uy * vx < 0 else angle


def _flatten_arc(
    start: Point,
    rx: float,
    ry: float,
    rotation: float,
    large_arc: bool,
    sweep: bool,
    end: Point,
    matrix: Matrix,
    tolerance: float,
) -> list[Point]:
    if rx == 0 or ry == 0 or start == end:
        return [matrix.apply(end)]
    rx = abs(rx)
    ry = abs(ry)
    phi = math.radians(rotation % 360)
    cos_phi = math.cos(phi)
    sin_phi = math.sin(phi)
    dx = (start.x - end.x) / 2
    dy = (start.y - end.y) / 2
    x_prime = cos_phi * dx + sin_phi * dy
    y_prime = -sin_phi * dx + cos_phi * dy
    radius_scale = x_prime * x_prime / (rx * rx) + y_prime * y_prime / (ry * ry)
    if radius_scale > 1:
        factor = math.sqrt(radius_scale)
        rx *= factor
        ry *= factor
    numerator = max(
        0.0,
        rx * rx * ry * ry - rx * rx * y_prime * y_prime - ry * ry * x_prime * x_prime,
    )
    denominator = rx * rx * y_prime * y_prime + ry * ry * x_prime * x_prime
    coefficient = 0.0 if denominator == 0 else math.sqrt(numerator / denominator)
    if large_arc == sweep:
        coefficient = -coefficient
    center_x_prime = coefficient * rx * y_prime / ry
    center_y_prime = -coefficient * ry * x_prime / rx
    center_x = cos_phi * center_x_prime - sin_phi * center_y_prime + (start.x + end.x) / 2
    center_y = sin_phi * center_x_prime + cos_phi * center_y_prime + (start.y + end.y) / 2
    start_vector = ((x_prime - center_x_prime) / rx, (y_prime - center_y_prime) / ry)
    end_vector = ((-x_prime - center_x_prime) / rx, (-y_prime - center_y_prime) / ry)
    start_angle = _vector_angle(1, 0, *start_vector)
    delta = _vector_angle(*start_vector, *end_vector)
    if not sweep and delta > 0:
        delta -= 2 * math.pi
    elif sweep and delta < 0:
        delta += 2 * math.pi
    physical_radius = max(rx, ry) * matrix.maximum_scale
    if physical_radius <= tolerance:
        count = 1
    else:
        step = 2 * math.acos(max(-1.0, 1 - tolerance / physical_radius))
        count = max(1, math.ceil(abs(delta) / step))
    count = min(count, 4_096)
    points: list[Point] = []
    for index in range(1, count + 1):
        angle = start_angle + delta * index / count
        local = Point(
            center_x + cos_phi * rx * math.cos(angle) - sin_phi * ry * math.sin(angle),
            center_y + sin_phi * rx * math.cos(angle) + cos_phi * ry * math.sin(angle),
        )
        points.append(matrix.apply(local))
    points[-1] = matrix.apply(end)
    return points


def _tokenize_path(data: str) -> list[str]:
    tokens: list[str] = []
    position = 0
    for match in PATH_TOKEN.finditer(data):
        if data[position : match.start()].replace(",", " ").strip():
            raise SvgInputError("invalid path data")
        tokens.append(match.group(0))
        position = match.end()
    if data[position:].replace(",", " ").strip() or not tokens:
        raise SvgInputError("invalid path data")
    return tokens


def _path_points(data: str, matrix: Matrix, tolerance: float) -> tuple[Point, ...]:
    tokens = _tokenize_path(data)
    index = 0
    command: str | None = None
    current = Point(0, 0)
    start = Point(0, 0)
    transformed: list[Point] = []
    previous_command: str | None = None
    previous_control: Point | None = None
    moved = False
    closed = False

    parameter_count = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7}

    def consume(count: int) -> list[float]:
        nonlocal index
        if index + count > len(tokens) or any(
            token.isalpha() for token in tokens[index : index + count]
        ):
            raise SvgInputError("invalid path data: missing command parameters")
        result = [float(token) for token in tokens[index : index + count]]
        index += count
        return result

    def absolute(x: float, y: float, relative: bool) -> Point:
        return Point(current.x + x, current.y + y) if relative else Point(x, y)

    while index < len(tokens):
        if tokens[index].isalpha():
            command = tokens[index]
            index += 1
        if command is None:
            raise SvgInputError("invalid path data: first command must be M or m")
        upper = command.upper()
        relative = command.islower()
        if upper == "Z":
            if not moved:
                raise SvgInputError("invalid path data: Z before M")
            current = start
            closed = True
            previous_command = command
            previous_control = None
            command = None
            continue
        if upper not in parameter_count:
            raise SvgInputError("invalid path data")
        if closed:
            raise SvgInputError("each path piece must contain one closed subpath")
        values = consume(parameter_count[upper])

        if upper == "M":
            if moved:
                raise SvgInputError("each path piece must contain one closed subpath")
            destination = absolute(values[0], values[1], relative and moved)
            current = destination
            start = destination
            transformed.append(matrix.apply(destination))
            moved = True
            command = "l" if relative else "L"
            previous_control = None
        elif not moved:
            raise SvgInputError("invalid path data: first command must be M or m")
        elif upper == "L":
            current = absolute(values[0], values[1], relative)
            transformed.append(matrix.apply(current))
            previous_control = None
        elif upper == "H":
            current = Point(current.x + values[0] if relative else values[0], current.y)
            transformed.append(matrix.apply(current))
            previous_control = None
        elif upper == "V":
            current = Point(current.x, current.y + values[0] if relative else values[0])
            transformed.append(matrix.apply(current))
            previous_control = None
        elif upper == "C":
            first = absolute(values[0], values[1], relative)
            second = absolute(values[2], values[3], relative)
            destination = absolute(values[4], values[5], relative)
            transformed.extend(
                _flatten_cubic(
                    matrix.apply(current),
                    matrix.apply(first),
                    matrix.apply(second),
                    matrix.apply(destination),
                    tolerance,
                )
            )
            current = destination
            previous_control = second
        elif upper == "S":
            if previous_command and previous_command.upper() in {"C", "S"} and previous_control:
                first = Point(
                    2 * current.x - previous_control.x, 2 * current.y - previous_control.y
                )
            else:
                first = current
            second = absolute(values[0], values[1], relative)
            destination = absolute(values[2], values[3], relative)
            transformed.extend(
                _flatten_cubic(
                    matrix.apply(current),
                    matrix.apply(first),
                    matrix.apply(second),
                    matrix.apply(destination),
                    tolerance,
                )
            )
            current = destination
            previous_control = second
        elif upper == "Q":
            control = absolute(values[0], values[1], relative)
            destination = absolute(values[2], values[3], relative)
            transformed.extend(
                _flatten_quadratic(
                    matrix.apply(current),
                    matrix.apply(control),
                    matrix.apply(destination),
                    tolerance,
                )
            )
            current = destination
            previous_control = control
        elif upper == "T":
            if previous_command and previous_command.upper() in {"Q", "T"} and previous_control:
                control = Point(
                    2 * current.x - previous_control.x, 2 * current.y - previous_control.y
                )
            else:
                control = current
            destination = absolute(values[0], values[1], relative)
            transformed.extend(
                _flatten_quadratic(
                    matrix.apply(current),
                    matrix.apply(control),
                    matrix.apply(destination),
                    tolerance,
                )
            )
            current = destination
            previous_control = control
        elif upper == "A":
            if values[3] not in {0.0, 1.0} or values[4] not in {0.0, 1.0}:
                raise SvgInputError("arc flags must be 0 or 1")
            destination = absolute(values[5], values[6], relative)
            transformed.extend(
                _flatten_arc(
                    current,
                    values[0],
                    values[1],
                    values[2],
                    bool(values[3]),
                    bool(values[4]),
                    destination,
                    matrix,
                    tolerance,
                )
            )
            current = destination
            previous_control = None
        previous_command = command

    if not closed:
        raise SvgInputError("path pieces must be closed with Z")
    return _dedupe_closed(transformed)


def _sample_ellipse(
    center: Point, radius_x: float, radius_y: float, matrix: Matrix, tolerance: float
) -> tuple[Point, ...]:
    if radius_x <= 0 or radius_y <= 0:
        raise SvgInputError("circle and ellipse radii must be positive")
    physical_radius = max(radius_x, radius_y) * matrix.maximum_scale
    if physical_radius <= tolerance:
        count = 12
    else:
        step = 2 * math.acos(max(-1.0, 1 - tolerance / physical_radius))
        count = max(12, math.ceil(2 * math.pi / step))
    count = min(count, 4_096)
    return tuple(
        matrix.apply(
            Point(
                center.x + radius_x * math.cos(2 * math.pi * index / count),
                center.y + radius_y * math.sin(2 * math.pi * index / count),
            )
        )
        for index in range(count)
    )


def _shape_points(
    element: ET.Element, tag: str, matrix: Matrix, tolerance: float
) -> tuple[Point, ...]:
    if tag == "path":
        data = element.get("d")
        if not data:
            raise SvgInputError("<path> needs non-empty d data")
        return _path_points(data, matrix, tolerance)
    if tag in {"polygon", "polyline"}:
        values = _numbers(element.get("points", ""), context=f"<{tag}> points")
        if len(values) < 6 or len(values) % 2:
            raise SvgInputError(f"<{tag}> needs at least three coordinate pairs")
        local = [Point(values[index], values[index + 1]) for index in range(0, len(values), 2)]
        if tag == "polyline":
            if local[0] != local[-1]:
                raise SvgInputError("piece polyline must repeat its first point at the end")
            local.pop()
        return _dedupe_closed([matrix.apply(point) for point in local])
    if tag == "rect":
        if _float(element, "rx", default=0) or _float(element, "ry", default=0):
            raise SvgInputError("rounded rectangles are unsupported; convert the rect to a path")
        x = _float(element, "x", default=0)
        y = _float(element, "y", default=0)
        width = _float(element, "width")
        height = _float(element, "height")
        if width <= 0 or height <= 0:
            raise SvgInputError("rectangle width and height must be positive")
        return tuple(
            matrix.apply(point)
            for point in (
                Point(x, y),
                Point(x + width, y),
                Point(x + width, y + height),
                Point(x, y + height),
            )
        )
    if tag == "circle":
        return _sample_ellipse(
            Point(_float(element, "cx", default=0), _float(element, "cy", default=0)),
            _float(element, "r"),
            _float(element, "r"),
            matrix,
            tolerance,
        )
    if tag == "ellipse":
        return _sample_ellipse(
            Point(_float(element, "cx", default=0), _float(element, "cy", default=0)),
            _float(element, "rx"),
            _float(element, "ry"),
            matrix,
            tolerance,
        )
    raise AssertionError(tag)


def parse_svg_text(
    source: str,
    *,
    source_name: str = "input.svg",
    flatness_mm: float = 0.25,
    scale_mm_per_unit: float | None = None,
) -> SvgDocument:
    if flatness_mm <= 0:
        raise SvgInputError("flatness must be positive")
    if len(source.encode("utf-8")) > MAX_INPUT_BYTES:
        raise SvgInputError("SVG input exceeds the 10 MiB limit")
    upper_source = source.upper()
    if "<!DOCTYPE" in upper_source or "<!ENTITY" in upper_source:
        raise SvgInputError("SVG DTD and entity declarations are not allowed")
    try:
        root = ET.fromstring(source)
    except ET.ParseError as error:
        raise SvgInputError(f"invalid SVG XML: {error}") from error
    namespace, root_name = _local_name(root.tag)
    if root_name != "svg" or namespace not in {None, SVG_NAMESPACE}:
        raise SvgInputError("document root must be an SVG element")
    root_matrix, width_mm, height_mm, description = _root_geometry(root, scale_mm_per_unit)
    pieces: list[Piece] = []
    total_points = 0

    def visit(element: ET.Element, parent_matrix: Matrix, *, is_root: bool = False) -> None:
        nonlocal total_points
        namespace, tag = _local_name(element.tag)
        if namespace not in {None, SVG_NAMESPACE}:
            return
        if _is_hidden(element):
            return
        if tag in IGNORED_SUBTREES:
            return
        if tag in IGNORED_ELEMENTS:
            return
        if tag == "svg" and not is_root:
            raise SvgInputError("nested <svg> viewports are unsupported in v0.1")
        matrix = parent_matrix @ parse_transform(element.get("transform"))
        if tag in SHAPES:
            if _shape_is_ignored(element):
                return
            points = _shape_points(element, tag, matrix, flatness_mm)
            explicit_id = element.get("id")
            piece_id = explicit_id or f"piece-{len(pieces) + 1:03d}"
            pieces.append(Piece(piece_id, explicit_id is not None, tag, points))
            total_points += len(points)
            if len(pieces) > MAX_PIECES:
                raise SvgInputError("SVG exceeds the 5,000 piece limit")
            if total_points > MAX_POINTS:
                raise SvgInputError("flattened SVG exceeds the 200,000 point limit")
            return
        if tag not in CONTAINERS:
            raise SvgInputError(f"unsupported SVG geometry <{tag}>")
        for child in element:
            visit(child, matrix)

    visit(root, root_matrix, is_root=True)
    if not pieces:
        raise SvgInputError("SVG contains no visible, closed piece geometry")
    if width_mm == 0 or height_mm == 0:
        all_points = [point for piece in pieces for point in piece.points]
        width_mm = max(point.x for point in all_points) - min(point.x for point in all_points)
        height_mm = max(point.y for point in all_points) - min(point.y for point in all_points)
    return SvgDocument(
        source_name=Path(source_name).name,
        width_mm=width_mm,
        height_mm=height_mm,
        flatness_mm=flatness_mm,
        scale_description=description,
        pieces=tuple(pieces),
    )


def read_svg(
    path: Path, *, flatness_mm: float = 0.25, scale_mm_per_unit: float | None = None
) -> SvgDocument:
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise SvgInputError(f"cannot read UTF-8 SVG {path.name}: {error}") from error
    return parse_svg_text(
        source,
        source_name=path.name,
        flatness_mm=flatness_mm,
        scale_mm_per_unit=scale_mm_per_unit,
    )
