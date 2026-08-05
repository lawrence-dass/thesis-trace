import { Card } from "./ui/Card";

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

/** Absolute amounts, in the filer's own reporting currency — CP files in CAD, so
 *  the unit is never assumed. Deliberately NOT a percentage of anything: these
 *  buckets are undiscounted contractual principal and do not reconcile to the
 *  total debt shown above (QSR FY2023 sums to 13,043M against a filed 12,921M). */
function amount(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 1e9) return `${(value / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `${(value / 1e6).toFixed(0)}M`;
  return value.toLocaleString();
}

export function MaturityProfileCard({ profiles }: { profiles: MaturityProfile[] }) {
  // Renders NOTHING when there is no schedule — no wrapper, no heading, no
  // "missing" badge. Five of seven filers structurally cannot publish this, so an
  // empty-state affordance would assert a deficiency that does not exist. This is
  // a deliberate, scoped exception to the AD-16 convention that absence is shown.
  if (!profiles || profiles.length === 0) return null;

  const [latest, ...earlier] = profiles;

  // Bars are scaled to the LARGEST BUCKET, not to a total. Scaling to a total
  // would imply the buckets sum to the debt, which is exactly the reconciliation
  // that does not hold.
  const peak = Math.max(...latest.buckets.map((b) => Math.abs(b.value)), 1);

  return (
    <Card className="space-y-3 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-[var(--color-ink)]">Repayment schedule</h3>
          <p className="text-xs text-[var(--color-ink-muted)]">
            As published by the company{latest.unit ? `, in ${latest.unit}` : ""}
          </p>
        </div>
        <span className="text-xs text-[var(--color-ink-faint)]">FY{latest.fiscal_year}</span>
      </div>

      <ul className="space-y-1.5">
        {latest.buckets.map((bucket) => (
          <li key={bucket.canonical_concept} className="flex items-center gap-3 text-xs">
            <span className="w-24 flex-shrink-0 text-[var(--color-ink-muted)]">{bucket.label}</span>
            <span className="h-2 flex-1 overflow-hidden rounded-[var(--radius-pill)] bg-[var(--color-canvas)]">
              <span
                className="block h-full rounded-[var(--radius-pill)] bg-[var(--color-brand-500)]"
                style={{ width: `${Math.max((Math.abs(bucket.value) / peak) * 100, 1.5)}%` }}
              />
            </span>
            <span className="w-20 flex-shrink-0 text-right font-medium tabular-nums text-[var(--color-ink)]">
              {amount(bucket.value)}
            </span>
          </li>
        ))}
      </ul>

      {latest.truncated && latest.truncation_message ? (
        <p className="rounded-[var(--radius-chip)] bg-[var(--color-canvas)] p-2 text-xs text-[var(--color-ink-muted)]">
          {latest.truncation_message}
        </p>
      ) : null}

      {earlier.length > 0 ? (
        <details>
          <summary className="cursor-pointer text-xs text-[var(--color-ink-muted)] hover:text-[var(--color-ink)]">
            Earlier years ({earlier.length})
          </summary>
          <div className="mt-2 overflow-x-auto">
            <table className="w-full min-w-[28rem] text-xs tabular-nums">
              <thead>
                <tr className="text-[var(--color-ink-faint)]">
                  <th className="py-1 text-left font-normal">FY</th>
                  {latest.buckets.map((b) => (
                    <th key={b.canonical_concept} className="py-1 text-right font-normal">
                      {b.label}
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
                        {/* The truncation marker travels per row: a year missing its
                            tail bucket can be showing a small fraction of the debt.
                            CP FY2021 shows 7,376M of a 20,127M total. */}
                        {p.truncated ? <span title="Schedule truncated — see note above"> *</span> : null}
                      </td>
                      {latest.buckets.map((b) => (
                        <td key={b.canonical_concept} className="py-1 text-right text-[var(--color-ink)]">
                          {byConcept.has(b.canonical_concept)
                            ? amount(byConcept.get(b.canonical_concept)!.value)
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

      {/* States that this does NOT add up to the total debt above it — the single
          most likely way to misread the panel. */}
      <p className="border-t border-[var(--color-border)] pt-2 text-xs text-[var(--color-ink-faint)]">
        {latest.attribution}
      </p>
    </Card>
  );
}
