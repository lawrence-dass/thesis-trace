# System Architecture

ThesisTrace end to end: a read-only Next.js frontend over a FastAPI query API, backed by
Postgres, with a separate scheduled batch pipeline owning the entire write path.

The split down the middle is the point. **Nothing on the read path ever calls an external
provider or computes a score** — the API only reads rows the batch pipeline already wrote.

```mermaid
flowchart TB
    USER(["Investor / Analyst<br/>public · no auth in Phase 1"]):::actor

    subgraph FE["FRONTEND — Next.js 16.2.10 App Router · React 19.2.7 · Tailwind v4 · Vercel target"]
        direction LR
        PAGES["4 route pages<br/>/ · /company/[ticker]<br/>/compare · /methodology/[model]"]:::frontend
        COMP["7 components<br/>SearchBox · AddToCompare<br/>Badge Button Card CitationChip Gauge icons"]:::frontend
        PAGES --- COMP
    end

    subgraph BE["READ PATH — FastAPI 0.139 · Python 3.12 · uv · Render web service thesistrace-api target"]
        direction LR
        READ["api/routes.py<br/>4 endpoints under /api"]:::backend
        REPO["api/repository.py<br/>list_companies<br/>get_company_overview"]:::backend
        EXPL["explanation/<br/>template.py · methodology.py<br/>llm.py"]:::backend
        HEALTH["app/main.py<br/>GET /health<br/>GET /health/db"]:::backend
        READ --> REPO
        READ --> EXPL
    end

    subgraph DATA["DATA — Postgres 17 · SQLAlchemy 2.0.51 async + asyncpg · Alembic · Supabase target"]
        DB[("11 tables · 5 migrations<br/>issuers · filings · raw_facts · concept_mappings · canonical_facts<br/>score_runs · score_inputs · score_results<br/>market_prices · fx_rates · data_quality_issues")]:::database
    end

    subgraph WRITE["WRITE PATH — pipeline/run.py · Render cron job thesistrace-pipeline target"]
        direction LR
        CRON["schedule 0 6 * * *<br/>daily run doubles as<br/>Supabase keep-alive ping"]:::infra
        ING["ingestion/<br/>edgar · company_facts<br/>tiingo · fx"]:::backend
        CANON["canonicalization/<br/>AD-3 tiebreak"]:::backend
        VALID["validation/<br/>identity checks · advisory"]:::backend
        SCORE["scoring/ + formulas/engine.py<br/>piotroski · altman<br/>beneish · sloan"]:::backend
        CRON --> ING --> CANON --> VALID --> SCORE
    end

    subgraph EXT["EXTERNAL PROVIDERS"]
        direction LR
        EDGAR["SEC EDGAR<br/>data.sec.gov/api/xbrl/companyfacts"]:::source
        TIINGO["Tiingo free tier<br/>api.tiingo.com daily prices"]:::source
        BOC["Bank of Canada Valet<br/>FXUSDCAD · CAD filers only"]:::source
        LLM["Anthropic<br/>claude-haiku-4-5-20251001"]:::llm
    end

    USER --> PAGES
    PAGES -->|"server-side fetch<br/>NEXT_PUBLIC_API_BASE_URL · cache no-store"| READ
    REPO --> DB
    HEALTH -->|"SELECT 1"| DB
    EXPL -.->|"opt · ?polish_text=true"| LLM
    ING --> EDGAR
    ING --> TIINGO
    ING --> BOC
    SCORE --> DB

    classDef actor fill:#F3E8FF,stroke:#7E22CE,color:#3B0764,stroke-width:2px;
    classDef frontend fill:#DBEAFE,stroke:#2563EB,color:#1E3A8A,stroke-width:1.5px;
    classDef backend fill:#DCFCE7,stroke:#16A34A,color:#14532D,stroke-width:1.5px;
    classDef database fill:#FEF3C7,stroke:#D97706,color:#78350F,stroke-width:1.5px;
    classDef source fill:#FFF7ED,stroke:#EA580C,color:#9A3412,stroke-width:1.5px;
    classDef llm fill:#FCE7F3,stroke:#DB2777,color:#831843,stroke-width:1.5px;
    classDef infra fill:#E0F2FE,stroke:#0284C7,color:#0C4A6E,stroke-width:1.5px;
```

## Reading the diagram

The two paths meet only at the database. The read path (top) is synchronous and serves
requests; the write path (bottom) runs once a day on a schedule and is the *only* thing that
talks to SEC EDGAR, Tiingo, or the Bank of Canada. A dotted edge is the one optional call —
the Anthropic rewrite, which is skipped unless explicitly requested.

## Deployment status — honest snapshot

`render.yaml` defines both services and CI is green, but **no environment is live**. Every
host named in a subgraph title is a configured target, not a running machine.

| Target | Config | Provisioned |
|---|---|---|
| Render — `thesistrace-api` web service | `render.yaml`, `healthCheckPath: /health` | ❌ not yet |
| Render — `thesistrace-pipeline` cron | `render.yaml`, `0 6 * * *` | ❌ not yet |
| Supabase Postgres | `DATABASE_URL` (`sync: false`) | ❌ not yet — local Docker `thesistrace-pg` only |
| Vercel | — | ❌ not yet, no `vercel.json` |

Local dev runs the API at `http://localhost:8000` (the `NEXT_PUBLIC_API_BASE_URL` fallback)
against the Docker Postgres container. Four secrets are declared `sync: false` on both Render
services: `DATABASE_URL`, `EDGAR_CONTACT`, `TIINGO_API_KEY`, `LLM_API_KEY`.

## CI

`.github/workflows/ci.yml` runs on push to `main` and on every PR, as two parallel jobs:

| Job | Steps |
|---|---|
| `backend` | `postgres:17` service container → `uv sync --locked --all-groups` → `alembic upgrade head` (from repo root) → `ruff check` → `pytest` (57 tests) |
| `frontend` | Node 22 → `npm ci` → `eslint` → `next build` |

**There is no deploy step.** CI proves the build and tests; nothing is shipped from it.

## API surface

Six endpoints total. Only the four under `/api` are public product surface.

| Method | Path | Reads | Notes |
|---|---|---|---|
| GET | `/health` | — | Liveness, no dependencies |
| GET | `/health/db` | `SELECT 1` | Readiness, 503 envelope on failure |
| GET | `/api/companies` | `issuers` | Company cards |
| GET | `/api/companies/{ticker}/overview` | `score_runs`, `score_results`, `score_inputs`, `canonical_facts`, `filings`, `data_quality_issues` | Verdict per model |
| GET | `/api/companies/{ticker}/explanation` | same as overview | `?polish_text=true` enables the LLM rewrite |
| GET | `/api/methodology/{model}` | `formulas/specs/*.yaml` | No DB access |

An uncovered company returns a **200 with `state: not_available`** — never an error and never
a fabricated zero. Unhandled errors use one envelope: `{error: {code, message, details}}`.
