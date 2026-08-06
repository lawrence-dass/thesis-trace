# ThesisTrace Direction, Risk, and Blind-Spot Assessment

**Assessment date:** 2026-08-02  
**Repository:** ThesisTrace  
**Purpose:** Explain the product and technical issues identified during a repository-wide review, document potential solutions, and recommend an execution sequence.

## Executive Summary

ThesisTrace is building an evidence-backed equity-research product for diligence-driven retail investors. It ingests financial facts from SEC EDGAR, converts filer-specific XBRL facts into a canonical financial model, computes established accounting and forensic scores deterministically, and presents the result with provenance. An optional language-model layer is intended to improve the wording of explanations without originating scores or financial claims.

The project is moving in the right technical direction. Its strongest qualities are deterministic computation, explicit handling of missing data, versioned formulas and mappings, immutable provenance, and an honest refusal to produce a single opaque investment score. These choices create a credible foundation for a financial product where trust matters.

The principal risk is no longer whether the system can compute the models. That has largely been demonstrated. The principal risk is whether the current experience materially improves an investment decision. At present, the product is closer to a reliable forensic-score browser than a complete thesis-building tool. Value, growth, change detection, valuation assumptions, thesis falsification, and decision journaling remain future work even though they are closer to the user's final job-to-be-done.

The recommended direction is to finish the active mapping-engine refactor, close the most important trust and operational gaps, and then build one complete investment-decision workflow for a company the primary user is genuinely researching. Universe expansion should follow that validation rather than precede it.

## 1. What ThesisTrace Is Building

ThesisTrace is intended to help an investor answer four broad questions:

1. Is the company financially healthy?
2. Are the reported earnings and accounting signals credible?
3. Is the business growing in a durable way?
4. Is the current price reasonable relative to the business and its risks?

The current implementation concentrates on the first two questions through four deterministic models:

- Piotroski F-Score;
- Altman Z-Score;
- Beneish M-Score; and
- Sloan accruals ratio.

The intended data path is:

1. Fetch issuer facts and supporting market/FX data.
2. Store source facts without mutating the historical record.
3. Map issuer-specific XBRL concepts into versioned canonical concepts.
4. validate the canonical facts and expose data-quality warnings.
5. Compute versioned model outputs and their sub-signals.
6. Materialize results in Postgres.
7. Serve them through a read-only FastAPI API.
8. Present the evidence through a Next.js interface.

This separation is well suited to the product. Scores are reproducible, API reads cannot trigger financial computation, and the language model is outside the numeric path.

## 2. Overall Direction Assessment

### What is working well

- The deterministic/LLM boundary is the correct foundation for a trust-sensitive financial product.
- Missing inputs become `insufficient_data`, rather than fabricated zeroes or silently inferred values.
- Raw facts, canonical facts, mapping versions, formula versions, score inputs, and score runs create an auditable chain.
- Real EDGAR data has been used to discover accounting and XBRL edge cases that synthetic fixtures did not represent.
- IFRS support is being designed from real Canadian filers instead of assumed taxonomy equivalence.
- Model classifications remain separate instead of being blended into an unjustified composite rating.
- The batch-write/read-only-query split is proportionate and understandable.
- CI, linting, migrations, backend tests, and frontend production builds are present.
- The public interface states when data is missing or a company is not covered.

### Where the direction needs correction

The system has validated a technical hypothesis: reliable deterministic scoring from raw filing data is achievable. It has not yet validated the product hypothesis: that these scores, presented this way, change or improve an investment decision.

Further taxonomy coverage would strengthen the data platform, but it would not by itself answer that product question. The next meaningful proof should combine the accounting foundation with valuation, material changes, explicit uncertainties, and a saved thesis for one real decision.

## 3. Detailed Findings and Potential Solutions

### 3.1 The canonical product contract contradicts the implementation

#### Issue

The canonical SPEC still declares a four-company, US-GAAP-only Phase 1 universe and explicitly excludes IFRS companies. The implementation and foundational decision D8 now support `ifrs-full` and include Cameco. The SPEC also retains resolved open questions, including golden-dataset sourcing.

This is a governance defect, not merely stale prose. The repository calls the SPEC and its companions the complete canonical contract. A future contributor could faithfully follow that contract and remove or avoid the IFRS behavior that the project now considers intentional.

#### Potential solution

- Reconcile the SPEC, PRD, architecture spine, foundational decisions, README, sprint status, and golden-dataset universe.
- Make D8's supersession explicit everywhere D6's former IFRS exclusion appears.
- Replace resolved open questions with a decision record and evidence link.
- Add a lightweight documentation-consistency check for fixed universe names, supported taxonomies, and phase status.

#### Acceptance criteria

- One unambiguous Phase 1 universe is declared across code, tests, and planning artifacts.
- No active document states that IFRS is excluded.
- Cameco's expected level of support and caveats are explicitly documented.
- Resolved questions no longer appear as blocking open questions.

### 3.2 Product language promises four lenses while only two are live

#### Issue

The product describes four lenses—Value, Growth, Quality/Health, and Integrity/Evidence—but the current four models populate only Quality/Health and Integrity/Evidence. Calling four models “four transparent lenses” can lead users to believe valuation and growth are already part of the result.

#### Potential solution

- Change Phase 1 marketing copy to “four transparent forensic models across two live lenses.”
- Show Value and Growth as clearly planned rather than partially implied.
- Do not describe the product as portfolio-complete until all four decision dimensions are genuinely usable.

#### Acceptance criteria

- Landing-page language distinguishes models from lenses.
- Every page uses the same phase-honest vocabulary.
- Pending lenses cannot be mistaken for computed analysis.

### 3.3 Technical correctness is being used as a proxy for product usefulness

#### Issue

The golden dataset demonstrates that the implementation matches hand-verified calculations. That is essential, but it does not demonstrate that the models help the user decide whether to investigate, avoid, buy, hold, or monitor a company.

The current “real use” success signal—informing one decision—is too loosely defined to generate actionable learning. Almost any exposure to the product could be interpreted as “informing” a decision.

#### Potential solution

Define a structured decision-validation exercise:

- Record the user's initial thesis before using ThesisTrace.
- Record questions, risks, and assumptions the user would otherwise investigate manually.
- Complete the research using ThesisTrace.
- Record which conclusions changed, which new risks surfaced, how much research time was saved, and where the tool failed to provide enough evidence.
- Repeat with at least three real research decisions before expanding the roadmap.

#### Acceptance criteria

- Each validation session produces a before/after thesis record.
- The project can identify at least one decision changed or materially clarified by the product.
- The user can name the most valuable and least useful elements without relying on general impressions.

### 3.4 The current product is a score browser rather than a thesis workflow

#### Issue

Scores are useful diagnostic evidence, but they are rarely the final investment decision. The current interface does not organize evidence around the investor's central questions:

- What changed in the latest filing?
- Which risks are material?
- Which model inputs drove the result?
- What assumptions would make the thesis wrong?
- What valuation range is plausible?
- What should be monitored next quarter?

Without that workflow, users must translate the model pages into a thesis themselves.

#### Potential solution

Create an “Investment Decision Packet” for each company containing:

1. A concise thesis and counter-thesis.
2. Changes since the prior filing.
3. Quality and integrity evidence.
4. A reverse-DCF or valuation range with explicit assumptions.
5. Material uncertainties and missing evidence.
6. Thesis falsifiers and monitoring triggers.
7. A locally saved decision journal.

#### Acceptance criteria

- A user can move from company selection to a saved, evidence-backed thesis without leaving the product for basic synthesis.
- Every conclusion separates filed facts, deterministic calculations, user assumptions, and generated prose.
- The packet identifies what would invalidate the thesis.

### 3.5 Sub-signal explanations do not expose the full calculation

#### Issue

The product contract promises comparisons such as “ROA 2024 versus ROA 2023,” but the read API and UI primarily show a signal result, a single value, and provenance chips. A user cannot always reconstruct which operands produced a pass, fail, ratio, or weighted component.

#### Potential solution

- Extend the read contract with typed calculation operands.
- Return the input concept, fiscal period, original value, normalized value, units, operator, and role for every signal.
- Render a short deterministic equation for each result.
- Keep presentation logic out of the frontend by returning a structured calculation, not an opaque explanatory string alone.

#### Acceptance criteria

- Every signal can be independently recomputed from the API response.
- The UI shows both compared periods for change-based signals.
- Weighted model components show the raw ratio, coefficient, and contribution.

### 3.6 Provenance links do not reach the exact source fact

#### Issue

Citation chips open the SEC filing directory and display a canonical concept. They do not deep-link to the Inline XBRL fact, identify the source taxonomy tag, show the original units/context, or expose the complete transformation chain. The user must still locate the filed number manually.

This falls short of the strongest interpretation of “exact line-item provenance.”

#### Potential solution

- Persist and expose the source taxonomy, source concept, unit, period context, accession, and Inline XBRL locator where available.
- Add a provenance drawer that distinguishes filed facts from derived facts.
- For derived facts, list every operand and link each operand to its source.
- Deep-link into the filing's Inline XBRL viewer when a stable locator can be constructed; otherwise display the original source-fact record directly in ThesisTrace.

#### Acceptance criteria

- A user can see the original tag, value, unit, period, accession, and transformation without searching the filing.
- A derived number never appears to be directly filed.
- Every derived fact exposes all operands, not only one provenance root.

### 3.7 The LLM boundary is protected by instruction rather than enforcement

#### Issue

The LLM is told not to change claims, numbers, tickers, or citations, but its returned text is accepted without validation. A prompt is not a deterministic guardrail. Enabling the rewrite feature therefore weakens an invariant described as inviolable.

#### Potential solution

The preferred option is to remove free-form rewriting from the critical path until enforcement exists. If retained:

- Extract and compare all numbers, fiscal years, model names, classifications, tickers, and citation identifiers before accepting a rewrite.
- Reject the rewrite and return the deterministic template if any protected token changes.
- Require structured output containing only approved sentence rewrites keyed to existing claim IDs.
- Add adversarial tests for modified signs, decimals, thresholds, caveats, and citations.

#### Acceptance criteria

- A rewrite that changes or removes any protected fact is deterministically rejected.
- Provider failure, timeout, or invalid output always falls back to deterministic text.
- Tests prove the fallback behavior against realistic malicious or accidental alterations.

### 3.8 The public LLM endpoint creates a cost-abuse surface

#### Issue

Any caller can request `polish_text=true`. When an API key is configured, the endpoint can make an LLM request for each historical lens explanation. There is no authentication, quota, rate limit, caching, or request coalescing. An external caller could generate cost and load without using the frontend.

#### Potential solution

- Do not expose the live rewrite as an unrestricted query parameter.
- Prefer precomputed rewrites during the batch pipeline, stored by deterministic explanation hash and model version.
- If on-demand rewriting remains, add rate limiting, response caching, a strict per-request model/year limit, timeouts, and cost telemetry.
- Consider disabling the LLM entirely for Phase 1; the deterministic explanation already satisfies the core trust promise.

#### Acceptance criteria

- One public request can trigger at most one bounded rewrite.
- Repeated requests for identical content do not generate repeated provider calls.
- A monthly hard limit or automatic circuit breaker protects the cost ceiling.

### 3.9 Explanation generation returns unnecessary historical output

#### Issue

The explanation builder iterates across all returned score runs. The overview normally needs the current verdict or a specifically selected model and fiscal year. Rewriting every historical explanation increases latency, payload size, and cost while diluting the most relevant result.

#### Potential solution

- Make the endpoint address a specific model and fiscal year.
- Default to the same latest-valid run used by the verdict.
- Load historical explanations only when the user explicitly selects a historical period.
- Paginate or separately query historical score runs.

#### Acceptance criteria

- The default company view loads only current explanations.
- Historical analysis is fetched on demand.
- API response size remains bounded as history grows.

### 3.10 The overview repository uses an N+1 query pattern

#### Issue

The overview loads runs, then loads results separately for each run, then loads provenance separately for each signal. Query count grows with every historical year and model signal.

#### Potential solution

- Fetch runs, results, inputs, canonical facts, and filings with a bounded set of joined or select-in queries.
- Split current verdict and historical series into separate endpoints.
- Add query-count and response-time tests using representative long-history issuers.

#### Acceptance criteria

- Current overview assembly uses a small, fixed number of database round trips.
- Query count does not scale linearly with the number of signals.
- A defined latency budget is met for the longest-history supported issuer.

### 3.11 Daily scoring can create unnecessary score-run growth

#### Issue

The daily pipeline revisits all scoreable historical years. New score runs supersede prior runs, which preserves history, but unchanged source data and unchanged formula versions do not require new output. Repeated identical recomputation can grow the database and obscure meaningful revisions.

#### Potential solution

- Compute an input fingerprint from canonical fact IDs/content hashes, mapping version, formula version, market-price record, FX record, and applicability metadata.
- Skip score creation when the latest current run has the same fingerprint.
- Create a new run only when inputs, formula, mappings, applicability, or relevant caveats change.

#### Acceptance criteria

- Two identical pipeline executions produce no new score runs.
- A changed fact or version creates a new run and supersedes the previous one.
- Audit history distinguishes meaningful revisions from operational reruns.

### 3.12 One issuer failure can terminate the remaining daily universe

#### Issue

The scheduled pipeline processes issuers sequentially without an issuer-level failure boundary. A transient failure for one company can prevent later companies from updating.

#### Potential solution

- Wrap each issuer execution in an isolated error boundary.
- Record a pipeline-run and issuer-run status with timestamps, stage, error class, and retry eligibility.
- Continue processing independent issuers after a failure.
- Return a non-success job result when any issuer fails so deployment monitoring can alert.

#### Acceptance criteria

- Failure of one issuer does not prevent other issuers from completing.
- The failed company is visibly stale and carries an operator-readable failure reason.
- Scheduled-job monitoring receives a failure signal for partial runs.

### 3.13 External ingestion recovery is incomplete

#### Issue

EDGAR retry behavior covers a limited set of response codes. Timeouts, connection resets, invalid JSON, and other transient server errors can terminate the run. Similar considerations apply to market price and FX ingestion.

#### Potential solution

- Use bounded exponential backoff with jitter for retryable transport failures and 5xx responses.
- Validate content type and payload schema before persistence.
- Record fetch metadata, attempts, response status, and final outcome.
- Use a durable cache so transient upstream failure does not invalidate previously correct materialized results.

#### Acceptance criteria

- Retry policy is consistent and tested across external providers.
- Invalid upstream payloads cannot overwrite or supersede known-good results.
- Operators can distinguish upstream failure from parsing or canonicalization failure.

### 3.14 Golden coverage does not match the active universe

#### Issue

The golden dataset still declares SHOP, CP, QSR, and OTEX as the universe, while production code includes Cameco. This weakens the claim that the active universe is comprehensively regression-guarded.

#### Potential solution

- Add Cameco to the golden universe and use a committed real EDGAR fixture.
- Verify all resolvable canonical inputs and model components independently.
- Explicitly encode expected insufficient-data states and caveats.
- Generate the declared universe for the test from the production universe definition, or assert equality between the two.

#### Acceptance criteria

- Golden-universe membership equals production-universe membership.
- Every active issuer has an independently verified real-data fixture.
- Expected missing models are asserted rather than silently omitted.

### 3.15 Synthetic fixtures protect mechanics but not filer semantics

#### Issue

Several tests use a fabricated Shopify fixture with tags and accessions that do not reflect Shopify's real filings. These tests are useful for isolated mechanics, but they can remain green while real-filer mappings are wrong.

#### Potential solution

- Keep small synthetic fixtures for unit-level edge cases and label them clearly.
- Add real-fixture characterization tests for every supported issuer and taxonomy.
- Test per-year concept coverage, tag switches, amendments, opening balances, quarterly shadowing, derivations, and expected gaps.
- Require a live-data spot check before adding or reprioritizing a mapping fallback.

#### Acceptance criteria

- Mapping behavior is guarded by both focused synthetic tests and representative real fixtures.
- No test presents fabricated data as real-company verification.
- Mapping pull requests document the filer, filing period, and evidence that motivated each fallback.

### 3.16 The active mapping-engine refactor is not yet green

#### Issue

At the time of this assessment, backend verification produced 87 passing tests and one failure. Seven IFRS fallback rules lost or lack the verification note required by `test_every_rule_carries_its_verification_note`. This appears related to the user-owned in-progress conversion of `canonicalization/mappings.py` into declarative YAML specifications.

#### Potential solution

- Restore the filer/date/evidence note for every priority fallback in the YAML files.
- Keep list order as priority but validate uniqueness and documentation during spec loading.
- Complete the refactor before starting additional universe or model work.

#### Acceptance criteria

- The complete backend suite passes.
- Every non-primary mapping has a verification note.
- Golden results remain unchanged through the refactor.

### 3.17 The landing page hides operational failures as an empty universe

#### Issue

The landing page catches all API failures and returns an empty array. It then tells the user that the pipeline has not run. A backend outage, malformed response, deployment misconfiguration, and genuinely empty database therefore appear identical.

#### Potential solution

- Represent `loading`, `empty`, `unreachable`, and `invalid_response` as separate states.
- Log server-side fetch failures with safe context.
- Display a retryable service-unavailable message for operational failures.
- Reserve the empty-universe message for a successful API response containing no issuers.

#### Acceptance criteria

- Users can distinguish no data from unavailable service.
- Operational failures generate an observable server-side event.
- A temporary backend outage does not misleadingly claim that the pipeline never ran.

### 3.18 Operational freshness and failure status are not first-class product data

#### Issue

A trust product can display numerically correct but stale results. The current interface lacks a clear per-company last-successful-pipeline time, latest filing processed, data-provider freshness, failed-stage status, or stale-data policy.

#### Potential solution

- Add pipeline-run and issuer-run tables.
- Expose the latest successful ingestion, latest filing accession, latest score computation, and current failure state.
- Define freshness thresholds based on filing cadence and scheduled-job expectations.
- Display stale or partially updated states in the product.

#### Acceptance criteria

- Every company page states what filing and computation version it reflects.
- Missed or failed scheduled runs are visible to operators.
- The UI does not present stale data as fully current.

### 3.19 The roadmap is too broad for the next product-validation phase

#### Issue

Phase 2 currently combines Value, Growth, filing Q&A, thesis journaling, re-verification, and potentially a larger universe. These are separate product bets and could produce a wide but shallow research dashboard.

#### Potential solution

Sequence Phase 2 around the decision workflow:

1. Latest-filing change detection.
2. A narrow valuation capability, preferably reverse DCF with explicit assumptions.
3. A local thesis journal and thesis-diff workflow.
4. Growth trends required by that workflow.
5. Filing Q&A only after the evidence and citation evaluation framework is ready.
6. Universe expansion after the workflow proves useful.

#### Acceptance criteria

- Each increment is tied to a specific user decision or research task.
- Features are validated with real research before the next major capability begins.
- Universe growth does not substitute for workflow depth.

### 3.20 Canada-first positioning has an unresolved coverage boundary

#### Issue

Using EDGAR provides good access to cross-listed Canadian companies but excludes TSX-only issuers and provides shorter tagged histories for many 40-F filers. This limits both the Canadian differentiation claim and long-horizon Growth analysis.

#### Potential solution

- Define the near-term promise as “Canadian companies available through EDGAR,” not broad Canadian-market coverage.
- Display available history per company and avoid fixed decade-long promises.
- Treat SEDAR+ ingestion as a separate future architecture decision with its own cost and data-quality analysis.
- Choose expansion candidates based on user research needs, not only ease of XBRL coverage.

#### Acceptance criteria

- Coverage language explicitly states EDGAR/cross-listing constraints.
- Trend views adapt to the actual available history.
- No roadmap commitment implies TSX-wide coverage without a SEDAR+ plan.

### 3.21 Model applicability needs stronger treatment

#### Issue

Piotroski, Altman, Beneish, and Sloan are established models, but their thresholds and calibration do not apply uniformly across sectors, reporting regimes, capital structures, or modern asset-light businesses. A visible label such as “Distress” can appear more conclusive than the underlying model warrants.

#### Potential solution

- Make applicability an explicit model output with `applicable`, `applicable_with_caveat`, `out_of_calibration`, and `excluded` states.
- Document the original sample, intended use, known limitations, and ThesisTrace-specific presentation guards for every model.
- Keep a computed value unchanged while clearly separating model output from applicability assessment.
- Avoid presenting threshold labels without nearby applicability context.

#### Acceptance criteria

- Every displayed classification includes its applicability state.
- ThesisTrace-authored calibration or presentation rules are distinguished from the original methodology.
- Users can understand why two valid calculations may not carry equal decision weight.

## 4. Recommended Execution Plan

### Stage 1 — Restore a trustworthy baseline

1. Complete the mapping-YAML refactor and restore all verification notes.
2. Make the backend suite fully green.
3. Reconcile the SPEC, PRD, README, universe, and golden dataset with D8.
4. Add Cameco to the golden coverage contract.
5. Correct product language from four live lenses to four models across two live lenses.

### Stage 2 — Close immediate trust and cost risks

1. Disable unrestricted on-demand LLM rewriting or add deterministic output validation.
2. Protect the rewrite path with caching, request bounds, rate limits, and cost controls.
3. Return only current explanations by default.
4. Expose complete calculation operands and stronger provenance.
5. Separate empty-data states from backend failure states.

### Stage 3 — Make production behavior observable and idempotent

1. Add pipeline-run and per-issuer-run status records.
2. Isolate issuer failures and continue independent work.
3. Add robust provider retry and payload validation.
4. Fingerprint score inputs and skip unchanged score runs.
5. Optimize overview queries and separate current from historical endpoints.

### Stage 4 — Validate the actual product thesis

Build a complete Investment Decision Packet for one company the primary user is actively evaluating. Cameco is a strong candidate because it exercises the Canada-first positioning, IFRS support, capital-intensity caveats, and real model edge cases.

The packet should include:

- an initial user-authored thesis;
- latest-filing changes;
- quality and integrity findings;
- a narrow reverse-DCF or valuation range;
- material uncertainties and missing evidence;
- explicit thesis falsifiers;
- monitoring triggers; and
- a before/after decision record.

### Stage 5 — Expand only after evidence of usefulness

Use the decision exercise to select the next investment:

- deepen Value and Growth;
- implement thesis diff;
- add filing Q&A;
- expand the issuer universe; or
- add SEDAR+ coverage.

The next feature should address the largest observed research failure, not simply the next item in the existing roadmap.

## 5. Recommended Priority Decision

**Recommended:** Finish the active mapping refactor, repair contract drift, and then build one complete Cameco Investment Decision Packet before adding BCE, Suncor, or filing Q&A.

This recommendation preserves the high-quality technical foundation while testing whether ThesisTrace delivers its intended outcome. More issuers would prove breadth. A complete decision packet will prove whether the product helps an investor reason better.

## 6. Verification Evidence From This Assessment

- Backend Ruff checks passed.
- Frontend ESLint passed.
- Frontend production build passed when allowed to fetch the configured Google font.
- The full backend suite reached 87 passing tests and one failing test.
- The remaining failure identified seven IFRS fallback mappings without required verification notes in the active declarative mapping refactor.
- No repository source files were modified during the assessment itself.

## 7. Definition of Done for Directional Alignment

The project can be considered directionally aligned when all of the following are true:

- Canonical documents, implementation, universe, and regression fixtures describe the same product.
- All active issuers are protected by real-data golden verification.
- Every displayed model result is independently reconstructable from exposed inputs.
- Provenance reaches the original filed fact or transparently explains why it cannot.
- LLM output cannot change protected financial claims.
- Public requests cannot create uncontrolled LLM cost.
- Daily pipeline runs are failure-isolated, observable, and idempotent.
- The user has completed at least one documented before/after investment decision using the product.
- The next roadmap choice is based on evidence from that decision rather than infrastructure momentum.

## Conclusion

ThesisTrace has a strong and differentiated technical core. The project should not abandon its emphasis on deterministic accounting, provenance, and honest missing-data handling. Those are its defensible strengths.

The needed correction is one of emphasis: move from proving that more companies and taxonomies can be processed to proving that the resulting evidence changes an investment decision. Closing the documented trust gaps and completing one end-to-end decision workflow is the shortest path to determining whether ThesisTrace is merely an impressive financial-engineering system or a genuinely useful investing product.

## 8. Hiring-Asset Technology Addendum (2026-08-05)

The hiring note is directionally strong, but it should be integrated as one product-aligned vertical slice rather than as a parallel checklist of GenAI keywords. The repository already makes the key orchestration decision in D7: direct SDK calls for Phase-1 narration and LangGraph only for a genuinely stateful filing-aware workflow. That is the right default and should remain the governing decision ([foundational decisions](../_bmad-output/planning-artifacts/foundational-decisions.md#d7--charting-library-and-llm-orchestration-tooling)).

### Current capability gap

The following items are not currently implemented in source or dependencies: LangGraph, RAG/embeddings, LangSmith tracing, MCP, a Dockerfile, a deployment workflow, or an AI-evaluation job. GitHub Actions now covers migrations, Ruff, pytest, ESLint, and the frontend build ([CI workflow](../.github/workflows/ci.yml)), but it has no generative-evaluation or deployment gate. Render configuration exists ([render.yaml](../render.yaml)), but the repository has no evidence of a live environment and the deployment definition does not run an explicit migration step.

The immediate reliability blocker remains the mapping-version rollout: the code is on `concepts_v7`, while the current handoff records that production has not yet been re-canonicalized. Until that is completed, adding an AI mapping assistant would make an already ambiguous data state harder to explain.

There are also two mapping-schema issues to resolve before onboarding automation: `RawFact.concept` permits 256 characters while `ConceptMapping.source_concept` and its migration permit only 128, despite real custom XBRL tags exceeding 128; and `seed_concept_mappings()` checks existing rows by `(canonical_concept, source_concept)` without `source_taxonomy`, even though the database uniqueness key includes the taxonomy. Both can drop or reject a legitimate cross-taxonomy/custom-tag mapping. They are especially dangerous in an agent that proposes previously unseen tags.

### Feature and technology decisions

| Proposal | Decision | Why | Guardrail / stopping rule |
|---|---|---|---|
| Offline XBRL mapping assistant | **Build first after the real decision packet, if onboarding is the largest observed failure** | It targets the real manual scaling bottleneck and demonstrates a stateful propose/check/revise workflow. | Candidate proposals only; no direct writes to `canonical_facts`, `score_runs`, or mappings. Max three attempts, then manual review. |
| Change-explanation RAG | **Build only if the decision packet shows filing interpretation is the binding gap** | It extends the deterministic change-detection work into a useful, cited explanation. | Retrieve only approved filing chunks; every claim needs an exact citation and an abstention path. Do not infer causality when the filing only reports correlation. |
| LangGraph | **Yes, narrowly** | Its state, conditional edges, and loop control fit propose → deterministic check → revise → human review ([official graph API](https://docs.langchain.com/oss/python/langgraph/graph-api)). | Keep it in an offline/admin or evidence-explanation boundary. LangGraph itself is not a safety control. |
| LangChain/LCEL | **No application-level adoption** | A direct Anthropic call is simpler for the existing narration path. A LangGraph dependency may bring transitive LangChain packages; that is different from designing the product around LCEL abstractions. | Do not add an abstraction layer without a second provider/store or a real composition need. |
| LangSmith | **Yes for trace/eval, with data minimization** | It supports datasets, code/LLM/human evaluators, and experiment history ([evaluation concepts](https://docs.langchain.com/langsmith/evaluation-concepts)). | Scrub secrets and unnecessary filing text; pin model/prompt/index versions; define retention before sending financial content to a SaaS service. |
| pgvector RAG | **Yes, when RAG is selected** | Postgres can keep chunks, metadata, and vectors transactionally in the existing store ([pgvector](https://github.com/pgvector/pgvector)). | Add chunk IDs, accession/section/page anchors, embedding model/version, and a corpus version. Do not use vector similarity as evidence by itself. |
| MCP | **Small read-only adapter after the API is stable** | MCP standardizes typed model-controlled tools and output schemas ([MCP tools](https://modelcontextprotocol.io/specification/2025-06-18/server/tools)). | Expose verified scores, changes, methodology, and provenance only. No raw SQL, mapping approval, ingestion, or mutation tools. Add authentication before treating it as a shared service. |
| Docker | **Build now** | It makes the backend reproducible and is useful for Render or Cloud Run. | Image must include a health check, non-root runtime, pinned dependencies, and a separate migration/job command. |
| Kubernetes/GKE | **Defer** | At one-user scale it adds IAM, registry, ingress, rollout, secret, and cost complexity without proving a product need. | Use Cloud Run or Render first; add Kubernetes only if a real deployment requirement or interview demo needs it. Cloud Run accepts standard OCI/Docker images subject to its runtime contract ([Cloud Run](https://docs.cloud.google.com/run/docs/container-contract)). |
| Cloud certification | **Personal hiring activity, not a product dependency** | It may satisfy a screening checkbox, but it does not repair the product. | Schedule only after a shareable deployment exists. |

### The important model-risk qualification

The phrase “the LLM never touches the numbers” is fully accurate for score narration, but not literally accurate for an XBRL mapping assistant. A proposed mapping can change which raw fact is selected and therefore change a later deterministic score. The safer and more honest claim is:

> The model cannot write a financial fact or score. It may propose a mapping that could influence a future deterministic result, but that proposal is isolated, mechanically checked, versioned, and human-approved before canonicalization.

The identity check and golden dataset are necessary but not sufficient. Two tags can produce the same expected value while having different semantics, units, dimensions, period contexts, sign conventions, or consolidation scope. The deterministic gate must therefore validate more than an aggregate score:

- source taxonomy and exact tag;
- unit and period/duration semantics;
- dimensions and consolidation context;
- sign and polarity;
- candidate concept compatibility;
- accounting identities where one exists; and
- expected filed value and provenance for the selected fiscal years.

Every approved proposal should record the candidate tag, canonical concept, evidence spans, confidence, deterministic-check results, reviewer identity, approval time, graph run ID, model ID, prompt version, and the mapping version it created. The promotion operation must be the only path that can create a new mapping version; the agent must never call the production canonicalization writer directly.

### Recommended vertical slice

Do not build both GenAI features at once. The recommended hiring-critical slice is:

1. Close the `concepts_v7` production rollout and complete one real investment decision packet, as required by D9/D10.
2. Add an offline mapping-proposal schema and a staging mapping version for one new filer and one concept family (for example PP&E or debt).
3. Implement a LangGraph workflow with `retrieve`, `propose`, `check`, `route`, and `manual_review` nodes. Cap retries at three and persist failed proposals.
4. Run canonicalization and the golden dataset only after human approval; compare old and new mapping versions and require an explicit diff review.
5. Add an AI-evaluation job to CI. Use deterministic checks for schema, exact tag/concept, citation coverage, and abstention; use LLM-as-judge only as a secondary quality signal. Run provider-backed evaluations on a protected/nightly workflow, not on every pull request.
6. Containerize the backend and deploy one URL that can be screen-shared. Add a health/readiness check, migration job, rollback note, and a visible build/version identifier.
7. Add the read-only MCP server after the REST API contract is stable and demonstrate `get_score`, `get_changes`, `get_provenance`, and `get_methodology` with typed output schemas.

This produces a credible interview story: a real accounting-data bottleneck, a stateful agent, deterministic verification, human approval, versioned promotion, evaluation, and a deployed system. It does not claim autonomous financial analysis.

### Evaluation contract

Before adding LangSmith or a live provider, commit a small evaluation set covering:

- correct mapping;
- deliberate abstention on ambiguous tags;
- wrong unit or dimension;
- restated versus originally filed values;
- taxonomy/tag changes over time;
- a failed identity check followed by a useful revision;
- retry-limit termination; and
- exact citation preservation.

Track at least proposal precision, abstention rate, deterministic-gate pass rate, human-approval rate, citation support rate, latency, provider errors, and cost per onboarding run. A high confidence score is not an acceptance criterion; verified evidence and reviewer approval are.

### Scope decision

The hiring note should be accepted as a prioritization lens, not as permission to bypass D9. The mapping assistant is the strongest combined product-and-hiring candidate, but only if the real decision packet confirms onboarding/mapping is the largest research or coverage failure. Otherwise the next increment should be selected from the actual packet, and the mapping assistant should remain a documented future option. Filing Q&A, Kubernetes, fine-tuning, full-history embeddings, monitoring dashboards, and a broad MCP mutation surface remain explicitly out of the hiring-critical slice.

The earlier sections of this document are point-in-time findings from 2026-08-02. This addendum supersedes their old test-count wording where it conflicts with the current handoff; the current repository reports 245 backend tests passing and one skipped, with backend/frontend CI green. No production deployment or GenAI dependency was added as part of this assessment.
