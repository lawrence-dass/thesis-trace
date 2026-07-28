---
name: ThesisTrace
status: draft
description: PENDING — brand/color/typography direction awaits the competitive design-research pass (Bloomberg Terminal, Koyfin, Simply Wall St, TipRanks, Finchat.io, Morningstar, YCharts, stockanalysis.com), in flight.
rounded:
  # Extends the existing globals.css radius tokens (kept as-is — no complaint
  # in the audit about card/control roundedness reading wrong). Adds the
  # missing finer step so small chips/inputs aren't stuck using the card radius.
  sm: 0.4rem
  md: 0.6rem      # was --radius-control
  lg: 1rem         # was --radius-card
  full: 999px      # was --radius-pill
spacing:
  # [ASSUMPTION] No spacing scale exists today (globals.css defines colors/
  # radii/shadows only; layout spacing is ad-hoc Tailwind utility values
  # scattered across pages — p-5, gap-4, space-y-10, max-w-5xl). Naming an
  # explicit 4px-base scale here is a consistency fix independent of the
  # pending color/typography research, so it's drafted now rather than held.
  '1': 4px
  '2': 8px
  '3': 12px
  '4': 16px
  '5': 20px
  '6': 24px
  '8': 32px
  '10': 40px
  '12': 48px
  '16': 64px
  '20': 80px
  card-padding: '{spacing.5}'
  section-gap: '{spacing.10}'
  page-margin-desktop: '{spacing.6}'
  page-margin-mobile: '{spacing.4}'
---

## Brand & Style

`PENDING RESEARCH SYNTHESIS.` Not yet drafted — this is the section the competitive/design research pass most directly informs (what "enterprise-grade, institutional-research-tool" actually looks like versus the current "clean SaaS MVP" register). Filling this in before the research lands would mean guessing at the one thing explicitly asked for. See `EXPERIENCE.md`'s Foundation section for the audience calibration already locked: institutional equity-research register (Bloomberg Research / FactSet / Morningstar Direct), not a trading-platform or consumer-fintech register — sober, credible, citation-forward, never gamified.

## Colors

`PENDING RESEARCH SYNTHESIS.` The existing palette (`--color-canvas`, `--color-surface`, `--color-ink*`, `--color-brand-*`, and the five-way `--color-signal-*` tri-state set) is a real strength worth preserving in spirit — see `EXPERIENCE.md`'s Accessibility Floor, which depends on the signal palette's existing icon+color pairing discipline. What's undecided: whether to extend to a dark-mode token set (several comparables in this category default to dark for long analyst sessions — to be confirmed against the research), whether the neutral scale needs more steps for the data-density this redesign is aiming for, and whether the single brand blue needs a companion accent. Not drafting hex values until the research lands rather than picking colors and rationalizing them after the fact.

## Typography

`PENDING RESEARCH SYNTHESIS.` Current state: Inter for everything, a system monospace stack for numbers/codes (`tabular-nums` already used correctly for score values), no named type scale — sizes are Tailwind's raw utility scale (`text-sm`, `text-2xl`, `text-3xl`, etc.) applied ad hoc per element rather than through named semantic roles (`display`, `headline`, `body`, `label`, `caption` per the DESIGN.md convention). Whether Inter stays, gets a companion display face, or the whole ramp gets restructured awaits the research on how comparable serious data products handle type.

## Layout & Spacing

Single-column layout today (`max-w-5xl`, ~1024px, centered) across every page — reads as a marketing site rather than a data workbench. `[ASSUMPTION]` For a genuinely data-dense "enterprise" register, the content width should grow substantially on large viewports (the Verdict grid and comparison table are both currently width-starved at 1024px — the comparison table already needs horizontal scroll at only 4 columns). Recommend widening the max content width on `xl`+ viewports (e.g. `max-w-7xl`/1280px or wider, matching the research's findings on comparable products' grid widths) while keeping a comfortable single-column reading measure for prose-heavy areas (methodology descriptions, explanation text) — i.e. width should vary by content type, not be one fixed container for the whole app.

Spacing scale: see frontmatter `{spacing}` — a straightforward 4px-base scale with named aliases for the four places spacing decisions repeat across pages (`{spacing.card-padding}`, `{spacing.section-gap}`, `{spacing.page-margin-desktop}`, `{spacing.page-margin-mobile}`). This formalizes values already close to what's in use (`p-5` ≈ `{spacing.5}`, `space-y-10` ≈ `{spacing.10}`) rather than changing the rhythm — the existing whitespace rhythm itself isn't the problem, the fixed narrow container is.

Grid: Verdict cards and Company-Universe cards both currently break at `sm`/`lg` only (2-col / 4-col). Retained in `EXPERIENCE.md`'s Responsive & Platform table; `[ASSUMPTION]` add an `xl` step once the page width grows, so 4 Verdict cards don't have to compress as tightly as they would on a still-1024px-capped row.

## Elevation & Depth

Existing two-tier shadow system (`--shadow-card`, `--shadow-card-hover`) is well-judged for a light, single-elevation-layer product — a soft ambient shadow plus a slightly stronger one on hover, no harsh drop-shadows. Keep as the light-mode baseline regardless of what the color research recommends; extend rather than replace:

- `[ASSUMPTION]` Add one step below the existing pair — a barely-there `shadow-card-flat` (border-only, no shadow) for dense list rows (e.g. inside an expanded sub-factor's signal list) where every row currently has no elevation cue at all and a full card-shadow per row would be too heavy at that density.
- If a dark mode is adopted (pending Colors), dark-mode elevation should shift from "shadow" to "surface lightness steps" (a raised panel is a lighter gray, not a darker shadow against black) — the conventional dark-mode elevation pattern, to confirm against the research rather than assume.

## Shapes

Existing radius scale (`sm`/`md`/`lg`/`full` in frontmatter, mapped from the current `--radius-control`/`--radius-card`/`--radius-pill`) reads consistent already — pill badges, moderately-rounded cards and controls. No complaint surfaced in the audit about corner treatment; keep as-is. The one gap: no `sm` step existed before this draft (badges/cards had radius, but a tighter chip-level radius for dense elements like provenance citation chips didn't) — added at `0.4rem` to sit below `{rounded.md}`.

## Components

`PENDING RESEARCH SYNTHESIS + behavioral cross-check.` Per-component visual specs (Badge, Button, Card, Gauge and its planned successors, the new provenance-citation link, any trend/sparkline component) will be specified here once Colors/Typography land, cross-referenced against `EXPERIENCE.md.Component Patterns` for the behavioral half of each one. The current `Gauge` component (a 6px linear band with a dot marker) is the single biggest concrete redesign target flagged by the audit — see the memlog for the full reasoning; its replacement design depends on the research's findings on how comparable products visualize "a number and its classification zone."

## Do's and Don'ts

Locked already (from the project's own standing decisions, not from research):

| Do | Don't |
|---|---|
| Keep the tri-state signal palette's icon+color pairing discipline everywhere, including any new chart/gauge | Convey a classification by hue alone anywhere |
| Show every score with its band/applicability state, even `excluded_out_of_scope`/`computed_with_caveat` (AD-20) | Show a bare number without its classification context |
| Use a real charting library (Recharts/visx are explicitly named in D7) for genuinely custom visualizations over ThesisTrace's own computed data | Use TradingView or any off-the-shelf ticker/candlestick widget suite |
| Render every value with resolvable provenance, ideally as an actual link to the source filing (AD-19) | Display a value with no resolvable provenance as if it were fact |
| Keep Verdict as a per-model juxtaposition | Blend models into a single composite "buy/sell" score for visual simplicity |
