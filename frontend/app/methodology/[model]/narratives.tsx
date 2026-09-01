// "Why this works" narratives and worked-example arithmetic config (Story 11.9).
//
// Every claim below is grounded in the model's own primary paper, read directly
// (not a secondary summary) before writing this file:
//   - Piotroski, J. (2000), "Value Investing...", Journal of Accounting Research
//     38 (Ivey Business School open copy, pp. 1-15 read in full: intro, lit
//     review, and section 2.3's per-signal + F_SCORE construction rationale).
//   - Altman, E. (1968), "Financial Ratios, Discriminant Analysis...",
//     Journal of Finance 23(4) (JSTOR scan, pp. 589-601 read in full: sections
//     I-IV covering MDA's rationale and each ratio's economic meaning).
//   - Beneish, M. (1999), "The Detection of Earnings Manipulation", Financial
//     Analysts Journal 55(5) (the freely available June 1999 preprint, all 6
//     pages — it ends at the sample-selection section, before the eight
//     variables are individually defined, so the explainer below only makes
//     primary-sourced claims about the five variables his own introduction
//     names explicitly: DSRI/receivables, GMI/margins, AQI/asset quality,
//     SGI/sales growth, TATA/accruals. DEPI, SGAI and LVGI are described
//     mechanically, from what they compute per beneish_v1.yaml, without
//     attributing an unverified causal claim to Beneish specifically).
//   - Sloan, R. (1996), "Do Stock Prices Fully Reflect Information in
//     Accruals and Cash Flows...", The Accounting Review (CUHK open copy,
//     read in full for the persistence mechanism and the market-fixation
//     explanation).
//
// The Beneish five-variable model (DEPI-vs-TATA coefficient question,
// `research-beneish-five-variable-model.md`) is not encoded anywhere in this
// product — `beneish_v1.yaml` ships only the eight-variable model — so it is
// out of scope for this page and not mentioned, rather than silently resolved.
//
// Coefficients and the Beneish constant below are Beneish (1999)'s own
// published numbers, identical to `beneish_v1.yaml` (confirmed by
// reconstructing QSR's real FY2023 M-score from them and matching the live
// API's `aggregate_value` to 6 decimal places). They are hardcoded here
// rather than added to the `/api/methodology` payload because the AC scopes
// this story to narrative content, not a new API field — and the formula's
// own `description` string already publishes them as text.

import type { ReactNode } from "react";
import { Term } from "../../components/ui/Term";

export const WORKED_EXAMPLE_TICKER: Record<string, string> = {
  piotroski: "QSR",
  altman: "QSR",
  beneish: "QSR",
  sloan: "QSR",
};

export const WHY_IT_WORKS: Record<string, ReactNode> = {
  piotroski: (
    <>
      <p>
        Piotroski built the F-Score for a specific, narrow problem: high book-to-market
        (&ldquo;value&rdquo;) stocks are financially distressed as a group, but that
        average hides enormous range — some are genuinely recovering, others are
        genuinely deteriorating, and the market rarely tells them apart because these
        firms are thinly followed, have little analyst coverage, and their own
        disclosures aren&rsquo;t seen as credible. That leaves the financial statements
        themselves as the most reliable source of information about which is which.
      </p>
      <p>
        The nine signals span three areas of a company&rsquo;s condition — profitability
        (e.g. is <Term id="roa_positive">ROA positive</Term> this year, and is it{" "}
        <Term id="roa_increasing">increasing</Term>?), funding and liquidity (e.g. is{" "}
        <Term id="leverage_decreasing">leverage falling</Term> and the{" "}
        <Term id="current_ratio_increasing">current ratio rising</Term>?), and operating
        efficiency (<Term id="gross_margin_increasing">margin</Term> and{" "}
        <Term id="asset_turnover_increasing">asset turnover</Term> trends). Each one is
        simple, cheap to compute from a filing, and unambiguous about which direction is
        good news for a distressed firm.
      </p>
      <p>
        Piotroski deliberately chose a sum of nine pass/fail signals over a fitted
        statistical model — his own description calls it &ldquo;a step back&rdquo; from
        the probability models used in prior research. A fitted model risks tuning
        itself to the historical sample it was built on; a plain count of how many
        signals point the right way is transparent, doesn&rsquo;t need re-estimating,
        and — in his tests — separated eventual winners from losers just as well.
      </p>
    </>
  ),
  altman: (
    <>
      <p>
        Before Altman, distress analysis meant reading ratios one at a time, and that is
        genuinely ambiguous: a company with a poor profitability record but strong
        liquidity is hard to call — is it in trouble, or not? Altman&rsquo;s own paper
        makes exactly this point to motivate the Z-score. Multiple discriminant analysis
        (MDA) replaces individual judgment calls with a single linear combination of
        ratios, fitted statistically to best separate companies that actually went
        bankrupt from those that didn&rsquo;t.
      </p>
      <p>
        Each of the five ratios captures a different dimension of financial health:{" "}
        <Term id="x1_working_capital">X1</Term> is short-term liquidity relative to
        size, <Term id="x2_retained_earnings">X2</Term> is cumulative profitability
        (and implicitly company age — a young firm hasn&rsquo;t had time to build
        retained earnings), <Term id="x3_ebit">X3</Term> is pure earning power
        independent of leverage or tax, <Term id="x4_market_value_equity">X4</Term> is
        how much of a solvency cushion the market itself is pricing in, and{" "}
        <Term id="x5_sales">X5</Term> is asset productivity.
      </p>
      <p>
        The paper reports a genuinely counterintuitive result that is the best argument
        for combining ratios rather than picking one: X5 (sales/total assets) is
        statistically insignificant on its own — a univariate test would likely have
        dropped it — yet it ranks second in contribution to the combined model, because
        of a strong negative correlation with X3 among bankrupt firms. A ratio that
        looks useless alone can still sharpen the combined picture.
      </p>
    </>
  ),
  beneish: (
    <>
      <p>
        Beneish&rsquo;s starting observation is that earnings manipulation almost always
        means inflating revenue or deflating expenses in ways that leave traces in
        specific places, not in the bottom-line number itself. His model looks directly
        at the accounts where the effects of that inflation would land, rather than at
        earnings.
      </p>
      <p>
        His own introduction names five variables as driving the probability of
        manipulation: an unusual rise in receivables relative to sales (
        <Term id="dsri">DSRI</Term>), deteriorating gross margins (
        <Term id="gmi">GMI</Term>), decreasing asset quality (<Term id="aqi">AQI</Term>
        ), high sales growth — the precondition, since growth firms face the most
        pressure to keep the story going (<Term id="sgi">SGI</Term>), and rising
        accruals relative to cash flow (<Term id="tata">TATA</Term>). The eight-variable
        model this product implements adds three further indices —{" "}
        <Term id="depi">DEPI</Term>, <Term id="sgai">SGAI</Term> and{" "}
        <Term id="lvgi">LVGI</Term> — which check further, related preconditions
        (a slowing depreciation rate, SG&amp;A not keeping pace with sales, rising
        leverage) consistent with the same story, though refining the model rather
        than being singled out in his own introduction.
      </p>
      <p>
        The reason to combine several indices rather than scrutinize one ratio is that
        manipulation rarely distorts a single line item in isolation — Beneish notes
        that variables capturing simultaneous bloating across asset accounts carry real
        predictive content, which a single ratio checked alone would miss.
      </p>
    </>
  ),
  sloan: (
    <>
      <p>
        Reported earnings are cash flow plus accruals. Accruals — the non-cash
        adjustments like booking a sale before the cash arrives — mechanically reverse
        over time: money accrued today either gets collected later or gets written off.
        Sloan&rsquo;s finding is that this makes the accrual component of today&rsquo;s
        earnings inherently less informative about next year&rsquo;s earnings than the
        cash component is, purely as a matter of how accrual accounting works.
      </p>
      <p>
        The reason this shows up in stock prices at all is what Sloan calls market
        &ldquo;fixation&rdquo;: investors tend to treat a dollar of earnings as a dollar
        of earnings, without disentangling how much of it came from cash versus
        accruals. A company with an unusually high{" "}
        <Term id="accruals_ratio">accruals ratio</Term> is priced as if this
        year&rsquo;s earnings level will persist — and when the accrual portion
        reverses the way accruals mechanically do, the market is caught by surprise.
      </p>
      <p className="text-[var(--color-ink-faint)]">
        One honest gap: Sloan&rsquo;s own paper sorts firms into return deciles rather
        than publishing a single bright-line cutoff. The 0.10 &ldquo;high
        accruals&rdquo; threshold this product uses is ThesisTrace&rsquo;s own working
        convention, not a number from the paper itself — flagged as pending
        verification in the underlying spec, and stated here rather than presented as
        Sloan&rsquo;s own rule.
      </p>
    </>
  ),
};

export const BENEISH_CONSTANT = -4.84;
export const BENEISH_COEFFICIENTS: Record<string, number> = {
  dsri: 0.92,
  gmi: 0.528,
  aqi: 0.404,
  sgi: 0.892,
  depi: 0.115,
  sgai: -0.172,
  tata: 4.679,
  lvgi: -0.327,
};
export const BENEISH_SIGNAL_ORDER = ["dsri", "gmi", "aqi", "sgi", "depi", "sgai", "tata", "lvgi"];
export const ALTMAN_SIGNAL_ORDER = [
  "x1_working_capital",
  "x2_retained_earnings",
  "x3_ebit",
  "x4_market_value_equity",
  "x5_sales",
];
