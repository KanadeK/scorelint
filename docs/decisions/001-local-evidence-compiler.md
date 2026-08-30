# ADR-001: Build a local evidence compiler, not an editor or oracle

## Status

Accepted

## Date

2026-08-30

## Context

Makers already create patterns in vector editors and dedicated stained-glass tools.
The observed gap is an independent check for measurable geometry risks before material
is cut. The input may be private artwork, and the physical result depends on facts an
SVG cannot contain: glass texture and grain, tools, skill, reinforcement, and assembly
order.

The first release also needs to install reliably on current CPython across Windows and
Linux, and to run in pattern-library automation.

## Decision

ScoreLint is a dependency-free runtime CLI that reads one local SVG and emits four
deterministic evidence artifacts. Parsing, geometry, audit rules, and presentation are
separate modules. Unsupported SVG constructs fail loudly. Findings name measurements
and thresholds rather than declaring cuttability, and the original artwork is never
modified.

## Alternatives considered

### Hosted web editor

- Benefit: immediate visual interaction.
- Rejected: duplicates existing editors, introduces an upload/privacy boundary, and
  makes repeatable CI use harder.

### Automatic seam repair

- Benefit: could appear to solve a finding in one action.
- Rejected: moving a seam changes both the art and its physical structure; there is no
  evidence for a universally correct repair.

### Native geometry or SVG dependency

- Benefit: broader SVG/rendering coverage with less parser code.
- Rejected for v0.1: native wheels and large rendering semantics raise installation
  and trust costs for a narrow closed-geometry subset. The supported subset is tested
  against the SVG 2 path and transform semantics we use.

### Possible/impossible classifier

- Benefit: simpler headline result.
- Rejected: geometry alone cannot support that claim. Measured findings let the maker
  apply context without hiding uncertainty.

## Consequences

- Private artwork stays local and runtime has no service dependency.
- A strict subset rejects some valid SVGs rather than silently guessing.
- Curve results depend on an explicit, reported flattening tolerance.
- New rules must expose evidence, threshold semantics, and tests before release.
- Supporting a materially broader SVG surface may justify revisiting the dependency
  decision in a future ADR.
