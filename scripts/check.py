"""Run the complete local and CI release gate."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from release_assets import create_release_assets, project_version

ROOT = Path(__file__).resolve().parents[1]


def run(*arguments: str) -> None:
    print(f"+ {' '.join(arguments)}", flush=True)
    subprocess.run(arguments, cwd=ROOT, check=True)


def assert_dependency_free_wheel(wheel: Path) -> None:
    with zipfile.ZipFile(wheel) as archive:
        metadata_name = next(
            name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
        )
        metadata = archive.read(metadata_name).decode("utf-8")
    if any(line.startswith("Requires-Dist:") for line in metadata.splitlines()):
        raise RuntimeError("release wheel unexpectedly has runtime dependencies")


def installed_acceptance(wheel: Path) -> None:
    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("uv is required to run isolated installation acceptance")
    with tempfile.TemporaryDirectory(prefix="scorelint-fresh-install-") as temporary:
        environment = Path(temporary) / "venv"
        subprocess.run(
            [uv, "venv", "--python", sys.executable, str(environment)], cwd=ROOT, check=True
        )
        installed_python = environment / (
            "Scripts/python.exe" if sys.platform == "win32" else "bin/python"
        )
        executable = environment / (
            "Scripts/scorelint.exe" if sys.platform == "win32" else "bin/scorelint"
        )
        subprocess.run(
            [uv, "pip", "install", "--python", str(installed_python), str(wheel)],
            cwd=ROOT,
            check=True,
        )
        version = project_version(ROOT)
        subprocess.run(
            [str(executable), "--version"],
            cwd=ROOT,
            check=True,
            text=True,
        )
        cases = (
            ("clean-panel.svg", 0),
            ("risky-panel.svg", 1),
            ("malformed-open-path.svg", 2),
        )
        for filename, expected in cases:
            output = Path(temporary) / f"report-{filename}"
            completed = subprocess.run(
                [
                    str(executable),
                    "audit",
                    str(ROOT / "examples" / filename),
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                check=False,
            )
            if completed.returncode != expected:
                raise RuntimeError(
                    f"installed scorelint {version} returned {completed.returncode} for "
                    f"{filename}; expected {expected}"
                )
            if expected in {0, 1} and {path.name for path in output.iterdir()} != {
                "report.json",
                "findings.csv",
                "annotated.svg",
                "report.html",
            }:
                raise RuntimeError(f"installed audit did not create all reports for {filename}")
            if expected == 2 and output.exists():
                raise RuntimeError("invalid installed audit created a successful output directory")


def main() -> None:
    run(sys.executable, "-m", "ruff", "check", ".")
    run(sys.executable, "-m", "ruff", "format", "--check", ".")
    run(sys.executable, "-m", "mypy")
    run(sys.executable, "-m", "coverage", "erase")
    with tempfile.TemporaryDirectory(prefix="scorelint-pytest-") as pytest_temporary:
        run(
            sys.executable,
            "-m",
            "coverage",
            "run",
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "--basetemp",
            pytest_temporary,
        )
    run(sys.executable, "-m", "coverage", "report")
    run(sys.executable, "-m", "pip_audit")

    distribution = ROOT / "dist"
    if distribution.exists():
        shutil.rmtree(distribution)
    run(sys.executable, "-m", "build")
    assets = create_release_assets(ROOT)
    assert_dependency_free_wheel(assets[0])
    installed_acceptance(assets[0])
    print("SCORELINT_RELEASE_GATE=PASS")


if __name__ == "__main__":
    main()
