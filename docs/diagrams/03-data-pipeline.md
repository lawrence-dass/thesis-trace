# Data Pipeline

The write path, end to end: `pipeline/run.py` orchestrates **ingest → canonicalize → score**
for each of the four Phase-1 issuers, then commits. The read API never enters this flow — it
only queries the tables this pipeline wrote.

Every arrow below is deterministic Python. No LLM touches any value on this path.

```mermaid
flowchart TB
    subgraph SRC["1 · Sources — live HTTP"]
        direction LR
        EDGAR["SEC EDGAR<br/>companyfacts/CIK{cik}.json<br/>4 confirmed CIKs"]:::source
        TIINGO["Tiingo daily prices<br/>EOD close · skipped if<br/>TIINGO_API_KEY unset"]:::source
        BOC["Bank of Canada Valet<br/>FXUSDCAD + LEGACY_NOON_RATES<br/>only for non-USD filers"]:::source
    end

    subgraph ING["2 · Ingest — ingestion/"]
        direction LR
        FETCH["edgar.fetch_company_facts"]:::action
        PARSE["company_facts.parse_company_facts<br/>→ ParsedFiling per accession"]:::action
        PRICE["tiingo.select_fye_close<br/>resolve close at fiscal-year-end"]:::action
        FX["fx.select_rate_on_or_before<br/>USD/CAD at FYE"]:::action
        FETCH --> PARSE
    end

    subgraph RAW["3 · Raw store — raw_store/"]
        direction LR
        T_CORE[("issuers · filings · raw_facts<br/>every fact as filed, never edited")]:::table
        T_MP[("market_prices")]:::table
        T_FX[("fx_rates")]:::table
    end

    subgraph CANON["4 · Canonicalize — canonicalization/"]
        direction TB
        SEED["mappings.seed_concept_mappings<br/>MAPPING_VERSION"]:::action
        RANK["canonicalize_issuer · AD-3 tiebreak<br/>as-filed > concept-priority<br/>> decimals > fetched_at"]:::action
        FYE{"full-year duration<br/>AND period_end matches<br/>issuer's own FYE day?"}:::decision
        DERIVE["derive total_liabilities<br/>fallback for untagged filers"]:::action
        SEED --> RANK --> FYE
    end

    subgraph STORE["5 · Canonical store"]
        direction LR
        T_CM[("concept_mappings")]:::table
        T_CF[("canonical_facts")]:::table
        T_DQ[("data_quality_issues<br/>status = needs_review")]:::table
    end

    subgraph SC["6 · Score — scoring/ + formulas/"]
        direction TB
        YEARS["scoreable_years<br/>year with year-1 present"]:::action
        ENGINE["formulas/engine.py<br/>4 versioned YAML specs<br/>piotroski_v1 altman_v1<br/>beneish_v1 sloan_v1"]:::action
        RUN["runner.py · always runs<br/>score_piotroski · score_sloan<br/>score_beneish"]:::action
        GATE{"FYE close price resolved?<br/>joins market_prices + fx_rates"}:::decision
        ALT["score_altman also runs"]:::action
        SKIP["Altman → insufficient_data<br/>other 3 models unaffected"]:::action
        YEARS --> ENGINE --> RUN --> GATE
        GATE -->|yes| ALT
        GATE -->|no| SKIP
    end

    subgraph RES["7 · Results — append-only, AD-6"]
        direction LR
        T_SR[("score_runs · superseded flag, never mutated<br/>score_inputs · → canonical_fact_id provenance<br/>score_results · pass / fail / insufficient_data")]:::table
    end

    subgraph READ["8 · Read path"]
        direction TB
        REPO["api/repository.py<br/>get_company_overview<br/>filters superseded = false"]:::backend
        API["GET /api/companies/{ticker}/overview"]:::backend
        UI["Verdict cards · signal rows<br/>CitationChip → accession number"]:::insight
        REPO --> API --> UI
    end

    VAL["validation/checks.run_validation<br/>DEFINED + TESTED, NOT WIRED<br/>see note below"]:::decision

    EDGAR --> FETCH
    TIINGO --> PRICE
    BOC --> FX
    PARSE -->|"persist_company_facts"| T_CORE
    PRICE -->|"upsert_fye_close"| T_MP
    FX -->|"upsert_fx_rate"| T_FX

    T_CORE --> RANK
    SEED --> T_CM
    FYE -->|"yes · single winner"| T_CF
    FYE -->|"no · unresolvable conflict"| T_DQ
    RANK -.->|"Liabilities untagged"| DERIVE --> T_CF

    T_CF --> YEARS
    T_CF -.->|"gap · never invoked by pipeline/run.py"| VAL

    RUN --> T_SR
    ALT --> T_SR
    SKIP --> T_SR

    T_SR --> REPO
    T_DQ --> REPO

    classDef backend fill:#DCFCE7,stroke:#16A34A,color:#14532D,stroke-width:1.5px;
    classDef table fill:#EDE9FE,stroke:#7C3AED,color:#4C1D95,stroke-width:1.5px;
    classDef source fill:#FFF7ED,stroke:#EA580C,color:#9A3412,stroke-width:1.5px;
    classDef decision fill:#FCE7F3,stroke:#DB2777,color:#831843,stroke-width:1.5px;
    classDef action fill:#FEF3C7,stroke:#D97706,color:#78350F,stroke-width:1.5px;
    classDef insight fill:#F3E8FF,stroke:#7E22CE,color:#3B0764,stroke-width:1.5px;
```

## Phase-1 universe

Four issuers, all US-GAAP 10-K filers, all CIKs confirmed live against `data.sec.gov`
before being hardcoded in `pipeline/universe.py`. An entry with `cik: None` is **skipped and
reported**, so coverage gaps stay explicit rather than silently disappearing.

| Ticker | Company | CIK | Flags |
|---|---|---|---|
| SHOP | Shopify Inc. | `0001594805` | — |
| CP | Canadian Pacific Kansas City Limited | `0000016875` | `capital_intensive` → Altman caveat; reports in **CAD** |
| QSR | Restaurant Brands International Inc. | `0001618756` | — |
| OTEX | Open Text Corporation | `0001002638` | non-Dec-31 FYE (June 30) |

## Degradation rules — why a stage can be skipped

The pipeline is built so a missing input narrows the output rather than failing the run:

- **No `TIINGO_API_KEY`** → `_fye_prices_for` returns `{}`, Altman shows `insufficient_data`, and Piotroski / Beneish / Sloan still score normally.
- **Non-USD filer with no FX source** → only USD/CAD is supported; any other currency returns `{}` and Altman X4 degrades rather than silently dividing mismatched currencies.
- **Unresolvable fact conflict** → a `data_quality_issues` row flagged `needs_review`, never a guess or a default.
- **Missing input to a signal** → `insufficient_data`, never a defaulted `0`/`false` (AD-16 tri-state).

## Gap worth flagging

`validation/checks.py::run_validation` is fully implemented and covered by
`tests/test_canonicalization.py:234`, but **`pipeline/run.py` never calls it**. Its imports go
straight from `canonicalize_issuer` to the `score_*` functions. The spec's stage order is
ingest → canonicalize → **validate** → score; the validate stage is currently only exercised
by tests, so it's drawn dashed above rather than as a live stage.
