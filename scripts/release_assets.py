"""Build deterministic non-package assets for a ScoreLint release."""

from __future__ import annotations

import hashlib
import tomllib
import zipfile
from pathlib import Path


def project_version(root: Path) -> str:
    with (root / "pyproject.toml").open("rb") as handle:
        return str(tomllib.load(handle)["project"]["version"])


def create_release_assets(root: Path) -> tuple[Path, ...]:
    version = project_version(root)
    distribution = root / "dist"
    wheel = distribution / f"scorelint-{version}-py3-none-any.whl"
    source = distribution / f"scorelint-{version}.tar.gz"
    for artifact in (wheel, source):
        if not artifact.is_file():
            raise FileNotFoundError(f"missing built artifact: {artifact.name}")

    examples = distribution / f"scorelint-{version}-examples.zip"
    with zipfile.ZipFile(
        examples, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted((root / "examples").glob("*.svg")):
            info = zipfile.ZipInfo(
                f"scorelint-{version}-examples/{path.name}",
                date_time=(2026, 8, 30, 0, 0, 0),
            )
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())

    hashed = (wheel, source, examples)
    checksums = distribution / "SHA256SUMS.txt"
    checksums.write_text(
        "".join(
            f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n" for path in hashed
        ),
        encoding="utf-8",
        newline="\n",
    )
    return (*hashed, checksums)


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[1]
    for built_asset in create_release_assets(project_root):
        print(built_asset.relative_to(project_root))
