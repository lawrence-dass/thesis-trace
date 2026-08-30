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
  fiscalYear?: number;
};

// Deliberately short but never zero (AD-16) and always dashed/pending- or
// excluded-toned, so it cannot be mistaken for a real, low value.
const NOMINAL_PCT = 22;
const KNOWN_APPLICABILITY = new Set(["computed", "computed_with_caveat", "excluded_out_of_scope"]);

function absenceState(v: VerdictItem, label = "Insufficient data"): AxisState {
  return { model: v.model, label, tone: "pending", pct: NOMINAL_PCT, dashed: true, fiscalYear: v.fiscal_year };
}

export function axisState(v: VerdictItem): AxisState {
  if (v.applicability === "excluded_out_of_scope") {
    return {
      model: v.model,
      label: applicabilityLabel(v.applicability),
      tone: applicabilityVariant(v.applicability),
      pct: NOMINAL_PCT,
      dashed: true,
      fiscalYear: v.fiscal_year,
    };
  }
  if (v.aggregate_value === null || !Number.isFinite(v.aggregate_value)) {
    // No value to plot takes precedence over a caveat attached to the run.
    return absenceState(v);
  }
  if (!KNOWN_APPLICABILITY.has(v.applicability)) {
    // Never turn an enum value the UI does not understand into a measured
    // pass/fail-looking spoke.
    return absenceState(v, "Unavailable");
  }
  const pct = domainPct(v.model, v.aggregate_value);
  if (v.applicability === "computed_with_caveat") {
    // Real position, real tone (from the actual band) — only the label
    // differs, matching the existing Verdict grid card's own choice to show
    // "Caveat" as the primary badge while the gauge beneath it still marks
    // the real classification.
    return {
      model: v.model,
      label: applicabilityLabel(v.applicability),
      tone: bandTone(v.band_label),
      pct,
      dashed: false,
      fiscalYear: v.fiscal_year,
    };
  }
  if (v.band_label) {
    return { model: v.model, label: v.band_label, tone: bandTone(v.band_label), pct, dashed: false, fiscalYear: v.fiscal_year };
  }
  return { model: v.model, label: String(v.aggregate_value), tone: "neutral", pct, dashed: false, fiscalYear: v.fiscal_year };
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

// The label coordinates reserve a safe text box inside the viewBox. Side-axis
// statuses are wrapped because text-anchor="end"/"start" otherwise grows away
// from the axis and can clip long labels such as Beneish's "Manipulation risk
// flagged" on narrow screens. `overflow="visible"` remains a safety net for
// browser font metrics, not the primary layout mechanism.
const SIZE = 260;
const CENTER = SIZE / 2;
const MAX_RADIUS = 82;
const LABEL_LINE_HEIGHT = 14;
const SIDE_LABEL_MAX_CHARS = 14;

const LABEL_POSITION: Record<number, { x: number; y: number; anchor: "middle" | "start" | "end" }> = {
  0: { x: CENTER, y: 14, anchor: "middle" },
  1: { x: 178, y: 112, anchor: "start" },
  2: { x: CENTER, y: 218, anchor: "middle" },
  3: { x: 82, y: 112, anchor: "end" },
};

function point(axisIndex: number, radius: number): { x: number; y: number } {
  const angle = -Math.PI / 2 + axisIndex * (Math.PI / 2);
  return { x: CENTER + radius * Math.cos(angle), y: CENTER + radius * Math.sin(angle) };
}

function wrapLabel(label: string): string[] {
  const words = label.split(/\s+/).filter(Boolean);
  const lines: string[] = [];
  let line = "";
  for (const word of words) {
    const candidate = line ? `${line} ${word}` : word;
    if (line && candidate.length > SIDE_LABEL_MAX_CHARS) {
      lines.push(line);
      line = word;
    } else {
      line = candidate;
    }
  }
  if (line) lines.push(line);
  return lines.length > 0 ? lines : [label];
}

export function VerdictGlyph({ verdict }: { verdict: VerdictItem[] }) {
  const byModel = new Map(verdict.map((v) => [v.model, v]));
  const axes = AXIS_ORDER.map((model, i) => {
    const v = byModel.get(model);
    const state = v
      ? axisState(v)
      : { model, label: "Not covered", tone: "pending" as BadgeVariant, pct: NOMINAL_PCT, dashed: true };
    return { index: i, model, state };
  });

  if (verdict.length === 0) return null;

  return (
    <div className="flex justify-center py-2">
      <svg
        viewBox={`0 0 ${SIZE} ${SIZE}`}
        role="group"
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
          const labelPosition = LABEL_POSITION[index];
          const statusLines = index === 1 || index === 3 ? wrapLabel(state.label) : [state.label];
          const labelLines = [
            MODEL_SHORT_LABEL[model] ?? model,
            ...statusLines,
            ...(state.fiscalYear !== undefined ? [`FY ${state.fiscalYear}`] : []),
          ];
          const color = TONE_SOLID[state.tone];

          return (
            // A hover tooltip via the plain `title` ATTRIBUTE, not an SVG
            // <title> CHILD ELEMENT — that child form caused a genuine
            // hydration mismatch, caught live: React's server HTML
            // serializer and the browser's real SVG-namespace DOM parsing
            // disagreed on it (`<title>` doubles as HTML page-metadata,
            // which the SSR string-render treats specially in a way the
            // client's real DOM does not). An attribute is a plain string
            // prop with no such ambiguity, and the anchor receives an
            // explicit accessible name below.
            <a
              key={model}
              href={SECTION_FOR_MODEL[model]}
              title={`${MODEL_SHORT_LABEL[model] ?? model}: ${state.label}`}
              aria-label={`${MODEL_SHORT_LABEL[model] ?? model}: ${state.label}${state.fiscalYear !== undefined ? `, FY ${state.fiscalYear}` : ""}`}
              role="link"
              tabIndex={0}
              // `outline-2`/`outline-[color]`/`outline-offset-2` alone set
              // width/color/offset but never `outline-style` — it stayed
              // `none` (from the base `outline-none`) even while genuinely
              // focus-visible, so nothing painted. Caught by checking the
              // COMPUTED style after a real keyboard Tab, not by trusting
              // the class list read correctly. `focus-visible:outline`
              // supplies the missing solid style.
              className="cursor-pointer outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-brand-link)] focus-visible:outline-offset-2"
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
                x={labelPosition.x}
                y={labelPosition.y}
                textAnchor={labelPosition.anchor}
                className="text-[11px] font-semibold uppercase tracking-[var(--tracking-label)]"
                fill="var(--color-ink)"
              >
                {labelLines.map((line, lineIndex) => (
                  <tspan
                    key={lineIndex}
                    x={labelPosition.x}
                    dy={lineIndex === 0 ? 0 : LABEL_LINE_HEIGHT}
                    fill={
                      lineIndex === 0 || (state.fiscalYear !== undefined && lineIndex === labelLines.length - 1)
                        ? "var(--color-ink)"
                        : color
                    }
                    className={lineIndex === 0 ? "text-[11px] font-semibold" : "text-[10px] font-normal"}
                  >
                    {line}
                  </tspan>
                ))}
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
