# Story 1.1: Project scaffold and deployable skeleton

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As Lawrence (operator/developer),
I want the monorepo, FastAPI service, Next.js app, and Supabase connection scaffolded and deployable,
so that every later story has a working, hosted foundation to build on.

This is the first story of Epic 1 (Foundation & First Evidence, the walking skeleton). It establishes the source tree, both runtimes, the database connection, env-var configuration, and deployability — but **no domain logic** (no ingestion, no scoring, no data-model tables). Those arrive in Stories 1.2+.

## Acceptance Criteria

_(Verbatim from `epics.md` Epic 1 Story 1.1; each maps to tasks below.)_

1. **AC1** — The source tree matches the architecture spine (§Structural Seed): `frontend/` (Next.js, presentation only), `backend/` with subpackages `ingestion/ raw_store/ canonicalization/ validation/ formulas/ scoring/ explanation/ api/`, and `db/migrations/`.
2. **AC2** — The FastAPI app exposes a `/health` endpoint returning HTTP 200, deployable as a Render Web Service (AD-13).
3. **AC3** — The Next.js app builds and deploys to Vercel and can call the FastAPI health endpoint.
4. **AC4** — All secrets (DB URL, EDGAR contact, Tiingo key, LLM key) load from environment variables only — never hardcoded — with a committed `.env.example`.
5. **AC5** — The app connects to a Supabase Postgres 17 instance using SQLAlchemy async.

## Tasks / Subtasks

- [ ] **Task 1 — Monorepo source tree (AC: 1)**
  - [ ] Create `frontend/`, `backend/`, `db/migrations/` at repo root.
  - [ ] Create the backend subpackages as empty Python packages (each with `__init__.py`): `backend/ingestion/`, `backend/raw_store/`, `backend/canonicalization/`, `backend/validation/`, `backend/formulas/`, `backend/scoring/`, `backend/explanation/`, `backend/api/`.
  - [ ] Add a top-level `README.md` describing the two runtimes and how to run each locally (point at `HANDOFF.md` for project state).
  - [ ] Confirm the tree matches the spine's Structural Seed exactly; no extra top-level dirs.
- [ ] **Task 2 — Python/FastAPI backend skeleton (AC: 2, 4, 5)**
  - [ ] Add `backend/pyproject.toml` targeting Python 3.12/3.13, pinning: `fastapi>=0.139,<0.140`, `pydantic>=2.13,<2.14`, `pydantic-settings`, `sqlalchemy[asyncio]==2.0.51`, `asyncpg`, `uvicorn[standard]`. Dev deps: `pytest`, `pytest-asyncio`, `httpx`, `ruff`.
  - [ ] Create `backend/app/main.py` with a FastAPI app and a `GET /health` returning `{"status": "ok"}` (200). Use the standard error envelope shape `{error:{code,message,details}}` for error handlers (AD conventions) even though health is the only route now.
  - [ ] Create `backend/app/config.py` using `pydantic-settings` `BaseSettings` to read `DATABASE_URL`, `EDGAR_CONTACT`, `TIINGO_API_KEY`, `LLM_API_KEY` from the environment — no defaults that embed secrets (AD-15 conventions, D7).
  - [ ] Create `backend/app/db.py` with an async SQLAlchemy engine + `async_sessionmaker` built from `DATABASE_URL` (AD-8: Python owns data access).
  - [ ] Add a `GET /health/db` route (or extend `/health`) that opens an async session and runs `SELECT 1` to prove the Supabase connection (AC5). It must degrade gracefully (503 via the error envelope) if the DB is unreachable, not crash the app.
- [ ] **Task 3 — Next.js frontend skeleton (AC: 3)**
  - [ ] Scaffold `frontend/` as a Next.js 16.2.x App-Router project with React 19.2.x and TypeScript (do **not** run `create-next-app` interactively in CI; pin versions in `package.json`).
  - [ ] Add an env var `NEXT_PUBLIC_API_BASE_URL` (read from environment) pointing at the FastAPI base URL.
  - [ ] Add a minimal landing page that fetches `${NEXT_PUBLIC_API_BASE_URL}/health` server-side and renders "backend: ok" / "backend: unreachable". This proves the frontend→backend wire (AC3); it is a skeleton, not FR-1.
  - [ ] Confirm `frontend/` contains no scoring/canonicalization logic (AD-8).
- [ ] **Task 4 — Env config + `.env.example` (AC: 4)**
  - [ ] Commit `.env.example` at repo root listing every variable with placeholder values and a one-line comment each: `DATABASE_URL`, `EDGAR_CONTACT`, `TIINGO_API_KEY`, `LLM_API_KEY`, `NEXT_PUBLIC_API_BASE_URL`.
  - [ ] Confirm `.gitignore` already ignores `.env`/`.env.*` (it does) and that `.env.example` is the one tracked exception.
  - [ ] Grep the codebase to confirm no secret literal is committed.
- [ ] **Task 5 — Deploy configuration (AC: 2, 3)**
  - [ ] Add a Render config (`render.yaml` or documented dashboard settings) for a Web Service running `uvicorn app.main:app` from `backend/`, plus a placeholder note for the future Cron Job (Story 1.10, AD-13). Do not create the Cron Job yet.
  - [ ] Add Vercel config for `frontend/` (root directory, build command, `NEXT_PUBLIC_API_BASE_URL` env). Free/hobby tier.
  - [ ] Document the one-time Supabase project setup (Postgres 17) and where `DATABASE_URL` comes from, in `README.md`.
- [ ] **Task 6 — Tests + lint (AC: 2, 5)**
  - [ ] `backend`: pytest test asserting `GET /health` returns 200 and the expected body (use `httpx.AsyncClient`); a test asserting config raises/flags when a required env var is missing; a DB-connectivity test that is skipped when `DATABASE_URL` is unset so the suite is green with no live DB.
  - [ ] `frontend`: a build check (`next build`) passing in CI.
  - [ ] Wire `ruff` (Python) and the Next.js lint as the lint gate. (Full CI automation is Phase-4-deferred per the spine; a runnable local `make test`/npm script is enough here.)

## Dev Notes

### What this story is (and isn't)

- **Is:** the deployable skeleton — tree, two runtimes, DB connection, env config, health checks, deploy configs.
- **Is not:** any data-model tables (Story 1.2 creates only the tables the scoring slice needs — do **not** create tables here), any ingestion/scoring, any real UI. Resist scaffolding tables or domain packages with logic now; the subpackages are empty placeholders.

### Binding architecture (from the adopted spine — read these ADs)

- **AD-1 (CQRS split):** the read path (FastAPI/Next.js) only ever queries materialized Postgres; it never computes or calls external sources. The skeleton must not introduce any compute-on-request path.
- **AD-8 (Python/TS boundary):** Python owns all data access and (later) computation; Next.js is presentation only and renders what the API returns. Keep DB/session code in `backend/`, never in `frontend/`.
- **AD-10 (read path never triggers writes):** public endpoints are read-only. `/health/db` does `SELECT 1` only.
- **AD-13 (hosting):** FastAPI read API = Render Web Service; the scheduled pipeline = Render Cron Job (added in Story 1.10, not now). Both on Render, one bill.
- **AD-15 conventions:** financial figures will be `NUMERIC`/`DECIMAL` (no float) — no financial columns exist yet, but establish the convention in code comments/config so Story 1.2 inherits it.
- **Config convention:** env vars only for secrets (EDGAR contact, Tiingo key, LLM key, DB URL) — never hardcoded.

### Stack versions (web-verified 2026-07-21)

| Component | Pin | Notes |
|---|---|---|
| Next.js | 16.2.x (latest 16.2.10) | App Router |
| React | 19.2.x (latest 19.2.7) | |
| FastAPI | 0.139.x (latest 0.139.2) | |
| Pydantic | 2.13.x (latest 2.13.4) | + pydantic-settings |
| SQLAlchemy | 2.0.51 | async `AsyncSession` + asyncpg |
| Python | 3.12 / 3.13 | |
| Postgres | 17 (Supabase) | free tier; 7-day auto-pause (keep-alive is Story 1.10) |
| Hosting | Render (backend) + Vercel (frontend) | free/hobby tiers, ~$8–10/mo total ceiling |

### Source tree components to touch (all NEW — greenfield, no third-party starter)

```
README.md                     (NEW)
.env.example                  (NEW)
render.yaml                   (NEW)
frontend/                     (NEW — Next.js app)
backend/pyproject.toml        (NEW)
backend/app/main.py           (NEW — FastAPI + /health)
backend/app/config.py         (NEW — env settings)
backend/app/db.py             (NEW — async engine/session)
backend/{ingestion,raw_store,canonicalization,validation,formulas,scoring,explanation,api}/__init__.py  (NEW, empty)
backend/tests/test_health.py  (NEW)
db/migrations/                (NEW — empty dir; migration tooling chosen in Story 1.2)
```

### Testing standards summary

- Backend: `pytest` + `pytest-asyncio`, `httpx.AsyncClient` for endpoint tests. Suite must be green with **no** live DB (skip DB test when `DATABASE_URL` unset).
- Frontend: `next build` must pass; Next lint clean.
- No formal performance/security/coverage targets this phase (NFR-9, deliberate) — correctness comes online with scoring in later stories.
- Leave the migration tool decision (Alembic is the natural fit for SQLAlchemy) to Story 1.2, but nothing here should block it.

### Project Structure Notes

- Matches the spine's Structural Seed exactly. The only additions beyond the spine tree are conventional support files (`README.md`, `.env.example`, `render.yaml`, `backend/pyproject.toml`, `backend/app/`, `backend/tests/`), which the spine implies but does not enumerate — no conflict.
- `db/migrations/` is created empty; the first migration lands in Story 1.2 (create tables only when a story needs them).

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 1.1: Project scaffold and deployable skeleton]
- [Source: _bmad-output/specs/spec-thesistrace/SPEC.md#Constraints] (stack pins, env-var config, ~$25/mo ceiling)
- [Source: _bmad-output/planning-artifacts/architecture/architecture-ThesisTrace-2026-07-19/ARCHITECTURE-SPINE.md#Structural Seed] (source tree)
- [Source: .../ARCHITECTURE-SPINE.md#AD-1] (CQRS split) · [#AD-8] (Python/TS boundary) · [#AD-10] (read-only) · [#AD-13] (Render+Vercel hosting) · [#Consistency Conventions] (env-var secrets, error envelope)
- [Source: _bmad-output/planning-artifacts/foundational-decisions.md#D7] (stack, single-provider, no LangChain/LangGraph in Phase 1)

## Dev Agent Record

### Agent Model Used

_(to be filled by the dev agent)_

### Debug Log References

### Completion Notes List

### File List
