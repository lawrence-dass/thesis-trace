import { Card } from "./ui/Card";
import { Badge, type BadgeVariant } from "./ui/Badge";
import { compactAmount } from "./ui/format";

export type NearTermDebtShare = {
  fiscal_year: number;
  // null exactly when insufficient_data. A genuinely filed zero is 0, not null —
  // Cameco reports no debt maturing within twelve months in four fiscal years,
  // and 0.0% is the right thing to show for those.
  share: number | null;
  band_label: string;
  tone: string | null;
  near_term_debt: number | null;
  total_debt: number | null;
  insufficient_data: boolean;
  attribution: string;
  spec_version: string;
};

/** The spec's tone vocabulary -> the badge vocabulary. Kept as an explicit map
 *  rather than passing the tone straight through: `bandTone()` shipping a
 *  model's band vocabulary it did not actually cover is a bug this project has
 *  already had once, and an unrecognised tone must fall back visibly-neutral
 *  rather than render as a pass. */
function toneVariant(tone: string | null): BadgeVariant {
  if (tone === "positive") return "pass";
  if (tone === "caution") return "caveat";
  return "neutral";
}

export function NearTermDebtShareCard({ rows }: { rows: NearTermDebtShare[] }) {
  if (!rows || rows.length === 0) return null;

  // Newest first from the API. The most recent year leads; the rest give the
  // trend, which is the whole reason this figure is interesting.
  const [latest, ...history] = rows;
  const withValues = history.filter((r) => !r.insufficient_data);

  return (
    <Card className="space-y-3 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-[var(--color-ink)]">Near-term debt share</h3>
          <p className="text-xs text-[var(--color-ink-muted)]">
            Long-term debt due within twelve months
          </p>
        </div>
        <span className="text-xs text-[var(--color-ink-faint)]">FY{latest.fiscal_year}</span>
      </div>

      {latest.insufficient_data ? (
        <div className="space-y-1">
          <Badge variant="neutral">{latest.band_label}</Badge>
          {/* Deliberately does NOT say "this filer does not report it". That is true
              for BCE (it stopped tagging its current portion after FY2023) but FALSE
              for SHOP, which reports its current portion perfectly well — what is
              missing there is the other half of the denominator. One phrasing has to
              be honest for both causes, so it states what ThesisTrace could not do
              rather than accusing the filer of an omission. */}
          <p className="text-xs text-[var(--color-ink-muted)]">
            Both figures this needs could not be resolved for FY{latest.fiscal_year}.
          </p>
        </div>
      ) : (
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <span className="text-2xl font-semibold tabular-nums text-[var(--color-ink)]">
            {(latest.share! * 100).toFixed(1)}%
          </span>
          <Badge variant={toneVariant(latest.tone)} icon={false}>
            {latest.band_label}
          </Badge>
          <span className="text-xs tabular-nums text-[var(--color-ink-faint)]">
            {compactAmount(latest.near_term_debt ?? 0)} of {compactAmount(latest.total_debt ?? 0)}
          </span>
        </div>
      )}

      {withValues.length > 0 ? (
        <details className="group">
          <summary className="cursor-pointer text-xs text-[var(--color-ink-muted)] hover:text-[var(--color-ink)]">
            Earlier years ({withValues.length})
          </summary>
          <ul className="mt-2 space-y-1">
            {withValues.map((r) => (
              <li
                key={r.fiscal_year}
                className="flex items-baseline justify-between gap-3 text-xs tabular-nums"
              >
                <span className="text-[var(--color-ink-faint)]">FY{r.fiscal_year}</span>
                <span className="text-[var(--color-ink-muted)]">{r.band_label}</span>
                <span className="font-medium text-[var(--color-ink)]">
                  {(r.share! * 100).toFixed(1)}%
                </span>
              </li>
            ))}
          </ul>
        </details>
      ) : null}

      {/* Travels with the figure, never optional: it names whose judgment the
          bands are AND states the short-term-borrowings exclusion, which is the
          single most likely way to misread this number. */}
      <p className="border-t border-[var(--color-border)] pt-2 text-xs text-[var(--color-ink-faint)]">
        {latest.attribution}
      </p>
    </Card>
  );
}
