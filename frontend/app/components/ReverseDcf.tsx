// What today's price implies about growth (Epic 6, Story 6.6).
//
// Presentation only — every figure here is computed by the backend solver and
// read verbatim (AD-8). Nothing on this card is derived in the browser except
// the pixel positions of the marks.
//
// Two rules govern the design, both inherited from the API contract:
//
//  1. THE RANGE IS THE ANSWER. Real bands are ~30 percentage points wide and two
//     of them cross zero, so the point figure is drawn INSIDE the band rather
//     than above it — a large solitary number would read as a precise estimate.
//  2. There is no fair value, price target, upside or midpoint anywhere, because
//     running the model backwards exists precisely to avoid producing one.

import { Badge } from "./ui/Badge";
import { Card } from "./ui/Card";
import { CitationChip } from "./ui/CitationChip";
import { compactAmount } from "./ui/format";

export type SensitivityCell = {
  discount_rate: number;
  terminal_growth: number;
  implied_growth: number | null;
  reason: string | null;
};

export type ReverseDcfOperand = {
  name: string;
  value: number;
  // Set only for a FILED figure. A computed one carries `derived_from` instead
  // and never wears a filed-line citation (AD-19).
  accession_number?: string | null;
  derived_from?: string[];
  derivation?: string | null;
  operation?: string | null;
  unit?: string | null;
  source?: string | null;
  period_end?: string | null;
  observed_on?: string | null;
  conversion_rate?: number | null;
  conversion_rate_date?: string | null;
  conversion_rate_source?: string | null;
};

export type ReverseDcf = {
  fiscal_year: number;
  implied_growth: number | null;
  insufficient_data: boolean;
  reason: string | null;
  range_low: number | null;
  range_high: number | null;
  sensitivity?: SensitivityCell[];
  resolved_cells: number;
  total_cells: number;
  discount_rate: number;
  terminal_growth: number;
  horizon_years: number;
  operands?: ReverseDcfOperand[];
  historical_revenue_cagr: number | null;
  historical_from_fiscal_year: number | null;
  historical_to_fiscal_year: number | null;
  caveats?: string[];
  attribution: string;
  spec_version: string;
};

/** Rates cross the wire as FRACTIONS (0.372), never as percentages. */
export function formatRate(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return `${(value * 100).toFixed(digits)}%`;
}

// Every operand the solver emits. Kept exhaustive on purpose: an unmapped name
// falls back to its raw snake_case, which renders lowercase beside mapped labels
// and makes one list look like two conventions.
//
// The last four are DERIVATION LEAVES. `_append_reverse_dcf_fact_operand` walks
// each derived fact's own operands, so a filer whose total debt or cash is a
// derivation exposes the parts too: CCJ emits near_term_debt/long_term_debt, and
// BCE emits all four (it tags Cash and CashEquivalents separately and never the
// combined concept). Neither filer was in the browser spot-check that this map's
// first version was written against — which is exactly how they got missed.
const OPERAND_LABEL: Record<string, string> = {
  free_cash_flow: "Free cash flow",
  cash_from_operations: "Cash from operations",
  capex: "Capital expenditure",
  market_cap: "Market capitalisation",
  market_price: "Market price",
  shares_outstanding: "Shares outstanding",
  total_debt: "Total debt",
  cash_and_equivalents: "Cash and equivalents",
  enterprise_value: "Enterprise value",
  near_term_debt: "Near-term debt",
  long_term_debt: "Long-term debt",
  cash: "Cash",
  cash_equivalents: "Cash equivalents",
};

function labelFor(name: string): string {
  return OPERAND_LABEL[name] ?? name.replace(/_/g, " ");
}

/** The same label mid-sentence. None of these are proper nouns, so lowering the
 *  first character is safe and keeps "computed from cash from operations and
 *  capital expenditure" reading as prose rather than as a list of headings. */
function inlineLabel(name: string): string {
  const label = labelFor(name);
  return label.charAt(0).toLowerCase() + label.slice(1);
}

/** "a", "a and b", "a, b, and c" — three operands joined with bare "and"s read as
 *  one run-on ("market cap and total debt and cash"), which obscures that
 *  enterprise value is a three-term expression.
 *
 *  The serial comma is load-bearing here rather than stylistic: one operand is
 *  itself named "cash and equivalents", so without it the last term reads
 *  "total debt and cash and equivalents" — three items or two, unknowable. */
function joinList(parts: string[]): string {
  if (parts.length <= 1) return parts[0] ?? "";
  if (parts.length === 2) return `${parts[0]} and ${parts[1]}`;
  return `${parts.slice(0, -1).join(", ")}, and ${parts[parts.length - 1]}`;
}

// Amounts use the SHARED helper rather than a local one. `compactAmount` rounds
// before its magnitude test so 999,999,999 reads "1.00B" and not "1000M"; a local
// re-implementation of the same idea drifted from it on that exact boundary, which
// is the divergence ui/format.ts was extracted to end. Two cards on this page show
// money — they must only ever differ when the numbers do.

export function ReverseDcfCard({ dcf, cik }: { dcf?: ReverseDcf | null; cik?: string }) {
  // `null` means the filer resolved NO fiscal year at all — there is no run to
  // describe, so there is nothing to be missing. This is not the AD-16 case:
  // a filer that ran and could not resolve comes back as an OBJECT carrying
  // `insufficient_data` and a reason, and is rendered in full below.
  if (!dcf) return null;

  return (
    <section className="space-y-3">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--color-ink-faint)]">
        What the price implies
      </h2>
      {/* AC: the assumptions must read as ThesisTrace's, distinctly from the four
          academic models above, so the page cannot be mistaken for a published
          model's output. Stated here in the section lead, again on the assumption
          chips, and once more in the API's own attribution line at the foot. */}
      <p className="text-sm text-[var(--color-ink-faint)]">
        Not a published model and not a valuation — ThesisTrace runs a discounted cash
        flow backwards to ask what growth today&apos;s price would require.
      </p>

      <Card className="space-y-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-semibold text-[var(--color-ink)]">Implied revenue growth</h3>
            <Badge variant="brand" icon={false}>
              ThesisTrace assumptions
            </Badge>
          </div>
          <span className="text-xs text-[var(--color-ink-faint)]">FY{dcf.fiscal_year}</span>
        </div>

        {dcf.insufficient_data || dcf.implied_growth === null ? (
          <InsufficientData dcf={dcf} />
        ) : (
          <Resolved dcf={dcf} />
        )}

        {dcf.caveats && dcf.caveats.length > 0 ? (
          <ul className="space-y-1 border-t border-[var(--color-border)] pt-3">
            {dcf.caveats.map((c, i) => (
              <li key={i} className="text-xs leading-snug text-[var(--color-ink-muted)]">
                {c}
              </li>
            ))}
          </ul>
        ) : null}

        {dcf.operands && dcf.operands.length > 0 ? (
          <Operands operands={dcf.operands} cik={cik} fiscalYear={dcf.fiscal_year} />
        ) : null}

        {/* The API's own words, not a paraphrase — it states that the discount
            rate is a setting rather than a fact about this company. */}
        <p className="border-t border-[var(--color-border)] pt-3 text-xs leading-relaxed text-[var(--color-ink-faint)]">
          {dcf.attribution}
        </p>
      </Card>
    </section>
  );
}

/** AD-16: absence is SHOWN, with the reason. Not the maturity profile's
 *  render-nothing exception — this is a lens capability, so a filer it cannot
 *  cover must say so rather than vanish. */
function InsufficientData({ dcf }: { dcf: ReverseDcf }) {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-x-6 gap-y-2">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-3xl font-semibold tabular-nums text-[var(--color-ink-faint)]">
              —
            </span>
            <Badge variant="pending">Insufficient data</Badge>
          </div>
        </div>
        {/* The achieved CAGR is computed independently of whether the DCF
            resolves, so it EXISTS here — Suncor's is 7.7% over FY2016-FY2025.
            Dropping it left the one card with no figure at all showing nothing,
            when half of the comparison the story exists for was available. */}
        <Achieved dcf={dcf} />
      </div>
      {dcf.reason ? (
        <p className="text-sm leading-relaxed text-[var(--color-ink-muted)]">{dcf.reason}</p>
      ) : null}
      {/* A base can be insufficient while some grid cells still resolve (the
          implied rate falls outside the solver's search bounds at the base pair
          but not at every other one). No filer in the universe does this today,
          so this is unobserved rather than verified — but dropping a resolved
          band would invert the contract's rule that failed cells are shown, not
          silently removed. */}
      {dcf.range_low !== null && dcf.range_high !== null ? (
        <p className="text-xs text-[var(--color-ink-muted)]">
          Some assumption combinations still resolve:{" "}
          <span className="font-medium tabular-nums text-[var(--color-ink)]">
            {formatRate(dcf.range_low)} to {formatRate(dcf.range_high)}
          </span>{" "}
          <span className="text-[var(--color-ink-faint)]">
            ({dcf.resolved_cells} of {dcf.total_cells})
          </span>
        </p>
      ) : null}
      <Assumptions dcf={dcf} />
    </div>
  );
}

/** The filer's own achieved revenue growth. Shared by both branches, because it
 *  is available whether or not the reverse DCF resolved. */
function Achieved({ dcf }: { dcf: ReverseDcf }) {
  if (dcf.historical_revenue_cagr === null) return null;
  return (
    <div>
      <div className="font-mono text-xl font-semibold tabular-nums text-[var(--color-ink-muted)]">
        {formatRate(dcf.historical_revenue_cagr)}
      </div>
      <p className="text-xs text-[var(--color-ink-faint)]">
        actually achieved
        {dcf.historical_from_fiscal_year && dcf.historical_to_fiscal_year
          ? `, FY${dcf.historical_from_fiscal_year}–FY${dcf.historical_to_fiscal_year}`
          : ""}
      </p>
    </div>
  );
}

function Resolved({ dcf }: { dcf: ReverseDcf }) {
  const implied = dcf.implied_growth!;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-x-6 gap-y-2">
        <div>
          <div className="font-mono text-3xl font-semibold tabular-nums text-[var(--color-ink)]">
            {formatRate(implied)}
          </div>
          <p className="text-xs text-[var(--color-ink-faint)]">
            a year for {dcf.horizon_years} years, at a {formatRate(dcf.discount_rate, 0)} discount rate
          </p>
        </div>
        <Achieved dcf={dcf} />
      </div>

      <BandPlot dcf={dcf} />

      <Assumptions dcf={dcf} />
    </div>
  );
}

/** The band across the declared assumption grid, with the filer's own achieved
 *  growth marked on the SAME axis — the comparison is the entire point of the
 *  capability, and putting the two on separate scales would defeat it.
 *
 *  Custom SVG-free rendering: positioned spans over a track. No charting
 *  library, per the story's constraint. */
function BandPlot({ dcf }: { dcf: ReverseDcf }) {
  const implied = dcf.implied_growth;
  const historical = dcf.historical_revenue_cagr;
  const low = dcf.range_low;
  const high = dcf.range_high;

  // Nothing to plot without a band. The figures above still stand.
  if (low === null || high === null || implied === null) return null;

  // Zero is ALWAYS in the domain. Two real bands cross it, and whether the price
  // implies contraction or growth is the single most important read on this card —
  // a domain that floated above zero would hide the sign change.
  const marks = [low, high, implied, 0];
  if (historical !== null) marks.push(historical);
  const rawMin = Math.min(...marks);
  const rawMax = Math.max(...marks);
  const span = rawMax - rawMin || 0.01;
  const pad = span * 0.08;
  const domainMin = rawMin - pad;
  const domainMax = rawMax + pad;

  const pos = (v: number) => ((v - domainMin) / (domainMax - domainMin)) * 100;

  const bandLeft = pos(low);
  const bandWidth = Math.max(pos(high) - bandLeft, 0.5);

  return (
    <div className="space-y-2">
      <div className="relative h-14">
        {/* Track */}
        <div className="absolute inset-x-0 top-5 h-4 rounded-[var(--radius-pill)] bg-[var(--color-canvas)]" />

        {/* The band itself */}
        <div
          className="absolute top-5 h-4 rounded-[var(--radius-pill)] bg-[var(--color-brand-500)] opacity-30"
          style={{ left: `${bandLeft}%`, width: `${bandWidth}%` }}
        />

        {/* Zero: drawn over the band, because a band crossing zero is the point */}
        <div
          className="absolute top-3 h-8 w-px bg-[var(--color-ink-faint)]"
          style={{ left: `${pos(0)}%` }}
        />
        <span
          className="absolute top-0 -translate-x-1/2 text-[10px] text-[var(--color-ink-faint)]"
          style={{ left: `${pos(0)}%` }}
        >
          0%
        </span>

        {/* Implied: the point estimate, drawn INSIDE its band.
            BOTH marks are labelled. Labelling only one leaves a reader with two
            marks and one name on a card whose entire purpose is telling them
            apart — caught in browser verification, not by the type checker. */}
        <div
          className="absolute top-4 h-6 w-[3px] -translate-x-1/2 rounded-full bg-[var(--color-brand-600)]"
          style={{ left: `${pos(implied)}%` }}
        />
        <span
          className="absolute top-11 -translate-x-1/2 whitespace-nowrap text-[10px] font-medium text-[var(--color-brand-600)]"
          style={{ left: `${pos(implied)}%` }}
        >
          implied
        </span>

        {/* Achieved: visually distinct from the implied mark, because confusing
            the two would invert the entire reading of the card. */}
        {historical !== null ? (
          <>
            <div
              className="absolute top-4 h-6 w-[3px] -translate-x-1/2 rounded-full bg-[var(--color-ink)]"
              style={{ left: `${pos(historical)}%` }}
            />
            <span
              className="absolute top-11 -translate-x-1/2 whitespace-nowrap text-[10px] font-medium text-[var(--color-ink)]"
              style={{ left: `${pos(historical)}%` }}
            >
              achieved
            </span>
          </>
        ) : null}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-[var(--color-ink-muted)]">
        <span>
          Range across the assumption grid:{" "}
          <span className="font-medium tabular-nums text-[var(--color-ink)]">
            {formatRate(low)} to {formatRate(high)}
          </span>
        </span>
        {/* Stated whenever the grid is not fully resolved, so a partial band is
            never read as a complete one. */}
        {dcf.resolved_cells < dcf.total_cells ? (
          <span className="text-[var(--color-ink-faint)]">
            {dcf.resolved_cells} of {dcf.total_cells} combinations resolved
          </span>
        ) : null}
      </div>
    </div>
  );
}

/** The assumptions that produced the figure. Without these the number means
 *  nothing, so they are visible without interaction. */
function Assumptions({ dcf }: { dcf: ReverseDcf }) {
  const items = [
    { label: "Discount rate", value: formatRate(dcf.discount_rate, 0) },
    { label: "Terminal growth", value: formatRate(dcf.terminal_growth) },
    { label: "Horizon", value: `${dcf.horizon_years} years` },
  ];
  return (
    <dl className="flex flex-wrap gap-x-6 gap-y-1 border-t border-[var(--color-border)] pt-3">
      {items.map((it) => (
        <div key={it.label} className="flex items-baseline gap-1.5">
          <dt className="text-xs text-[var(--color-ink-faint)]">{it.label}</dt>
          <dd className="font-mono text-xs font-medium tabular-nums text-[var(--color-ink-muted)]">
            {it.value}
          </dd>
        </div>
      ))}
      <div className="flex items-baseline gap-1.5">
        <dt className="text-xs text-[var(--color-ink-faint)]">Spec</dt>
        <dd className="font-mono text-xs text-[var(--color-ink-faint)]">{dcf.spec_version}</dd>
      </div>
    </dl>
  );
}

/** Every operand, so enterprise value and free cash flow can be recomputed from
 *  the page rather than taken on trust (risk-assessment finding 3.5). Behind a
 *  disclosure because it is verification detail, not the headline. */
function Operands({
  operands,
  cik,
  fiscalYear,
}: {
  operands: ReverseDcfOperand[];
  cik?: string;
  fiscalYear: number;
}) {
  return (
    <details className="border-t border-[var(--color-border)] pt-3">
      <summary className="cursor-pointer text-xs text-[var(--color-ink-muted)] hover:text-[var(--color-ink)]">
        Inputs ({operands.length})
      </summary>
      <ul className="mt-2 space-y-1.5">
        {operands.map((op) => (
          <li key={op.name} className="flex flex-wrap items-center gap-2 text-xs">
            <span className="w-40 flex-shrink-0 text-[var(--color-ink-muted)]">{labelFor(op.name)}</span>
            <span className="font-medium tabular-nums text-[var(--color-ink)]">
              {compactAmount(op.value)}
              {op.unit ? <span className="ml-1 text-[var(--color-ink-faint)]">{op.unit}</span> : null}
            </span>
            {/* A filed figure gets a citation; a computed one gets its derivation
                and NO accession, so the two can never be confused (AD-19). */}
            {op.accession_number ? (
              cik ? (
                <CitationChip
                  cik={cik}
                  accessionNumber={op.accession_number}
                  canonicalConcept={op.name}
                  fiscalYear={fiscalYear}
                  derivation={null}
                />
              ) : (
                // Without a cik the chip cannot build its EDGAR link, but the
                // operand IS filed and saying so beats rendering nothing —
                // silent loss of provenance is the worse failure.
                <span className="text-[var(--color-ink-faint)]">as filed, FY{fiscalYear}</span>
              )
            ) : op.derived_from && op.derived_from.length > 0 ? (
              <span className="text-[var(--color-ink-faint)]">
                computed from {joinList(op.derived_from.map(inlineLabel))}
              </span>
            ) : op.source ? (
              <span className="text-[var(--color-ink-faint)]">
                {op.source}
                {op.observed_on ? `, ${op.observed_on}` : ""}
              </span>
            ) : null}
            {/* The displayed price is the CONVERTED one — CP files in CAD but is
                quoted in USD — so without the rate a reader checking it against
                the exchange sees a mismatch and no explanation. Recomputability
                is the whole point of this list. */}
            {op.conversion_rate ? (
              <span className="text-[var(--color-ink-faint)]">
                converted at {op.conversion_rate}
                {op.conversion_rate_source ? ` (${op.conversion_rate_source}` : ""}
                {op.conversion_rate_source && op.conversion_rate_date
                  ? `, ${op.conversion_rate_date})`
                  : op.conversion_rate_source
                    ? ")"
                    : ""}
              </span>
            ) : null}
          </li>
        ))}
      </ul>
    </details>
  );
}
