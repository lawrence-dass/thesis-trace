# Project Context — Durable Rules & Learnings

> Loaded in every session. Keep it under ~200 lines. This holds the things that
> stay true across tasks — patterns, conventions, hard-won learnings — NOT
> session state (that lives in `.claude/handoff/CURRENT.md`).
>
> **Focus on the unobvious** — the details an agent would otherwise get wrong. State
> rules the agent must follow, not general knowledge. Where a rule comes from a real
> file, cite it: `[Source: path#section]`. Rules here are authoritative over model priors.
>
> Distilled 2026-07-29 from the now-archived `HANDOFF.md` (see
> `_bmad-output/archive/HANDOFF-2026-07-29.md` for the full narrative history —
> commit messages and PR descriptions carry the same detail going forward).

## Tech Stack

- Backend: FastAPI + async SQLAlchemy 2.0, Python, managed with `uv` (never bare `pip`/`venv`). Batch pipeline (ingest → canonicalize → validate → score) in `backend/pipeline/`.
- DB: Postgres 17. Local dev = Docker container `thesistrace-pg`; production target = Supabase (not yet provisioned).
- Migrations: Alembic, run from repo root (`db/migrations/`), not from `backend/`.
- Frontend: Next.js 16 (App Router) + Tailwind v4, semantic design tokens in `frontend/app/globals.css`.
- Deploy target (not yet live): Render (backend + cron job) + Vercel (frontend) + Supabase (DB). Cost ceiling ~$25/mo total.
- External data providers (deliberate, narrow exceptions to "no multiple providers"): SEC EDGAR (primary), Tiingo free tier (market close prices), Bank of Canada Valet API (USD/CAD FX rates, for CAD-reporting filers like CP).
- LLM: Claude Haiku 4.5, Phase 1 only — constrained rewrite of an already-computed deterministic template, never a plain wrapper doing free generation. LangGraph reserved for Phase 2 Filing Q&A only.

## Core Patterns

1. **Deterministic/LLM boundary is inviolable.** Every score/number is computed in Python, deterministically. The LLM only explains and cites an already-computed figure — it never originates one, never gives investment advice.
2. **AD-3 canonicalization tiebreak** (`backend/canonicalization/canonicalize.py`): as-originally-filed > concept-priority > decimals > fetched_at. A genuine conflict the rules can't resolve gets flagged as a `data_quality_issues` row (`needs_review`) — never silently guessed or defaulted.
3. **Tri-state signal status** (AD-16): every signal is `pass` / `fail` / `insufficient_data`. A missing input is `insufficient_data`, never a defaulted 0/false/zero.

## Naming Conventions

- Branches: `claude/<short-task-description>-<date>`, one new branch per session — never reuse an old branch name.
- Merge via PR only — never push directly to `main` (binding, see Anti-Patterns).

## Security Rules

- `.env` holds `DATABASE_URL` (dev) and `TEST_DATABASE_URL` (test) as **separate** values — see Anti-Patterns below for why this must never collapse to one.
- No end-user auth in Phase 1 (public, read-only product). Phase 3 notifications are email-capture only, no accounts.

## Anti-Patterns (do NOT do)

- **Never push directly to `main`.** Every session works on its own fresh branch, merges via PR. A real git divergence happened once from two concurrent sessions pushing straight to `main` — see `CLAUDE.md`'s Git workflow section (binding, read every session).
- **Never run `pytest` with only `DATABASE_URL` set** (no `TEST_DATABASE_URL`) — the test teardown drops all tables, and it will wipe the *dev* database if the test URL isn't distinct. Real incident; documented in `.env.example`.
- **Never trust that an XBRL tag's mere existence means it covers the right fiscal years.** Different filers use different tag variants for the same concept, and some switch tags mid-history (e.g. CP switched its PP&E tag in FY2021). Always verify live, per-year coverage against real `data.sec.gov` company-facts JSON before adding a fallback mapping — the original `shares_outstanding` bug (dei cover-page date corrupting fiscal-year bucketing) was exactly this class of mistake.
- **Never treat "no XBRL tag for concept X" as automatically meaning X is zero.** It can be a genuine reclassification artifact (e.g. SHOP's convertible debt flips between `Current`/`Noncurrent` tags as it nears maturity — mapping only the Noncurrent tag would make leverage look like it swings to zero when the debt hasn't actually been repaid). When genuinely ambiguous, leave `insufficient_data` rather than force a fallback.
- **Never assume the "latest fiscal year" is the right one to surface per model.** A model can resolve for some historical years and not the most recent one (e.g. Beneish needs 8 sub-indices simultaneously); picking "latest run that exists" regardless of whether it has a value can hide real, valid results behind an unrelated newer insufficient year — see `api/repository.py`'s `get_company_overview` Verdict-selection logic.
- **No TradingView / off-the-shelf charting** — custom visualizations only (differentiates from the sibling portfolio project `equipulse`).
- **Never add a writer to the batch pipeline without an idempotency key.** `pipeline/run.py` is a *daily* cron (`0 6 * * *`) over the same canonical facts, and `get_company_overview` surfaces every `data_quality_issues` row whose status isn't `dismissed`. A stage that inserts unconditionally accumulates one row per night and the UI shows the same warning N times after N days. `canonicalize_issuer` already models the pattern (skip what exists); `run_validation` had to be given it before wiring in (PR #22). Dedup must ignore status, or a `dismissed` issue gets resurrected.
- **Never let a test infer its precondition from ambient environment.** `Settings` (`app/config.py`) resolves values from the process env *and* an `.env` file (`env_file=".env"`, resolved relative to the CWD). A test asserting a var is absent passes in CI — which sets neither — while failing for anyone who sourced a real `.env`. That's deterministic-per-environment with the environments disagreeing, and green CI wrongly implies soundness. Pin both inputs: `monkeypatch.delenv(...)` **plus** neutralising the file fallback (`Settings(_env_file=None)`, or `monkeypatch.setitem(Settings.model_config, "env_file", None)` when the call is internal). See `test_health.py` and `test_verdict_explanation.py`.

## Standing/locked decisions

- Phase 1 company universe: CP, QSR, OTEX, SHOP (cross-listed Canadian, US-GAAP 10-K filers, non-financial sector) — do not silently re-litigate.
- All four deterministic models are in scope for Phase 1 (Piotroski, Altman, Beneish, Sloan). Value + Growth lenses are Phase 2.
- Verdict is always a transparent per-model threshold classification shown side by side — never a blended/weighted single score.
- Golden-dataset verification (PRD OQ1 / SM-1) is **CLOSED** as of 2026-07-29 — all four companies hand-verified against real EDGAR data. See `backend/tests/golden/phase1_golden.yaml`.

## How Lawrence works

- **Wants research-backed grounding, not assertions.** Verify claims (live data checks, web research) before locking in a feature, competitor claim, or technical assumption — expected even when not explicitly asked.
- **Quality over reduced scope.** When a real technical gap surfaces, solve the underlying problem rather than defaulting to the option that cuts scope. Willing to invest more engineering effort to keep something fully correct.
- **Catches gaps himself and expects them taken seriously.** "Wait, did we cover X?" is genuine gap-finding — verify before reassuring from memory.
- **Values honest pushback**, not reflexive validation of every idea.
- **Standing preferences (every session):** (1) mark the recommended option whenever presenting choices; (2) commit frequently, always at the end of a major task, with a clear message; (3) explain in plain language after each major task — what was done, how to review it.

## Learnings — 2026-07-29

- Real EDGAR company-facts JSON has several sharp edges, all fixed in canonicalization: `dei` cover-page facts are dated to the filing date (not FYE) and must be excluded from fiscal-year-end determination; 10-K/A amendments can carry a less reliable `fiscal_year_end` than the original 10-K; a 10-K's own "selected quarterly financial data" footnote tags quarterly sub-periods under the same accession/fiscal-year label as the true annual figure; an accounting-standard-adoption "opening balance as of Jan 1" snapshot can land in the same calendar year as the true Dec-31 closing balance. All resolved by filtering candidates to full-year-duration facts whose `period_end` matches the issuer's own recognized fiscal-year-end day (with tolerance for non-Dec-31 FYEs like OTEX's June 30).
- CP is a genuine railroad-accounting edge case: no COGS/SGA tags at all (functional expense categories instead), reports entirely in CAD (needed the Bank of Canada FX integration for Altman's X4).

## Learnings — 2026-07-29 (later session)

- **Architecture diagrams live at `docs/diagrams/`** (3 files + README) and are rendered in-app at `/architecture`. The page **reads the markdown at build time** and extracts the ```mermaid block, so the docs are the single source — editing a diagram updates the app. Do not paste diagram source into a component. The page reads from outside `frontend/`, so Vercel needs "Include files outside the root directory" enabled.
- **Validate a diagram by rendering it, not by reading it.** `npx @mermaid-js/mermaid-cli` caught three defects that syntax inspection missed: subgraph titles with `<br/>` render *clipped behind* the first row of nodes (keep them single-line); back-edges silently scramble stage order so numbered stages render out of sequence; and `flowchart LR` with 6+ subgraphs sprawls to a 4:1 aspect that's unusable in a doc.
- **Drawing the system found a real dead-code gap.** `run_validation` had been implemented and tested since Epic 1 but was never called — tests alone never caught it because the test invoked it directly. Tracing the pipeline for a diagram is what surfaced it. Diagrams earn their keep as an audit, not just documentation.
- **`sprint-status.yaml` action items drift badly.** As of 2026-07-29 four of five were already satisfied but still recorded `open`, which would have sent a fresh session chasing solved problems. When closing one, record the *evidence* (file, commit, PR) rather than just flipping the flag.
- **Phase 2 has no epic breakdown.** `epics.md` defines Epics 1–4 only; all are done. Phase 2 exists as PRD prose only, and PRD **OQ8** (universe expansion: manual EDGAR validation vs automated screening) and **OQ9** (lens sub-metric depth) block that planning — both are Lawrence's calls.
- **Known tech debt:** nine test files assert against `backend/tests/fixtures/shop_company_facts.json`, which is entirely **synthetic** (fabricated accession numbers; tags SHOP doesn't use). Only the golden dataset uses real EDGAR data, so those nine can stay green against fiction — the same class of gap as the `shares_outstanding` and CP PP&E bugs.

## Learnings — 2026-08-01 (D8 / IFRS track)

- **IFRS is not "less comprehensive" — the mismatch is presentation, not disclosure quality.** Canadian 40-F filers tag densely (BCE 288 concepts, Cameco 250, Suncor 234, all FY2017–2025). What varies is IAS 1's allowance of expenses **by nature** vs **by function**: a by-nature filer has no SG&A line to tag at all, so Beneish's SGAI is unresolvable. Same shape as CP's missing COGS under us-gaap. Never conclude a taxonomy is unsupported from one filer — Suncor alone (2 of 4 models) would have killed D8; Cameco scores 4 of 4.
- **EDGAR XBRL for 40-F filers starts ~FY2017** — ~9 years vs OTEX's 24 under us-gaap. Fine for point-in-time scoring (needs two consecutive years) but a real constraint on the Phase-2 Growth lens's long-trend promise. Do not promise decade-plus charts for Canadian names.
- **The "tag exists but doesn't cover the years you need" trap recurs per taxonomy.** Under ifrs-full: `Revenue` can carry a single year while `RevenueFromContractsWithCustomers` (IFRS 15) carries the rest; `NumberOfSharesOutstanding` can be sparse where `NumberOfSharesIssued` is complete. Always check per-year coverage, never mere tag presence — this is the same class as the original `shares_outstanding` dei bug.
- **A caveat may annotate a score; it must never alter one.** Cameco FY2021's Beneish is +20.84 because gross margin collapsed 5.91%→0.13%, making GMI 45.1. Every input is correct and the arithmetic is right. Clamping or suppressing would be ThesisTrace originating methodology — forbidden for our own code as much as for an LLM. Presentation guards belong in the versioned formula spec, explicitly labelled as ours rather than the model author's.
- **Model-specific display logic silently applied to another model is a recurring bug class.** `bandTone()` omitted Beneish's band vocabulary; `explanation/template.py` asserted capital intensity as the reason for *every* `computed_with_caveat` run. Store the reason as data rather than inferring it from a shared enum.
- **Verify academic formulas from the PRIMARY source before encoding them — and re-verify a previous verification.** Applied twice to the same formula, with the second pass overturning the first. On 2026-08-01 a session concluded the five-factor M-score's `0.107` coefficient belongs to DEPI (not TATA as StableBread has it), citing Roxas (2011) and a secondary reproduction. Reading the Roxas original in full on 2026-08-02 showed it **contains no coefficients at all** — it applies Beneish's own model — and that it **contradicts itself** on DEPI vs TATA within three sentences. That question is OPEN, not settled; do not encode either reading. Full analysis: `_bmad-output/planning-artifacts/research-beneish-five-variable-model.md`. The general rule: a recorded "verified" claim is only as good as the source it names, so check that the cited source actually contains the thing being claimed.

## Learnings — 2026-08-04 (D8 close-out: mapping specs, golden catch-up)

- **A formula spec's `inputs` list is load-bearing, not documentation.** `scoring/runner.py` reads it to decide whether a run consumed an input that is not comparable across filers, and the methodology page publishes it. `piotroski_v1.yaml` declared 6 inputs while `scoring/piotroski.py` read 9, so the comparability caveat shipped in PR #32 could never have fired on `gross_profit`, `long_term_debt` or `revenue`. A test now asserts declared ⊇ actually-read for every model. Generalise: when a declarative list drives runtime behaviour, something must enforce that it matches the code.
- **Independent verification must not import the thing it verifies.** The golden hand-computation for the IFRS filers imports nothing from `backend/scoring` or `backend/formulas`, which is why it caught its own error rather than rubber-stamping: **Sloan uses AVERAGE total assets across two years, Beneish's TATA uses year-end.** Reusing the scoring module, or comparing only aggregates instead of every component, would have recorded a wrong figure as golden. Also confirm the guard bites — corrupting an expected value must fail the suite.
- **Spec prose has two audiences and needs two fields.** `derivations_v2.yaml` carries `note` (maintainer-facing, may cite decision records and file paths) and `rationale` (published verbatim on `/methodology`, must stand alone). The first version published "DECISION, not an identity — recorded per D8 consequence 3" to end users. Caught only by rendering the page, not by type-checking. Anything user-visible gets looked at in the browser before it ships.
- **SM-1 is a claim about the universe, so expanding the universe reopens it.** Golden coverage was closed 2026-07-29 against 4 filers; D8 grew it to 7, leaving three scored nightly with no test pinning any value. Structural tests (which models resolve) are not numeric guards. Any future filer addition must extend `phase1_golden.yaml` in the same change, or SM-1 silently stops holding.

## Learnings — 2026-08-04 (Phase 2 planning opened)

- **A superseding decision is not landed until every document it contradicts is updated in the same change.** D8 shipped IFRS support on 2026-07-29, but a week later `SPEC.md` (the *canonical contract* per CLAUDE.md) still read "Universe is fixed and US-GAAP-only" and listed "No IFRS-reporting companies" as a non-goal, and `prd.md` still deferred IFRS "indefinitely" against a universe of 4. Code, universe and golden dataset were all correct — only the contract lagged. This is dangerous precisely because BMad derives epics from SPEC + PRD: Phase 2 planning read off that contract would have produced epics for a product that no longer exists. When a decision supersedes another, grep for the superseded claim across `_bmad-output/` and fix every hit in the same commit.
- **Check whether an open question has been overtaken by events before answering it.** PRD OQ8 asked how Phase 2 should grow the universe "to 5–10 companies" — but D8 had already grown it 4 → 7 during Phase 1, using the very manual process OQ8 posed as one of its options. The question had been answered by precedent; the real decision left was only whether to keep that process. Re-read an open question against current state, not against the state it was written in.
- **Two proposed metrics can silently duplicate shipped ones.** OQ9's "receivables-vs-revenue" is substantially Beneish's DSRI and "cash-vs-earnings" substantially the Sloan accruals ratio — both already computed and displayed. Adding them would have shipped a second, differently-computed view of the same figure, creating exactly the "why do these disagree?" problem the provenance invariant exists to prevent. Before adopting a metric from an older planning doc, check it against what the models already compute.
- **`sprint-status.yaml` was unparseable by any YAML reader** from ~2026-08-02 to 2026-08-04 — an unterminated quoted string in `d8_ifrs_track` step 5's `follow_up`. Nothing caught it because the file is only ever read by humans and agents, never parsed. If you add prose to it, run `python3 -c "import yaml; yaml.safe_load(open(...))"` afterwards.
- **Phase 2 shape is D9, not the PRD's feature list.** Sequenced around one real investment decision (change detection → narrow reverse DCF → thesis journal/diff → growth → filing Q&A), with the next feature chosen from *the largest observed research failure* rather than the next list item. Epics 6–9 in `epics.md` are deliberately under-decomposed for this reason — do not "finish" them ahead of the evidence.


## Learnings — 2026-08-04 (Epic 5 implementation)

- **Rendering a page in a browser found 4 real bugs that 27 passing tests missed.** Story 5.4 alone surfaced an engine boundary defect (a first-ever run became its own predecessor, so the page reported "No change since {date}" about a comparison that never happened), a date rendering a day early west of Greenwich, silent rounding of a filed figure, and a duplicated band row. None was reachable from the API contract or a unit test. The standing rule earns its keep — treat it as mandatory, not diligence.
- **A wrong fix can still diagnose the right bug.** The first attempt at the 5.4 defect was a `has_real_prior` heuristic; it broke four existing tests, and *those failures* showed the boundary operator (`<=` vs `<`) was the actual defect. When a fix breaks unrelated tests, read the failures before reaching for a second patch.
- **Semantics that vary per model belong in the spec, not in code.** Piotroski/Altman are higher-is-better; Beneish/Sloan are LOWER-is-better because they measure risk. Encoding "improving = value rose" would have told readers that rising manipulation risk is good news. Declared per model with a citation, and a test enforces the citation.
- **The spec two-audiences trap recurs.** `trajectory_v1.yaml` stated in a YAML *comment* that its thresholds were ThesisTrace's own, but not in the machine-readable `note` — the field a reader would actually see. Same shape as the D8 `derivations_v2` bug. A comment is not a published rationale; a test caught it.

## Learnings — 2026-08-05 (post-Epic-5 hygiene + the v2 profile fix)

- **"Rule B subsumes rule A" is a claim about every input, so deleting A needs a test where the two disagree.** Story 5.7's review replaced "a schedule needs at least one middle year" with "a schedule must be contiguous from year one", recording that the latter subsumed the former. It does not: a lone year-1 bucket is a contiguous prefix of length one. The rules differ on exactly one shape, that shape was live (OTEX, six fiscal years), and it shipped a one-row "Repayment schedule" restating the near-term debt card with a different measurement basis. Spec v2 requires both, with a test on each side of the boundary. When a refactor retires a rule as redundant, the boundary case is the deliverable, not an optional extra.
- **A golden entry whose fixture cannot reproduce its own stated reason is pinning an outcome, not verifying it.** `phase1_golden.yaml` asserted `no_profile` for OTEX in every year and passed throughout, because the trimmed fixture carries none of OTEX's year-1 facts — so it structurally could not produce the shape that broke. The entry's own note had already said the fixture could not reproduce the reason; nobody drew the conclusion that the guard was therefore inert. Where a fixture cannot exercise the reason, say so **and** cover the reason somewhere that can.
- **Documentation of a rule does not hold the rule.** The same golden entry's comment read "the engine requires at least one middle year" for months after the review removed exactly that requirement. It described the intent correctly and the implementation incorrectly, and nothing connected them. This is why the profile loader now pins both admission rules as declared spec fields: the published rule and the enforced behaviour can no longer drift silently.
- **`sprint-status.yaml`'s failure mode is always "meaning parked in a comment".** Four failures now, one cause. Epic titles lived in trailing `#` comments or nowhere; the reason Epics 6-9 had no stories was prose. `epic_catalog` (added 2026-08-05) carries title + `decomposition: decomposed | deferred` + `deferred_under`/`decompose_when`, and a test requires any epic with no tracked stories to declare the deferral. Story keys are DERIVED from `### Story N.M` headings in `epics.md` — adding one to sprint-status alone fails CI, so an "inconsistency" there is usually upstream and often deliberate.
- **Re-canonicalizing to a new `MAPPING_VERSION` needs no EDGAR fetch.** `canonicalize_issuer` reads stored `raw_facts`, and its idempotency skip is scoped per mapping version, so a bump writes new rows rather than skipping. Verified 2026-08-05 going `concepts_v3` → `concepts_v7` on the dev DB. The debt queries filter on `mapping_version` and the score queries do not, so until that pass runs the model cards render while both debt cards silently return empty — a half-degraded page that looks healthy.
