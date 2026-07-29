# Application Diagrams (Mermaid)

Color-coded, presentation-ready diagrams of **ThesisTrace**. Reflect the stack as of
2026-07-29 (`main` @ `32c4cd5`). Every label traces to a real file, route, table, or
provider in this repo — nothing is illustrative.

1. [01-system-architecture.md](./01-system-architecture.md) — the whole system in one map: read path, write path, data layer, external providers, and the deploy targets that aren't provisioned yet.
2. [03-data-pipeline.md](./03-data-pipeline.md) — the deterministic write path: EDGAR / Tiingo / Bank of Canada → `raw_facts` → AD-3 canonicalization → four scoring models → append-only `score_runs`.
3. [05-explanation-lifecycle.md](./05-explanation-lifecycle.md) — a single request traced across eight participants, showing exactly where the deterministic/LLM boundary sits.

> Numbers follow the generator's stable slots. `02-user-flow`, `04-api-surface`, and
> `06-cicd-pipeline` were deliberately skipped — see [Why only three](#why-only-three).

## Stack / Infrastructure

| Layer | Technology / Service | Detail |
|-------|----------------------|--------|
| Frontend | Next.js 16.2.10 (App Router), React 19.2.7, Tailwind v4, TypeScript 5 | 4 route pages, 7 components. Host: Vercel — **not provisioned** |
| Backend | FastAPI 0.139, Python 3.12, uvicorn, managed by `uv` | 6 endpoints, 10 modules. Host: Render web service `thesistrace-api` (plan `starter`) — **not provisioned** |
| Database | Postgres 17, SQLAlchemy 2.0.51 async + asyncpg, Alembic | 11 tables, 5 migrations. Host: Supabase — **not provisioned**; local dev uses Docker container `thesistrace-pg` |
| Batch pipeline | `pipeline/run.py` — ingest → canonicalize → score | Render Cron Job `thesistrace-pipeline`, `0 6 * * *`; the daily run doubles as the Supabase free-tier keep-alive |
| External data | SEC EDGAR · Tiingo (free tier) · Bank of Canada Valet | `data.sec.gov/api/xbrl/companyfacts` · daily EOD closes · `FXUSDCAD` for CAD-reporting filers |
| LLM | Anthropic `claude-haiku-4-5-20251001` | Explanation prose rewrite only, triple-gated. Never originates a figure |
| Infra | `render.yaml` (2 services) | Cost ceiling ~$25/mo. 4 secrets: `DATABASE_URL`, `EDGAR_CONTACT`, `TIINGO_API_KEY`, `LLM_API_KEY` |
| CI | GitHub Actions — `.github/workflows/ci.yml` | Push to `main` + every PR. Backend: postgres:17 service → alembic → ruff → pytest. Frontend: node 22 → eslint → next build. **No deploy step** |
| Tests | pytest 8.3 (`asyncio_mode = auto`) | 54 test functions across 14 files, incl. `test_golden_dataset.py` against 4 hand-verified companies |

## The one invariant these diagrams exist to show

**Every score and number is computed deterministically in Python on the write path, days
before any request arrives. The LLM only rewrites already-final prose, and only when
explicitly asked.** Diagram 03 shows where the numbers come from; diagram 05 shows the gate
they pass through on the way out.

## Known gap, drawn honestly

`validation/checks.py::run_validation` is implemented and tested but **never called by
`pipeline/run.py`** — the spec's ingest → canonicalize → **validate** → score order currently
skips the validate stage in production code. It appears dashed in diagram 03 rather than as a
live pipeline stage.

## Why only three

`04-api-surface` would have been six boxes in a flowchart — that's a table, so it lives in
[01-system-architecture.md](./01-system-architecture.md#api-surface) instead.
`02-user-flow` collapses into the frontend subgraph of the same diagram; four pages with no
branching don't warrant their own chart. `06-cicd-pipeline` is deferred because CI has no
deploy step and no environment is provisioned — drawing a deploy pipeline for infrastructure
that doesn't exist would be exactly the kind of plausible-but-untrue diagram this suite
avoids. Worth generating once the cloud deployment lands.

## Keeping them current

Re-run `/generate-architecture-diagrams` after a significant architecture change — a new
service, a new endpoint group, a changed deploy target — so the diagrams don't drift from
the code. The most likely next trigger: **provisioning Render / Vercel / Supabase**, which
turns every "not provisioned" note above into a real hostname and makes `06-cicd-pipeline`
worth generating.
