// Provenance citation, promoted from plain gray text to a real link to the
// source SEC EDGAR filing (AD-19; PRD UJ-1/UJ-2's core differentiator).
// Outlined and transparent rather than filled, so it reads as a reference/
// footnote and never competes visually with the tri-state signal palette
// (DESIGN.md Components — Citation chip). The URL is constructed client-side
// from cik + accession_number; no backend change needed.
import { ExternalLinkIcon } from "./icons";

function edgarFilingUrl(cik: string, accessionNumber: string): string {
  const cikNoLeadingZeros = String(Number(cik));
  const accessionNoDashes = accessionNumber.replace(/-/g, "");
  return `https://www.sec.gov/Archives/edgar/data/${cikNoLeadingZeros}/${accessionNoDashes}/`;
}

export function CitationChip({
  cik,
  accessionNumber,
  canonicalConcept,
  fiscalYear,
}: {
  cik: string;
  accessionNumber: string;
  canonicalConcept: string;
  fiscalYear: number;
}) {
  return (
    <a
      href={edgarFilingUrl(cik, accessionNumber)}
      target="_blank"
      rel="noopener noreferrer"
      title={`View source filing on SEC EDGAR (accession ${accessionNumber})`}
      className="inline-flex items-center gap-1 rounded-[var(--radius-chip)] border border-[var(--color-border)] px-2 py-0.5 text-[var(--text-caption)] text-[var(--color-ink-faint)] transition-colors hover:border-[var(--color-border-strong)] hover:text-[var(--color-ink-muted)]"
    >
      <span>{canonicalConcept}</span>
      <span className="font-mono tabular-nums">FY{fiscalYear}</span>
      <ExternalLinkIcon className="h-3 w-3 flex-shrink-0" />
    </a>
  );
}
