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
