from __future__ import annotations

from pathlib import Path

import pytest

from scorelint.cli import main

CLEAN_SVG = """\
<svg xmlns="http://www.w3.org/2000/svg" width="20mm" height="10mm" viewBox="0 0 20 10">
  <rect id="pane" x="0" y="0" width="20" height="10"/>
</svg>
"""

RISKY_SVG = """\
<svg xmlns="http://www.w3.org/2000/svg" width="20mm" height="10mm" viewBox="0 0 20 10">
  <rect id="sliver" x="0" y="0" width="20" height="2"/>
</svg>
"""


def test_clean_audit_returns_zero_and_writes_all_artifacts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "clean.svg"
    output = tmp_path / "out"
    source.write_text(CLEAN_SVG, encoding="utf-8")

    result = main(["audit", str(source), "--output", str(output)])

    assert result == 0
    assert {path.name for path in output.iterdir()} == {
        "report.json",
        "findings.csv",
        "annotated.svg",
        "report.html",
    }
    assert "0 errors, 0 warnings, 0 notices" in capsys.readouterr().out


def test_risky_audit_returns_one_but_still_writes_reports(tmp_path: Path) -> None:
    source = tmp_path / "risky.svg"
    output = tmp_path / "out"
    source.write_text(RISKY_SVG, encoding="utf-8")

    result = main(["audit", str(source), "--output", str(output)])

    assert result == 1
    assert (output / "report.json").is_file()


def test_invalid_input_returns_two_without_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "invalid.svg"
    output = tmp_path / "out"
    source.write_text("<svg><path d='M 0 0 L'/></svg>", encoding="utf-8")

    result = main(["audit", str(source), "--output", str(output)])

    assert result == 2
    assert not output.exists()
    assert "scorelint: error:" in capsys.readouterr().err


def test_cli_accepts_explicit_scale_and_thresholds(tmp_path: Path) -> None:
    source = tmp_path / "unitless.svg"
    output = tmp_path / "out"
    source.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"><rect id="p" width="20" height="10"/></svg>',
        encoding="utf-8",
    )

    result = main(
        [
            "audit",
            str(source),
            "--output",
            str(output),
            "--scale-mm-per-unit",
            "1",
            "--tip-angle-deg",
            "20",
            "--min-area-mm2",
            "10",
        ]
    )

    assert result == 0


def test_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit, match="0"):
        main(["--version"])

    assert capsys.readouterr().out.strip() == "scorelint 0.1.0"
