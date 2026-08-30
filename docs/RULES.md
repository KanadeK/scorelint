# Rule Reference

ScoreLint findings are deterministic measurements for review. They are not a verdict
that glass can or cannot be cut. Default thresholds are intentionally visible and can
be changed at the command line; every report records the values used.

## Structural errors

### SL100 — invalid contour

Raised when a declared piece self-intersects, has zero area, or lacks three distinct
vertices. For an intersection, the report includes both edge indices and the contact
point. Other cut-risk rules do not run on an invalid contour because their metrics
would be misleading.

Action: repair the source contour and rerun the audit. ScoreLint does not choose which
seam to move.

### SL101 — overlapping declared pieces

Raised once for each pair of valid piece areas that overlap. Touching boundaries are
allowed; an area crossing or containment is not.

Action: verify whether the SVG accidentally duplicates or crosses a seam. Layer order
does not turn overlapping filled regions into separate physical pieces.

## Review warnings

### SL200 — sharp internal tip

Default: internal convex angle below `35 deg`.

The finding records the angle and vertex. A small angle can create a fragile point or
difficult score path, but feasibility depends on glass, orientation, and technique.

### SL201 — tight concave notch

Default: exterior opening at a concave vertex below `75 deg`.

The opening is `360 deg - internal angle`. This reports a local notch; it does not
model a scoring sequence, ring saw, grinder access, or relief cuts.

### SL202 — narrow section

Default: closest separation between non-adjacent contour edges below `3 mm`.

The report includes both edge indices and a midpoint between their closest witnesses.
Curve segments are first flattened under `--flatness-mm`, whose value is recorded in
the report. Change tolerance deliberately when comparing runs.

### SL203 — small piece

Default: polygon area below `50 mm2`.

This is a coarse handling prompt. Area alone cannot see aspect ratio, texture, grain,
or whether the piece is decorative, structural, or intentionally tiny.

## Tracking notice

### SL204 — generated piece ID

Raised when a source shape lacks an explicit SVG `id`. ScoreLint assigns
`piece-001`, `piece-002`, and so on for the current parse order. Add explicit IDs if
reports must remain comparable after shapes are reordered.

Notices do not change the exit code.

## Threshold options

| Option | Default | Valid range |
|---|---:|---|
| `--tip-angle-deg` | `35` | greater than 0 and less than 180 |
| `--concave-opening-deg` | `75` | greater than 0 and less than 180 |
| `--min-separation-mm` | `3` | greater than 0 |
| `--min-area-mm2` | `50` | greater than 0 |
| `--flatness-mm` | `0.25` | greater than 0 |

There are no named material profiles in v0.1 because we do not yet have evidence that
one shared preset truthfully represents different glasses, tools, and maker skills.
