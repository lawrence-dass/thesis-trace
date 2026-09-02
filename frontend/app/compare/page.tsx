// Side-by-side comparison (FR-14): parallel columns of Verdicts/lens scores for
// 2-4 companies, with diverging classifications highlighted. Shows only the
// lenses live in the current phase, consistent with the overview's phase honesty.

import type { ReactNode } from "react";
import { Badge, applicabilityLabel, applicabilityVariant, bandTone } from "../components/ui/Badge";
import { Card } from "../components/ui/Card";
import { caveatReasonText } from "../components/CaveatReason";
import type { VerdictItem } from "../components/VerdictGlyph";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type Overview = { state: string; ticker?: string; name?: string; verdict?: VerdictItem[] };

// Plain-language names for a model's own sub-signals — used only to explain
// WHY an aggregate is missing (shown as a hover tooltip in this compact
// table), never to recompute or reclassify anything (AD-8, AD-16).
const SIGNAL_LABEL: Record<string, string> = {
  dsri: "Days Sales in Receivables",
  gmi: "Gross Margin",
  aqi: "Asset Quality",
  sgi: "Sales Growth",
  depi: "Depreciation Rate",
  sgai: "SG&A Ratio",
  tata: "Total Accruals",
  lvgi: "Leverage",
  x1_working_capital: "Working Capital",
  x2_retained_earnings: "Retained Earnings",
  x3_ebit: "EBIT",
  x4_market_value_equity: "Market Value of Equity",
  x5_sales: "Sales Turnover",
  accruals_ratio: "Accruals",
};

async function getOverview(ticker: string): Promise<Overview> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/companies/${ticker}/overview`, { cache: "no-store" });
    return (await res.json()) as Overview;
  } catch {
    return { state: "unreachable", ticker };
  }
}

export function cellKey(v: VerdictItem | undefined): string {
  if (!v) return "—";
  const classification = v.band_label ?? (v.aggregate_value === null ? "—" : String(v.aggregate_value));
  const missing = v.aggregate_value === null ? v.missing_signals.slice().sort().join(",") : "";
  return [v.applicability, classification, missing].join("|");
}

const MODELS = ["piotroski", "altman", "beneish", "sloan"];
const MODEL_LABEL: Record<string, string> = {
  piotroski: "Piotroski F-Score",
  altman: "Altman Z-Score",
  beneish: "Beneish M-Score",
  sloan: "Sloan Accruals",
};

function VerdictValue({ verdict }: { verdict: VerdictItem }): ReactNode {
  if (verdict.applicability !== "computed" && verdict.applicability !== "computed_with_caveat") {
    return <Badge variant={applicabilityVariant(verdict.applicability)}>{applicabilityLabel(verdict.applicability)}</Badge>;
  }
  if (verdict.aggregate_value === null) return <Badge variant="pending">Insufficient data</Badge>;
  if (verdict.band_label) return <Badge variant={bandTone(verdict.band_label)} icon={false}>{verdict.band_label}</Badge>;
  return <span className="font-mono tabular-nums text-[var(--color-ink-muted)]">{verdict.aggregate_value}</span>;
}

export function VerdictCell({ verdict }: { verdict: VerdictItem | undefined }): ReactNode {
  if (!verdict) return <span className="text-[var(--color-ink-faint)]">—</span>;

  const caveated = verdict.applicability === "computed_with_caveat";
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <VerdictValue verdict={verdict} />
        {caveated ? <Badge variant="caveat">Caveat</Badge> : null}
      </div>
      {verdict.aggregate_value === null && verdict.missing_signals.length > 0 ? (
        <p className="text-xs leading-snug text-[var(--color-ink-faint)]">
          Missing: {verdict.missing_signals.map((k) => SIGNAL_LABEL[k] ?? k).join(", ")}
        </p>
      ) : null}
      {caveated ? (
        <details className="rounded-[var(--radius-control)] border border-[var(--color-signal-caveat-border)] bg-[var(--color-signal-caveat-bg)] px-2 py-1.5 text-xs text-[var(--color-signal-caveat)]">
          <summary className="cursor-pointer list-none font-semibold uppercase tracking-[var(--tracking-label)]">
            Caveat details
          </summary>
          <p className="mt-1 leading-snug">{caveatReasonText(verdict.caveat_reason)}</p>
        </details>
      ) : null}
    </div>
  );
}

export default async function ComparePage({ searchParams }: { searchParams: Promise<{ tickers?: string }> }) {
  const { tickers } = await searchParams;
  const list = (tickers ?? "").split(",").map((t) => t.trim().toUpperCase()).filter(Boolean).slice(0, 4);

  if (list.length < 2) {
    return (
      <main className="mx-auto w-full max-w-5xl space-y-3">
        <h1 className="text-2xl font-semibold text-[var(--color-ink)]">Comparison</h1>
        <Card>
          <p className="text-[var(--color-ink-muted)]">Add at least 2 companies (max 4) to compare.</p>
        </Card>
      </main>
    );
  }

  const overviews = await Promise.all(list.map(getOverview));
  const verdictFor = (o: Overview, model: string) => o.verdict?.find((x) => x.model === model);

  return (
    <main className="mx-auto w-full max-w-7xl space-y-6">
      <section className="space-y-2">
        <p className="text-sm font-semibold uppercase tracking-wide text-[var(--color-brand-link)]">Comparison</p>
        <h1 className="text-2xl font-semibold tracking-tight text-[var(--color-ink)] sm:text-3xl">
          {list.join(" · ")}
        </h1>
      </section>

      <Card className="overflow-x-auto p-0">
        <table className="w-full min-w-[560px] border-collapse text-sm">
          <thead>
            <tr>
              <th className="border-b border-[var(--color-border)] p-4 text-left font-semibold text-[var(--color-ink-faint)]">
                Lens
              </th>
              {overviews.map((o) => (
                <th
                  key={o.ticker}
                  className="border-b border-[var(--color-border)] p-4 text-left font-mono font-semibold text-[var(--color-ink)]"
                >
                  {o.ticker}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {MODELS.map((model) => {
              const verdicts = overviews.map((o) => verdictFor(o, model));
              const diverges = new Set(verdicts.map(cellKey)).size > 1;
              return (
                <tr key={model} className={diverges ? "bg-[var(--color-signal-caveat-bg)]" : undefined}>
                  <td className="border-b border-[var(--color-border)] p-4 font-medium text-[var(--color-ink)]">
                    {MODEL_LABEL[model] ?? model}
                  </td>
                  {verdicts.map((v, i) => (
                    <td key={i} className="border-b border-[var(--color-border)] p-4">
                      <VerdictCell verdict={v} />
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </Card>
      <p className="text-sm text-[var(--color-ink-faint)]">
        Rows where companies diverge are highlighted. Value &amp; Growth lenses arrive in a later phase.
      </p>
    </main>
  );
}
