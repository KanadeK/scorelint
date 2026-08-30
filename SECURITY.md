# Security Policy

## Supported version

Security fixes are provided for the latest released version.

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting for this repository instead of a
public issue. Include a minimal SVG or report when safe to do so, the affected version,
and expected impact. Do not attach private customer artwork.

## Input and output boundary

ScoreLint treats SVG files as untrusted input. v0.1:

- rejects DTD and entity declarations;
- limits input to 10 MiB, 5,000 pieces, and 200,000 flattened points;
- rejects unsupported geometry instead of executing or silently interpreting it;
- ignores script/style/metadata content and never renders the input in a browser;
- escapes source-derived IDs and messages in generated HTML/SVG;
- performs no network requests and does not modify the source SVG.

The standalone HTML report contains no script. As with any local tool, choose an output
directory you control and avoid replacing unrelated files with the four documented
artifact names.
