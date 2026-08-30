from __future__ import annotations

import os
from pathlib import Path

from release_assets import project_version

ROOT = Path(__file__).resolve().parents[1]
actual = os.environ.get("GITHUB_REF_NAME")
expected = f"v{project_version(ROOT)}"
if actual != expected:
    raise SystemExit(f"release tag {actual!r} does not match package version {expected!r}")
print(f"release tag matches package version: {expected}")
