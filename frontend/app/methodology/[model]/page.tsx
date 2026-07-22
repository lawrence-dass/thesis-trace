// Methodology page per score (FR-11): formula, inputs, version, cited source.
// Presentation only — renders exactly what the read API returns (AD-8).

import { Card } from "../../components/ui/Card";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type Signal = { key: string; description: string };
type Methodology = {
  state: string;
  model?: string;
  formula_version?: string;
  description?: string;
  inputs?: string[];
  signals?: Signal[];
  source?: string;
  threshold?: Record<string, unknown> | null;
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
  const m = await getMethodology(model);

  if (m.state !== "ok") {
    return (
      <main className="space-y-3">
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
    <main className="space-y-8">
      <section className="space-y-2">
        <p className="text-sm font-semibold uppercase tracking-wide text-[var(--color-brand-600)]">Methodology</p>
        <h1 className="text-2xl font-semibold tracking-tight text-[var(--color-ink)] sm:text-3xl">{m.model}</h1>
        <p className="font-mono text-sm text-[var(--color-ink-faint)]">{m.formula_version}</p>
      </section>

      <Card className="space-y-2">
        <p className="text-sm leading-relaxed text-[var(--color-ink-muted)]">{m.description}</p>
      </Card>

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

      {m.source ? (
        <p className="text-sm text-[var(--color-ink-muted)]">
          <span className="font-semibold text-[var(--color-ink)]">Source: </span>
          {m.source}
        </p>
      ) : null}
    </main>
  );
}
