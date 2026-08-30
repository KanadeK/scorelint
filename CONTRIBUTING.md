# Contributing to ScoreLint

ScoreLint welcomes reproducible SVG fixtures, parser fixes, rule evidence, and report
improvements that preserve the local-review boundary.

## Before opening a change

- For a false positive or missed finding, provide the smallest SVG that demonstrates
  it and explain the physical review concern. Remove private artwork first.
- For a new rule, define its measurement, default threshold evidence, location
  witness, and limitation. A label without inspectable evidence is out of scope.
- For new SVG support, cite the relevant W3C semantics and add positive and rejection
  tests. Unsupported content must never disappear silently.
- Automatic art generation, seam repair, accounts, telemetry, and safety
  certification are outside the v0.1 product boundary.

## Development setup

Install [uv](https://docs.astral.sh/uv/), clone the repository, then run:

```console
uv sync --all-groups --locked
uv run python scripts/check.py
```

Focused test commands are listed in [tasks/todo.md](tasks/todo.md). Runtime code stays
compatible with Python 3.11 and uses the standard library only.

## Change shape

1. Add a failing test that demonstrates the desired behavior or defect.
2. Make the smallest complete change that removes the root cause.
3. Keep parsing, geometry, rule evaluation, and rendering authority in their existing
   modules; do not add a second source of truth.
4. Run the full gate.
5. Explain user-visible behavior, evidence, limitations, and test results in the pull
   request.

Do not include copyrighted or private pattern files unless you have permission to
publish them under the repository license.
