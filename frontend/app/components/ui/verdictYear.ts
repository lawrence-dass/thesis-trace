// The fiscal year a verdict comes from, stated beside it.
//
// The verdict shows each model's latest year WITH a value (an insufficient newer
// year must not hide a valid older one; see api/repository.py's verdict
// selection). So the models on one card row can come from different years: QSR's
// Beneish is FY2020 while its other models are FY2025 (Ops 5), SHOP's Beneish
// FY2024. Without the year, an older figure reads as current (Ops 5 review).

type Dated = { fiscal_year: number };

/** The newest fiscal year among a company's verdicts: what "current" means here. */
export function newestVerdictYear(verdicts: readonly Dated[]): number | null {
  return verdicts.length ? Math.max(...verdicts.map((v) => v.fiscal_year)) : null;
}

/** "FY2025", or "FY2020 · later years insufficient" when it lags the newest. */
export function verdictYearLabel(fiscalYear: number, newestYear: number | null): string {
  const label = `FY${fiscalYear}`;
  return newestYear !== null && fiscalYear < newestYear ? `${label} · later years insufficient` : label;
}

/** True when a verdict is older than the company's newest one. */
export function isBackdated(fiscalYear: number, newestYear: number | null): boolean {
  return newestYear !== null && fiscalYear < newestYear;
}
