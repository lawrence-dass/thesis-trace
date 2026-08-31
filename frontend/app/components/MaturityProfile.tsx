import { Card } from "./ui/Card";
import { CitationChip } from "./ui/CitationChip";
import { compactAmount } from "./ui/format";

export type MaturityBucket = {
  canonical_concept: string;
  label: string;
  value: number;
  accession_number: string;
  fiscal_year: number;
};

export type MaturityProfile = {
  fiscal_year: number;
  buckets: MaturityBucket[];
  truncated: boolean;
  truncation_message: string | null;
  unit: string;
  attribution: string;
  spec_version: string;
};

export function MaturityProfileCard({
  profiles,
  cik,
}: {
  profiles: MaturityProfile[];
  cik?: string;
}) {
  // Renders NOTHING when there is no schedule — no wrapper, no heading, no
  // "missing" badge. Most filers here cannot produce one, so an empty-state
  // affordance would assert a deficiency that mostly does not exist. A deliberate,
  // scoped exception to the AD-16 convention that absence is shown.
  if (!profiles || profiles.length === 0) return null;

  const [latest, ...earlier] = profiles;

  // Bars scale to the LARGEST BUCKET, never to a sum — scaling to a total would
  // imply the buckets add up to the debt, which is the reconciliation that does
  // not hold.
  const peak = Math.max(...latest.buckets.map((b) => Math.abs(b.value)), 1);

  // Columns are the UNION across every year shown, in ladder order — NOT the
  // latest year's buckets. QSR's newest year is truncated (it stops tagging a
  // tail bucket after FY2024), so keying columns off `latest` would delete the
  // "After year 5" column from every earlier year — hiding FY2023's 8,566M, the
  // largest figure in the ladder, with no marker at all.
  const columns: { concept: string; label: string }[] = [];
  for (const profile of profiles) {
    for (const bucket of profile.buckets) {
      if (!columns.some((c) => c.concept === bucket.canonical_concept)) {
        columns.push({ concept: bucket.canonical_concept, label: bucket.label });
      }
    }
  }
  const ladderOrder = latest.buckets.map((b) => b.canonical_concept);
  columns.sort((a, b) => {
    const ai = ladderOrder.indexOf(a.concept);
    const bi = ladderOrder.indexOf(b.concept);
    // A column absent from the latest year sorts last — it can only be the tail,
    // since a schedule is contiguous from year one by construction.
    return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
  });

  // The note is shown whenever ANY displayed year is truncated, not only the
  // latest. CP is the case: its latest years are complete while FY2010-2021 are
  // not, so gating on `latest` left every historical asterisk pointing at a note
  // that was never rendered — for FY2021, standing in for 63% of the debt.
  const anyTruncated = profiles.some((p) => p.truncated);
  const truncationMessage =
    profiles.find((p) => p.truncated && p.truncation_message)?.truncation_message ?? null;

  return (
    <Card className="space-y-3 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-label font-semibold text-[var(--color-ink)]">Repayment schedule</h3>
          <p className="text-caption text-[var(--color-ink-muted)]">
            As published by the company{latest.unit ? `, in ${latest.unit}` : ""}
          </p>
        </div>
        <span className="text-caption text-[var(--color-ink-faint)]">FY{latest.fiscal_year}</span>
      </div>

      <ul className="space-y-1.5">
        {latest.buckets.map((bucket) => (
          <li key={bucket.canonical_concept} className="flex items-center gap-3 text-caption">
            <span className="w-24 flex-shrink-0 text-[var(--color-ink-muted)]">{bucket.label}</span>
            <span className="h-2 flex-1 overflow-hidden rounded-[var(--radius-pill)] bg-[var(--color-canvas)]">
              {/* A filed zero draws NO bar. It is a real value — the company
                  scheduled nothing that year — and a minimum-width bar would
                  render it identically to a small real repayment. */}
              <span
                className="block h-full rounded-[var(--radius-pill)] bg-[var(--color-brand-500)]"
                style={{
                  width:
                    bucket.value === 0
                      ? "0%"
                      : `${Math.max((Math.abs(bucket.value) / peak) * 100, 0.5)}%`,
                }}
              />
            </span>
            <span className="w-20 flex-shrink-0 text-right font-medium tabular-nums text-[var(--color-ink)]">
              {compactAmount(bucket.value)}
            </span>
            {cik ? (
              <CitationChip
                cik={cik}
                accessionNumber={bucket.accession_number}
                canonicalConcept={bucket.canonical_concept}
                fiscalYear={bucket.fiscal_year}
                derivation={null}
              />
            ) : null}
          </li>
        ))}
      </ul>

      {anyTruncated && truncationMessage ? (
        <p className="rounded-[var(--radius-chip)] bg-[var(--color-canvas)] p-2 text-caption text-[var(--color-ink-muted)]">
          {truncationMessage}
          {!latest.truncated ? " Years marked * below are affected." : ""}
        </p>
      ) : null}

      {earlier.length > 0 ? (
        <details>
          <summary className="cursor-pointer text-caption text-[var(--color-ink-muted)] hover:text-[var(--color-ink)]">
            Earlier years ({earlier.length})
          </summary>
          <div className="mt-2 overflow-x-auto">
            <table className="w-full min-w-[28rem] text-caption tabular-nums">
              <thead>
                <tr className="text-[var(--color-ink-faint)]">
                  <th className="py-1 text-left font-normal">FY</th>
                  {columns.map((c) => (
                    <th key={c.concept} className="py-1 text-right font-normal">
                      {c.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {earlier.map((p) => {
                  const byConcept = new Map(p.buckets.map((b) => [b.canonical_concept, b]));
                  return (
                    <tr key={p.fiscal_year} className="border-t border-[var(--color-border)]">
                      <td className="py-1 text-left text-[var(--color-ink-faint)]">
                        {p.fiscal_year}
                        {p.truncated ? (
                          <span title="Schedule truncated — see the note above"> *</span>
                        ) : null}
                      </td>
                      {columns.map((c) => (
                        <td key={c.concept} className="py-1 text-right text-[var(--color-ink)]">
                          {byConcept.has(c.concept)
                            ? compactAmount(byConcept.get(c.concept)!.value)
                            : "—"}
                        </td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </details>
      ) : null}

      {/* States that this does NOT add up to the total debt above it, and that its
          first row is not the near-term share — the two likeliest misreadings. */}
      <p className="border-t border-[var(--color-border)] pt-2 text-caption text-[var(--color-ink-faint)]">
        {latest.attribution}
      </p>
    </Card>
  );
}
