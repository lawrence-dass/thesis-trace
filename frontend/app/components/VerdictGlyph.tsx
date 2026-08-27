// Verdict constellation — the four-model hero glyph (Story 10.2, D12).
//
// Four INDEPENDENT spokes, one per model, never connected into a polygon and
// never summarized into one number or shape (D12 guard 1 — the locked
// Verdict rule, "never a blended/weighted single score," applied to pixels).
// Each spoke's position is that model's own aggregate value normalized
// against ITS OWN domain (Gauge's `domainPct` — the same function the
// existing per-model gauge already uses, so this glyph can never disagree
// with the detail cards below it about where a value sits).
//
// insufficient_data / excluded_out_of_scope render as a short DASHED spoke at
// a fixed nominal length, never zero-length — a real absence must not read
// as "measured and low" (AD-16). computed_with_caveat keeps its REAL
// position and REAL band tone (matching what the Gauge on the detail card
// already shows for the same model) — only the label text says "Caveat",
// mirroring the existing Verdict grid's own choice, not a third convention.
//
// Custom SVG, no charting library (D7) — and deliberately visually distinct
// from Simply Wall St's design-patented, filled-polygon "Snowflake."

import { applicabilityLabel, applicabilityVariant, bandTone, type BadgeVariant } from "./ui/Badge";
import { TONE_SOLID, domainPct } from "./ui/Gauge";

export type VerdictItem = {
  model: string;
  category: string;
  fiscal_year: number;
  aggregate_value: number | null;
  band_label: string | null;
  applicability: string;
  missing_signals: string[];
};

export type AxisState = {
  model: string;
  label: string;
  tone: BadgeVariant;
  pct: number; // 0-100, spoke length as % of the max radius
  dashed: boolean; // true when `pct` is a fixed placeholder, not a real position
};

// Deliberately short but never zero (AD-16) and always dashed/pending- or
// excluded-toned, so it cannot be mistaken for a real, low value.
const NOMINAL_PCT = 22;

export function axisState(v: VerdictItem): AxisState {
  if (v.applicability === "excluded_out_of_scope") {
    return { model: v.model, label: applicabilityLabel(v.applicability), tone: applicabilityVariant(v.applicability), pct: NOMINAL_PCT, dashed: true };
  }
  if (v.aggregate_value === null) {
    return { model: v.model, label: "Insufficient data", tone: "pending", pct: NOMINAL_PCT, dashed: true };
  }
  const pct = domainPct(v.model, v.aggregate_value);
  if (v.applicability === "computed_with_caveat") {
    // Real position, real tone (from the actual band) — only the label
    // differs, matching the existing Verdict grid card's own choice to show
    // "Caveat" as the primary badge while the gauge beneath it still marks
    // the real classification.
    return { model: v.model, label: applicabilityLabel(v.applicability), tone: bandTone(v.band_label), pct, dashed: false };
  }
  if (v.band_label) {
    return { model: v.model, label: v.band_label, tone: bandTone(v.band_label), pct, dashed: false };
  }
  return { model: v.model, label: String(v.aggregate_value), tone: "neutral", pct, dashed: false };
}

const MODEL_SHORT_LABEL: Record<string, string> = {
  piotroski: "Piotroski",
  altman: "Altman",
  beneish: "Beneish",
  sloan: "Sloan",
};

// Clockwise from 12 o'clock, matching MODELS' existing order elsewhere on
// the page (top, right, bottom, left) — not required by the spec, but a
// deterministic, memorable layout beats an arbitrary one.
const AXIS_ORDER = ["piotroski", "altman", "beneish", "sloan"];

// Where each model's axis navigates — the two sections Story 10.1 already
// gives these models (quality_health -> Financial Health, integrity ->
// Integrity & Evidence), never a per-model anchor that doesn't exist.
const SECTION_FOR_MODEL: Record<string, string> = {
  piotroski: "#financial-health",
  altman: "#financial-health",
  beneish: "#integrity-evidence",
  sloan: "#integrity-evidence",
};

// Sized so a two-line label (model name + state) has real room outside
// MAX_RADIUS in every direction — the first pass at these numbers left only
// ~6px of edge margin and clipped every label against the SVG's own default
// `overflow: hidden` viewBox boundary, caught rendering in a real browser
// (top/bottom labels sliced to their bottom half; left/right labels sliced
// to their last 1-2 characters, since text-anchor="end"/"start" grows AWAY
// from the axis and needs headroom the old LABEL_RADIUS never budgeted).
const SIZE = 260;
const CENTER = SIZE / 2;
const MAX_RADIUS = 82;
const LABEL_RADIUS = MAX_RADIUS + 22;

function point(axisIndex: number, radius: number): { x: number; y: number } {
  const angle = -Math.PI / 2 + axisIndex * (Math.PI / 2);
  return { x: CENTER + radius * Math.cos(angle), y: CENTER + radius * Math.sin(angle) };
}

function labelAnchor(axisIndex: number): "middle" | "start" | "end" {
  if (axisIndex === 1) return "start"; // right
  if (axisIndex === 3) return "end"; // left
  return "middle"; // top, bottom
}

export function VerdictGlyph({ verdict }: { verdict: VerdictItem[] }) {
  const byModel = new Map(verdict.map((v) => [v.model, v]));
  const axes = AXIS_ORDER.map((model, i) => {
    const v = byModel.get(model);
    const state = v ? axisState(v) : { model, label: "Not covered", tone: "pending" as BadgeVariant, pct: NOMINAL_PCT, dashed: true };
    return { index: i, model, state };
  }).filter((a) => byModel.has(a.model));

  if (axes.length === 0) return null;

  return (
    <div className="flex justify-center py-2">
      <svg
        viewBox={`0 0 ${SIZE} ${SIZE}`}
        role="img"
        aria-label="Verdict constellation: each model's classification on its own independent axis, never combined into one score"
        // Safety net alongside the sized-for-real-content margins above: a
        // label a browser's own font metrics render wider than expected
        // (rather than being silently sliced by the viewBox's default
        // overflow:hidden) is far more visible and fixable than clipped.
        overflow="visible"
        className="aspect-square w-full max-w-[280px]"
      >
        {axes.map(({ index, model, state }) => {
          const full = point(index, MAX_RADIUS);
          const tip = point(index, (state.pct / 100) * MAX_RADIUS);
          const labelPt = point(index, LABEL_RADIUS);
          const anchor = labelAnchor(index);
          const color = TONE_SOLID[state.tone];

          return (
            // A hover tooltip via the plain `title` ATTRIBUTE, not an SVG
            // <title> CHILD ELEMENT — that child form caused a genuine
            // hydration mismatch, caught live: React's server HTML
            // serializer and the browser's real SVG-namespace DOM parsing
            // disagreed on it (`<title>` doubles as HTML page-metadata,
            // which the SSR string-render treats specially in a way the
            // client's real DOM does not). An attribute is a plain string
            // prop with no such ambiguity, and the anchor's accessible name
            // still comes correctly from its own visible text content
            // either way.
            <a
              key={model}
              href={SECTION_FOR_MODEL[model]}
              title={`${MODEL_SHORT_LABEL[model] ?? model}: ${state.label}`}
              className="cursor-pointer"
            >
              {/* Invisible, wide hit-area — the visible track below is only
                  2px, far too thin a target to reliably click; this widens
                  the whole spoke's clickable region without changing what's
                  actually painted. */}
              <line
                x1={CENTER}
                y1={CENTER}
                x2={full.x}
                y2={full.y}
                stroke="transparent"
                strokeWidth={20}
                // A `transparent` stroke is NOT hit-tested under the SVG
                // default (visiblePainted) — Chrome silently ignored clicks
                // on this line without this, caught by actually clicking it
                // rather than trusting the geometry looked right.
                pointerEvents="stroke"
              />
              {/* Full-range guide — this axis's own track, never implying a
                  cross-model-comparable scale (each is independently
                  normalized to its own domain). */}
              <line x1={CENTER} y1={CENTER} x2={full.x} y2={full.y} stroke="var(--color-border)" strokeWidth={2} />
              <line
                x1={CENTER}
                y1={CENTER}
                x2={tip.x}
                y2={tip.y}
                stroke={color}
                strokeWidth={4}
                strokeLinecap="round"
                strokeDasharray={state.dashed ? "3 4" : undefined}
              />
              <circle cx={tip.x} cy={tip.y} r={5} fill={color} stroke="var(--color-surface)" strokeWidth={2} />
              <text
                x={labelPt.x}
                y={labelPt.y - 4}
                textAnchor={anchor}
                className="text-[11px] font-semibold"
                fill="var(--color-ink)"
              >
                {MODEL_SHORT_LABEL[model] ?? model}
              </text>
              <text x={labelPt.x} y={labelPt.y + 10} textAnchor={anchor} className="text-[10px]" fill={color}>
                {state.label}
              </text>
            </a>
          );
        })}
        {/* Deliberately nothing at the center — no aggregate number, shape,
            or grade summarizing multiple models anywhere on this glyph
            (D12 guard 1). */}
        <circle cx={CENTER} cy={CENTER} r={2} fill="var(--color-border-strong)" />
      </svg>
    </div>
  );
}
