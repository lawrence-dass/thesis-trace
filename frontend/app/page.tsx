// Landing page: Company Universe starter list (FR-1) + ticker search (FR-2).
// Presentation only (AD-8). No auth (D4).

import SearchBox from "./components/SearchBox";
import { Card } from "./components/ui/Card";
import { ArrowRightIcon } from "./components/ui/icons";
import { apiGetAtBuild } from "./lib/api";

type CompanyCard = { cik: string; ticker: string; name: string; last_updated: string | null };

// Throws when the API is unreachable (app/lib/api.ts): an empty universe list
// cached for an hour would look like ThesisTrace covers nothing.
async function getCompanies(): Promise<CompanyCard[]> {
  return apiGetAtBuild<CompanyCard[]>("/api/companies", []);
}

export default async function Home() {
  const companies = await getCompanies();

  return (
    <main className="mx-auto w-full max-w-5xl space-y-10">
      <section className="space-y-3">
        <p className="text-sm font-semibold uppercase tracking-wide text-[var(--color-brand-link)]">
          Evidence-backed equity intelligence
        </p>
        <h1 className="text-3xl font-semibold tracking-tight text-[var(--color-ink)] sm:text-4xl">
          Deterministic forensic scores, traced to the filing.
        </h1>
        <p className="max-w-2xl text-base leading-relaxed text-[var(--color-ink-muted)]">
          Four transparent lenses computed directly from SEC EDGAR filings — never an LLM-invented
          number. Every score links back to the exact line item it came from.
        </p>
        <SearchBox />
      </section>

      <section className="space-y-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--color-ink-faint)]">
          Company Universe
        </h2>

        {companies.length === 0 ? (
          <Card className="text-center text-[var(--color-ink-muted)]">
            No companies available yet — the pipeline hasn&apos;t run for this environment.
          </Card>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {companies.map((c) => (
              <Card key={c.cik} href={`/company/${c.ticker}`} className="group flex flex-col gap-1">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-lg font-semibold tracking-tight text-[var(--color-ink)]">
                    {c.ticker}
                  </span>
                  <ArrowRightIcon className="h-4 w-4 text-[var(--color-ink-faint)] transition-transform group-hover:translate-x-0.5 group-hover:text-[var(--color-brand-link)]" />
                </div>
                <div className="text-sm text-[var(--color-ink-muted)]">{c.name}</div>
                {c.last_updated ? (
                  <div className="pt-2 text-xs text-[var(--color-ink-faint)]">
                    Updated {c.last_updated.slice(0, 10)}
                  </div>
                ) : null}
              </Card>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
