# Spec: ScoreLint v0.1.0

## Objective

ScoreLint gives stained-glass makers and pattern-library maintainers a local,
repeatable answer to: "Which measurable parts of this SVG deserve human review before
I cut glass?"

The success condition is a real input-to-report compiler, not a user interface. Given
a supported SVG, it must either produce deterministic evidence artifacts or fail
loudly with a stable exit code and no fabricated result.

## Tech Stack

- Python 3.11+ using only the standard library at runtime.
- Hatchling build backend and PEP 621 project metadata.
- pytest, Coverage.py, Ruff, mypy, build, and pip-audit as development gates.

## Commands

```powershell
$env:UV_CACHE_DIR = "$PWD\.uv-cache"
uv sync --all-groups --locked
uv run --no-sync pytest
uv run --no-sync coverage run -m pytest
uv run --no-sync coverage report
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync mypy
uv run --no-sync python -m build
uv run --no-sync python scripts/check.py
```

End-user acceptance:

```powershell
scorelint audit examples/clean-panel.svg --output .artifacts/clean
scorelint audit examples/risky-panel.svg --output .artifacts/risky
```

## Project Structure

```text
src/scorelint/     package, SVG parser, geometry rules, reports, CLI
tests/             unit, integration, and installed-CLI tests
examples/          deterministic SVG fixtures
docs/              idea, research, rule reference, generated demo
scripts/check.py   single full release gate
tasks/             implementation plan and completed checklist
```

## Code Style

Use typed immutable data records at module boundaries and plain functions for geometry:

```python
@dataclass(frozen=True, slots=True)
class Point:
    x: float
    y: float
```

Names describe evidence, not certainty: `tight_concavity` is acceptable;
`impossible_cut` is not.

## Testing Strategy

- Unit tests cover transforms, path flattening, intersections, angles, distances,
  rule thresholds, and deterministic serialization.
- Integration tests run the CLI against committed SVG fixtures and assert artifacts
  and exit codes.
- Packaging tests install the built wheel into an isolated environment and run the
  console entry point.
- Branch coverage must remain at or above 90%; no skipped tests in the release gate.

## Input Contract

- Maximum input size: 10 MiB; XML DTD/entity declarations are rejected.
- Supported geometry: `path`, `polygon`, `polyline`, `rect`, `circle`, and `ellipse`.
- Supported path commands: `M/L/H/V/C/S/Q/T/A/Z`, absolute and relative.
- Supported transforms: matrix, translate, scale, rotate, skewX, and skewY, including
  nested groups.
- Every audited piece is a closed, filled geometry element. Elements inside `defs`,
  clip paths, masks, metadata, and symbols are ignored in v0.1.
- Physical scaling comes from root width/height units and viewBox, or from an explicit
  `--scale-mm-per-unit` override. Unitless documents without an override fail.

## Findings and Exit Codes

| Code | Meaning | Default level |
|---|---|---|
| `SL100` | contour is self-intersecting or degenerate | error |
| `SL101` | two declared pieces overlap in area | error |
| `SL200` | internal tip angle is below threshold | warning |
| `SL201` | concave notch opening is below threshold | warning |
| `SL202` | non-adjacent edges form a section below minimum width | warning |
| `SL203` | piece area is below minimum area | warning |
| `SL204` | stable SVG piece ID is missing | notice |

- Exit `0`: no error or warning findings (notices allowed).
- Exit `1`: one or more error or warning findings; reports are still written.
- Exit `2`: input, configuration, XML, I/O, or unsupported-geometry failure; no report
  is presented as a successful audit.

## Output Contract

The output directory receives `report.json`, `findings.csv`, `annotated.svg`, and
`report.html`. JSON includes schema/tool versions, source basename, physical scale,
flattening tolerance, thresholds, per-piece metrics, and stable findings. Reports do
not embed absolute local paths or upload any content.

## Boundaries

- Always: fail fast on malformed/unsupported input; make thresholds visible; keep
  output deterministic; escape all source-derived text in HTML/SVG.
- Ask first: add runtime dependencies; reinterpret unsupported SVG silently; publish a
  breaking report schema.
- Never: call risk indicators proof of cuttability, modify the input pattern, upload
  artwork, fetch live services at runtime, or claim structural/safety certification.

## Success Criteria

- Clean, risky, curved/transformed, overlapping, and malformed examples exercise real
  parsing and findings.
- The full release gate passes locally and in GitHub Actions on Ubuntu/Python 3.11 and
  Windows/Python 3.14.
- Wheel and sdist install cleanly; the installed CLI creates all four artifact types.
- Public `main` and `v0.1.0` CI pass; the GitHub Release is non-draft/non-prerelease
  and contains wheel, sdist, example bundle, and checksums.
- A fresh install from downloaded Release assets passes the documented command.

## Open Questions

None block v0.1. The user explicitly delegated product selection and end-to-end
delivery, so the documented assumptions serve as the approved working boundary.
