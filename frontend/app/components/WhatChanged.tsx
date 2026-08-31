// "What changed" summary (FR-22, Story 5.4). Presentation only — renders
// exactly what /api/companies/{ticker}/changes returns and classifies nothing
// itself (AD-8). Every change shows BOTH endpoints, each citable to its filing
// (AD-19).
//
// Two rules drive the visual design and are not negotiable:
//
//  1. A BAND CROSSING is not the same event as a value moving within a band.
//     Crossing Altman Grey -> Distress changes the published classification;
//     the Z-score drifting inside Grey does not. They are rendered as visibly
//     different things, not as one "it changed" row with different numbers.
//
//  2. COVERAGE CHANGES ARE NOT DIRECTIONAL. insufficient_data -> a value means
//     the data arrived, not that the company improved; the reverse means an
//     input was lost, not that it declined. These get neutral styling and
//     explicitly non-directional wording — no arrows, no pass/fail palette.
//     Colouring them would assert something the filing never said.

import { Badge, bandTone } from "./ui/Badge";
import { Card } from "./ui/Card";
import { CitationChip } from "./ui/CitationChip";
import { AlertIcon } from "./ui/icons";

export type ChangeProvenance = {
  accession_number: string | null;
  canonical_concept?: string | null;
  fiscal_year?: number | null;
  derivation?: string | null;
};

export type SignalChange = {
  kind: string;
  signal_key: string;
  prior_status: string | null;
  current_status: string | null;
  prior_value: number | null;
  current_value: number | null;
};

export type FactChange = {
  kind: string;
  signal_key: string;
  canonical_concept: string;
  prior_value: number | null;
  current_value: number | null;
  prior_provenance: ChangeProvenance | null;
  current_provenance: ChangeProvenance | null;
};

/** A React key for one fact-change list item (Story 10.7).
 *
 *  `signal_key`+`canonical_concept` alone is NOT unique: a signal that reads
 *  the same concept across two comparison years (leverage_decreasing needs
 *  BOTH years' long_term_debt) legitimately produces two DISTINCT fact
 *  changes sharing that pair — confirmed live on SHOP and CP, same key,
 *  different `current_provenance.fiscal_year`, both real data, not
 *  duplicates. `index` is a safe final tiebreaker: this list is static per
 *  render (a single fetch, never reordered), so index-based key churn is not
 *  a concern here the way it would be for an editable/reorderable list.
 */
export function factChangeKey(f: FactChange, index: number): string {
  const year = f.current_provenance?.fiscal_year ?? f.prior_provenance?.fiscal_year ?? index;
  return `${f.signal_key}-${f.canonical_concept}-${year}`;
}

export type RunChange = {
  model: string;
  fiscal_year: number;
  kinds: string[];
  prior_accession_number: string | null;
  current_accession_number: string;
  prior_aggregate: number | null;
  current_aggregate: number | null;
  prior_band_label: string | null;
  current_band_label: string | null;
  signal_changes: SignalChange[];
  fact_changes: FactChange[];
  version_caveat: string | null;
};

export type DataQualityChange = {
  kind: string;
  issue_type: string;
  status: string;
  raised_by: string;
};

export type Changes = {
  state: string;
  comparison_state?: string;
  since?: string;
  since_basis?: string;
  since_accession?: string | null;
  run_changes?: RunChange[];
  data_quality_changes?: DataQualityChange[];
};

const MODEL_LABEL: Record<string, string> = {
  piotroski: "Piotroski F-Score",
  altman: "Altman Z-Score",
  beneish: "Beneish M-Score",
  sloan: "Sloan Accruals",
};

// Deliberately non-directional wording for the two coverage kinds. See rule 2.
const KIND_LABEL: Record<string, string> = {
  band_change: "Classification changed",
  aggregate_change: "Score moved",
  signal_status_change: "Signal changed",
  signal_value_change: "Signal value moved",
  coverage_gained: "Data now available",
  coverage_lost: "Data no longer available",
  fact_change: "Source figure changed",
  applicability_change: "Applicability changed",
  scored_year_added: "New fiscal year scored",
};

const ISSUE_LABEL: Record<string, string> = {
  identity_violation: "Accounting identity check",
  ambiguous_selection: "Ambiguous source selection",
  source_conflict: "Conflicting sources",
};

// Rendered in UTC deliberately. The pivot is a stored UTC instant, and
// formatting it in the viewer's zone shifts a midnight timestamp to the
// PREVIOUS day for anyone west of Greenwich — so the page would claim to
// compare against a date one day off from the filing it names.
function formatDate(iso: string | undefined): string {
  if (!iso) return "the previous check";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "the previous check";
  return d.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

// Thousands separators WITHOUT precision loss. `toLocaleString`'s default
// caps at 3 fraction digits, which would silently round a filed figure — not
// acceptable for a number the page claims is traceable to a filing.
function num(v: number | null): string {
  if (v === null || v === undefined) return "—";
  return v.toLocaleString(undefined, { maximumFractionDigits: 20 });
}

/** Signal rows worth listing under a run.
 *
 * Excludes signals whose only movement is the band, because the run-level
 * Classification block already renders that transition — and the signal's own
 * value typically did not change, so it would render as "1 -> 1".
 */
function signalRows(r: RunChange): SignalChange[] {
  return r.signal_changes.filter(
    (s) => !(s.kind === "band_change" && r.kinds.includes("band_change")),
  );
}

/** prior -> current, in mono. Neutral by default: the arrow marks a transition,
 *  never a judgement about whether it is good news. */
function Transition({ from, to }: { from: string; to: string }) {
  return (
    <span className="inline-flex items-center gap-2 font-mono text-label tabular-nums">
      <span className="text-[var(--color-ink-faint)] line-through decoration-1">{from}</span>
      <span aria-hidden className="text-[var(--color-ink-faint)]">&rarr;</span>
      <span className="font-semibold text-[var(--color-ink)]">{to}</span>
    </span>
  );
}

export function WhatChanged({ changes, cik }: { changes: Changes; cik: string }) {
  if (changes.state !== "ok") return null;

  const state = changes.comparison_state;
  const runs = changes.run_changes ?? [];
  const dq = changes.data_quality_changes ?? [];
  const when = formatDate(changes.since);

  // FR-22: "nothing to compare" and "compared, nothing moved" must never render
  // the same, and NEITHER may look like a failed load. Both get an explicit
  // sentence rather than an empty region.
  if (state === "no_prior_state") {
    return (
      <Section>
        <p className="text-label text-[var(--color-ink-muted)]">
          No earlier record to compare against yet — this is the first scored state ThesisTrace has
          for this company. Changes will appear here once a later filing is processed.
        </p>
      </Section>
    );
  }

  if (state === "no_change" || (runs.length === 0 && dq.length === 0)) {
    return (
      <Section since={when} sinceAccession={changes.since_accession}>
        <p className="text-label text-[var(--color-ink-muted)]">
          No change since {when}. Scores, signals and source figures are all unchanged.
        </p>
      </Section>
    );
  }

  return (
    <Section since={when} sinceAccession={changes.since_accession}>
      <div className="space-y-3">
        {runs.map((r) => (
          <Card key={`${r.model}-${r.fiscal_year}`} className="space-y-3">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h3 className="text-label font-semibold text-[var(--color-ink)]">
                {MODEL_LABEL[r.model] ?? r.model}{" "}
                <span className="font-mono text-caption font-normal text-[var(--color-ink-faint)]">
                  FY{r.fiscal_year}
                </span>
              </h3>
              <div className="flex flex-wrap gap-1.5">
                {r.kinds.map((k) => (
                  <Badge key={k} variant="neutral" icon={false}>
                    {KIND_LABEL[k] ?? k}
                  </Badge>
                ))}
              </div>
            </div>

            {/* Rule 1: a band crossing is its own event, rendered with both
                published classifications rather than as a number delta. */}
            {r.kinds.includes("band_change") ? (
              <div className="flex flex-wrap items-center gap-2 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-canvas)] px-3 py-2">
                <span className="text-caption font-medium uppercase tracking-[var(--tracking-label)] text-[var(--color-ink-faint)]">
                  Classification
                </span>
                {r.prior_band_label ? (
                  <Badge variant={bandTone(r.prior_band_label)} icon={false}>
                    {r.prior_band_label}
                  </Badge>
                ) : (
                  <Badge variant="pending">None</Badge>
                )}
                <span aria-hidden className="text-[var(--color-ink-faint)]">&rarr;</span>
                {r.current_band_label ? (
                  <Badge variant={bandTone(r.current_band_label)} icon={false}>
                    {r.current_band_label}
                  </Badge>
                ) : (
                  <Badge variant="pending">None</Badge>
                )}
              </div>
            ) : null}

            {/* A value move that did NOT cross a band: quieter, no badges. */}
            {r.kinds.includes("aggregate_change") ? (
              <p className="flex flex-wrap items-center gap-2 text-label text-[var(--color-ink-muted)]">
                <span>Score</span>
                <Transition from={num(r.prior_aggregate)} to={num(r.current_aggregate)} />
                {!r.kinds.includes("band_change") ? (
                  <span className="text-caption text-[var(--color-ink-faint)]">
                    (within the same classification)
                  </span>
                ) : null}
              </p>
            ) : null}

            {/* A signal whose ONLY change is the band is dropped here: the
                run-level Classification block above already states that
                transition. Real scoring hangs the band on a sub-signal
                (Piotroski's roa_positive, Altman's first component), so
                without this the same crossing would appear twice — the second
                time as a meaningless "1 -> 1" value transition, because the
                signal's own value did not move. */}
            {signalRows(r).length > 0 ? (
              <ul className="space-y-1.5 text-label">
                {signalRows(r).map((s) => {
                  const isCoverage = s.kind === "coverage_gained" || s.kind === "coverage_lost";
                  return (
                    <li key={s.signal_key} className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-caption text-[var(--color-ink-faint)]">
                        {s.signal_key}
                      </span>
                      {isCoverage ? (
                        // Rule 2: neutral, non-directional. No arrow, no
                        // pass/fail colour — the company did not move.
                        <span className="text-[var(--color-ink-muted)]">
                          {KIND_LABEL[s.kind]}
                          {s.kind === "coverage_gained" && s.current_value !== null ? (
                            <span className="ml-2 font-mono tabular-nums text-[var(--color-ink)]">
                              {num(s.current_value)}
                            </span>
                          ) : null}
                        </span>
                      ) : (
                        <Transition from={num(s.prior_value)} to={num(s.current_value)} />
                      )}
                    </li>
                  );
                })}
              </ul>
            ) : null}

            {r.fact_changes.length > 0 ? (
              <div className="space-y-1.5">
                <p className="text-caption font-medium uppercase tracking-[var(--tracking-label)] text-[var(--color-ink-faint)]">
                  Source figures
                </p>
                <ul className="space-y-2 text-label">
                  {r.fact_changes.map((f, i) => (
                    <li key={factChangeKey(f, i)} className="space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-[var(--color-ink-muted)]">{f.canonical_concept}</span>
                        <Transition from={num(f.prior_value)} to={num(f.current_value)} />
                      </div>
                      {/* AD-19: both endpoints citable, so a reported change is
                          auditable rather than asserted. */}
                      <div className="flex flex-wrap gap-1.5">
                        {f.prior_provenance?.accession_number ? (
                          <CitationChip
                            cik={cik}
                            accessionNumber={f.prior_provenance.accession_number}
                            canonicalConcept={`was: ${f.prior_provenance.canonical_concept ?? f.canonical_concept}`}
                            fiscalYear={f.prior_provenance.fiscal_year ?? 0}
                            derivation={f.prior_provenance.derivation ?? null}
                          />
                        ) : null}
                        {f.current_provenance?.accession_number ? (
                          <CitationChip
                            cik={cik}
                            accessionNumber={f.current_provenance.accession_number}
                            canonicalConcept={`now: ${f.current_provenance.canonical_concept ?? f.canonical_concept}`}
                            fiscalYear={f.current_provenance.fiscal_year ?? 0}
                            derivation={f.current_provenance.derivation ?? null}
                          />
                        ) : null}
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {/* Never silently dropped: a moved number may be OUR doing. */}
            {r.version_caveat ? (
              <div className="flex gap-2 rounded-[var(--radius-card)] border border-[var(--color-signal-caveat-border)] bg-[var(--color-signal-caveat-bg)] px-3 py-2">
                <AlertIcon className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-[var(--color-signal-caveat)]" />
                <p className="text-caption leading-snug text-[var(--color-ink-muted)]">{r.version_caveat}</p>
              </div>
            ) : null}
          </Card>
        ))}

        {dq.length > 0 ? (
          <Card className="space-y-2">
            <h3 className="text-label font-semibold text-[var(--color-ink)]">Data-quality changes</h3>
            <ul className="space-y-1 text-label text-[var(--color-ink-muted)]">
              {dq.map((d, i) => (
                <li key={`${d.issue_type}-${i}`} className="flex flex-wrap items-center gap-2">
                  <Badge variant={d.kind === "data_quality_opened" ? "caveat" : "pass"} icon={false}>
                    {d.kind === "data_quality_opened" ? "Opened" : "Closed"}
                  </Badge>
                  <span>{ISSUE_LABEL[d.issue_type] ?? d.issue_type}</span>
                  <span className="text-caption text-[var(--color-ink-faint)]">raised by {d.raised_by}</span>
                </li>
              ))}
            </ul>
          </Card>
        ) : null}
      </div>
    </Section>
  );
}

function Section({
  since,
  sinceAccession,
  children,
}: {
  since?: string;
  sinceAccession?: string | null;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-label font-semibold uppercase tracking-[var(--tracking-label)] text-[var(--color-ink-faint)]">
          What changed
        </h2>
        {since ? (
          <p className="text-caption text-[var(--color-ink-faint)]">
            Compared against {since}
            {sinceAccession ? (
              <span className="ml-1 font-mono">(before filing {sinceAccession})</span>
            ) : null}
          </p>
        ) : null}
      </div>
      {children}
    </section>
  );
}
