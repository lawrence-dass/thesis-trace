# Review — Version & Reality-Check Verification

**Artifact:** `ARCHITECTURE-SPINE.md` (ThesisTrace, created 2026-07-19)
**Reviewer lens:** Was every committed technical decision web-researched / reality-checked, or asserted from training data?
**Review date:** 2026-07-21
**Method:** WebSearch against current release trackers, vendor pages, and financial-model references. Network is proxied; no item hit a TLS/403 failure this session, so nothing is marked "could not verify" for network reasons. Vercel is the one item not independently re-searched (noted below).

---

## Verdict

**PASS with minor flags.** The spine is substantially grounded in current reality rather than asserted. The fast-moving JavaScript pins (Next.js 16.2.10, React 19.2.7) match today's exact latest releases — strong evidence of live checking. Postgres 17 (Supabase default), SEC EDGAR Company Facts API + its 10 req/s / User-Agent discipline, Tiingo free-tier EOD, Render Web Service + Cron Job, and the Supabase free-tier limits all check out. The Altman, Beneish, and Sloan financial claims are correctly stated.

Two categories of soft findings: (1) the **Python-side dependency pins (Pydantic 2.10.x, SQLAlchemy 2.0.36, FastAPI 0.136.x) are all several releases behind current** — they exist and are internally coherent, but read like conservative/training-era pins rather than freshly-checked latest; (2) the **Piotroski "0–4 Weak" band is a non-canonical simplification** (Piotroski's own low band is 0–2). None of these are correctness-breaking for a Phase-1 hobby build.

---

## Item-by-item

### Stack table

| Item (as pinned) | Status | Notes |
| --- | --- | --- |
| Next.js **16.2.10** | confirmed-current | 16.2.10 is the latest supported release as of July 2026. Exact match — looks live-checked. |
| React **19.2.7** | confirmed-current | v19.2.7 published 2026-06-01 is the current 19.2.x patch. Exact match. |
| FastAPI **0.136.x** | slightly-behind (not stale/wrong) | Real version and works, but current is 0.139.2 (2026-07-16). ~3 minor releases behind. `.x` range pin is reasonable; consider bumping to 0.139.x. |
| Pydantic **2.10.x** | stale-ish (behind) | Current is v2.13 (May 2026). 2.10.x is a real line (~late-2024) but materially behind. Note: `pydantic-core` was merged into `pydantic` and archived 2026-04-11 — no impact on a range pin, but signals the ecosystem has moved on from the 2.10 era. |
| SQLAlchemy **2.0.36 (async AsyncSession)** | valid but behind (patch lag) | 2.0.x is current (2.0.51, 2026-06-15); 2.1.x still in beta. 2.0.36 is ~15 patch releases old. `AsyncSession`/asyncio API is correct. Reminder: greenlet no longer auto-installs — must use `sqlalchemy[asyncio]`. |
| Python **3.12 / 3.13** | confirmed-current (supported) | Both fully supported; 3.14.3 is the latest feature series but 3.12/3.13 are current maintenance lines. FastAPI needs ≥3.10, so fine. |
| Postgres **17 (Supabase)** | confirmed-current | Postgres 17 is Supabase's current platform default (self-hosted default also moved to PG17 the week of 2026-06-15). |
| Render (Web Service + Cron Job, **~$8–10/mo**) | confirmed-current | Both service types exist and are first-class. Cron Job min ~$1/mo; smallest paid Web Service ~$7/mo → ~$8 baseline matches the estimate. Free tier deliberately not relied on (15-min spin-down; free DB deleted after 30 days). |
| Vercel (free/hobby, $0) | could-not-verify (not re-searched this session) | Hobby tier is well-established and low-risk; not independently re-fetched today. Recommend a quick confirm that hobby ToS still permits this use. |
| Tiingo (free tier, closing-price EOD, $0) | confirmed-current | Free tier exists with EOD closing prices, 30+ yrs history, ~50 symbols/hr. Caveat: free tier is personal/non-commercial — fine for a thesis project, revisit if commercialized. |

### Named services / fit

| Item | Status | Notes |
| --- | --- | --- |
| SEC EDGAR Company Facts API | confirmed-current | Endpoint `data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json` live. AD-9's 10 req/s cap + identifying User-Agent + backoff match SEC's stated fair-access policy exactly. AD-4's "Company Facts primary, Inline XBRL fallback for omitted custom-taxonomy facts" is a correct characterization. |
| Supabase free tier (500MB, 5GB egress, 7-day auto-pause) | confirmed-current | 500MB DB, 5GB egress, 2 projects, 7-day inactivity pause all confirmed for July 2026. **Keep-alive claim holds:** pause triggers only after 7 consecutive days with no DB request, so a daily scheduled batch job resets the counter and prevents pause. One nuance to record: once a project *has* paused, restart is a manual dashboard action — the daily job prevents that state but cannot self-recover from it if the pipeline ever stalls >7 days. |

### Financial-model claims

| Item | Status | Notes |
| --- | --- | --- |
| Piotroski F-Score bands (8–9 Strong / 5–7 Moderate / **0–4 Weak**) | plausible, minor deviation | 9-point scale and 8–9 = strong are correct. Canonical *low* band in Piotroski's work is **0–2** (3–4 is low-moderate); "0–4 Weak" is a defensible display simplification but not the textbook cutoff. Recommend documenting it as a product banding choice in the formula spec (AD-5). |
| Altman Z: **>2.99 Safe / 1.81–2.99 Grey / <1.81 Distress** | confirmed-current | Matches the original 1968 public-manufacturer Z-Score zones exactly. |
| Beneish M-Score: **M > −1.78 ⇒ potential manipulator** | confirmed-current | −1.78 is the standard cutoff; above it flags likely earnings manipulation. |
| Sloan accruals | confirmed-current | Accruals anomaly (high accruals → weaker future returns) correctly described; both balance-sheet and cash-flow accrual-ratio variants exist, so AD-5's insistence on pinning the exact variant/threshold in a versioned spec is well-founded. Deferring the numeric threshold to the spec is appropriate, not a gap. |
| AD-11 Altman market-value-of-equity via Tiingo close × `dei:EntityCommonStockSharesOutstanding` at FYE | reasonable / consistent | Sound approach; correctly avoids `EntityPublicFloat` (wrong as-of date) and book-value substitution. Not a version issue; noted for completeness. |

---

## Recommendations

1. Refresh the three Python pins to current before implementation: Pydantic → 2.13.x, SQLAlchemy → 2.0.51 (stay on 2.0 until 2.1 leaves beta), FastAPI → 0.139.x. Low effort, removes the "asserted-from-training-data" smell on the Python row.
2. Record the Piotroski "0–4 Weak" banding as an explicit product decision in `formulas/piotroski_v1.yaml`, noting it diverges from the canonical 0–2 low band.
3. Add an explicit note that Supabase auto-pause recovery is manual, so a >7-day pipeline outage needs an operator step (the keep-alive prevents, doesn't self-heal).
4. Quick confirm Vercel hobby-tier ToS (only item not re-checked live this session).
