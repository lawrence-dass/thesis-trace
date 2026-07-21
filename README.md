# ThesisTrace

Evidence-backed equity intelligence for retail investors. Four transparent analytical lenses (Value, Growth, Quality/Health, Integrity) computed **deterministically** from SEC EDGAR filings — never an LLM-invented score. An LLM layer explains already-computed results and answers filing-grounded questions, but never originates a number or gives investment advice.

**New here? Read [`HANDOFF.md`](./HANDOFF.md) first** for full project state, then the canonical contract at [`_bmad-output/specs/spec-thesistrace/SPEC.md`](./_bmad-output/specs/spec-thesistrace/SPEC.md) and the architecture at [`_bmad-output/planning-artifacts/architecture/architecture-ThesisTrace-2026-07-19/ARCHITECTURE-SPINE.md`](./_bmad-output/planning-artifacts/architecture/architecture-ThesisTrace-2026-07-19/ARCHITECTURE-SPINE.md).

## Architecture at a glance

Batch pipeline (write) + read-only query API (read) — a CQRS-style split (AD-1). The scheduled pipeline ingests EDGAR/Tiingo → raw store → canonicalize → validate → score → Postgres. FastAPI and Next.js only query materialized Postgres; they never compute a score or call EDGAR/Tiingo live.

```
frontend/   Next.js (Vercel) — presentation only, renders read-API output (AD-8)
backend/    FastAPI read API + batch-pipeline packages (Render)
  app/                FastAPI app (health now; read endpoints later)
  ingestion/ raw_store/ canonicalization/ validation/ formulas/ scoring/ explanation/ api/
db/migrations/  schema migrations (first tables land in Story 1.2)
```

## Stack

Next.js 16.2 / React 19.2 (Vercel) · FastAPI 0.139 + Pydantic 2.13 + SQLAlchemy 2.0.51 async / Python 3.12–3.13 (Render) · Postgres 17 (Supabase).

## Local development

Copy `.env.example` to `.env` and fill in values (all secrets come from the environment — never hardcoded).

### Backend

```bash
cd backend
uv sync                 # create the venv and install deps (Python 3.12+)
uv run uvicorn app.main:app --reload   # serves http://localhost:8000
uv run pytest           # test suite (DB test auto-skips when DATABASE_URL is unset)
uv run ruff check .     # lint
```

Health checks: `GET /health` (liveness), `GET /health/db` (Supabase connectivity; 503 if `DATABASE_URL` unset).

### Frontend

```bash
cd frontend
npm install
npm run dev             # http://localhost:3000
npm run build           # production build
npm run lint
```

Set `NEXT_PUBLIC_API_BASE_URL` to the backend URL; the landing page shows backend health as a wiring check.

## Deployment

- **Backend:** Render Web Service from `backend/` (see `render.yaml`, AD-13). The scheduled pipeline (Render Cron Job) is added in Story 1.10.
- **Frontend:** Vercel from `frontend/` (free/hobby tier).
- **Database:** Supabase Postgres 17. Create a project, copy its connection string into `DATABASE_URL` as a `postgresql+asyncpg://` DSN.

## Where work is tracked

Story backlog: `_bmad-output/planning-artifacts/epics.md` (Phase 1: 4 epics, 26 stories). Per-story dev specs: `_bmad-output/implementation-artifacts/`.
