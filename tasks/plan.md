# Implementation Plan: ScoreLint v0.1.0

## Overview

Build a standard-library Python compiler that turns supported stained-glass SVG
pieces into deterministic geometry evidence and human-review artifacts.

## Architecture Decisions

- Keep runtime dependency-free so private patterns never require a service and wheels
  install on current CPython without native extensions.
- Separate SVG ingestion, pure geometry, rule evaluation, and presentation so every
  claim has focused tests.
- Flatten curves under a recorded tolerance; never hide approximation.
- Treat warnings as evidence for review, not automatic repair or cut certification.

## Task List

### Phase 1: Geometry foundation

- [x] Task 1: Define immutable domain records and tested polygon metrics.
- [x] Task 2: Parse supported SVG shapes, paths, transforms, and physical scale.
- [x] Task 3: Implement piece and cross-piece findings with stable codes.

### Checkpoint: Core

- [x] Focused tests pass for clean, risky, transformed, curved, and invalid geometry.

### Phase 2: Product slice

- [x] Task 4: Implement JSON/CSV/SVG/HTML renderers.
- [x] Task 5: Implement CLI, exit codes, boundaries, and deterministic examples.

### Checkpoint: End to end

- [x] CLI creates four artifacts from a clean example and returns `1` for risk findings.

### Phase 3: Ship

- [x] Task 6: Complete README, rule reference, contributor guidance, and repair flow.
- [x] Task 7: Add single local release gate, packaging checks, and cross-platform CI.
- [ ] Task 8: Commit, publish, verify Release assets, and perform fresh-install acceptance.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| SVG path support grows into a renderer | High | Support an explicit geometry subset and reject unsupported constructs |
| Geometry findings overstate physical reality | High | Name measurable indicators, expose thresholds, and document missing material factors |
| Curve flattening changes findings | Medium | Record tolerance and test deterministic convergence fixtures |
| HTML/SVG embeds hostile IDs | Medium | Escape all text and test markup-shaped IDs |

## Open Questions

None block v0.1.
