// Company overview (FR-9, FR-10): transparent per-model Verdict juxtaposition,
// in-page expandable sub-factor breakdown, data-quality warnings, cited
// explanation. Presentation only — renders exactly what the read API returns,
// no scoring logic (AD-8).

import AddToCompare from "../../components/AddToCompare";
import { Badge, applicabilityLabel, applicabilityVariant, bandTone, signalVariant } from "../../components/ui/Badge";
import { Card } from "../../components/ui/Card";
import { AlertIcon, ChevronIcon } from "../../components/ui/icons";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type Provenance = { accession_number: string; canonical_concept: string; fiscal_year: number };
type Signal = { signal_key: string; status: string; value: number | null; provenance: Provenance[] };
type LensScore = {
  model: string;
  category: string;
  fiscal_year: number;
  aggregate_value: number | null;
  band_label: string | null;
  applicability: string;
  signals: Signal[];
};
type DataQuality = { issue_type: string; status: string; raised_by: string };
type VerdictItem = {
  model: string;
  category: string;
  fiscal_year: number;
  aggregate_value: number | null;
  band_label: string | null;
  applicability: string;
};
type Overview = {
  state: string;
  ticker?: string;
  name?: string;
  scores?: LensScore[];
  data_quality?: DataQuality[];
  verdict?: VerdictItem[];
  lenses_pending?: string[];
};
type Explanation = { model: string; text: string; citations: string[] };

const CATEGORY_LABEL: Record<string, string> = {
  quality_health: "Quality & Health",
  integrity: "Integrity & Evidence",
};

const MODEL_LABEL: Record<string, string> = {
  piotroski: "Piotroski F-Score",
  altman: "Altman Z-Score",
  beneish: "Beneish M-Score",
  sloan: "Sloan Accruals",
};

async function getExplanations(ticker: string): Promise<Explanation[]> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/companies/${ticker}/explanation`, { cache: "no-store" });
    const body = (await res.json()) as { explanations?: Explanation[] };
    return body.explanations ?? [];
  } catch {
    return [];
  }
}

async function getOverview(ticker: string): Promise<Overview> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/companies/${ticker}/overview`, { cache: "no-store" });
    return (await res.json()) as Overview;
  } catch {
    return { state: "unreachable" };
  }
}

export default async function CompanyPage({ params }: { params: Promise<{ ticker: string }> }) {
  const { ticker } = await params;
  const data = await getOverview(ticker);
  const explanations = data.state === "ok" ? await getExplanations(ticker) : [];
  const explanationByModel = new Map(explanations.map((e) => [e.model, e]));

  if (data.state !== "ok") {
    return (
      <main className="space-y-3">
        <h1 className="text-2xl font-semibold text-[var(--color-ink)]">{ticker.toUpperCase()}</h1>
        <Card>
          <p className="text-[var(--color-ink-muted)]">
            {data.state === "not_available" ? "Not yet covered by ThesisTrace." : "Backend unreachable."}
          </p>
        </Card>
      </main>
    );
  }

  const categories = ["quality_health", "integrity"];

  return (
    <main className="space-y-10">
      <section className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="font-mono text-sm font-semibold text-[var(--color-brand-600)]">{data.ticker}</p>
          <h1 className="text-2xl font-semibold tracking-tight text-[var(--color-ink)] sm:text-3xl">{data.name}</h1>
        </div>
        <AddToCompare ticker={data.ticker ?? ticker.toUpperCase()} />
      </section>

      {/* Verdict: each live model's own cited classification, side by side (FR-9, AD-12). */}
      {data.verdict && data.verdict.length > 0 ? (
        <section className="space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--color-ink-faint)]">Verdict</h2>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            {data.verdict.map((v) => (
              <Card key={v.model} className="space-y-2">
                <div className="text-xs font-semibold uppercase tracking-wide text-[var(--color-ink-faint)]">
                  {MODEL_LABEL[v.model] ?? v.model}
                </div>
                <div className="font-mono text-2xl font-semibold tabular-nums text-[var(--color-ink)]">
                  {v.aggregate_value ?? "—"}
                </div>
                {v.applicability !== "computed" ? (
                  <Badge variant={applicabilityVariant(v.applicability)}>{applicabilityLabel(v.applicability)}</Badge>
                ) : v.band_label ? (
                  <Badge variant={bandTone(v.band_label)} icon={false}>
                    {v.band_label}
                  </Badge>
                ) : null}
              </Card>
            ))}
          </div>
          {data.lenses_pending && data.lenses_pending.length > 0 ? (
            <p className="text-sm text-[var(--color-ink-faint)]">
              Pending lenses (future phase): {data.lenses_pending.join(", ")}.
            </p>
          ) : null}
        </section>
      ) : null}

      {data.data_quality && data.data_quality.length > 0 ? (
        <div className="flex gap-3 rounded-[var(--radius-card)] border border-[var(--color-signal-caveat-border)] bg-[var(--color-signal-caveat-bg)] p-4">
          <AlertIcon className="mt-0.5 h-4 w-4 flex-shrink-0 text-[var(--color-signal-caveat)]" />
          <div className="space-y-1 text-sm">
            <p className="font-semibold text-[var(--color-signal-caveat)]">Data-quality warnings</p>
            <ul className="space-y-0.5 text-[var(--color-ink-muted)]">
              {data.data_quality.map((dq, i) => (
                <li key={i}>
                  {dq.issue_type}{" "}
                  <span className="text-[var(--color-ink-faint)]">
                    ({dq.status}, raised by {dq.raised_by})
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      ) : null}

      {categories.map((cat) => {
        const lenses = data.scores?.filter((l) => l.category === cat) ?? [];
        if (lenses.length === 0) return null;
        return (
          <section key={cat} className="space-y-3">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--color-ink-faint)]">
              {CATEGORY_LABEL[cat] ?? cat}
            </h2>
            <div className="space-y-3">
              {lenses.map((lens) => {
                const exp = explanationByModel.get(lens.model);
                return (
                  <Card key={`${lens.model}-${lens.fiscal_year}`} className="p-0">
                    {/* In-page expandable breakdown (FR-10) via native <details>. */}
                    <details className="group">
                      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 p-5">
                        <span className="flex flex-wrap items-center gap-2.5">
                          <span className="font-medium text-[var(--color-ink)]">
                            {MODEL_LABEL[lens.model] ?? lens.model}
                          </span>
                          <span className="text-xs text-[var(--color-ink-faint)]">FY{lens.fiscal_year}</span>
                          {lens.aggregate_value !== null ? (
                            <span className="font-mono text-sm tabular-nums text-[var(--color-ink-muted)]">
                              {lens.aggregate_value}
                            </span>
                          ) : null}
                          {lens.applicability !== "computed" ? (
                            <Badge variant={applicabilityVariant(lens.applicability)}>
                              {applicabilityLabel(lens.applicability)}
                            </Badge>
                          ) : lens.band_label ? (
                            <Badge variant={bandTone(lens.band_label)} icon={false}>
                              {lens.band_label}
                            </Badge>
                          ) : null}
                        </span>
                        <ChevronIcon className="h-4 w-4 flex-shrink-0 text-[var(--color-ink-faint)] transition-transform group-open:rotate-180" />
                      </summary>

                      <div className="space-y-4 border-t border-[var(--color-border)] p-5">
                        {exp ? <p className="text-sm leading-relaxed text-[var(--color-ink-muted)]">{exp.text}</p> : null}
                        <ul className="space-y-2">
                          {lens.signals.map((s) => (
                            <li
                              key={s.signal_key}
                              className="flex flex-wrap items-center gap-2 border-b border-[var(--color-border)] pb-2 text-sm last:border-0 last:pb-0"
                            >
                              <Badge variant={signalVariant(s.status)}>{s.signal_key}</Badge>
                              {s.value !== null ? (
                                <span className="font-mono tabular-nums text-[var(--color-ink-muted)]">{s.value}</span>
                              ) : null}
                              {s.provenance.length > 0 ? (
                                <span className="text-xs text-[var(--color-ink-faint)]">
                                  {s.provenance.map((p) => `${p.canonical_concept} FY${p.fiscal_year}`).join(", ")}
                                </span>
                              ) : null}
                            </li>
                          ))}
                        </ul>
                        <a
                          href={`/methodology/${lens.model}`}
                          className="inline-flex items-center gap-1 text-sm font-medium text-[var(--color-brand-600)] hover:text-[var(--color-brand-700)]"
                        >
                          Methodology →
                        </a>
                      </div>
                    </details>
                  </Card>
                );
              })}
            </div>
          </section>
        );
      })}
    </main>
  );
}
