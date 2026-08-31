# ScoreLint v0.1.0 Tasks

- [x] Domain records and polygon geometry
  - Acceptance: deterministic area, angles, intersections, and edge distances.
  - Verify: `uv run --no-sync pytest tests/test_geometry.py`
- [x] SVG ingestion
  - Acceptance: supported shapes, curves, transforms, and physical units parse; unsafe
    or unsupported input fails loudly.
  - Verify: `uv run --no-sync pytest tests/test_svg.py`
- [x] Audit rules
  - Acceptance: all `SL1xx`/`SL2xx` rules have positive and negative fixtures.
  - Verify: `uv run --no-sync pytest tests/test_audit.py`
- [x] Reports and CLI
  - Acceptance: all four artifacts, deterministic bytes, stable exit codes.
  - Verify: `uv run --no-sync pytest tests/test_reports.py tests/test_cli.py`
- [x] Examples, docs, package, and CI
  - Acceptance: build/install/examples/full gate pass locally and remotely.
  - Verify: `uv run --no-sync python scripts/check.py`
- [x] Public release closure
  - Acceptance: public repo, passing main/tag CI, annotated `v0.1.0`, Release assets,
    fresh-install acceptance, and Gmail notification.
