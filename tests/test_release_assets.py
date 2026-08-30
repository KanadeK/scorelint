from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

from scripts.release_assets import create_release_assets


def test_release_examples_and_checksums_are_deterministic(tmp_path: Path) -> None:
    (tmp_path / "dist").mkdir()
    (tmp_path / "examples").mkdir()
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "scorelint"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    wheel = tmp_path / "dist" / "scorelint-0.1.0-py3-none-any.whl"
    source = tmp_path / "dist" / "scorelint-0.1.0.tar.gz"
    wheel.write_bytes(b"wheel")
    source.write_bytes(b"source")
    (tmp_path / "examples" / "z.svg").write_text("<svg/>\n", encoding="utf-8")
    (tmp_path / "examples" / "a.svg").write_text("<svg />\n", encoding="utf-8")

    assets = create_release_assets(tmp_path)
    first_zip = assets[2].read_bytes()
    first_checksums = assets[3].read_text(encoding="utf-8")
    create_release_assets(tmp_path)

    assert assets[2].read_bytes() == first_zip
    assert assets[3].read_text(encoding="utf-8") == first_checksums
    with zipfile.ZipFile(assets[2]) as archive:
        assert archive.namelist() == [
            "scorelint-0.1.0-examples/a.svg",
            "scorelint-0.1.0-examples/z.svg",
        ]
        assert all(item.date_time == (2026, 8, 30, 0, 0, 0) for item in archive.infolist())
    expected = hashlib.sha256(wheel.read_bytes()).hexdigest()
    assert first_checksums.splitlines()[0] == f"{expected}  {wheel.name}"
