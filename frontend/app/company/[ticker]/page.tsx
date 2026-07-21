// Thin company overview (Story 1.8): renders the read-API scores + provenance.
// This is a skeleton view; the full Verdict/overview UI is Epic 3 (FR-9/FR-10).
// Presentation only — renders exactly what the API returns (AD-8).

import AddToCompare from "../../components/AddToCompare";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type Provenance = {
  accession_number: string;
  canonical_concept: string;
  fiscal_year: number;
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
      <main style={{ fontFamily: "system-ui, sans-serif", padding: "2rem" }}>
        <h1>{ticker.toUpperCase()}</h1>
        <p>{data.state === "not_available" ? "Not yet covered." : "Backend unreachable."}</p>
      </main>
    );
  }

  const categories = ["quality_health", "integrity"];

  return (
    <main style={{ fontFamily: "system-ui, sans-serif", padding: "2rem", maxWidth: 760 }}>
      <h1>
        {data.name} ({data.ticker})
      </h1>

      <AddToCompare ticker={data.ticker ?? ticker.toUpperCase()} />

      {/* Verdict: each live model's own cited classification, side by side (FR-9, AD-12). */}
      {data.verdict && data.verdict.length > 0 ? (
        <section style={{ marginBottom: "1.5rem" }}>
          <h2>Verdict</h2>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem" }}>
            {data.verdict.map((v) => (
              <div key={v.model} style={{ border: "1px solid #ccc", borderRadius: 6, padding: "0.5rem 0.75rem", minWidth: 150 }}>
                <div style={{ fontWeight: 600 }}>{v.model}</div>
                <div>{v.aggregate_value ?? "—"}</div>
                <div style={{ color: "#444" }}>{v.band_label ?? (v.applicability !== "computed" ? v.applicability : "—")}</div>
              </div>
            ))}
          </div>
          {data.lenses_pending && data.lenses_pending.length > 0 ? (
            <p style={{ color: "#666" }}>
              Pending lenses (future phase): {data.lenses_pending.join(", ")}.
            </p>
          ) : null}
        </section>
      ) : null}

      {data.data_quality && data.data_quality.length > 0 ? (
        <section style={{ background: "#fff6e5", border: "1px solid #e0b050", padding: "0.75rem 1rem", marginBottom: "1.5rem" }}>
          <strong>Data-quality warnings</strong>
          <ul>
            {data.data_quality.map((dq, i) => (
              <li key={i}>
                {dq.issue_type} <span style={{ color: "#666" }}>({dq.status}, raised by {dq.raised_by})</span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {categories.map((cat) => {
        const lenses = data.scores?.filter((l) => l.category === cat) ?? [];
        if (lenses.length === 0) return null;
        return (
          <div key={cat}>
            <h2>{CATEGORY_LABEL[cat] ?? cat}</h2>
            {lenses.map((lens) => {
              const exp = explanationByModel.get(lens.model);
              return (
                <section key={`${lens.model}-${lens.fiscal_year}`} style={{ marginBottom: "1rem" }}>
                  {/* In-page expandable breakdown (FR-10) via native <details>. */}
                  <details>
                    <summary style={{ cursor: "pointer", fontWeight: 600 }}>
                      {lens.model} — FY{lens.fiscal_year}
                      {lens.aggregate_value !== null ? ` · ${lens.aggregate_value}` : ""}
                      {lens.band_label ? ` · ${lens.band_label}` : ""}
                      {lens.applicability !== "computed" ? ` · [${lens.applicability}]` : ""}
                    </summary>
                    {exp ? <p style={{ color: "#333" }}>{exp.text}</p> : null}
                    <ul>
                      {lens.signals.map((s) => (
                        <li key={s.signal_key}>
                          <strong>{s.signal_key}</strong>: {s.status}
                          {s.value !== null ? ` (${s.value})` : ""}
                          {s.provenance.length > 0 ? (
                            <span style={{ color: "#666" }}>
                              {" "}
                              — {s.provenance.map((p) => `${p.canonical_concept} FY${p.fiscal_year}`).join(", ")}
                            </span>
                          ) : null}
                        </li>
                      ))}
                    </ul>
                    <a href={`/methodology/${lens.model}`}>Methodology →</a>
                  </details>
                </section>
              );
            })}
          </div>
        );
      })}
    </main>
  );
}
