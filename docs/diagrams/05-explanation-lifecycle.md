# Explanation Lifecycle

One request traced end to end: a visitor opens a company page and gets a narrative
explanation of its Verdict scores.

This is the flow that enforces the project's central constraint — **the LLM never originates a
number.** Every figure is computed in Python and persisted before the request starts; the
optional Anthropic call receives already-final text and is allowed only to rewrite prose.
If the LLM is disabled, unreachable, or errors, the user still gets the complete, cited
deterministic explanation.

```mermaid
sequenceDiagram
    autonumber
    actor U as Investor
    participant NX as Next.js server component<br/>app/company/[ticker]/page.tsx
    participant API as FastAPI<br/>api/routes.py
    participant REPO as api/repository.py
    participant PG as Postgres
    participant TPL as explanation/template.py
    participant LLM as explanation/llm.py
    participant ANT as Anthropic API

    U->>NX: open /company/OTEX
    Note over NX: server-side fetch, cache no-store<br/>3 parallel calls to NEXT_PUBLIC_API_BASE_URL

    rect rgb(219, 234, 254)
        Note over NX,PG: Phase 1 — read already-computed scores
        NX->>API: GET /api/companies/OTEX/explanation
        API->>REPO: get_company_overview session, ticker
        REPO->>PG: SELECT issuers WHERE ticker = OTEX
        PG-->>REPO: Issuer row or none
    end

    alt issuer not found or no scores yet
        REPO-->>API: None
        API-->>NX: 200 state not_available
        NX-->>U: honest empty state, no fabricated zero
    else issuer covered
        rect rgb(254, 243, 199)
            Note over REPO,PG: Phase 2 — assemble the Verdict
            REPO->>PG: SELECT score_runs WHERE superseded = false<br/>ORDER BY model, fiscal_year DESC
            PG-->>REPO: runs across piotroski altman beneish sloan
            Note over REPO: per model pick the latest year that<br/>actually RESOLVED a value, not merely the<br/>latest run that exists
            REPO->>PG: SELECT score_results per run
            PG-->>REPO: signals as pass / fail / insufficient_data
            REPO->>PG: JOIN score_inputs to canonical_facts to filings
            PG-->>REPO: provenance, accession number per signal
            REPO->>PG: SELECT data_quality_issues WHERE status not dismissed
            PG-->>REPO: open review flags
            REPO-->>API: CompanyOverviewOut
        end

        rect rgb(220, 252, 231)
            Note over API,TPL: Phase 3 — deterministic text, no LLM
            API->>TPL: build_explanations overview
            Note over TPL: sentences built from computed values only<br/>an ungroundable statement is simply not produced
            TPL-->>API: LensExplanation per model<br/>text plus citation accession numbers
        end

        opt polish_text=true AND LLM_API_KEY set
            rect rgb(252, 231, 243)
                Note over API,ANT: Phase 4 — optional prose rewrite
                API->>LLM: polish text
                LLM->>ANT: claude-haiku-4-5-20251001<br/>constrained rewrite of existing text
                ANT-->>LLM: reworded prose, same figures
                LLM-->>API: polished text
            end
        end

        API-->>NX: 200 state ok<br/>llm_rewrite flag plus explanations array
        NX-->>U: rendered Verdict cards<br/>signals plus CitationChip per accession
    end

    Note over U,ANT: every number shown was computed on the write path<br/>days earlier by the Render cron pipeline
```

## Participants — real modules

| Participant | File | Role |
|---|---|---|
| Next.js server component | `frontend/app/company/[ticker]/page.tsx` | Fetches `overview`, `explanation`, `methodology` server-side |
| FastAPI route | `backend/api/routes.py:45` | `GET /api/companies/{ticker}/explanation` |
| Repository | `backend/api/repository.py:85` | `get_company_overview` — the only DB reader |
| Template | `backend/explanation/template.py` | Deterministic sentence construction (FR-12, AD-7, AD-19) |
| LLM adapter | `backend/explanation/llm.py` | `polish` — lazy `anthropic` import, gated |

## Why the LLM step is `opt`, not required

Three independent gates must all be true before Anthropic is called:

1. The request must pass `?polish_text=true` — the default is `false`.
2. `rewrite_enabled()` must be true, which requires `LLM_API_KEY` to be set.
3. The `anthropic` package is imported **lazily inside the call**, so the dependency is only touched when a rewrite actually runs.

The response reports which path was taken via the `llm_rewrite` boolean, so a consumer can
always tell whether text was model-touched. The scores themselves are byte-identical either
way — they came out of `score_runs`.

## The subtle bug this flow already survived

Step 8's note is not decoration. `get_company_overview` originally selected each model's
latest *existing* run regardless of whether it resolved a value. Because Beneish needs eight
sub-indices to resolve simultaneously, a newer `insufficient_data` run would mask QSR's and
OTEX's real historical M-Scores. The fix — pick the latest year that actually resolved — is
why the note calls it out explicitly as part of the contract, not an implementation detail.
