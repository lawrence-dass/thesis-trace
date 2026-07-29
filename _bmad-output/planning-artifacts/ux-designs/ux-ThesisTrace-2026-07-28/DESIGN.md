---
name: ThesisTrace
status: final
description: Institutional equity-research register (Morningstar/YCharts/stockanalysis.com analog) — sober, citation-forward, data-dense; explicitly not a trading-terminal or gamified consumer-fintech register.
updated: 2026-07-29
colors:
  # Light mode (existing, formalized as named tokens — carried forward from globals.css, kept as-is)
  canvas: '#f6f7fb'
  surface: '#ffffff'
  border: '#e2e5ec'
  border-strong: '#c7cbd6'
  ink: '#12141c'
  ink-muted: '#565c6d'
  ink-faint: '#8b91a1'
  brand-50: '#eef4ff'
  brand-100: '#dbe7fe'
  brand-500: '#2f6fed'
  brand-600: '#1f56d6'
  brand-700: '#1a45ad'
  signal-pass: '#0f8a5f'
  signal-pass-bg: '#e6f6ee'
  signal-pass-border: '#b9e5cd'
  signal-fail: '#c4392b'
  signal-fail-bg: '#fbeae8'
  signal-fail-border: '#f2c3bd'
  signal-caveat: '#a86b06'
  signal-caveat-bg: '#fdf3de'
  signal-caveat-border: '#f2debb'
  signal-pending: '#5c6270'
  signal-pending-bg: '#eef0f4'
  signal-pending-border: '#d8dbe3'
  signal-excluded: '#6941a8'
  signal-excluded-bg: '#f2ecfb'
  signal-excluded-border: '#ddccf0'
  # Dark mode (new — [ASSUMPTION] core hues only; see Colors section for how badge bg/border derive from these)
  canvas-dark: '#0d1117'
  surface-dark: '#151a23'
  surface-raised-dark: '#1c222d'
  border-dark: '#2a3140'
  ink-dark: '#e8eaf0'
  ink-muted-dark: '#9ba3b4'
  ink-faint-dark: '#6b7280'
  brand-dark: '#5b8dff'
  signal-pass-dark: '#3ddc97'
  signal-fail-dark: '#ff6b5e'
  signal-caveat-dark: '#e8a83c'
  signal-pending-dark: '#8992a3'
  signal-excluded-dark: '#b48ee0'
typography:
  families:
    sans: { fontFamily: "'Inter', system-ui, sans-serif" }
    mono: { fontFamily: "'SFMono-Regular', ui-monospace, Menlo, Consolas, monospace" }
  display: { fontFamily: '{typography.families.sans.fontFamily}', fontSize: '2.5rem', fontWeight: 700, lineHeight: '1.15', letterSpacing: '-0.01em' }
  headline: { fontFamily: '{typography.families.sans.fontFamily}', fontSize: '1.75rem', fontWeight: 600, lineHeight: '1.25' }
  title: { fontFamily: '{typography.families.sans.fontFamily}', fontSize: '1.25rem', fontWeight: 600, lineHeight: '1.3' }
  body: { fontFamily: '{typography.families.sans.fontFamily}', fontSize: '1rem', fontWeight: 400, lineHeight: '1.5' }
  label: { fontFamily: '{typography.families.sans.fontFamily}', fontSize: '0.875rem', fontWeight: 500, lineHeight: '1.4', letterSpacing: '0.01em' }
  caption: { fontFamily: '{typography.families.sans.fontFamily}', fontSize: '0.75rem', fontWeight: 400, lineHeight: '1.4' }
  data: { fontFamily: '{typography.families.mono.fontFamily}', fontSize: '0.9375rem', fontWeight: 500, lineHeight: '1.4' }
components:
  gauge:
    track-height: '10px'
    track-radius: '{rounded.full}'
    track-color: '{colors.border}'
    tick-color: '{colors.border-strong}'
    marker-size: '14px'
    marker-border: '2px solid {colors.surface}'
    fill-pass: '{colors.signal-pass}'
    fill-fail: '{colors.signal-fail}'
    fill-caveat: '{colors.signal-caveat}'
  badge:
    radius: '{rounded.full}'
    padding: '{spacing.2} {spacing.3}'
    font: '{typography.label}'
    icon-gap: '{spacing.1}'
  citation-chip:
    radius: '{rounded.sm}'
    border: '1px solid {colors.border}'
    background: transparent
    font: '{typography.caption}'
    font-family: '{typography.families.mono.fontFamily}'
    hover-border: '{colors.border-strong}'
  sparkline:
    height: '32px'
    stroke-width: '1.5px'
    stroke-color: '{colors.ink-muted}'
    point-color-current: '{colors.brand-500}'
    library: Recharts
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

Institutional equity-research register — the closest analogs from the competitive pass are **Morningstar** (achromatic, disciplined star rating; single restrained accent — "Morningstar Red"; codified design system rather than ad hoc styling) and **stockanalysis.com** (chrome-free, dense spreadsheet-style tables, no upsells, no gamification, speed and clarity over decoration), with **YCharts**' advisor-facing "tear sheet" polish as a close third. This is the register `EXPERIENCE.md`'s Foundation already locked (Bloomberg Research / FactSet / Morningstar Direct, not a trading-platform or consumer-fintech register) — the research confirms it and gives it concrete texture.

Explicitly rejected registers, by name, from the same research:
- **Simply Wall St / TipRanks** — a single colorful "hero visualization" (the Snowflake, the Smart Score gauge) as the product's signature graphic, broad green/red applied to overall "quality" rather than just price deltas, card/infographic layout over raw tables, "less intimidating" onboarding copy. ThesisTrace's tri-state signal palette already exists and must stay disciplined/local to each signal — never expand into a single blended hero score (this is also locked at AD-12, independent of the design research).
- **Bloomberg Terminal / Koyfin** — the amber-on-black CRT aesthetic and the `TICKER <FUNCTION> <GO>` command-key culture are trading-desk signifiers ThesisTrace should not adopt literally; Daniel is doing research, not executing trades, and `EXPERIENCE.md`'s Interaction Primitives already reject a keyboard-power-user-first model for this reason. The one thing worth keeping from this pair, decoupled from its trading connotation: a command bar / keyboard shortcut *reads* as a serious tool, and ThesisTrace's minimal `/`-search-to-ticker pattern already gestures at this without the terminal cosplay.

Overall posture: content-forward, low-chrome, data as the primary visual material — never illustration, never a mascot, never a single "score of scores." Every visual decision below serves legibility of a specific cited number over decorative polish.

## Colors

The existing five-way tri-state signal palette (`{colors.signal-pass}` / `-fail` / `-caveat` / `-pending` / `-excluded`, each with its own `-bg`/`-border` pair) and the single-hue brand blue (`{colors.brand-500}`) are kept exactly as-is — this is the "single disciplined accent" pattern the Morningstar research praises (one committed brand color, not a rotating rainbow), and the existing icon+color pairing on every badge already meets the discipline the audit found lacking elsewhere. No companion accent is added: a second accent hue is exactly the kind of decorative addition the "institutional" cluster in the research avoided and the "consumer-fintech" cluster leaned on.

New: a dark-mode token set (`{colors.canvas-dark}`, `{colors.surface-dark}`, `{colors.surface-raised-dark}`, `{colors.border-dark}`, the `-dark` ink triad, `{colors.brand-dark}`, and one `-dark` foreground tone per signal). `[ASSUMPTION]` Justified by the research: two of the three closest comparables in this category (Koyfin, Simply Wall St) ship dark mode by default or as a first-class toggle, and long analyst sessions are a plausible real use case here even though Daniel isn't a trader. Dark-mode elevation follows the "surface lightness steps" convention noted in the Elevation & Depth section (a raised panel is a lighter gray, not a darker shadow), not Bloomberg's true-black CRT look — `{colors.canvas-dark}` is a dark charcoal-navy (`#0d1117`), not pure black, matching the sober-not-terminal posture. Dark-mode badge backgrounds/borders are not separately swatched here: derive them at implementation time from the `-dark` foreground hue via a reduced-opacity mix (e.g. `color-mix(in srgb, {colors.signal-pass-dark} 16%, {colors.surface-dark})`) rather than hand-picked hex pairs, and run a contrast audit against `{colors.surface-dark}`/`{colors.surface-raised-dark}` before shipping — this is implementation-time verification, not a design decision to guess at here.

The neutral/border scale is otherwise kept as-is; the audit found no complaint about the existing canvas/surface/ink relationship, only about the container it's poured into (see Layout & Spacing).

## Typography

Inter stays as the sole sans face (`{typography.families.sans}`) — no companion display/serif typeface is added. This is a deliberate call against Bloomberg/Koyfin's monospace-terminal signature and against inventing a "brand moment" typeface the research gives no institutional-cluster precedent for (Morningstar, YCharts, and stockanalysis.com all read as clean modern sans-driven products, not display-typeface-branded ones). The existing system-monospace stack (`{typography.families.mono}`) is kept and its role is *widened*, not replaced: today it's only used for score values via `tabular-nums`; per stockanalysis.com's dense spreadsheet-style financial-statement tables (the strongest "data-forward" signal in the research), every tabular numeric context — comparison-table cells, methodology formula inputs, provenance fiscal-year/accession text — should use `{typography.data}`, not just headline scores.

Named type scale (replacing the current ad hoc Tailwind-utility-per-element approach): `{typography.display}` (2.5rem/700 — landing wordmark moment only, used once), `{typography.headline}` (1.75rem/600 — page-level titles: ticker + company name), `{typography.title}` (1.25rem/600 — section/card headers: "Quality & Health", "Verdict"), `{typography.body}` (1rem/400 — default prose and labels), `{typography.label}` (0.875rem/500 — form labels, table column headers, badge text), `{typography.caption}` (0.75rem/400 — provenance metadata, helper text), `{typography.data}` (0.9375rem/500, mono — every numeric table cell and score value, always `tabular-nums`).

## Layout & Spacing

Single-column layout today (`max-w-5xl`, ~1024px, centered) across every page — reads as a marketing site rather than a data workbench. `[ASSUMPTION]` For a genuinely data-dense "enterprise" register, the content width should grow substantially on large viewports (the Verdict grid and comparison table are both currently width-starved at 1024px — the comparison table already needs horizontal scroll at only 4 columns). Recommend widening the max content width on `xl`+ viewports (e.g. `max-w-7xl`/1280px or wider, matching the research's findings on comparable products' grid widths) while keeping a comfortable single-column reading measure for prose-heavy areas (methodology descriptions, explanation text) — i.e. width should vary by content type, not be one fixed container for the whole app.

Spacing scale: see frontmatter `{spacing}` — a straightforward 4px-base scale with named aliases for the four places spacing decisions repeat across pages (`{spacing.card-padding}`, `{spacing.section-gap}`, `{spacing.page-margin-desktop}`, `{spacing.page-margin-mobile}`). This formalizes values already close to what's in use (`p-5` ≈ `{spacing.5}`, `space-y-10` ≈ `{spacing.10}`) rather than changing the rhythm — the existing whitespace rhythm itself isn't the problem, the fixed narrow container is.

Grid: Verdict cards and Company-Universe cards both currently break at `sm`/`lg` only (2-col / 4-col). Retained in `EXPERIENCE.md`'s Responsive & Platform table; `[ASSUMPTION]` add an `xl` step once the page width grows, so 4 Verdict cards don't have to compress as tightly as they would on a still-1024px-capped row.

## Elevation & Depth

Existing two-tier shadow system (`--shadow-card`, `--shadow-card-hover`) is well-judged for a light, single-elevation-layer product — a soft ambient shadow plus a slightly stronger one on hover, no harsh drop-shadows. Keep as the light-mode baseline regardless of what the color research recommends; extend rather than replace:

- `[ASSUMPTION]` Add one step below the existing pair — a barely-there `shadow-card-flat` (border-only, no shadow) for dense list rows (e.g. inside an expanded sub-factor's signal list) where every row currently has no elevation cue at all and a full card-shadow per row would be too heavy at that density.
- Dark mode is adopted (see Colors) — its elevation shifts from "shadow" to "surface lightness steps": `{colors.surface-raised-dark}` is a lighter gray than `{colors.surface-dark}`, not a darker shadow against black. This is the conventional dark-mode elevation pattern the research confirms (see Colors' `[ASSUMPTION]` note on dark mode generally).

## Shapes

Existing radius scale (`sm`/`md`/`lg`/`full` in frontmatter, mapped from the current `--radius-control`/`--radius-card`/`--radius-pill`) reads consistent already — pill badges, moderately-rounded cards and controls. No complaint surfaced in the audit about corner treatment; keep as-is. The one gap: no `sm` step existed before this draft (badges/cards had radius, but a tighter chip-level radius for dense elements like provenance citation chips didn't) — added at `0.4rem` to sit below `{rounded.md}`.

## Components

Per-component visual specs; behavioral rules live in `EXPERIENCE.md.Component Patterns`.

**Gauge** (`{components.gauge}`) — the audit's single biggest concrete redesign target: today a bare 6px linear band with a dot marker, no zone boundaries drawn. Redesign: a `{components.gauge.track-height}` (10px) horizontal band on `{components.gauge.track-color}`, with tick marks (`{components.gauge.tick-color}`) at each band-boundary threshold so the classification zones are visible as *shape*, not just inferred from marker position — a colorblind reader can read "which zone" from the tick divisions and marker position alone, per the Accessibility Floor. The marker itself is a `{components.gauge.marker-size}` circle with a `{colors.surface}` ring, filled with the zone's signal color (`fill-pass`/`fill-fail`/`fill-caveat`). Deliberately *not* a radial/circular dial or an arc gauge — the research flagged the radial dial (Simply Wall St's Snowflake, TipRanks' Smart Score circle) as the consumer-fintech "hero visualization" pattern to avoid; a horizontal band with tick-marked zones reads as a measurement instrument, not a mascot. Always paired with the band-label badge per the existing Do's-and-Don'ts rule (never hue alone).

**Badge** (`{components.badge}`) — existing signal-chip pattern, kept: pill shape (`{rounded.full}`), icon + label + color always paired, sized to `{typography.label}`. No visual change; already meets the discipline the research's institutional cluster (Morningstar's achromatic-but-clear star rating) exemplifies.

**Citation chip** (`{components.citation-chip}`) — new, replacing today's plain small gray provenance text. A low-emphasis outlined chip (`{rounded.sm}`, `1px solid {colors.border}`, transparent fill — intentionally *not* filled, so it reads as a reference/footnote rather than another colored badge competing with the signal palette), set in `{typography.caption}` with the fiscal-year/accession fragment in `{typography.data}` (mono, so accession numbers read as data, not prose). Renders as an actual `<a>` to the source SEC EDGAR filing (constructible client-side from CIK + accession_number). Hover state darkens the border only (`{components.citation-chip.hover-border}`) — no background fill on hover, keeping it visually quiet until interacted with. This is the product's core differentiator (PRD UJ-1/UJ-2) and the chip form makes it feel like real citation apparatus, not decoration.

**Sparkline / trend** (`{components.sparkline}`) — new, for the audit's flagged historical-trend opportunity (Piotroski/Altman across fiscal years). A thin (`{components.sparkline.stroke-width}`, 1.5px) line at `{components.sparkline.height}` (32px) in `{colors.ink-muted}`, with the current-fiscal-year point highlighted in `{colors.brand-500}` — restrained, table-row-height scale (stockanalysis.com/YCharts register: a data annotation, not a standalone chart moment). Built with Recharts per D7/AD-locked charting-library choice, never a custom SVG hand-roll. **Depends on a backend change** — the read API currently returns only the current run's fiscal year (`EXPERIENCE.md`'s memlog note) — so this component is spec'd now but not buildable until that endpoint extension ships; treat as Phase-next, not part of this redesign's first cut.

**Card** (existing, unchanged) — the existing `{rounded.lg}` / `{shadow.card}` treatment carries forward; the audit's complaint was never about the card itself, only the single narrow column it's constrained to (see Layout & Spacing) and the flat, un-elevated dense-list-row case (see Elevation & Depth's new `shadow-card-flat` step).

## Do's and Don'ts

Locked already (from the project's own standing decisions, not from research):

| Do | Don't |
|---|---|
| Keep the tri-state signal palette's icon+color pairing discipline everywhere, including any new chart/gauge | Convey a classification by hue alone anywhere |
| Show every score with its band/applicability state, even `excluded_out_of_scope`/`computed_with_caveat` (AD-20) | Show a bare number without its classification context |
| Use a real charting library (Recharts/visx are explicitly named in D7) for genuinely custom visualizations over ThesisTrace's own computed data | Use TradingView or any off-the-shelf ticker/candlestick widget suite |
| Render every value with resolvable provenance, ideally as an actual link to the source filing (AD-19) | Display a value with no resolvable provenance as if it were fact |
| Keep Verdict as a per-model juxtaposition | Blend models into a single composite "buy/sell" score for visual simplicity |
| Draw gauges as a tick-marked horizontal band (a measurement instrument) | Draw a radial/circular "hero dial" for any score (Simply Wall St Snowflake / TipRanks Smart Score pattern — rejected register) |
