from __future__ import annotations

import math
from pathlib import Path

import pytest

from scorelint.geometry import Point
from scorelint.svg import MAX_INPUT_BYTES, SvgInputError, parse_svg_text, parse_transform, read_svg


def wrapped(
    fragment: str, root_attributes: str = 'width="40mm" height="40mm" viewBox="0 0 40 40"'
) -> str:
    return f'<svg xmlns="http://www.w3.org/2000/svg" {root_attributes}>{fragment}</svg>'


def test_all_transform_forms_have_explicit_matrix_semantics() -> None:
    translated = parse_transform("matrix(1 0 0 1 2 3)").apply(Point(1, 1))
    rotated = parse_transform("rotate(90 10 10)").apply(Point(11, 10))
    skewed = parse_transform("skewX(45) skewY(0)").apply(Point(2, 3))

    assert (translated.x, translated.y) == pytest.approx((3, 4))
    assert (rotated.x, rotated.y) == pytest.approx((10, 11))
    assert (skewed.x, skewed.y) == pytest.approx((5, 3))
    assert parse_transform(None).apply(Point(2, 3)) == Point(2, 3)


def test_transform_maximum_scale_is_conservative_under_shear() -> None:
    matrix = parse_transform("matrix(1 0 1 1 0 0)")

    assert matrix.maximum_scale == pytest.approx((1 + math.sqrt(5)) / 2)


@pytest.mark.parametrize(
    ("transform", "message"),
    [
        ("translate(nope)", "invalid numeric list"),
        ("oops translate(1)", "invalid transform syntax"),
        ("translate(1) trailing", "invalid transform syntax"),
        ("rotate(1 2)", "unsupported or malformed"),
        ("nonsense", "invalid transform syntax"),
    ],
)
def test_malformed_transforms_fail_loudly(transform: str, message: str) -> None:
    with pytest.raises(SvgInputError, match=message):
        parse_transform(transform)


def test_physical_units_no_viewbox_and_aspect_ratio_modes() -> None:
    no_viewbox = parse_svg_text(
        wrapped(
            '<rect id="p" width="96" height="48"/>',
            root_attributes='width="10cm" height="2in"',
        )
    )
    none = parse_svg_text(
        wrapped(
            '<rect id="p" width="100" height="100"/>',
            root_attributes=(
                'width="100mm" height="50mm" viewBox="0 0 100 100" preserveAspectRatio="none"'
            ),
        )
    )
    deferred_slice = parse_svg_text(
        wrapped(
            '<rect id="p" width="100" height="100"/>',
            root_attributes=(
                'width="100mm" height="50mm" viewBox="0 0 100 100" '
                'preserveAspectRatio="defer xMaxYMax slice"'
            ),
        )
    )

    assert no_viewbox.width_mm == pytest.approx(100)
    assert no_viewbox.height_mm == pytest.approx(50.8)
    assert no_viewbox.pieces[0].points[2].x == pytest.approx(25.4)
    assert none.pieces[0].points[2].y == pytest.approx(50)
    assert deferred_slice.pieces[0].points[0].y == pytest.approx(-50)


def test_explicit_scale_without_viewbox_derives_document_extent() -> None:
    document = parse_svg_text(
        wrapped('<rect x="10" y="20" width="5" height="7"/>', root_attributes=""),
        scale_mm_per_unit=2,
    )

    assert document.width_mm == pytest.approx(10)
    assert document.height_mm == pytest.approx(14)


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ("<svg", "invalid SVG XML"),
        ("<html/>", "root must be an SVG"),
        (wrapped(""), "no visible, closed piece"),
        (wrapped("<svg><rect width='2' height='2'/></svg>"), "nested <svg>"),
        (wrapped("<rect width='2' height='2' rx='1'/>"), "rounded rectangles"),
        (wrapped("<rect height='2'/>"), "needs width"),
        (wrapped("<rect width='-2' height='2'/>"), "must be positive"),
        (wrapped("<circle r='0'/>"), "radii must be positive"),
        (wrapped("<polygon points='0,0 2,0 bad'/>"), "invalid numeric list"),
        (wrapped("<polygon points='0,0 2,0 0,0'/>"), "three distinct points"),
        (wrapped("<path/>"), "non-empty d"),
        (wrapped("<path d='Z'/>"), "Z before M"),
        (wrapped("<path d='L 1 1 Z'/>"), "first command must be M"),
        (wrapped("<path d='M 0 0 A 5 5 0 2 0 10 0 Z'/>"), "arc flags"),
    ],
)
def test_invalid_xml_and_geometry_boundaries(source: str, message: str) -> None:
    with pytest.raises(SvgInputError, match=message):
        parse_svg_text(source)


@pytest.mark.parametrize(
    ("root_attributes", "message"),
    [
        ('height="10mm"', "physical width"),
        ('width="10" height="10mm"', "must use mm"),
        ('width="-1mm" height="10mm"', "must be positive"),
        ('width="10mm" height="10mm" viewBox="0 0 0 10"', "viewBox must contain"),
        (
            'width="10mm" height="10mm" viewBox="0 0 10 10" preserveAspectRatio="bad"',
            "unsupported preserveAspectRatio",
        ),
    ],
)
def test_invalid_root_scale_boundaries(root_attributes: str, message: str) -> None:
    with pytest.raises(SvgInputError, match=message):
        parse_svg_text(wrapped('<rect width="2" height="2"/>', root_attributes))


def test_zero_radius_arc_becomes_a_line_segment() -> None:
    document = parse_svg_text(wrapped('<path d="M 0 0 A 0 5 0 0 1 10 0 L 10 10 L 0 10 Z"/>'))

    assert any(
        math.isclose(point.x, 10) and math.isclose(point.y, 0)
        for point in document.pieces[0].points
    )


def test_read_svg_reports_invalid_utf8(tmp_path: Path) -> None:
    source = tmp_path / "bad.svg"
    source.write_bytes(b"\xff\xfe")

    with pytest.raises(SvgInputError, match="cannot read UTF-8 SVG"):
        read_svg(source)


def test_read_svg_rejects_oversized_file_before_decoding(tmp_path: Path) -> None:
    source = tmp_path / "oversized.svg"
    with source.open("wb") as handle:
        handle.write(b"\xff")
        handle.seek(MAX_INPUT_BYTES)
        handle.write(b"x")

    with pytest.raises(SvgInputError, match="10 MiB limit"):
        read_svg(source)


@pytest.mark.parametrize(
    "source",
    [
        wrapped('<rect width="1e999" height="2"/>'),
        wrapped('<path d="M 0 0 L 1e999 0 L 0 2 Z"/>'),
    ],
)
def test_non_finite_svg_numbers_are_rejected(source: str) -> None:
    with pytest.raises(SvgInputError, match="finite"):
        parse_svg_text(source)


@pytest.mark.parametrize(
    ("keyword", "value"),
    [("flatness_mm", float("nan")), ("scale_mm_per_unit", float("inf"))],
)
def test_non_finite_parser_configuration_is_rejected(keyword: str, value: float) -> None:
    with pytest.raises(SvgInputError, match="finite"):
        parse_svg_text(wrapped('<rect width="2" height="2"/>'), **{keyword: value})
