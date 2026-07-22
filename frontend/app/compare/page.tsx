// Side-by-side comparison (FR-14): parallel columns of Verdicts/lens scores for
// 2-4 companies, with diverging classifications highlighted. Shows only the
// lenses live in the current phase, consistent with the overview's phase honesty.

import { Badge, applicabilityLabel, applicabilityVariant, bandTone } from "../components/ui/Badge";
import { Card } from "../components/ui/Card";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type VerdictItem = { model: string; aggregate_value: number | null; band_label: string | null; applicability: string };
type Overview = { state: string; ticker?: string; name?: string; verdict?: VerdictItem[] };

async function getOverview(ticker: string): Promise<Overview> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/companies/${ticker}/overview`, { cache: "no-store" });
    return (await res.json()) as Overview;
  } catch {
    return { state: "unreachable", ticker };
  }
}

const MODELS = ["piotroski", "altman", "beneish", "sloan"];
const MODEL_LABEL: Record<string, string> = {
  piotroski: "Piotroski F-Score",
  altman: "Altman Z-Score",
  beneish: "Beneish M-Score",
  sloan: "Sloan Accruals",
};

export default async function ComparePage({ searchParams }: { searchParams: Promise<{ tickers?: string }> }) {
  const { tickers } = await searchParams;
  const list = (tickers ?? "").split(",").map((t) => t.trim().toUpperCase()).filter(Boolean).slice(0, 4);

  if (list.length < 2) {
    return (
      <main className="space-y-3">
        <h1 className="text-2xl font-semibold text-[var(--color-ink)]">Comparison</h1>
        <Card>
          <p className="text-[var(--color-ink-muted)]">Add at least 2 companies (max 4) to compare.</p>
        </Card>
      </main>
    );
  }

  const overviews = await Promise.all(list.map(getOverview));
  const verdictFor = (o: Overview, model: string) => o.verdict?.find((x) => x.model === model);
  const cellKey = (v: VerdictItem | undefined) =>
    !v ? "—" : v.band_label ?? (v.applicability !== "computed" ? v.applicability : String(v.aggregate_value ?? "—"));

  return (
    <main className="space-y-6">
      <section className="space-y-2">
        <p className="text-sm font-semibold uppercase tracking-wide text-[var(--color-brand-600)]">Comparison</p>
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
                      {!v ? (
                        <span className="text-[var(--color-ink-faint)]">—</span>
                      ) : v.applicability !== "computed" ? (
                        <Badge variant={applicabilityVariant(v.applicability)}>
                          {applicabilityLabel(v.applicability)}
                        </Badge>
                      ) : v.band_label ? (
                        <Badge variant={bandTone(v.band_label)} icon={false}>
                          {v.band_label}
                        </Badge>
                      ) : (
                        <span className="font-mono tabular-nums text-[var(--color-ink-muted)]">
                          {v.aggregate_value ?? "—"}
                        </span>
                      )}
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
