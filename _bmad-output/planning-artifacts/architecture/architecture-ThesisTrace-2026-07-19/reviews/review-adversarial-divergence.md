---
title: 'Adversarial Divergence Review — ThesisTrace Architecture Spine'
type: architecture-review
lens: adversarial-divergence
target: '_bmad-output/planning-artifacts/architecture/architecture-ThesisTrace-2026-07-19/ARCHITECTURE-SPINE.md'
reviewer: adversarial-reviewer
created: '2026-07-21'
---

# Adversarial Divergence Review — ThesisTrace Architecture Spine

## Method

The lens: assume every builder is a rules-lawyer. Two teams (or two future selves) build
adjacent units, each reading the spine and obeying **every AD to the letter**, yet the units
still fail to compose — because the spine constrains *where computation lives* and *what may not
happen* far more tightly than it constrains *the shape of the data crossing each seam*. Each
finding below names two concrete units, shows an exact AD-compliant divergence, and proposes AD
text to close it.

## Verdict

**CONDITIONAL — the spine is directionally sound but under-specifies its internal seams.** AD-1
through AD-15 lock the *paradigm* (batch write / read-only query, one-way dependency, no LLM in
the number loop, NUMERIC everywhere) rigorously. But almost every *contract between two units one
level down* is left to convention: the shape of `score_results`, the representation of
"insufficient data", the `data_quality_issues.status` vocabulary, the formula-spec schema and
rounding mode, and the owner of threshold/Verdict classification are all undefined. Two
independently-built, fully-compliant units can therefore diverge in ways that silently corrupt
scores (F1, F4) or produce ownership deadlocks (F2, F5). These are shippable holes; the spine
should not go to build without closing at least F1–F5.

Nine divergence pairs follow, ordered by severity.

---

## F1 — `[CRITICAL]` "Insufficient data" has no defined representation at the scoring→API→frontend seam

**Units:** `backend/scoring/` (producer of `score_results`) vs `backend/api/` + `frontend/app` (consumers, FR-5/FR-9/FR-10).

**The ADs both units obey:** FR-3/FR-4/FR-6 require a missing Canonical Fact to mark the affected
signal "insufficient data" **rather than guessed or defaulted**. AD-15 mandates NUMERIC for every
financial figure. AD-8 says the frontend renders exactly what the read API returns.

**The compliant-but-incompatible scenario:** Nothing in the spine says *how* "insufficient data"
is encoded in a `score_results` row. Piotroski signals are binary (0/1). The scoring team, obeying
AD-15 (NUMERIC) and the "never defaulted" rule, stores the signal value as SQL `NULL` and considers
itself compliant (it did not guess or default — it left the cell empty). The API team reads the
row and, mapping a Piotroski signal to a boolean pass/fail for FR-5, coerces `NULL` → `0` (a failed
signal) or sums the 9 signals with `COALESCE(x,0)` to produce the aggregate 0–9 score. The result:
a company missing one input silently shows an **8/9 instead of an explicit "insufficient data"
signal** — precisely the "guessed or defaulted" outcome FR-3 forbids, produced entirely by
AD-compliant code on both sides of the seam. This is also a direct threat to SM-1 (golden-dataset
match) because the golden score and the rendered score differ only when data is incomplete.

**Proposed fix — new AD-16 (Explicit tri-state signal status):**
> Every stored signal in `score_results` carries a discrete `status` enum — `computed`,
> `insufficient_data`, or `not_applicable` (e.g. sector-excluded per FR-4/FR-6) — alongside its
> nullable NUMERIC `value`. A `value` is non-NULL if and only if `status = computed`. Consumers
> (API, frontend, explanation) MUST branch on `status`; they MUST NOT coerce a NULL/absent value
> to a numeric default or fold an `insufficient_data`/`not_applicable` signal into an aggregate.
> The aggregate score itself carries a status and is `insufficient_data` if any contributing
> signal is not `computed`, unless the formula spec (AD-5) declares a partial-aggregation policy.

---

## F2 — `[CRITICAL]` `data_quality_issues` has two writers and no shared `status` vocabulary

**Units:** `backend/canonicalization/` vs `backend/validation/` (both write `data_quality_issues`); `backend/api/` reads it for FR-8.

**The ADs both units obey:** AD-3 says canonicalization writes a `data_quality_issues` row with
status **`needs_review`** for any unresolved fact-selection ambiguity. FR-8 says validation writes
a `data_quality_issues` "data-quality warning" when an accounting identity fails. The structural
seed's ER diagram confirms **both** `FILINGS` and `CANONICAL_FACTS` flag `DATA_QUALITY_ISSUES` —
two owners of one entity.

**The compliant-but-incompatible scenario:** The spine pins exactly one status literal
(`needs_review`, from AD-3) and leaves the rest of the enum open. The canonicalization team writes
rows scoped to a `canonical_fact_id` with `status='needs_review'`. The validation team, building
independently, writes rows scoped to a `filing_id` (balance sheet doesn't balance) with
`status='warning'` (or `'flag'`, or `'open'` — their choice, since no AD constrains it) and a
different set of columns to describe the failing identity. Both are fully AD-compliant. Now:
(a) the table has two incompatible row shapes and two disjoint status vocabularies; (b) the FR-8
read endpoint cannot render a stable set of provenance/quality states because the enum is
open-ended and grows per writer; (c) there is no defined ownership of a row's lifecycle — if
validation later resolves an issue, may it mutate a canonicalization-authored row? AD-2's
append-only rule covers `raw_facts`/`canonical_facts` but is silent on `data_quality_issues`,
so one team treats it as mutable (flip `status` to `resolved`) and the other as append-only,
producing conflicting state-mutation paths on the same table.

**Proposed fix — new AD-17 (Single data-quality issue contract):**
> `data_quality_issues` has one schema owned jointly by canonicalization and validation:
> `issue_id (UUID)`, `source_stage` (`canonicalization` | `validation`), a nullable
> `filing_id` **and** nullable `canonical_fact_id` (at least one set), `issue_type` (closed enum,
> extended only by spine amendment), `status` (closed enum: `needs_review`, `warning`,
> `resolved`, `dismissed`), `detail` JSON, and `detected_at TIMESTAMPTZ`. Rows are append-only in
> the AD-2 sense; a status change is a new row referencing the prior `issue_id`, never an in-place
> mutation. The read API exposes only this closed enum.

---

## F3 — `[HIGH]` `score_results` row shape is undefined: EAV vs JSON-blob vs wide-column

**Units:** `backend/scoring/` (writer) vs `backend/explanation/` (AD-7 template reader) vs `backend/api/` (FR-5/FR-9/FR-10 reader).

**The ADs both units obey:** AD-7 requires explanation text to be templated **directly from
`score_results`/`canonical_facts`**. FR-3/FR-4/FR-6 require each of the 9/5/8 sub-signals to be
"individually computed and stored, not just the aggregate." AD-5 puts formula structure in a
versioned spec.

**The compliant-but-incompatible scenario:** "Individually stored" admits at least three legal
encodings. The scoring team ships **EAV**: one row per `(score_run_id, signal_key, value)`. The
explanation team, building the AD-7 templater against an early draft, assumes a **wide JSON blob**
(`score_results.components = {"roa_positive": true, ...}`) and hardcodes `components.roa_positive`
into its template. Both satisfy "individually stored" and "templated from score_results." At
integration the explanation module reads a column that doesn't exist; worse, if a later refactor
swaps encodings, the templater silently emits empty citations — and AD-7's guarantee (LLM only
rewrites already-correct text) is meaningless if the deterministic text it rewrites is empty. The
`signal_key` namespace is itself undefined: scoring might key Piotroski signal 1 as `roa_positive`
while the methodology page (FR-11) and explanation refer to it as `f1_roa` — the same signal under
two names across three units.

**Proposed fix — new AD-18 (Canonical score_results shape + signal key registry):**
> `score_results` is normalized: one row per signal, `(score_run_id, signal_key, status, value,
> weight_or_direction, threshold_ref)`, plus one aggregate row per model. `signal_key` values are
> drawn from a registry defined once inside each formula spec (AD-5) and are the single identifier
> shared by scoring, explanation, methodology (FR-11), and API. No unit may introduce a private
> alias for a signal.

---

## F4 — `[HIGH]` Rounding mode and formula-spec schema are per-spec free-form, so two formula implementations diverge under AD-15

**Units:** two independently-built formula-spec implementations, e.g. `formulas/piotroski_v1.yaml` + its evaluator vs `formulas/beneish_v1.yaml` + its evaluator (or two developers implementing the same spec).

**The ADs both units obey:** AD-5 says each formula's "rounding policy, missing-data policy, and
divide-by-zero policy lives in a versioned config/spec artifact" — *per formula, self-declared*.
AD-15 mandates NUMERIC/DECIMAL and explicitly exists to "prevent silent floating-point rounding
divergence between independently-built calculation code."

**The compliant-but-incompatible scenario:** AD-15 fixes the *storage type* but not the *rounding
mode* or the *spec grammar*. NUMERIC arithmetic still requires a rounding decision at every divide
and every threshold comparison. Beneish's DSRI, GMI etc. involve ratios of ratios; the Beneish spec
declares `rounding: 2dp` and its evaluator uses Python `Decimal` `ROUND_HALF_UP`. The Piotroski (or
a second Beneish) implementer declares the same string `rounding: 2dp` but uses `ROUND_HALF_EVEN`
(banker's rounding, NumPy/Pandas default). Both obey AD-5 (policy is in the spec) and AD-15 (type
is NUMERIC). At a value landing exactly on a .xx5 boundary — or, more dangerously, at a threshold
comparison such as Beneish `> -1.78` or Altman `< 1.81` — the two evaluators classify the same
company differently. Because AD-5 gives each spec its own private schema, there is also no shared
validator ensuring every spec even *declares* divide-by-zero behavior, so one formula silently
propagates NaN/None while another raises. This is exactly the "hard-to-trace SM-1 divergence"
AD-15's rationale names, reintroduced one level up from float-vs-decimal.

**Proposed fix — tighten AD-5 + AD-15:**
> AD-5: All formula specs conform to one shared spec schema (a JSON/YAML schema checked in CI) that
> **requires** `rounding_mode` (from a closed set, default `ROUND_HALF_EVEN`), `decimal_places`,
> `divide_by_zero` (`insufficient_data` | `error`), and `missing_data`. A single shared spec-
> evaluation engine (not per-formula bespoke code) interprets these fields, so rounding and
> zero/missing handling are identical across all four models by construction. AD-15 adds: rounding
> mode is part of the "no silent divergence" guarantee — comparisons against thresholds use the
> spec's declared mode and precision, applied identically in every evaluator.

---

## F5 — `[HIGH]` Ownership of Verdict/threshold classification is ambiguous between backend and frontend (AD-8 vs AD-12)

**Units:** `backend/api/` (+ `backend/scoring/`) vs `frontend/app` for FR-9's Verdict.

**The ADs both units obey:** AD-12 defines the Verdict as each model's **own published threshold
classification shown side by side** and embeds the literal bands (Piotroski 8-9 Strong / 5-7
Moderate / 0-4 Weak; Altman >2.99 Safe / 1.81–2.99 Grey / <1.81 Distress; Beneish >-1.78; Sloan
per spec). AD-8 says Python owns all scoring and the frontend "contains no scoring/canonicalization
logic — it renders exactly what the read API returns."

**The compliant-but-incompatible scenario:** AD-12 states the *rule* but names no *owner* of the
classification step, and AD-12 conveniently prints the threshold numbers inline — inviting a
frontend developer to hardcode "if score >= 8 → Strong" in a React component. Two defensible
readings collide:
- **Backend team** reads AD-8 strictly ("frontend contains no scoring logic; applying a published
  threshold band is scoring logic") → returns raw numeric scores only, assuming the client cannot
  classify.
- **Frontend team** reads AD-12 literally (bands are right there in the architecture, and mapping a
  number to a label is "presentation") → renders `8 → Strong` client-side, assuming the API is thin.

Result A: neither computes the band, and the Verdict page has no classification. Result B (worse):
both hardcode bands, and when the Sloan threshold moves in `sloan_v2.yaml` (AD-5 allows this) the
backend updates but the frontend's hardcoded copy does not — the Verdict label now contradicts the
sub-factor detail on the same page. The threshold values live authoritatively in the formula spec
(AD-5, backend), yet AD-12 duplicated them into a frontend-readable location.

**Proposed fix — tighten AD-8/AD-12:**
> Threshold classification is scoring output, not presentation. The batch pipeline computes and
> stores each model's band label (`Strong`/`Grey`/`Distress`/etc.) in `score_results`, derived from
> the threshold in that model's formula spec (AD-5) — the single source of truth. The read API
> returns both the NUMERIC score and its precomputed band + the `threshold_ref` used. The frontend
> renders the label verbatim and MUST NOT contain any threshold constant or classification
> conditional. The bands printed in AD-12 are illustrative of the spec's contents, not a value the
> frontend may re-implement.

---

## F6 — `[MEDIUM]` AD-3 selection rules have no source-precedence tiebreaker for AD-4 dual-source facts

**Units:** `backend/ingestion/` (AD-4 dual source) vs `backend/canonicalization/` (AD-3 selection).

**The ADs both units obey:** AD-4 makes SEC Company Facts primary and Inline XBRL the fallback
"for facts the Company Facts API omits." AD-9 makes ingestion idempotent by `(accession_number,
content_hash)`. AD-2 makes `raw_facts` append-only, keyed by `(accession_number, content_hash)`.
AD-3's selection order is: (1) as-filed over restated, (2) least-dimensioned, (3) higher decimals.

**The compliant-but-incompatible scenario:** "Omits" is a runtime judgment with no defined
detection point. A conservative ingestion implementation fetches *both* the Company Facts value and
the Inline XBRL value for the same concept/period (e.g. to have the audit path always populated) —
legal under AD-4, and both rows persist under AD-2 because their `content_hash` differs. Now
canonicalization sees two raw facts for `Assets FY2024` from two sources. AD-3's three tiebreakers
say nothing about *source*: if the two agree on filing-status and dimensioning but the Inline XBRL
carries `decimals=-3` while Company Facts carries `decimals=-6`, rule (3) "higher decimals
precision" selects the Inline XBRL value — silently overriding AD-4's "Company Facts is primary."
A different canonicalization author, reading AD-4 as authoritative, hardcodes source precedence and
ignores decimals. Two compliant canonicalizers, two different canonical values, both traceable —
breaking SM-1 reproducibility.

**Proposed fix — tighten AD-3:**
> Add selection rule (0), highest priority: when the same concept/period is present from both
> ingestion sources, the SEC Company Facts value is authoritative (AD-4); the Inline XBRL value is
> retained in `raw_facts` for audit but is selected as canonical only when Company Facts omits the
> fact. Rules (1)–(3) break ties only *within* the chosen source.

---

## F7 — `[MEDIUM]` FYE-to-trading-day price resolution is undefined between market_prices and Altman scoring

**Units:** `backend/ingestion/` (writes `market_prices`, AD-14) vs `backend/scoring/` Altman path (AD-11 join).

**The ADs both units obey:** AD-11 defines Altman's market value of equity as **period-end closing
price** × shares outstanding at FYE. AD-14 stores `market_prices(issuer_id, price_date,
close_price, source, fetched_at)` and requires Altman to join through this table, never calling
Tiingo live.

**The compliant-but-incompatible scenario:** A fiscal year-end commonly falls on a weekend or
market holiday, so there is no `price_date` equal to FYE. Neither AD defines the resolution. The
ingestion team stores only the exact trading closes it fetched (no synthetic FYE row). The scoring
team joins `market_prices ON price_date = fye_date` and gets zero rows → NULL market value → per
F1's gap this could become an insufficient-data Altman, or per a naive implementation a
divide-related error. A second scoring author instead picks "last close ≤ FYE"; a third picks
"nearest trading day." Three compliant Altman scores for the same FYE, differing by the price of a
Friday vs the following Monday — directly moving the `MVE/Total Liabilities` term and possibly the
Safe/Grey/Distress band. AD-11 says "period-end closing price" as if it were unambiguous; it is not
for a calendar FYE.

**Proposed fix — tighten AD-11/AD-14:**
> "Period-end closing price" resolves to the closing price on the **last trading day on or before
> the fiscal year-end date**. The scoring join uses `MAX(price_date) WHERE price_date <= fye_date`
> within a bounded lookback window (spec-declared, e.g. 7 calendar days); if no row exists in that
> window the Altman market-value input is `insufficient_data` (AD-16), never zero or a
> nearest-future price.

---

## F8 — `[MEDIUM]` "Current" score_run selection is undefined for the read path after supersession

**Units:** `backend/scoring/` (AD-6 supersede semantics) vs `backend/api/` + `frontend/app` (FR-9 Verdict, FR-14 comparison).

**The ADs both units obey:** AD-6 says an amendment (10-K/A) creates a **new** `score_run`
referencing new canonical facts and marks the prior run **superseded**, never deleted. AD-10 makes
the API read-only against materialized Postgres.

**The compliant-but-incompatible scenario:** The write path now guarantees ≥2 score_runs can exist
for one issuer/period (one `superseded`, one current). No AD tells the read path which to surface.
API author A selects `MAX(computed_at)`. Author B selects `WHERE status != 'superseded'`. These
usually agree — but not if a *re-run of an older formula version* is computed after an amendment,
or if `computed_at` ordering and supersession ordering disagree during a backfill. Worse, the
comparison view (FR-14) is built by a different code path than the single-company overview (FR-9);
one filters superseded runs and the other doesn't, so CP shows its post-amendment score on its
overview page but its pre-amendment (superseded) score in a side-by-side against QSR — a
self-contradiction inside one session. AD-6 also never states whether `superseded` is set by
marking the old row (a mutation the read path must tolerate) versus derivable purely from ordering.

**Proposed fix — new AD-19 (Canonical "current run" selection):**
> Exactly one `score_run` per `(issuer, fiscal_period, formula_version)` is flagged
> `is_current = true`; supersession sets the prior run `is_current = false` (an explicit,
> auditable state field, not an implicit `MAX(computed_at)`). Every read endpoint — overview,
> comparison, methodology, explanation — selects `WHERE is_current` and MUST NOT reconstruct
> currency from timestamps. Superseded runs are reachable only via an explicit history endpoint.

---

## F9 — `[MEDIUM]` "Not yet covered" (FR-2) has no defined home: error envelope vs normal payload

**Units:** `backend/api/` (search endpoint, FR-2) vs `frontend/app` (search UI).

**The ADs both units obey:** The Consistency Conventions table mandates one FastAPI error shape:
`{error: {code, message, details}}`. FR-2 requires an out-of-universe ticker to return an explicit
"not yet covered" message — "never a silent failure, generic error, or fabricated result."

**The compliant-but-incompatible scenario:** "Not yet covered" is a *known, expected, non-error*
business state, but the spine only standardizes the *error* envelope and never says whether
this state is an error. Backend author, wanting to reuse the one documented envelope, returns
HTTP 404 with `{error: {code: "NOT_COVERED", ...}}`. Frontend author treats any response carrying
an `error` object as a failure toast ("something went wrong") — which FR-2 explicitly forbids
("never a generic error"). Alternatively the backend returns 200 `{covered: false}` and the
frontend, coded to branch on HTTP status, treats 200 as "found" and navigates to a nonexistent
overview page. There is no defined success-envelope at all in the spine (only the error shape),
so every non-error response shape is ad hoc and the two units disagree on how "not covered" travels.

**Proposed fix — extend Consistency Conventions:**
> Define the success envelope as well as the error envelope. "Not yet covered" is a successful
> query result, returned HTTP 200 with a documented payload
> (`{covered: false, ticker, message}`), never via the error envelope. The error envelope is
> reserved for genuine faults (5xx, malformed request). Add a one-line rule: business "empty/absent"
> results are success payloads, not errors.

---

## Summary Table

| ID | Severity | Seam | Core divergence |
| --- | --- | --- | --- |
| F1 | CRITICAL | scoring → API/frontend | "insufficient data" encoded as NULL → coerced to failing signal |
| F2 | CRITICAL | canonicalization vs validation | two writers of `data_quality_issues`, open status enum, undefined mutation |
| F3 | HIGH | scoring vs explanation vs API | `score_results` shape (EAV/JSON/wide) + signal-key naming undefined |
| F4 | HIGH | two formula-spec impls | rounding mode / spec schema free-form → threshold-boundary divergence |
| F5 | HIGH | backend vs frontend | Verdict/threshold classification owner ambiguous (AD-8 vs AD-12) |
| F6 | MEDIUM | ingestion vs canonicalization | AD-3 has no source-precedence tiebreaker for AD-4 dual-source facts |
| F7 | MEDIUM | market_prices vs Altman | FYE-to-trading-day price resolution undefined |
| F8 | MEDIUM | scoring vs read path | "current" score_run selection undefined after supersession |
| F9 | MEDIUM | API vs frontend | "not yet covered" — error envelope vs success payload undefined |

**Recommended gate:** close F1–F5 (add AD-16, AD-17, AD-18; tighten AD-5/AD-15, AD-8/AD-12) before
build. F6–F9 (add AD-19, tighten AD-3/AD-11/AD-14, extend Consistency Conventions) should be closed
before the corresponding epic starts.
