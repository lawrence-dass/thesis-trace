// Methodology page per score (FR-11): formula, inputs, version, cited source.
// Presentation only — renders exactly what the read API returns (AD-8).

import { Card } from "../../components/ui/Card";
import { Term } from "../../components/ui/Term";
import { TERM_DEFINITIONS, type TermId } from "../../components/ui/termDefinitions";
import {
  ALTMAN_SIGNAL_ORDER,
  BENEISH_COEFFICIENTS,
  BENEISH_CONSTANT,
  BENEISH_SIGNAL_ORDER,
  WHY_IT_WORKS,
  WORKED_EXAMPLE_TICKER,
} from "./narratives";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// Every sub-signal key across all four models is wired to Term (Story 11.7) —
// a runtime check because `signal_key` is a string off the wire, not the
// fixed TermId union.
function isTermId(key: string): key is TermId {
  return Object.prototype.hasOwnProperty.call(TERM_DEFINITIONS, key);
}

type OverviewSignal = { signal_key: string; status: string; value: number | null };
type OverviewScore = {
  model: string;
  fiscal_year: number;
  aggregate_value: number | null;
  signals: OverviewSignal[];
};
type Overview = {
  state: string;
  ticker?: string;
  name?: string;
  verdict?: { model: string; fiscal_year: number }[];
  scores?: OverviewScore[];
};

async function getWorkedExample(model: string): Promise<{ name: string; ticker: string; run: OverviewScore } | null> {
  const ticker = WORKED_EXAMPLE_TICKER[model];
  if (!ticker) return null;
  try {
    const res = await fetch(`${API_BASE_URL}/api/companies/${ticker}/overview`, { cache: "no-store" });
    const overview = (await res.json()) as Overview;
    if (overview.state !== "ok" || !overview.verdict || !overview.scores) return null;
    const fiscalYear = overview.verdict.find((v) => v.model === model)?.fiscal_year;
    if (fiscalYear === undefined) return null;
    const run = overview.scores.find((s) => s.model === model && s.fiscal_year === fiscalYear);
    if (!run) return null;
    return { name: overview.name ?? ticker, ticker, run };
  } catch {
    return null;
  }
}

type Signal = { key: string; description: string };
type Derivation = {
  concept: string;
  rule: string;
  kind: "identity" | "decision";
  expression: string;
  rationale: string;
  only_when: string[];
};
type Methodology = {
  state: string;
  model?: string;
  formula_version?: string;
  description?: string;
  inputs?: string[];
  signals?: Signal[];
  source?: string;
  threshold?: Record<string, unknown> | null;
  derivations?: Derivation[];
};

async function getMethodology(model: string): Promise<Methodology> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/methodology/${model}`, { cache: "no-store" });
    return (await res.json()) as Methodology;
  } catch {
    return { state: "unreachable" };
  }
}

export default async function MethodologyPage({ params }: { params: Promise<{ model: string }> }) {
  const { model } = await params;
  const [m, workedExample] = await Promise.all([getMethodology(model), getWorkedExample(model)]);

  if (m.state !== "ok") {
    return (
      <main className="mx-auto w-full max-w-5xl space-y-3">
        <h1 className="text-2xl font-semibold text-[var(--color-ink)]">{model}</h1>
        <Card>
          <p className="text-[var(--color-ink-muted)]">
            {m.state === "not_available" ? "No methodology for this model." : "Backend unreachable."}
          </p>
        </Card>
      </main>
    );
  }

  return (
    <main className="mx-auto w-full max-w-5xl space-y-8">
      <section className="space-y-2">
        <p className="text-sm font-semibold uppercase tracking-wide text-[var(--color-brand-link)]">Methodology</p>
        <h1 className="text-2xl font-semibold tracking-tight text-[var(--color-ink)] sm:text-3xl">{m.model}</h1>
        <p className="font-mono text-sm text-[var(--color-ink-faint)]">{m.formula_version}</p>
      </section>

      <Card className="space-y-2">
        <p className="text-sm leading-relaxed text-[var(--color-ink-muted)]">{m.description}</p>
      </Card>

      {WHY_IT_WORKS[model] ? (
        <section className="space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--color-ink-faint)]">
            Why this works
          </h2>
          <Card className="space-y-3 text-sm leading-relaxed text-[var(--color-ink-muted)]">
            {WHY_IT_WORKS[model]}
          </Card>
        </section>
      ) : null}

      {m.inputs && m.inputs.length > 0 ? (
        <section className="space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--color-ink-faint)]">
            Inputs (canonical concepts)
          </h2>
          <div className="flex flex-wrap gap-2">
            {m.inputs.map((i) => (
              <span
                key={i}
                className="rounded-[var(--radius-control)] border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-1.5 font-mono text-xs text-[var(--color-ink-muted)]"
              >
                {i}
              </span>
            ))}
          </div>
        </section>
      ) : null}

      {m.signals && m.signals.length > 0 ? (
        <section className="space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--color-ink-faint)]">Signals</h2>
          <Card className="p-0">
            <ul>
              {m.signals.map((s, i) => (
                <li
                  key={s.key}
                  className={`p-4 text-sm ${i !== m.signals!.length - 1 ? "border-b border-[var(--color-border)]" : ""}`}
                >
                  <span className="font-mono font-medium text-[var(--color-ink)]">{s.key}</span>
                  <span className="text-[var(--color-ink-muted)]">: {s.description}</span>
                </li>
              ))}
            </ul>
          </Card>
        </section>
      ) : null}

      {m.derivations && m.derivations.length > 0 ? (
        <section className="space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--color-ink-faint)]">
            Computed inputs
          </h2>
          <p className="text-sm leading-relaxed text-[var(--color-ink-muted)]">
            Some filers do not report every input this model needs as a tagged line item. Where that
            happens, ThesisTrace computes the input rather than reading it, and says so here. A
            figure computed this way is never presented as a reported one.
          </p>
          <div className="space-y-3">
            {m.derivations.map((d) => (
              <Card key={d.rule} className="space-y-3">
                <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
                  <span className="font-mono text-sm font-medium text-[var(--color-ink)]">
                    {d.concept}
                  </span>
                  <span
                    className={`rounded-[var(--radius-control)] border px-2 py-0.5 text-xs font-semibold uppercase tracking-wide ${
                      d.kind === "decision"
                        ? "border-[var(--color-signal-caveat-border)] bg-[var(--color-signal-caveat-bg)] text-[var(--color-signal-caveat)]"
                        : "border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-ink-faint)]"
                    }`}
                  >
                    {d.kind === "decision" ? "Our judgment" : "Accounting identity"}
                  </span>
                </div>

                <p className="font-mono text-sm text-[var(--color-ink-muted)]">
                  {d.concept} = {d.expression}
                </p>

                {d.only_when.length > 0 ? (
                  <p className="text-xs text-[var(--color-ink-faint)]">
                    Applied only when {d.only_when.join("; ")}.
                  </p>
                ) : null}

                <p className="text-sm leading-relaxed text-[var(--color-ink-muted)]">
                  {d.rationale}
                </p>
              </Card>
            ))}
          </div>
        </section>
      ) : null}

      {workedExample ? (
        <section className="space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--color-ink-faint)]">
            Worked example — {workedExample.name} ({workedExample.ticker}), FY{workedExample.run.fiscal_year}
          </h2>
          <Card className="space-y-3">
            <p className="text-sm leading-relaxed text-[var(--color-ink-muted)]">
              Every figure below is {workedExample.ticker}&rsquo;s actual stored value for this fiscal
              year — the same data feeding {workedExample.ticker}&rsquo;s own report, not an
              illustrative example.
            </p>
            <ul className="space-y-1.5 text-sm text-[var(--color-ink-muted)]">
              {renderWorkedExampleRows(model, m.signals, workedExample.run)}
            </ul>
            <p className="border-t border-[var(--color-border)] pt-3 text-sm font-semibold text-[var(--color-ink)]">
              = {workedExample.run.aggregate_value} — the {m.model} score shown on{" "}
              {workedExample.ticker}&rsquo;s report for this year.
            </p>
          </Card>
        </section>
      ) : null}

      {m.source ? (
        <p className="text-sm text-[var(--color-ink-muted)]">
          <span className="font-semibold text-[var(--color-ink)]">Source: </span>
          {m.source}
        </p>
      ) : null}
    </main>
  );
}

function signalLabel(key: string) {
  return isTermId(key) ? <Term id={key}>{key}</Term> : <span className="font-mono">{key}</span>;
}

function renderWorkedExampleRows(model: string, methodologySignals: Signal[] | undefined, run: OverviewScore) {
  const byKey = new Map(run.signals.map((s) => [s.signal_key, s]));
  const describe = (key: string) => methodologySignals?.find((s) => s.key === key)?.description ?? key;

  if (model === "piotroski") {
    const passCount = run.signals.filter((s) => s.status === "pass").length;
    return (
      <>
        {(methodologySignals ?? []).map((sig) => {
          const found = byKey.get(sig.key);
          const outcome =
            found?.status === "pass" ? "PASS (+1)" : found?.status === "fail" ? "FAIL (+0)" : "insufficient data";
          return (
            <li key={sig.key}>
              {signalLabel(sig.key)} — {sig.description} → <span className="font-mono">{outcome}</span>
            </li>
          );
        })}
        <li className="pt-1 text-[var(--color-ink)]">
          {passCount} of 9 signals passed → F_SCORE = {run.aggregate_value}.
        </li>
      </>
    );
  }

  if (model === "altman") {
    return ALTMAN_SIGNAL_ORDER.map((key) => {
      const value = byKey.get(key)?.value;
      return (
        <li key={key}>
          {signalLabel(key)} <span className="font-mono">({describe(key)}) = {value ?? "—"}</span>
        </li>
      );
    });
  }

  if (model === "beneish") {
    return BENEISH_SIGNAL_ORDER.map((key) => {
      const raw = byKey.get(key)?.value;
      const coeff = BENEISH_COEFFICIENTS[key];
      const contribution = raw !== null && raw !== undefined ? raw * coeff : null;
      return (
        <li key={key}>
          {signalLabel(key)}{" "}
          <span className="font-mono">
            = {raw ?? "—"} &times; {coeff} = {contribution !== null ? contribution.toFixed(6) : "—"}
          </span>
        </li>
      );
    }).concat(
      <li key="constant" className="text-[var(--color-ink)]">
        Plus Beneish&rsquo;s constant, {BENEISH_CONSTANT}.
      </li>,
    );
  }

  // Sloan: a single ratio that IS the aggregate — no further arithmetic to show.
  return (methodologySignals ?? []).map((sig) => {
    const value = byKey.get(sig.key)?.value;
    return (
      <li key={sig.key}>
        {signalLabel(sig.key)} — {sig.description} = <span className="font-mono">{value ?? "—"}</span>
      </li>
    );
  });
}
