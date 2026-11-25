/** What each data-quality warning is ABOUT (Ops 8).
 *
 *  The Integrity panel used to print only the issue type, so AAPL's page showed
 *  "Ambiguous source selection (needs_review, raised by canonicalization)" seventeen
 *  times and a reader could not tell FY2008 history from a current-year figure. The
 *  API already served the year, concept and competing values in `detail`; the page
 *  dropped them (`engineering-findings.yaml#data_quality_warnings_hide_year_and_concept`).
 *
 *  `detail` is free-form JSON written by several writers, so every key is optional
 *  here and an unrecognised shape degrades to the old one-line rendering rather than
 *  to nothing (AC 6). Shapes observed in the dev store and in the writers:
 *    ambiguous_selection         canonical_concept, fiscal_year, values[]
 *    source_conflict             taxonomy, concept, period_end, company_facts_value,
 *                                inline_xbrl_value, resolution
 *    unmapped_member             taxonomy, source_concept, member_as_filed, fiscal_year
 *    ambiguous_member_selection  canonical_concept, member_as_filed, fiscal_year
 */
import { issueLabel } from "../issueLabels";

export type DataQualityItem = {
  issue_type: string;
  status: string;
  raised_by: string;
  detail?: Record<string, unknown> | null;
};

export type DescribedIssue = {
  label: string;
  meta: string;
  /** "FY2008", or "period ending 2023-06-30" when the writer stored no fiscal year. */
  when: string | null;
  concept: string | null;
  member: string | null;
  /** Competing values, exact, each optionally prefixed with the source it came from. */
  values: string[];
  resolution: string | null;
  sortYear: number | null;
};

const PLAIN_DECIMAL = /^(-?)(\d+)(?:\.(\d+))?$/;

/** A stored figure shown EXACTLY (AC 4). `compactAmount` cannot be used here: it
 *  renders AAPL's FY2007 equity conflict (14,531,000,000 vs 14,532,000,000) as
 *  "14.53B" on both sides, erasing the difference the warning exists to show, and
 *  prints a 0.000006 vs 0.00000625 par value as "0" vs "0". Decimal strings are
 *  reformatted as text, never parsed into a float. */
export function exactValue(v: unknown): string {
  if (typeof v === "number") {
    return Number.isFinite(v) ? v.toLocaleString("en-US", { maximumFractionDigits: 20 }) : String(v);
  }
  if (typeof v !== "string") return String(v);
  const m = PLAIN_DECIMAL.exec(v.trim());
  if (!m) return v;
  const [, sign, int, frac = ""] = m;
  const grouped = int.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  const trimmed = frac.replace(/0+$/, "");
  return `${sign}${grouped}${trimmed ? `.${trimmed}` : ""}`;
}

function str(v: unknown): string | null {
  return typeof v === "string" && v.length > 0 ? v : null;
}

export function describeIssue(dq: DataQualityItem): DescribedIssue {
  const d = dq.detail ?? {};
  const fy = typeof d.fiscal_year === "number" ? d.fiscal_year : null;
  const periodEnd = str(d.period_end);

  let when: string | null = null;
  let sortYear: number | null = null;
  if (fy != null) {
    when = `FY${fy}`;
    sortYear = fy;
  } else if (periodEnd) {
    when = `period ending ${periodEnd}`;
    const y = Number(periodEnd.slice(0, 4));
    sortYear = Number.isInteger(y) ? y : null;
  }

  const sourceConcept = str(d.concept) ?? str(d.source_concept);
  const concept =
    str(d.canonical_concept) ??
    (sourceConcept ? (str(d.taxonomy) ? `${d.taxonomy}:${sourceConcept}` : sourceConcept) : null);

  let values: string[] = [];
  if (Array.isArray(d.values)) {
    values = d.values.map(exactValue);
  } else if ("company_facts_value" in d || "inline_xbrl_value" in d) {
    if (d.company_facts_value != null) values.push(`Company Facts ${exactValue(d.company_facts_value)}`);
    if (d.inline_xbrl_value != null) values.push(`Inline XBRL ${exactValue(d.inline_xbrl_value)}`);
  }

  return {
    label: issueLabel(dq.issue_type),
    meta: `${dq.status}, raised by ${dq.raised_by}`,
    when,
    concept,
    member: str(d.member_as_filed),
    values,
    resolution: str(d.resolution),
    sortYear,
  };
}

/** Newest year first (AC 5); warnings with no year go last, in their API order. */
export function describeIssues(items: DataQualityItem[]): DescribedIssue[] {
  return items
    .map((dq, i) => ({ i, d: describeIssue(dq) }))
    .sort((a, b) => {
      if (a.d.sortYear == null || b.d.sortYear == null) {
        if (a.d.sortYear == null && b.d.sortYear == null) return a.i - b.i;
        return a.d.sortYear == null ? 1 : -1;
      }
      return b.d.sortYear - a.d.sortYear || a.i - b.i;
    })
    .map((x) => x.d);
}
