# ScoreLint

## Problem Statement

How might we help stained-glass makers review a vector pattern for measurable
cut-risk indicators before using material, without uploading their design,
generating replacement art, or pretending geometry alone proves a cut is possible?

## Recommended Direction

Build a deterministic command-line preflight for SVG patterns in which every glass
piece is a closed shape. ScoreLint flattens supported vector curves under an explicit
tolerance, validates every contour, and reports explainable indicators such as
self-intersections, overlapping pieces, sharp tips, tight concave notches, and narrow
sections. It produces machine-readable JSON/CSV plus a standalone annotated SVG and
HTML report.

The product wedge is not another editor. Makers keep Inkscape, Illustrator, or their
preferred drawing process. ScoreLint is the independent review step that can run
locally, repeatably, and in CI for shared pattern libraries.

## Key Assumptions to Validate

- [x] Makers encounter avoidable geometry problems in generated and hand-edited
  patterns. Public discussions contain repeated complaints about inside cuts, sharp
  shapes, narrow parts, and uploading private artwork.
- [x] A useful first release can identify measurable risk indicators without
  classifying a piece as definitively possible or impossible.
- [ ] Default thresholds will fit every glass, tool, and skill level. They will not;
  v0.1 therefore exposes thresholds and records them in every report.

## MVP Scope

- Parse common closed SVG geometry and transforms into physical millimetres.
- Detect invalid contours and five explicit cut-risk indicators.
- Emit deterministic JSON, CSV, annotated SVG, and standalone HTML.
- Include clean, risky, curved, transformed, overlapping, and malformed fixtures.
- Ship as a Python wheel/sdist with Linux and Windows CI.

## Not Doing (and Why)

- AI image or pattern generation — it is outside the review job and would undermine
  the human-authored-art boundary.
- A drawing editor — Inkscape and dedicated stained-glass editors already exist.
- Automatic repair — changing a seam changes both structure and art.
- Material purchasing or live prices — unrelated, volatile, and already covered by
  other tools.
- Safety or structural certification — geometry cannot see glass grain, texture,
  scoring technique, reinforcement, or installation loads.

## Open Questions

- Which additional SVG constructs deserve support after real pattern samples arrive?
- Which rule defaults should become named profiles after practitioner feedback?
