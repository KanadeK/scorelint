# Research and Differentiation

Research snapshot: 2026-08-30. Repository contents and market offerings can change.

## Observed Need

Two recent, highly visible stained-glass community discussions surfaced the same
failure: generated or converted patterns can contain deep inside cuts, sharp tips,
narrow pieces, and jagged lines that are frustrating or impractical at the bench. The
second discussion also raised discomfort about opaque uploads and replacing the
artist's structural judgment. ScoreLint responds by auditing an existing local SVG;
it does not create the pattern.

- Community cut-risk discussion:
  https://www.reddit.com/r/StainedGlass/comments/1s0jtrc/i_updated_my_stained_glass_pattern_tool_after/
- Earlier SVG/conversion discussion and practitioner objections:
  https://www.reddit.com/r/StainedGlass/comments/1rxwr6b/i_couldnt_find_a_stained_glass_pattern_for_my/

Delphi Glass's lead-came instructions confirm that pattern allowance, fitting order,
and exact bench adjustment matter; geometry software therefore must not claim to
replace physical fitting or maker judgment:
https://www.delphiglass.com/page/knowledgeBaseView?KBItemID=15

## Representative Alternatives

| Alternative | What it does | Why ScoreLint is not a clone |
|---|---|---|
| `christophernoessel/foil-and-solder-calculator` | Measures closed SVG edges and estimates foil/solder cost | ScoreLint reports piece-level geometry risks and invalid topology; it does not price materials |
| `loganr0217/LightScreenArt` | Commercial-era SVG→STL, pane packing, storefront, and production scripts | ScoreLint is a small offline audit CLI with no store, generator, printer, or nesting pipeline |
| Freecut / CutStock / `opcut` | Optimizes rectangular stock and guillotine cut sequences | ScoreLint does not arrange stock; it evaluates the geometry of individual stained-glass pieces |
| `sparrow` / Kenzap Nesting | General irregular 2D nesting for CNC workflows | ScoreLint targets hand-cut review signals, deterministic evidence, and pattern-library CI |
| Diafane / VArtGlass | Full hosted stained-glass editors and material calculators | ScoreLint is editor-independent, offline, source-control friendly, and does not retain designs |

Representative sources:

- https://github.com/christophernoessel/foil-and-solder-calculator
- https://github.com/loganr0217/LightScreenArt
- https://github.com/geri1701/freecut
- https://github.com/orohde/CutStock
- https://github.com/bozokopic/opcut
- https://github.com/JeroenGar/sparrow
- https://diafane.com/en/
- https://vartglass.com/

GitHub repository searches for `glasscutlint`, `glasscut-lint`, `scorelint`,
`stained glass SVG preflight`, `glass cut preflight`, and `stained glass cut sequence`
returned no directly matching public repository at selection time. Search absence is
not proof of global novelty, so the claim is deliberately narrower: no representative
open-source project inspected combined offline SVG parsing, explainable piece-level
cut-risk indicators, CI exit codes, and four deterministic evidence formats.

## Why It May Earn Attention

- The pain is visible and emotionally charged, not invented from a keyword list.
- The product stance respects the craft: review, do not generate; explain, do not
  pronounce; stay local, do not upload.
- SVG fixtures and annotated reports make the repository understandable in seconds.
- A stable JSON schema and exit codes make it useful beyond a one-off website.

Stars and page views cannot be guaranteed. The release optimizes for a clear problem,
distinct scope, low-friction install, visual evidence, and contribution-ready tests.
