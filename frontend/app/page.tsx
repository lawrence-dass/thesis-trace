// Landing page: Company Universe starter list (FR-1) + ticker search (FR-2).
// Presentation only (AD-8). No auth (D4).

import SearchBox from "./components/SearchBox";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type Card = { cik: string; ticker: string; name: string; last_updated: string | null };

async function getCompanies(): Promise<Card[]> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/companies`, { cache: "no-store" });
    return (await res.json()) as Card[];
  } catch {
    return [];
  }
}

export default async function Home() {
  const companies = await getCompanies();

  return (
    <main style={{ fontFamily: "system-ui, sans-serif", padding: "2rem", maxWidth: 760 }}>
      <h1>ThesisTrace</h1>
      <p>Evidence-backed equity intelligence. Deterministic forensic scores with provenance — never an LLM-invented number.</p>

      <SearchBox />

      <h2>Company Universe</h2>
      {companies.length === 0 ? (
        <p style={{ color: "#666" }}>No companies available yet.</p>
      ) : (
        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem" }}>
          {companies.map((c) => (
            <a
              key={c.cik}
              href={`/company/${c.ticker}`}
              style={{ border: "1px solid #ccc", borderRadius: 6, padding: "0.75rem 1rem", minWidth: 180, textDecoration: "none", color: "inherit" }}
            >
              <div style={{ fontWeight: 600 }}>{c.ticker}</div>
              <div>{c.name}</div>
              {c.last_updated ? (
                <div style={{ color: "#666", fontSize: "0.85rem" }}>Updated {c.last_updated.slice(0, 10)}</div>
              ) : null}
            </a>
          ))}
        </div>
      )}
    </main>
  );
}
