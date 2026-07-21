# LedgerLens and Fundalens Consolidation Review

## Purpose

This document captures the current comparison and proposed consolidation direction before creating a revised PRD, architecture, epics, stories, or sprint plan.

## Repository and source locations

- LedgerLens workspace: `/Users/lawrence/.codex/.chatgpt-projects/g-p-6a582c0cd0608191bbb731d8052a7041`
- Fundalens original directory: `/Users/lawrence/Desktop/Fundalens`
- Fundalens review copy inside the LedgerLens workspace: `/Users/lawrence/.codex/.chatgpt-projects/g-p-6a582c0cd0608191bbb731d8052a7041/Fundalens`

The original Fundalens directory should be treated as read-only during validation. The workspace copy contains the reviewed planning artifacts.

At present, LedgerLens is a concept and requirements discussion rather than an implemented repository. Its requirements came from the prior ChatGPT conversation and are summarized below. The workspace does not currently contain a LedgerLens PRD, architecture, epics, application source tree, or original attached brief.

Fundalens contains extensive planning artifacts but no application implementation. Its proposed `frontend/` and `backend/` trees appear in architecture documents but do not exist as source directories in the reviewed copy.

## LedgerLens concept

LedgerLens is an explainable forensic equity-analysis platform initially differentiated around Canadian equities. Its primary question is:

> Is this company genuinely undervalued, or is it a value trap supported by weak or unreliable financial statements?

Planned deterministic models include:

- Piotroski F-Score
- Altman Z-Score and appropriate variants
- Beneish M-Score
- Sloan accruals ratio
- DCF valuation and sensitivity analysis
- reverse DCF
- Graham Number

The intended architectural rule is that deterministic services calculate all financial values, scores, and verdict inputs. An LLM may explain completed calculations, retrieve filing context, and answer evidence-grounded questions, but may not create authoritative financial figures or canonical scores.

The proposed Canadian data strategy uses SEC EDGAR for cross-listed companies, SEDAR+ filings and limited PDF extraction for TSX-only companies, optional commercial providers, immutable raw storage, accounting validations, field-level provenance, confidence handling, and graceful degradation.

The current delivery preference is portfolio-first, hosted rather than laptop-only, low-cost initially, and progressively expanded across four phases using Next.js, FastAPI, Supabase, AWS, Terraform, Docker, GitHub Actions, and observability tooling.

## Fundalens findings

Fundalens is a planned US-focused fundamental-analysis workstation for value investors, growth investors, and due-diligence researchers. It is designed around SEC filings and earnings-call transcripts.

Its planned capabilities include:

- S&P 500 company discovery and search
- a five-dimensional company health score
- company deep-dive dashboard
- filing-backed AI summaries and citations
- sector health heatmap
- financial-statement visualizations
- historical trends
- peer comparisons
- risk-factor change detection
- earnings-call sentiment and management-language tracking
- authentication, watchlists, and dashboard personalization

Its five proposed health dimensions are liquidity, leverage, cash flow and earnings quality, operational risk, and market/growth risk.

Its planned architecture uses Next.js and a BFF on Vercel, Python/FastAPI on AWS Lambda, DynamoDB for job status, MongoDB for assessments and user data, Qdrant for retrieval, S3 for filings, EDGAR, Finnhub/FMP, Anthropic, OpenAI embeddings, and GitHub Actions.

Fundalens has strong planning, UX, citation, trajectory-analysis, comparison, and qualitative-growth concepts. However, its proposed MVP is too broad for a solo portfolio implementation, and its plan for LLM-generated canonical 0-100 health scores is less reproducible than a deterministic factor engine.

## Comparison

### Principal overlap

Both projects require filing acquisition, XBRL normalization, financial facts, historical analysis, AI explanations, citations, RAG, company dashboards, comparisons, asynchronous processing, and cloud deployment. Building them separately would duplicate most of the data, backend, AI, and frontend foundations.

### Fundalens strengths to preserve

- growth-investor persona and workflow
- revenue, margin, and earnings trajectory
- earnings-call and management-language analysis as supporting evidence
- peer comparison
- risk-factor change detection
- company deep-dive experience
- historical trend presentation
- financial visualizations
- mature UX and accessibility planning
- read-only AI copilot boundary

### LedgerLens strengths to preserve

- deterministic and academically recognized financial models
- valuation as a first-class capability
- bargain-versus-value-trap framing
- earnings-integrity analysis
- field-level provenance and confidence
- accounting validations
- source reconciliation and graceful degradation
- Canadian-market differentiation
- progressive cloud and DevOps learning path

## Recommended consolidated product

Build one evidence-backed equity intelligence platform rather than two applications. The proposed product promise is:

> Evaluate what a company is worth, how healthy its fundamentals are, whether its growth is durable, and whether its reported performance can be trusted—with every important conclusion traceable to evidence.

The analysis should expose four distinct lenses rather than hiding them inside one opaque score.

### Value lens

- DCF and sensitivity analysis
- reverse DCF
- Graham Number
- earnings and free-cash-flow yields
- selected peer multiples
- margin of safety and market-implied assumptions

### Growth lens

- revenue and EPS growth
- quarterly and annual growth acceleration
- gross and operating-margin trajectory
- free-cash-flow growth
- ROIC and reinvestment efficiency where data supports them
- dilution
- guidance and management commentary
- earnings-call sentiment only as qualitative supporting evidence

### Quality and health lens

- Piotroski F-Score
- Altman Z-Score
- liquidity and leverage
- interest coverage
- cash conversion
- profitability and returns
- debt maturity concentration
- trajectory-over-level rules

### Integrity and evidence lens

- Beneish M-Score
- Sloan accruals ratio
- receivables versus revenue
- cash versus earnings
- accounting identity validations
- new or changed risk disclosures
- citations, provenance, freshness, completeness, and confidence

The UI may synthesize the lenses into a transparent thesis or verdict, but it should retain the individual lens outcomes. A company can be high-growth but expensive, cheap but weak, healthy but slowing, or apparently cheap with questionable earnings quality.

## Recommended technical direction

- Next.js and TypeScript frontend
- Python and FastAPI backend
- Supabase PostgreSQL as the initial hosted relational store
- Supabase pgvector for the first RAG implementation
- Supabase Auth only when personalization becomes necessary
- SEC EDGAR as the initial structured filing source
- small cross-listed Canadian company universe for the first release
- deterministic, versioned calculation packages
- explicit observation, canonical fact, provenance, assessment, and snapshot models
- LLM provider behind a narrow interface
- AI used for explanations, qualitative extraction, risk changes, and filing Q&A
- AWS introduced later for raw storage, schedules, queues, workers, retries, dead letters, and observability
- Docker, Terraform, CI/CD, security scanning, monitoring, and rollback added progressively

Avoid introducing MongoDB, Qdrant, DynamoDB, S3, and multiple market-data providers before the initial end-to-end product works. They may be introduced later only where they teach or solve a concrete engineering problem.

## Proposed four-phase delivery plan

### Phase 1: Deterministic portfolio MVP

- 3-5 cross-listed Canadian companies
- EDGAR/XBRL ingestion
- normalized financial facts with provenance
- Piotroski, Altman, Beneish, and Sloan
- minimal valuation and growth lenses
- company result page
- deterministic verdict rules
- grounded AI explanation
- hosted frontend, API, and Supabase database

### Phase 2: Evidence and research experience

- 5-10 preprocessed companies
- polished company deep dive
- historical trends
- peer comparison
- filing-aware RAG using pgvector
- citations and source drill-down
- confidence and missing-data indicators
- risk-factor change detection
- one or two high-value financial visualizations

This phase should produce the first portfolio-complete release.

### Phase 3: Growth intelligence and cloud/data engineering

- stronger growth and reinvestment metrics
- limited earnings-call ingestion and language analysis
- S3 raw archive
- scheduled ingestion
- SQS and Lambda workers
- retries and dead-letter handling
- accounting validation pipeline
- versioned analysis snapshots
- limited SEDAR+ extraction experiment

### Phase 4: DevOps, evaluation, and startup readiness

- Docker
- Terraform
- GitHub Actions
- staging and production environments
- formula regression tests
- RAG retrieval, citation, groundedness, and abstention evaluation
- prompt, model, formula, and rubric versioning
- structured logs, metrics, traces, alerts, and cost monitoring
- deployment rollback and recovery exercises
- optional authentication and watchlists

## Features to defer

- full S&P 500 coverage
- broad TSX/TSXV coverage
- sector heatmap
- draggable dashboards
- authentication and watchlists in the initial release
- earnings-call sentiment across the full universe
- analyze-any-ticker workflows
- GraphRAG or LangGraph
- multiple vector databases
- multiple paid data providers
- subscriptions, payments, and startup growth features

## Questions requiring independent validation

1. Is consolidation into one platform preferable to maintaining two separate products?
2. Are Value, Growth, Quality/Health, and Integrity the correct top-level lenses?
3. Which calculations should be deterministic, and which qualitative judgments may safely use an LLM?
4. Is the proposed 3-5 company Phase 1 narrow enough for a solo developer while still showing meaningful value and growth analysis?
5. Should the initial universe use cross-listed Canadian companies through EDGAR, or should the project begin with US companies and add Canada later?
6. Is Supabase PostgreSQL plus pgvector a sound initial simplification of the Fundalens MongoDB/Qdrant architecture?
7. Which Fundalens Phase 1 features deliver insufficient portfolio value relative to their implementation cost?
8. Are the four phases ordered correctly for learning backend, data, AI/RAG, cloud, and DevOps skills?
9. What essential requirement is missing before producing a revised product brief and PRD?
10. What assumptions or claims in this consolidation proposal need evidence or correction?

