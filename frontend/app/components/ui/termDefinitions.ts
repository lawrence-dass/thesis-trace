// Versioned dataset backing the Term component (Story 11.5, D12 / AD-8):
// one definition per term, keyed consistently, never free text generated at
// render time. Presentation content only — it explains an already-published
// formula's own sub-signal, it never originates a figure or a judgment.
//
// Signal-key entries mirror `SIGNAL_LABEL` in `company/[ticker]/page.tsx`
// (Beneish's 8, Altman's 5, Sloan's 1 = 14) — Piotroski's 9 sub-signals are
// out of scope for this story and Story 11.7, which is explicit about the
// three models it extends the mechanism to.
export const TERM_DEFINITIONS_VERSION = "v1";

export const TERM_DEFINITIONS = {
  // Beneish M-Score sub-indices.
  dsri: "Days Sales in Receivables Index — year-over-year change in receivables relative to sales. A large jump can signal revenue inflation.",
  gmi: "Gross Margin Index — deteriorating margins add pressure toward manipulation.",
  aqi: "Asset Quality Index — rising non-core / soft assets relative to total assets.",
  sgi: "Sales Growth Index — high-growth firms face more pressure to manage earnings.",
  depi: "Depreciation Index — a slowing depreciation rate can inflate reported income.",
  sgai: "SG&A Index — a disproportionate rise can signal deteriorating sales efficiency.",
  tata: "Total Accruals to Total Assets — the non-cash component of reported earnings.",
  lvgi: "Leverage Index — rising leverage year over year.",

  // Altman Z-Score components.
  x1_working_capital: "(Current assets − current liabilities) ÷ total assets. Liquidity relative to size.",
  x2_retained_earnings: "Retained earnings ÷ total assets. A proxy for cumulative profitability and company age.",
  x3_ebit: "EBIT ÷ total assets. Operating earning power, independent of leverage or tax.",
  x4_market_value_equity: "Market value of equity ÷ total liabilities. How much of a leverage cushion the market itself is pricing in.",
  x5_sales: "Sales ÷ total assets. Asset turnover — how much revenue each dollar of assets generates.",

  // Sloan accruals.
  accruals_ratio: "(Net income − cash from operations) ÷ average total assets, across the two most recent fiscal years. The larger the accrual component of earnings, the lower the quality — accruals reverse; cash does not.",

  // General report jargon, not tied to one model's sub-signal set.
  "why-not-blended": "Each test measures something different — strength trend, distress distance, manipulation risk, earnings quality. Averaging them would hide which one is actually driving a concern. ThesisTrace never originates a combined figure; it only shows what each published model already outputs.",
} as const;

export type TermId = keyof typeof TERM_DEFINITIONS;
