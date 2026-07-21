// Side-by-side comparison (FR-14): parallel columns of Verdicts/lens scores for
// 2-4 companies, with diverging classifications highlighted. Shows only the
// lenses live in the current phase, consistent with the overview's phase honesty.

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

export default async function ComparePage({ searchParams }: { searchParams: Promise<{ tickers?: string }> }) {
  const { tickers } = await searchParams;
  const list = (tickers ?? "").split(",").map((t) => t.trim().toUpperCase()).filter(Boolean).slice(0, 4);

  if (list.length < 2) {
    return (
      <main style={{ fontFamily: "system-ui, sans-serif", padding: "2rem" }}>
        <h1>Comparison</h1>
        <p>Add at least 2 companies (max 4) to compare.</p>
      </main>
    );
  }

  const overviews = await Promise.all(list.map(getOverview));
  const cell = (o: Overview, model: string) => {
    const v = o.verdict?.find((x) => x.model === model);
    if (!v) return "—";
    return v.band_label ?? (v.applicability !== "computed" ? v.applicability : String(v.aggregate_value ?? "—"));
  };

  return (
    <main style={{ fontFamily: "system-ui, sans-serif", padding: "2rem", maxWidth: 900 }}>
      <h1>Comparison</h1>
      <table style={{ borderCollapse: "collapse", width: "100%" }}>
        <thead>
          <tr>
            <th style={{ textAlign: "left", padding: 8, borderBottom: "2px solid #333" }}>Lens</th>
            {overviews.map((o) => (
              <th key={o.ticker} style={{ textAlign: "left", padding: 8, borderBottom: "2px solid #333" }}>
                {o.ticker}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {MODELS.map((model) => {
            const values = overviews.map((o) => cell(o, model));
            const diverges = new Set(values).size > 1;
            return (
              <tr key={model} style={{ background: diverges ? "#fff6e5" : undefined }}>
                <td style={{ padding: 8, borderBottom: "1px solid #ddd", fontWeight: 600 }}>{model}</td>
                {values.map((val, i) => (
                  <td key={i} style={{ padding: 8, borderBottom: "1px solid #ddd" }}>
                    {val}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
      <p style={{ color: "#666" }}>Rows where companies diverge are highlighted. Value &amp; Growth lenses arrive in a later phase.</p>
    </main>
  );
}
