ScoreLint v0.1.0 is the first public release of the offline, explainable cut-risk
preflight for stained-glass SVG patterns.

Highlights:

- audits closed SVG pieces without uploading or modifying artwork;
- reports measured contour, overlap, tip, notch, width, area, and ID evidence;
- writes deterministic JSON, CSV, annotated SVG, and standalone HTML;
- supports local use and pattern-library CI through stable exit codes;
- ships with a dependency-free Python runtime and tested example bundle.

Start with `scorelint-0.1.0-py3-none-any.whl` and the README quick start. The example
bundle contains clean, risky, curved/transformed, overlapping, and intentionally
malformed inputs. Verify downloads with `SHA256SUMS.txt`.

ScoreLint identifies geometry worth human review. It does not certify cuttability,
structural integrity, or safety.
