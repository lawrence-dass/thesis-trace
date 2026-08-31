// Provenance and freshness footer (Story 10.6, D12). Renders exactly what
// the read API returns (AD-8) — every statement here is read from stored
// data, nothing hardcoded. A source the filer does not use is simply absent
// from `sources`, never listed with a "not used" caveat (the AC's own
// wording) — this component trusts the API to have already made that call
// rather than re-deciding it from other fields.

import { edgarFilingUrl } from "./ui/CitationChip";
import { ExternalLinkIcon } from "./ui/icons";

export type DataSource = { name: string; detail: string | null };
export type FormulaVersion = { model: string; version: string };
export type ReportFooter = {
  sources: DataSource[];
  latest_accession_number: string | null;
  latest_filing_date: string | null;
  latest_filing_form: string | null;
  last_pipeline_run: string | null;
  mapping_version: string;
  formula_versions: FormulaVersion[];
};

const MODEL_LABEL: Record<string, string> = {
  piotroski: "Piotroski F-Score",
  altman: "Altman Z-Score",
  beneish: "Beneish M-Score",
  sloan: "Sloan Accruals",
};

export function formatDateTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZoneName: "short",
  });
}

export function ProvenanceFooter({ footer, cik }: { footer?: ReportFooter | null; cik?: string }) {
  if (!footer) return null;

  return (
    <footer className="space-y-4 border-t border-[var(--color-border)] pt-6 text-label text-[var(--color-ink-muted)]">
      <h2 className="text-caption font-semibold uppercase tracking-[var(--tracking-label)] text-[var(--color-ink-faint)]">
        Data and provenance
      </h2>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="space-y-1">
          <p className="text-[var(--color-ink-faint)]">Sources used for this filer</p>
          <ul className="space-y-0.5">
            {footer.sources.map((s) => (
              <li key={s.name}>
                {s.name}
                {s.detail ? <span className="text-[var(--color-ink-faint)]"> ({s.detail})</span> : null}
              </li>
            ))}
          </ul>
        </div>

        <div className="space-y-1">
          <p className="text-[var(--color-ink-faint)]">Latest filing</p>
          {footer.latest_accession_number && cik ? (
            <a
              href={edgarFilingUrl(cik, footer.latest_accession_number)}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-[var(--color-brand-link)] no-underline hover:text-[var(--color-brand-link-hover)]"
            >
              {footer.latest_filing_form ?? "Filing"}
              {footer.latest_filing_date ? `, filed ${footer.latest_filing_date}` : ""}
              <ExternalLinkIcon className="h-3 w-3 flex-shrink-0" />
            </a>
          ) : (
            <p>Not available.</p>
          )}
        </div>

        <div className="space-y-1">
          <p className="text-[var(--color-ink-faint)]">Last pipeline run</p>
          <p>{footer.last_pipeline_run ? formatDateTime(footer.last_pipeline_run) : "Not yet run."}</p>
        </div>

        <div className="space-y-1">
          <p className="text-[var(--color-ink-faint)]">Mapping and formula versions in force</p>
          <ul className="space-y-0.5">
            <li>Canonicalization: {footer.mapping_version}</li>
            {footer.formula_versions.map((fv) => (
              <li key={fv.model}>
                {MODEL_LABEL[fv.model] ?? fv.model}: {fv.version}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </footer>
  );
}
