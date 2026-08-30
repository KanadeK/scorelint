from __future__ import annotations

import math

import pytest

from scorelint.svg import SvgInputError, parse_svg_text


def test_viewbox_maps_geometry_into_physical_millimetres() -> None:
    document = parse_svg_text(
        """
        <svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="50mm"
             viewBox="0 0 200 100">
          <rect id="pane-a" x="20" y="10" width="40" height="20" />
        </svg>
        """
    )

    assert document.width_mm == pytest.approx(100)
    assert document.height_mm == pytest.approx(50)
    assert document.scale_description == "viewBox to 100x50 mm viewport"
    assert document.pieces[0].piece_id == "pane-a"
    assert [(point.x, point.y) for point in document.pieces[0].points] == pytest.approx(
        [(10, 5), (30, 5), (30, 15), (10, 15)]
    )


def test_unitless_document_requires_explicit_scale() -> None:
    source = """
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="10 20 100 50">
      <polygon points="10,20 20,20 20,30 10,30" />
    </svg>
    """

    with pytest.raises(SvgInputError, match="scale-mm-per-unit"):
        parse_svg_text(source)

    document = parse_svg_text(source, scale_mm_per_unit=2)
    assert document.width_mm == pytest.approx(200)
    assert document.height_mm == pytest.approx(100)
    assert [(point.x, point.y) for point in document.pieces[0].points] == pytest.approx(
        [(0, 0), (20, 0), (20, 20), (0, 20)]
    )


def test_nested_transforms_are_applied_in_svg_order() -> None:
    document = parse_svg_text(
        """
        <svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm"
             viewBox="0 0 100 100">
          <g transform="translate(10 5)">
            <polygon id="moved" transform="scale(2)" points="0,0 5,0 5,5 0,5" />
          </g>
        </svg>
        """
    )

    assert [(point.x, point.y) for point in document.pieces[0].points] == pytest.approx(
        [(10, 5), (20, 5), (20, 15), (10, 15)]
    )


def test_linear_path_supports_relative_and_implicit_commands() -> None:
    document = parse_svg_text(
        """
        <svg xmlns="http://www.w3.org/2000/svg" width="40mm" height="40mm"
             viewBox="0 0 40 40">
          <path id="linear" d="m 5 5 h 10 5 v 10 l -20 0 z" />
        </svg>
        """
    )

    assert [(point.x, point.y) for point in document.pieces[0].points] == pytest.approx(
        [(5, 5), (15, 5), (20, 5), (20, 15), (0, 15)]
    )


def test_cubic_quadratic_and_smooth_curves_are_flattened() -> None:
    document = parse_svg_text(
        """
        <svg xmlns="http://www.w3.org/2000/svg" width="60mm" height="40mm"
             viewBox="0 0 60 40">
          <path id="curves"
                d="M 5 20 C 10 0 20 0 25 20 S 40 40 45 20
                   Q 50 10 55 20 T 45 30 Z" />
        </svg>
        """,
        flatness_mm=0.25,
    )

    piece = document.pieces[0]
    assert len(piece.points) > 20
    assert piece.points[0].x == pytest.approx(5)
    assert piece.points[0].y == pytest.approx(20)
    assert piece.points[-1].x == pytest.approx(45)
    assert piece.points[-1].y == pytest.approx(30)


def test_elliptical_arc_is_flattened_with_exact_endpoints() -> None:
    document = parse_svg_text(
        """
        <svg xmlns="http://www.w3.org/2000/svg" width="40mm" height="40mm"
             viewBox="0 0 40 40">
          <path id="arc" d="M 5 20 A 15 10 0 0 1 35 20 L 35 30 L 5 30 Z" />
        </svg>
        """,
        flatness_mm=0.2,
    )

    piece = document.pieces[0]
    assert len(piece.points) > 8
    assert piece.points[0].x == pytest.approx(5)
    assert piece.points[0].y == pytest.approx(20)
    assert any(math.isclose(point.x, 35) and math.isclose(point.y, 20) for point in piece.points)


def test_basic_shapes_and_closed_polyline_become_pieces() -> None:
    document = parse_svg_text(
        """
        <svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm"
             viewBox="0 0 100 100">
          <circle id="circle" cx="15" cy="15" r="5" />
          <ellipse id="ellipse" cx="35" cy="15" rx="8" ry="4" />
          <polyline id="polyline" points="50,10 60,10 60,20 50,20 50,10" />
        </svg>
        """
    )

    assert [piece.piece_id for piece in document.pieces] == ["circle", "ellipse", "polyline"]
    assert len(document.pieces[0].points) >= 12
    assert len(document.pieces[1].points) >= 12
    assert len(document.pieces[2].points) == 4


def test_hidden_guides_and_definition_geometry_are_ignored() -> None:
    document = parse_svg_text(
        """
        <svg xmlns="http://www.w3.org/2000/svg" width="30mm" height="30mm"
             viewBox="0 0 30 30">
          <defs><rect id="template" x="0" y="0" width="5" height="5" /></defs>
          <rect id="guide" x="0" y="0" width="10" height="10" fill="none" />
          <g style="display:none"><circle id="hidden" cx="5" cy="5" r="2" /></g>
          <rect id="piece" x="10" y="10" width="10" height="10" />
        </svg>
        """
    )

    assert [piece.piece_id for piece in document.pieces] == ["piece"]


def test_generated_piece_ids_are_stable_in_document_order() -> None:
    document = parse_svg_text(
        """
        <svg xmlns="http://www.w3.org/2000/svg" width="20mm" height="10mm"
             viewBox="0 0 20 10">
          <rect x="0" y="0" width="5" height="5" />
          <rect x="10" y="0" width="5" height="5" />
        </svg>
        """
    )

    assert [piece.piece_id for piece in document.pieces] == ["piece-001", "piece-002"]
    assert [piece.has_explicit_id for piece in document.pieces] == [False, False]


@pytest.mark.parametrize(
    ("fragment", "message"),
    [
        ("<path d='M0 0 L10 0 L10 10'/>", "closed with Z"),
        ("<polyline points='0,0 10,0 10,10'/>", "repeat its first point"),
        ("<path d='M0 0 L10 0 Z M20 20 L30 20 Z'/>", "one closed subpath"),
        ("<use href='#piece'/>", "unsupported SVG geometry"),
        ("<path d='M0 0 X 10 10 Z'/>", "invalid path data"),
    ],
)
def test_unsupported_or_open_geometry_fails_loudly(fragment: str, message: str) -> None:
    source = f"""
    <svg xmlns="http://www.w3.org/2000/svg" width="40mm" height="40mm"
         viewBox="0 0 40 40">{fragment}</svg>
    """

    with pytest.raises(SvgInputError, match=message):
        parse_svg_text(source)


def test_doctype_and_entity_declarations_are_rejected_before_xml_parsing() -> None:
    source = """<!DOCTYPE svg [<!ENTITY x "unsafe">]>
    <svg xmlns="http://www.w3.org/2000/svg" width="10mm" height="10mm">
      <rect id="&x;" x="0" y="0" width="5" height="5" />
    </svg>"""

    with pytest.raises(SvgInputError, match="DTD and entity declarations"):
        parse_svg_text(source)


def test_physical_scale_requires_positive_flatness_and_override() -> None:
    source = """
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">
      <rect x="0" y="0" width="5" height="5" />
    </svg>
    """

    with pytest.raises(SvgInputError, match="flatness"):
        parse_svg_text(source, scale_mm_per_unit=1, flatness_mm=0)
    with pytest.raises(SvgInputError, match="scale-mm-per-unit"):
        parse_svg_text(source, scale_mm_per_unit=-1)
