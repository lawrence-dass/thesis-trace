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
//     purely by what they compute (per beneish_v1.yaml), with an explicit
//     disclaimer that no causal "why" claim is made about them — the
//     preprint doesn't reach the section that would verify one).
//   - Sloan, R. (1996), "Do Stock Prices Fully Reflect Information in
//     Accruals and Cash Flows...", The Accounting Review (CUHK open copy,
//     read in full for the persistence mechanism and the market-fixation
//     explanation).
//
// The Beneish five-variable model (DEPI-vs-TATA coefficient question,
// `research-beneish-five-variable-model.md`) is not encoded anywhere in this
// product — `beneish_v1.yaml` ships only the eight-variable model — so it is
// out of scope for this page and not mentioned, rather than silently resolved.
// The "his introduction names TATA as the fifth" claim below describes what
// Beneish's own introduction emphasizes in the shipped 8-variable model; it
// makes no claim about the disputed, unshipped 5-variable model's coefficients.
//
// Coefficients and the Beneish constant below are Beneish (1999)'s own
// published numbers, identical to `beneish_v1.yaml` (confirmed by
// reconstructing QSR's real FY2023 M-score from them and matching the live
// API's `aggregate_value` to 6 decimal places). They are hardcoded here
// rather than added to the `/api/methodology` payload because the AC scopes
// this story to narrative content, not a new API field — and the formula's
// own `description` string already publishes them as text.
//
// LAYOUT CONSTRAINT (Story 11.9 code review): Term.tsx's own doc comment
// warns that its collapsed definition panel is still a block-level box, so
// any content placed after a closing </Term> in the same paragraph — even
// bare punctuation — gets pushed onto a new line. Every Term below is
// therefore the LAST rendered child of its own <li> or <p>, matching the
// only pattern already used elsewhere in this codebase (ReverseDcf.tsx,
// company/[ticker]/page.tsx's signal badges) — confirmed live in a browser
// (zoomed screenshot showed the earlier mid-sentence version forcing a hard
// line break after every Term, well short of the paragraph's right edge).

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
        The nine signals span three areas of a company&rsquo;s condition — profitability,
        funding and liquidity, and operating efficiency — each simple, cheap to compute
        from a filing, and unambiguous about which direction is good news for a
        distressed firm. Three representative examples:
      </p>
      <ul className="list-disc space-y-1 pl-5">
        <li>Profitability: is this year&rsquo;s return on assets positive? <Term id="roa_positive">ROA positive</Term></li>
        <li>Funding and liquidity: did leverage fall from last year? <Term id="leverage_decreasing">Leverage falling</Term></li>
        <li>Operating efficiency: did asset turnover rise from last year? <Term id="asset_turnover_increasing">Asset turnover rising</Term></li>
      </ul>
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
      <p>Each of the five ratios captures a different dimension of financial health:</p>
      <ul className="list-disc space-y-1 pl-5">
        <li>Short-term liquidity relative to size: <Term id="x1_working_capital">X1</Term></li>
        <li>
          Cumulative profitability — and implicitly company age, since a young firm
          hasn&rsquo;t had time to build retained earnings: <Term id="x2_retained_earnings">X2</Term>
        </li>
        <li>Pure earning power, independent of leverage or tax: <Term id="x3_ebit">X3</Term></li>
        <li>
          How much of a solvency cushion the market itself is pricing in:{" "}
          <Term id="x4_market_value_equity">X4</Term>
        </li>
        <li>Asset productivity — how much revenue each dollar of assets generates: <Term id="x5_sales">X5</Term></li>
      </ul>
      <p>
        The paper reports a genuinely counterintuitive result that is the best argument
        for combining ratios rather than picking one: sales/total assets is
        statistically insignificant on its own — a univariate test would likely have
        dropped it — yet it ranks second in contribution to the combined model, because
        of a strong negative correlation with EBIT/total assets among bankrupt firms. A
        ratio that looks useless alone can still sharpen the combined picture.
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
      <p>His own introduction names five variables as driving the probability of manipulation:</p>
      <ul className="list-disc space-y-1 pl-5">
        <li>An unusual rise in receivables relative to sales: <Term id="dsri">DSRI</Term></li>
        <li>Deteriorating gross margins: <Term id="gmi">GMI</Term></li>
        <li>Decreasing asset quality: <Term id="aqi">AQI</Term></li>
        <li>
          High sales growth — the precondition, since growth firms face the most
          pressure to keep the story going: <Term id="sgi">SGI</Term>
        </li>
        <li>Rising accruals relative to cash flow, which his introduction names as the fifth: <Term id="tata">TATA</Term></li>
      </ul>
      <p>
        The eight-variable model this product implements adds three further indices,
        each computing a further year-over-year accounting change:
      </p>
      <ul className="list-disc space-y-1 pl-5">
        <li>A slowing depreciation rate: <Term id="depi">DEPI</Term></li>
        <li>SG&amp;A growing out of step with sales: <Term id="sgai">SGAI</Term></li>
        <li>Rising leverage: <Term id="lvgi">LVGI</Term></li>
      </ul>
      <p className="text-[var(--color-ink-faint)]">
        The available primary source (the freely accessible preprint) ends before the
        section that would define these three individually, so no claim is made here
        about why each one specifically signals manipulation risk — only what it
        computes.
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
        accruals. A company with an unusually high accruals ratio is priced as if this
        year&rsquo;s earnings level will persist — and when the accrual portion
        reverses the way accruals mechanically do, the market is caught by surprise.
      </p>
      <p>See: <Term id="accruals_ratio">Accruals ratio</Term></p>
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
