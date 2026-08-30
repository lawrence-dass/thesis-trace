// Fundamentals summary and earnings waterfall (Story 10.4, D12). Canonical
// facts only — no ThesisTrace judgment, unlike RewardsRisks or the debt cards,
// so there is no `attribution` field to render (AD-8). "Other" (gross profit,
// or revenue when gross profit is not disclosed, down to net income) is plain
// arithmetic between two filed figures, cited as derived rather than filed
// (AD-19) — same shape as reverse DCF's free_cash_flow operand.

import { Card } from "./ui/Card";
import { CitationChip, DERIVATION_LABEL, edgarFilingUrl } from "./ui/CitationChip";
import { compactAmount } from "./ui/format";

export type Provenance = {
  accession_number: string;
  canonical_concept: string;
  fiscal_year: number;
  derivation?: string | null;
};

export type FundamentalsFigure = {
  value: number | null;
  provenance: Provenance | null;
  reason: string | null;
  as_of: string | null;
  source: string | null;
};

export type WaterfallStage = "revenue" | "cost_of_revenue" | "gross_profit" | "other" | "earnings";

export type WaterfallBar = {
  stage: WaterfallStage;
  bar_type: "total" | "decrease";
  figure: FundamentalsFigure;
};

export type Fundamentals = {
  fiscal_year: number;
  revenue: FundamentalsFigure;
  earnings: FundamentalsFigure;
  market_value: FundamentalsFigure;
  waterfall: WaterfallBar[];
};

const STAGE_LABEL: Record<WaterfallStage, string> = {
  revenue: "Revenue",
  cost_of_revenue: "Cost of revenue",
  gross_profit: "Gross profit",
  other: "Other",
  earnings: "Earnings",
};

export type WaterfallSegment = {
  stage: WaterfallStage;
  label: string;
  barType: "total" | "decrease";
  present: boolean;
  top: number;
  bottom: number;
  value: number | null;
  reason: string | null;
  provenance: Provenance | null;
};

/** Turns the API's bar list into drawable [top, bottom] rectangles.
 *
 *  An ABSENT bar is skipped without moving the running total — the engine
 *  already computes "other" relative to whichever anchor actually resolved
 *  (gross profit when known, revenue when cost detail is not disclosed at
 *  all), so the sequence of PRESENT bars alone closes correctly on earnings
 *  with no reconciliation needed here. Never draws an absent bar as a
 *  zero-height rectangle (Story 10.4 AC) — it is omitted from `segments` and
 *  the caller renders its `reason` instead.
 */
export function waterfallSegments(bars: WaterfallBar[]): WaterfallSegment[] {
  let runningTotal = 0;
  const segments: WaterfallSegment[] = [];
  for (const bar of bars) {
    const value = bar.figure.value;
    if (value === null) {
      segments.push({
        stage: bar.stage,
        label: STAGE_LABEL[bar.stage],
        barType: bar.bar_type,
        present: false,
        top: runningTotal,
        bottom: runningTotal,
        value: null,
        reason: bar.figure.reason,
        provenance: null,
      });
      continue;
    }
    if (bar.bar_type === "total") {
      segments.push({
        stage: bar.stage,
        label: STAGE_LABEL[bar.stage],
        barType: "total",
        present: true,
        top: value,
        bottom: 0,
        value,
        reason: null,
        provenance: bar.figure.provenance,
      });
      runningTotal = value;
    } else {
      const next = runningTotal - value;
      segments.push({
        stage: bar.stage,
        label: STAGE_LABEL[bar.stage],
        barType: "decrease",
        present: true,
        top: runningTotal,
        bottom: next,
        value,
        reason: null,
        provenance: bar.figure.provenance,
      });
      runningTotal = next;
    }
  }
  return segments;
}

// Fixed-pixel-like viewBox (NOT a 0-100 percentage box). A percentage viewBox
// paired with `preserveAspectRatio="none"` independently stretches X and Y to
// fill the container, and this card's container is far wider than it is
// tall — that anisotropic stretch mangled every text glyph into an illegible
// smear (confirmed live 2026-08-27, CP and Suncor both). The fix is a viewBox
// shaped like the chart actually is, scaled UNIFORMLY: `width: 100%` with no
// CSS height lets the browser derive height from the viewBox's own aspect
// ratio, so text and bars scale together and stay legible at any card width.
const WIDTH = 700;
const BAR_AREA_HEIGHT = 140;
const TOP_PADDING = 26; // room for a value label above the tallest bar
const BOTTOM_PADDING = 26; // room for a stage label below the baseline
const BASELINE_Y = TOP_PADDING + BAR_AREA_HEIGHT;
const TOTAL_HEIGHT = BASELINE_Y + BOTTOM_PADDING;
const BAR_GAP = 20;

function WaterfallChart({ bars, cik }: { bars: WaterfallBar[]; cik?: string }) {
  const segments = waterfallSegments(bars);
  const present = segments.filter((s) => s.present);
  const maxValue = Math.max(1, ...present.flatMap((s) => [s.top, s.bottom]));
  const scale = (v: number) => (v / maxValue) * BAR_AREA_HEIGHT;

  const n = segments.length;
  const barWidth = (WIDTH - BAR_GAP * (n - 1)) / n;

  return (
    // NOT role="img": that tells assistive tech to flatten everything inside
    // into one non-interactive picture, which would make the per-bar
    // citation links below unreachable by keyboard or screen reader even
    // though they are real <a> elements in the DOM. aria-label alone still
    // gives the chart as a whole an accessible name.
    <svg
      viewBox={`0 0 ${WIDTH} ${TOTAL_HEIGHT}`}
      className="block w-full"
      aria-label="Revenue to earnings waterfall"
    >
      {segments.map((seg, i) => {
        const x = i * (barWidth + BAR_GAP);
        if (!seg.present) {
          // Absent bar: a dashed baseline marker, never a drawn rectangle —
          // the reason is surfaced as text beneath the chart, not in the SVG,
          // so it stays readable to a screen reader (AD-16).
          return (
            <g key={seg.stage}>
              <line
                x1={x}
                x2={x + barWidth}
                y1={BASELINE_Y}
                y2={BASELINE_Y}
                stroke="var(--color-border-strong)"
                strokeWidth={1.5}
                strokeDasharray="5,4"
              />
              <text
                x={x + barWidth / 2}
                y={BASELINE_Y + 20}
                textAnchor="middle"
                fontSize={16}
                fill="var(--color-ink-faint)"
                className="uppercase"
              >
                {seg.label}
              </text>
            </g>
          );
        }
        const yTop = BASELINE_Y - scale(Math.max(seg.top, seg.bottom));
        const height = Math.max(scale(Math.abs(seg.top - seg.bottom)), 2);
        const fill = seg.barType === "total" ? "var(--color-brand-500)" : "var(--color-ink-faint)";
        const content = (
          <g>
            <rect x={x} y={yTop} width={barWidth} height={height} rx={4} fill={fill} />
            <text
              x={x + barWidth / 2}
              y={yTop - 8}
              textAnchor="middle"
              fontSize={18}
              fill="var(--color-ink-muted)"
              className="font-mono tabular-nums"
            >
              {compactAmount(seg.value ?? 0)}
            </text>
            <text
              x={x + barWidth / 2}
              y={BASELINE_Y + 20}
              textAnchor="middle"
              fontSize={16}
              fill="var(--color-ink-faint)"
              className="uppercase"
            >
              {seg.label}
            </text>
          </g>
        );
        // Every present bar cites its own provenance (Story 10.4 AC) — a
        // derived bar (gross profit, other) says so rather than implying a
        // filed line item (AD-19). A `title` ATTRIBUTE, never an SVG <title>
        // child: a child causes a real hydration mismatch (Story 10.2).
        if (cik && seg.provenance) {
          const derivation = seg.provenance.derivation ?? null;
          const title = derivation
            ? `Derived, not filed: computed as ${DERIVATION_LABEL[derivation] ?? derivation}. Opens the source filing for that balance-sheet date (accession ${seg.provenance.accession_number}) — it contains the inputs, not this figure.`
            : `View source filing on SEC EDGAR (accession ${seg.provenance.accession_number})`;
          return (
            <a
              key={seg.stage}
              href={edgarFilingUrl(cik, seg.provenance.accession_number)}
              target="_blank"
              rel="noopener noreferrer"
              title={title}
            >
              {content}
            </a>
          );
        }
        return <g key={seg.stage}>{content}</g>;
      })}
    </svg>
  );
}

function StatTile({
  label,
  figure,
  cik,
}: {
  label: string;
  figure: FundamentalsFigure;
  cik?: string;
}) {
  return (
    <div className="space-y-1">
      <div className="text-caption font-semibold uppercase tracking-[var(--tracking-label)] text-[var(--color-ink-faint)]">
        {label}
      </div>
      {figure.value !== null ? (
        <>
          <div className="font-mono text-title font-semibold tabular-nums text-[var(--color-ink)]">
            {compactAmount(figure.value)}
          </div>
          {figure.provenance && cik ? (
            <CitationChip
              cik={cik}
              accessionNumber={figure.provenance.accession_number}
              canonicalConcept={figure.provenance.canonical_concept}
              fiscalYear={figure.provenance.fiscal_year}
              derivation={figure.provenance.derivation ?? null}
            />
          ) : figure.as_of ? (
            <p className="text-caption text-[var(--color-ink-faint)]">
              As of {figure.as_of}
              {figure.source ? ` · ${figure.source}` : ""}
            </p>
          ) : null}
        </>
      ) : (
        <p className="text-label text-[var(--color-ink-faint)]">{figure.reason ?? "Not available"}</p>
      )}
    </div>
  );
}

export function FundamentalsCard({ data, cik }: { data: Fundamentals | null | undefined; cik?: string }) {
  if (!data) return null;

  const absentStages = data.waterfall.filter((b) => b.figure.value === null);

  return (
    <Card className="space-y-4">
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="text-label font-semibold uppercase tracking-[var(--tracking-label)] text-[var(--color-ink)]">
          Fundamentals
        </h3>
        <span className="text-caption text-[var(--color-ink-faint)]">FY{data.fiscal_year}</span>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatTile label="Revenue" figure={data.revenue} cik={cik} />
        <StatTile label="Earnings" figure={data.earnings} cik={cik} />
        <StatTile label="Market value" figure={data.market_value} cik={cik} />
      </div>

      <div>
        <WaterfallChart bars={data.waterfall} cik={cik} />
        {absentStages.length > 0 ? (
          <p className="mt-1 text-caption leading-relaxed text-[var(--color-ink-faint)]">
            {absentStages.map((b) => b.figure.reason).filter(Boolean)[0]}
          </p>
        ) : null}
      </div>

      <p className="border-t border-[var(--color-border)] pt-2 text-caption leading-relaxed text-[var(--color-ink-faint)]">
        &quot;Other&quot; is gross profit minus earnings (or revenue minus earnings when cost of
        revenue is not disclosed) — operating expenses, interest and tax combined, computed by
        ThesisTrace from filed figures rather than filed itself.
      </p>
    </Card>
  );
}
