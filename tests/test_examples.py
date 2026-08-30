from __future__ import annotations

import json
from pathlib import Path

import pytest

from scorelint.cli import main

ROOT = Path(__file__).parents[1]


@pytest.mark.parametrize(
    ("filename", "expected_exit", "expected_codes"),
    [
        ("clean-panel.svg", 0, set()),
        ("risky-panel.svg", 1, {"SL200", "SL201", "SL202", "SL203", "SL204"}),
        ("curved-transformed.svg", 0, set()),
        ("overlapping-panel.svg", 1, {"SL101"}),
    ],
)
def test_committed_examples_exercise_real_audits(
    filename: str,
    expected_exit: int,
    expected_codes: set[str],
    tmp_path: Path,
) -> None:
    output = tmp_path / filename

    result = main(["audit", str(ROOT / "examples" / filename), "--output", str(output)])

    assert result == expected_exit
    payload = json.loads((output / "report.json").read_text(encoding="utf-8"))
    assert {finding["code"] for finding in payload["findings"]} == expected_codes


def test_malformed_example_is_a_documented_exit_two(tmp_path: Path) -> None:
    output = tmp_path / "malformed"

    result = main(
        [
            "audit",
            str(ROOT / "examples" / "malformed-open-path.svg"),
            "--output",
            str(output),
        ]
    )

    assert result == 2
    assert not output.exists()
