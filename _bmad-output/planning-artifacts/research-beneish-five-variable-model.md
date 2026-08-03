# Research: the "Roxas-5" Beneish variant (D8 step 7)

**Date:** 2026-08-02
**Status:** ⛔ **NOT ENCODED — blocked on a primary source.** Do not implement from this document.
**Task:** verify and encode the five-variable Beneish M-score recorded in `sprint-status.yaml` as
`M = −6.065 + 0.823·DSRI + 0.906·GMI + 0.593·AQI + 0.717·SGI + 0.107·DEPI`, cutoff −2.76,
attributed to Roxas (2011).

**Outcome:** the attribution is wrong, and the DEPI-vs-TATA question the previous session
believed it had settled is **still open** — with the evidence now pointing the other way than
recorded. Encoding was stopped.

---

## Sources actually read

| Source | What it is | Access |
|---|---|---|
| Roxas, M. L. (2011), "Financial Statement Fraud Detection Using Ratio and Digital Analysis", *Journal of Leadership, Accountability and Ethics* **8(4)** 56–66 | The cited primary source | Full text, all 11 pages, from the publisher: `na-businesspress.com/jlae/roxas84web.pdf` |
| Beneish, M. D. (1999), "The Detection of Earnings Manipulation" | The model's actual origin | **Truncated** — the freely available June 1999 preprint (`calctopia.com/papers/beneish1999.pdf`) is 6 pages and ends before the coefficient tables. The published *Financial Analysts Journal* 55(5) 24–36 version is paywalled. |

---

## Finding 1 — "Roxas-5" is a misattribution

**Roxas (2011) contains no equations and no coefficients at all.** All 11 pages were read. She does
not derive a model; she *applies* Beneish's, and says so explicitly (p. 59):

> "Beneish (1999) calculated the M-score for two probit models: one with 5 coefficients (the first
> five indices) and the other with 8 coefficients (with all eight indices). **The M-score is
> calculated using the coefficients in Beneish's models.**"

So the model is **Beneish's own five-variable probit model**. Calling it "the Roxas-5 variant" and
citing Roxas (2011) for the coefficients would misattribute it in a versioned spec and on the
methodology page — the exact class of error the deterministic/provenance posture exists to prevent.

## Finding 2 — what Roxas *does* verify: the cutoff

Table 1 ("SUMMARY OF EARNINGS INDICATORS AND M SCORES FROM BENEISH (1999)") gives M-score
benchmarks of **> −2.76** for the 5-variable model and **> −2.22** for the 8-variable model.

So −2.76 is confirmed — but as a *Beneish* benchmark reported by Roxas, not a Roxas figure.

⚠️ Note in passing: Roxas uses **−2.22** for the 8-variable cutoff, while `beneish_v1.yaml`
currently uses **−1.78**. Both appear in the literature and correspond to different assumed prior
probabilities and error costs. This is not a defect in our spec, but the methodology page should
eventually say *which* cutoff we use and why.

## Finding 3 — DEPI vs TATA is not settled, and Roxas contradicts herself

Within three sentences on p. 60:

> "Beneish (1999) found the following indices as significant: DSRI, GMI, AQI, SGI and **TATA**."

> "This M-score combines the five indices: DSRI, GMI, AQI, SGI, and **DEPI**."

Both cannot be right. Her p. 59 phrase "the first five indices" matches **her own 1–8 numbering**,
in which #5 happens to be DEPI — so the DEPI reading may be an artefact of the order she happened
to list them in, rather than a statement about Beneish's model.

### Evidence for TATA

- **Beneish (1999) himself**, introduction: the probability of manipulation increases with
  "(i) unusual increases in receivables, (ii) deteriorating gross margins, (iii) decreasing asset
  quality, (iv) sales growth, and (v) **increasing accruals**." Five variables — receivables,
  margins, asset quality, sales growth, accruals. **Depreciation is not among them.**
- Roxas's own statement of which indices Beneish found significant (above).
- StableBread and several other secondary sources place 0.107 on TATA.

### Evidence for DEPI

- **Coefficient magnitude, and it is a strong argument.** In the 8-variable model DEPI's
  coefficient is **0.115** — almost exactly the disputed **0.107**. TATA's is **4.679**, roughly
  40× larger. Dropping three variables would not plausibly shrink TATA's coefficient by that much.
- Roxas's explicit "combines the five indices: DSRI, GMI, AQI, SGI, and DEPI".

### Why this cannot be resolved from what is available

The *variable-significance* evidence points to TATA. The *coefficient-magnitude* evidence points to
DEPI. They genuinely conflict, and the only thing that settles it — Beneish's own five-variable
coefficient table — is in the paywalled FAJ paper. The free preprint stops before it.

**A guess here has real consequences.** Putting 0.107 on the wrong index produces a plausible-looking
M-score that is silently wrong, and it would land in a *versioned spec* presented to users as a
cited academic model. That is precisely the deterministic/provenance guarantee the product is built
on.

---

## Correction to previously recorded state

`project-context.md` (2026-08-01 learnings) and `sprint-status.yaml` both assert that the correct
index is DEPI and that **"StableBread's version is wrong"**. That conclusion is **not safe** and
should not be relied on:

- It cited Roxas (2011) for coefficients that paper does not contain.
- It cited a secondary reproduction (Feruleva & Stefan 2016) rather than Beneish's table.
- Roxas's own text contradicts it, and Beneish's own summary of his significant variables
  contradicts it.

The underlying lesson from that session still stands and is reinforced: **verify from the primary
source before encoding.** Applied a second time here, it caught an error in the correction itself.

---

## Options

1. **Obtain the full Beneish (1999) FAJ 55(5) 24–36 paper** (institutional access, or ~$40 from
   CFA Institute) and read the five-variable coefficient table. The only thing that actually
   settles it. **Recommended if the variant is still wanted.**
2. **Drop the variant.** It was wanted to recover SHOP's Beneish (blocked on LVGI) and Suncor's
   (blocked on SGAI). Both currently return `insufficient_data`, which is honest and correct — a
   five-variable model would add coverage, not correctness.
3. **Encode with an explicit uncertainty caveat.** Not recommended: a caveat may annotate a score,
   but it cannot make a possibly-wrong coefficient right, and this would be ThesisTrace publishing
   a cited model it has not verified.

## What is already verified, if option 1 proceeds

- Five indices are DSRI, GMI, AQI, SGI + **one of** DEPI/TATA — the other three (SGAI, LVGI, and
  whichever of DEPI/TATA is excluded) are omitted.
- Cutoff **−2.76** (Roxas Table 1, from Beneish).
- Attribution must be **Beneish (1999)**, with Roxas (2011) cited only as the source of the −2.76
  benchmark and the out-of-sample evaluation.
- All five candidate indices are already computed by `scoring/beneish.py`, so implementation is
  small once the coefficients are known.
