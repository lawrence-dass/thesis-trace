// Company overview (FR-9, FR-10): transparent per-model Verdict juxtaposition,
// in-page expandable sub-factor breakdown, data-quality warnings, cited
// explanation. Presentation only — renders exactly what the read API returns,
// no scoring logic (AD-8).

import AddToCompare from "../../components/AddToCompare";
import { ReportNav, type ReportSection } from "../../components/ReportNav";
import { WhatChanged, type Changes } from "../../components/WhatChanged";
import { Badge, applicabilityLabel, applicabilityVariant, bandTone, signalVariant } from "../../components/ui/Badge";
import { Card } from "../../components/ui/Card";
import { CitationChip } from "../../components/ui/CitationChip";
import { Gauge, type BandClass } from "../../components/ui/Gauge";
import { TrajectoryChip, type Trajectory } from "../../components/ui/TrajectoryChip";
import {
  NearTermDebtShareCard,
  type NearTermDebtShare,
} from "../../components/NearTermDebtShare";
import {
  MaturityProfileCard,
  type MaturityProfile,
} from "../../components/MaturityProfile";
import { ReverseDcfCard, type ReverseDcf } from "../../components/ReverseDcf";
import { VerdictGlyph, type VerdictItem } from "../../components/VerdictGlyph";
import { RewardsRisks, type RewardRiskItem } from "../../components/RewardsRisks";
import { FundamentalsCard, type Fundamentals } from "../../components/Fundamentals";
import { AlertIcon, ChevronIcon } from "../../components/ui/icons";

// Report sections (Story 10.1, D12). Order is the reading order AND the nav
// order — Overview first (the Verdict, and from Story 10.2 the four-model
// glyph), Integrity & Evidence last, matching the four academic models'
// existing quality_health/integrity split onto Financial Health / Integrity
// & Evidence one-to-one.
const SECTIONS: ReportSection[] = [
  { id: "overview", label: "Overview" },
  { id: "valuation", label: "Valuation" },
  { id: "past-performance", label: "Past Performance" },
  { id: "financial-health", label: "Financial Health" },
  { id: "integrity-evidence", label: "Integrity & Evidence" },
];

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type Provenance = {
  accession_number: string;
  canonical_concept: string;
  fiscal_year: number;
  // null = filed tag; set = computed by ThesisTrace (see CitationChip).
  derivation?: string | null;
};
type Signal = { signal_key: string; status: string; value: number | null; provenance: Provenance[] };
type LensScore = {
  model: string;
  category: string;
  fiscal_year: number;
  aggregate_value: number | null;
  band_label: string | null;
  applicability: string;
  signals: Signal[];
  // ThesisTrace presentation rule (PRD OQ9) — shown next to the level, never
  // in place of it.
  trajectory?: Trajectory | null;
};
type DataQuality = { issue_type: string; status: string; raised_by: string };
type Overview = {
  state: string;
  cik?: string;
  ticker?: string;
  name?: string;
  scores?: LensScore[];
  // ThesisTrace presentation rule (PRD OQ9, Story 5.6). Newest year first.
  near_term_debt_share?: NearTermDebtShare[];
  // Story 5.7. Empty for most of the universe by structure — the component
  // renders nothing rather than a "missing" state.
  debt_maturity_profile?: MaturityProfile[];
  // Story 6.6. Latest resolvable fiscal year only. `null` when the filer
  // resolves no year at all; a filer that ran without resolving comes back as
  // an object carrying `insufficient_data` and its reason (AD-16).
  reverse_dcf?: ReverseDcf | null;
  data_quality?: DataQuality[];
  verdict?: VerdictItem[];
  lenses_pending?: string[];
  // Story 10.3. Empty when nothing qualifies — an honest empty state.
  rewards_risks?: RewardRiskItem[];
  // Story 10.4. Null when no fiscal year resolves both revenue and net income.
  fundamentals?: Fundamentals | null;
};
type Explanation = { model: string; text: string; citations: string[] };

const MODEL_LABEL: Record<string, string> = {
  piotroski: "Piotroski F-Score",
  altman: "Altman Z-Score",
  beneish: "Beneish M-Score",
  sloan: "Sloan Accruals",
};

// Plain-language teaching copy per model — what it measures and which
// direction is favorable. Presentational content, not a scoring input.
const MODEL_CAPTION: Record<string, string> = {
  piotroski: "Financial strength, scored 0–9. Higher is stronger.",
  altman: "Bankruptcy-risk score. Higher means safer.",
  beneish: "Earnings-manipulation risk. Lower (more negative) means safer.",
  sloan: "Accrual-based earnings quality. Lower means higher quality.",
};

// Plain-language names for a model's own sub-signals — used only to explain
// WHY an aggregate is missing (e.g. "Missing: Gross Margin, SG&A Ratio")
// rather than showing a bare dash with no reason. Presentational only; the
// underlying pass/fail/insufficient_data classification is never recomputed
// here (AD-8, AD-16).
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

const MODELS = ["piotroski", "altman", "beneish", "sloan"];

async function getBands(model: string): Promise<BandClass[]> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/methodology/${model}`, { cache: "no-store" });
    const body = (await res.json()) as { bands?: { classes?: BandClass[] } };
    return body.bands?.classes ?? [];
  } catch {
    return [];
  }
}

async function getAllBands(): Promise<Record<string, BandClass[]>> {
  const entries = await Promise.all(MODELS.map(async (m) => [m, await getBands(m)] as const));
  return Object.fromEntries(entries);
}

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

// FR-22. `since` is omitted so the API applies its default pivot — the instant
// before the most recent filing landed — which makes this section answer "what
// did the latest filing change?". A failure here must not take the page down:
// change detection is supplementary to the scores, so it degrades to absent
// rather than blocking the Verdict from rendering.
async function getChanges(ticker: string): Promise<Changes> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/companies/${ticker}/changes`, { cache: "no-store" });
    return (await res.json()) as Changes;
  } catch {
    return { state: "unreachable" };
  }
}

export default async function CompanyPage({ params }: { params: Promise<{ ticker: string }> }) {
  const { ticker } = await params;
  const data = await getOverview(ticker);
  const explanations = data.state === "ok" ? await getExplanations(ticker) : [];
  const explanationByModel = new Map(explanations.map((e) => [e.model, e]));
  const bandsByModel = data.state === "ok" ? await getAllBands() : {};
  const changes = data.state === "ok" ? await getChanges(ticker) : { state: "skipped" };

  if (data.state !== "ok") {
    return (
      <main className="mx-auto w-full max-w-5xl space-y-3">
        <h1 className="text-2xl font-semibold text-[var(--color-ink)]">{ticker.toUpperCase()}</h1>
        <Card>
          <p className="text-[var(--color-ink-muted)]">
            {data.state === "not_available" ? "Not yet covered by ThesisTrace." : "Backend unreachable."}
          </p>
        </Card>
      </main>
    );
  }

  // Renders one category's model cards — called once per report section
  // below rather than looped generically, now that each category has a
  // fixed, named home (quality_health -> Financial Health, integrity ->
  // Integrity & Evidence) instead of a page-order-derived heading.
  function renderLensCards(cat: string) {
    const lenses = data.scores?.filter((l) => l.category === cat) ?? [];
    return lenses.map((lens) => {
      const exp = explanationByModel.get(lens.model);
      return (
        <Card key={`${lens.model}-${lens.fiscal_year}`} className="p-0">
          {/* In-page expandable breakdown (FR-10) via native <details>. */}
          <details className="group">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-3 p-5">
              <span className="flex flex-wrap items-center gap-2.5">
                <span className="font-medium text-[var(--color-ink)]">{MODEL_LABEL[lens.model] ?? lens.model}</span>
                <span className="text-xs text-[var(--color-ink-faint)]">FY{lens.fiscal_year}</span>
                {lens.aggregate_value !== null ? (
                  <span className="font-mono text-sm tabular-nums text-[var(--color-ink-muted)]">
                    {lens.aggregate_value}
                  </span>
                ) : null}
                {lens.aggregate_value === null ? (
                  <Badge variant="pending">Insufficient data</Badge>
                ) : lens.applicability !== "computed" ? (
                  <Badge variant={applicabilityVariant(lens.applicability)}>
                    {applicabilityLabel(lens.applicability)}
                  </Badge>
                ) : lens.band_label ? (
                  <Badge variant={bandTone(lens.band_label)} icon={false}>
                    {lens.band_label}
                  </Badge>
                ) : null}
                {/* Alongside the level and the band, never replacing either —
                    and visually quieter than both, because this is our
                    annotation rather than the model's own classification
                    (Story 5.5). */}
                <TrajectoryChip trajectory={lens.trajectory} />
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
                    {s.provenance.length > 0 && data.cik ? (
                      <span className="flex flex-wrap items-center gap-1">
                        {s.provenance.map((p, i) => (
                          <CitationChip
                            key={i}
                            cik={data.cik!}
                            accessionNumber={p.accession_number}
                            canonicalConcept={p.canonical_concept}
                            fiscalYear={p.fiscal_year}
                            derivation={p.derivation ?? null}
                          />
                        ))}
                      </span>
                    ) : null}
                  </li>
                ))}
              </ul>
              <a
                href={`/methodology/${lens.model}`}
                className="inline-flex items-center gap-1 text-sm font-medium text-[var(--color-brand-link)] hover:text-[var(--color-brand-link-hover)]"
              >
                Methodology →
              </a>
            </div>
          </details>
        </Card>
      );
    });
  }

  const financialHealthLenses = renderLensCards("quality_health");
  const integrityLenses = renderLensCards("integrity");

  return (
    <main className="mx-auto w-full max-w-7xl space-y-10">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="font-mono text-sm font-semibold text-[var(--color-brand-link)]">{data.ticker}</p>
          <h1 className="text-2xl font-semibold tracking-tight text-[var(--color-ink)] sm:text-3xl">{data.name}</h1>
        </div>
        <AddToCompare ticker={data.ticker ?? ticker.toUpperCase()} />
      </div>

      {/* Persistent, scroll-tracking section nav (Story 10.1). -mx-6 cancels
          the page's own side padding so the bar spans full width like the
          site header above it, while its inner list still aligns to the
          same max-w-7xl content measure. */}
      <ReportNav sections={SECTIONS} />

      <section id="overview" className="scroll-mt-28 space-y-3">
        <h2 className="text-title font-semibold text-[var(--color-ink)]">Overview</h2>
        {/* Story 10.4: the scale and shape of the business — canonical facts
            only, no ThesisTrace judgment — before the forensic detail below. */}
        <FundamentalsCard data={data.fundamentals} cik={data.cik} />
        {/* Verdict: each live model's own cited classification, side by side (FR-9, AD-12). */}
        {data.verdict && data.verdict.length > 0 ? (
          <>
            {/* Story 10.2: the at-a-glance hero — four independent axes,
                never blended. Sits above the detail cards below, which are
                unchanged and still the place for the full per-model read. */}
            <VerdictGlyph verdict={data.verdict} />
            {/* Story 10.3: readable in ten seconds, evidence one click away —
                a SELECTION of the already-computed states above, not a new
                figure. Sits between the glyph and the full detail cards. */}
            <RewardsRisks items={data.rewards_risks ?? []} />
            <p className="text-sm text-[var(--color-ink-faint)]">
              Each model&apos;s own published threshold classification, shown side by side — not a
              buy/sell recommendation.
            </p>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              {data.verdict.map((v) => (
                <Card key={v.model} className="space-y-2">
                  <div className="text-xs font-semibold uppercase tracking-wide text-[var(--color-ink-faint)]">
                    {MODEL_LABEL[v.model] ?? v.model}
                  </div>
                  <div className="font-mono text-2xl font-semibold tabular-nums text-[var(--color-ink)]">
                    {v.aggregate_value ?? "—"}
                  </div>
                  {v.aggregate_value === null ? (
                    <Badge variant="pending">Insufficient data</Badge>
                  ) : v.applicability !== "computed" ? (
                    <Badge variant={applicabilityVariant(v.applicability)}>{applicabilityLabel(v.applicability)}</Badge>
                  ) : v.band_label ? (
                    <Badge variant={bandTone(v.band_label)} icon={false}>
                      {v.band_label}
                    </Badge>
                  ) : null}
                  {v.aggregate_value === null && v.missing_signals.length > 0 ? (
                    <p className="text-xs leading-snug text-[var(--color-ink-faint)]">
                      Missing: {v.missing_signals.map((k) => SIGNAL_LABEL[k] ?? k).join(", ")}
                    </p>
                  ) : null}
                  {v.aggregate_value !== null && v.applicability !== "excluded_out_of_scope" && bandsByModel[v.model]?.length ? (
                    <Gauge model={v.model} value={v.aggregate_value} bandLabel={v.band_label} bands={bandsByModel[v.model]} />
                  ) : null}
                  {MODEL_CAPTION[v.model] ? (
                    <p className="text-xs leading-snug text-[var(--color-ink-faint)]">{MODEL_CAPTION[v.model]}</p>
                  ) : null}
                </Card>
              ))}
            </div>
            {data.lenses_pending && data.lenses_pending.length > 0 ? (
              <p className="text-sm text-[var(--color-ink-faint)]">
                Pending lenses (future phase): {data.lenses_pending.join(", ")}.
              </p>
            ) : null}
          </>
        ) : (
          <RewardsRisks items={data.rewards_risks ?? []} />
        )}
      </section>

      {/* Story 6.6. A separate section from the Verdict grid, deliberately:
          these assumptions are ThesisTrace's own, and sitting beside the
          four published models would let the page read as though one of
          them produced the figure. */}
      <section id="valuation" className="scroll-mt-28 space-y-3">
        <h2 className="text-title font-semibold text-[var(--color-ink)]">Valuation</h2>
        <ReverseDcfCard dcf={data.reverse_dcf} cik={data.cik} />
      </section>

      {/* What changed since the latest filing (FR-22) now lives in its own
          section rather than above the Verdict — in a sectioned report the
          reader can jump straight to "what moved" via the nav, so physical
          position no longer has to carry that priority. */}
      <section id="past-performance" className="scroll-mt-28 space-y-3">
        <h2 className="text-title font-semibold text-[var(--color-ink)]">Past Performance</h2>
        <WhatChanged changes={changes} cik={data.cik ?? ""} />
      </section>

      <section id="financial-health" className="scroll-mt-28 space-y-3">
        <h2 className="text-title font-semibold text-[var(--color-ink)]">Financial Health</h2>
        <div className="space-y-3">
          {financialHealthLenses}
          {/* Near-term debt share sits inside Financial Health (Story 5.6),
              beneath the model cards — a standalone figure shown beside the
              scores, never blended into one. */}
          <NearTermDebtShareCard rows={data.near_term_debt_share ?? []} />
          {/* Supplementary detail beneath the share (Story 5.7). Renders
              nothing at all for a filer without a published schedule. */}
          <MaturityProfileCard profiles={data.debt_maturity_profile ?? []} cik={data.cik} />
        </div>
      </section>

      <section id="integrity-evidence" className="scroll-mt-28 space-y-3">
        <h2 className="text-title font-semibold text-[var(--color-ink)]">Integrity & Evidence</h2>
        <div className="space-y-3">
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
          {integrityLenses}
        </div>
      </section>
    </main>
  );
}
