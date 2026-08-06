# Phase 2 Brainstorm Brief — GenAI track, scope, and what is actually true

**Written:** 2026-08-05 · **Audience:** the cloud session that will turn this into epics and stories
**Status:** input to a brainstorm. **Nothing here is adopted.**

## How to use this document

This is a briefing, not a plan. It exists because two separate assessments
(`THESISTRACE-DIRECTION-AND-RISK-ASSESSMENT.md` and a scope/SEDAR+ analysis) contain findings that
are partly stale, partly contradictory, and partly unverified — and because turning them into epics
without reconciling them first would encode the contradictions into the backlog.

**Deliberately NOT written into `epics.md` or `sprint-status.yaml`.** Those files now formally record
Epics 6–9 as `decomposition: deferred` under D9, with D10 defining the gate. Writing a GenAI epic
into them today would bypass the gate this repo just spent a session making evaluable. The strawman
in §6 is something to argue with, not a backlog.

Claims below are tagged:

- **[VERIFIED]** — checked against this repository or live data on 2026-08-05, with the evidence stated.
- **[JUDGEMENT]** — an opinion. Argue with it.
- **[UNVERIFIED]** — inherited from another document and not independently confirmed here.

---

## 1. A third of the risk assessment is already fixed

`THESISTRACE-DIRECTION-AND-RISK-ASSESSMENT.md` is dated 2026-08-02. Its addendum corrects the test
counts but its body sections were not revisited. **[VERIFIED]**

| Finding | Status |
|---|---|
| 3.1 SPEC contradicts implementation | Fixed 2026-08-04 — contract drift repaired |
| 3.14 Golden ≠ active universe | Fixed 2026-08-04 — 7 of 7 hand-verified |
| 3.16 Mapping refactor not green | Fixed — 245 passed / 1 skipped |
| 3.19 Roadmap too broad | Addressed by D9 |
| 3.3 "Real use" too loosely defined | Addressed by D10 |
| 3.10 N+1 overview queries | **Partially** — Epic 5 applied AD-1 single-pass discipline. Needs measurement, not assumption. |

**Action for the cloud session:** do not create stories for the six rows above without re-checking.
This repo has been burned by exactly this before — four of five `sprint-status.yaml` action items were
recorded `open` while already satisfied, which sent a fresh session chasing solved problems.

## 2. Findings that are real and unfixed

Each verified in code or against live data on 2026-08-05. **[VERIFIED]**

| # | Finding | Evidence |
|---|---|---|
| 3.12 | **One issuer failure kills the rest of the nightly universe** | Zero `try`/`except` in `pipeline/run.py`'s universe loop |
| 3.7 | LLM rewrite output accepted unvalidated | `explanation/llm.py` — `polish()` returns provider text directly |
| 3.8 | Public cost-abuse surface | `api/routes.py:79` — `polish_text` is an unauthenticated query param |
| 3.11 | No score-run input fingerprint | No fingerprint/content-hash anywhere in `backend/scoring/` |
| — | `ConceptMapping.source_concept` is `String(128)`; `RawFact.concept` is `String(256)` | **140 rows in the local DB already carry tags over 128 chars, longest 170** |
| — | `seed_concept_mappings` dedups on 2 columns; DB constraint uses 4 | `mappings/engine.py:249` vs `uq_concept_mappings_version_key` |

**3.12 is the highest-value fix on this list. [JUDGEMENT]** It is a silent single point of failure on
a daily cron, and the fix is small.

### Severity corrections to the addendum's two schema claims

**Column width is understated.** The addendum presents it as a schema smell. It is a live wall: real
EDGAR tags in the *current* universe already exceed the limit. Any mapping-proposal feature hits this
on day one. Migration required before, not during.

**The dedup key is overstated as to current risk, and the mechanism matters.** Five `(canonical,
source)` pairs genuinely collide across taxonomies — `Assets→total_assets`, `ProfitLoss→net_income`,
`Liabilities→total_liabilities`, `SellingGeneralAndAdministrativeExpense→sga`,
`GrossProfit→gross_profit`. But **75 rules are declared and 75 rows are seeded**: `existing` is
snapshotted once before the loop, so both taxonomies land in a single pass. It bites only when a *new*
rule is added later whose `(canonical, source)` matches an existing row under a different taxonomy —
an incremental-operation bug, the same shape as `canonical_facts_amendment_gap`.

Blast radius is also smaller than implied: **`concept_mappings` is effectively write-only.**
Canonicalization reads `MAPPING_RULES` from YAML; the table's only read is its own dedup. A dropped
row corrupts the published audit record, not any score. Still worth fixing — and a genuine blocker for
an agent that writes proposals into that table — but it does not threaten correctness today.

## 3. Two contradictions that must be resolved before decomposition

### 3a. Finding 3.3 vs D10 — how many decision packets?

The risk assessment says *"repeat with at least three real research decisions before expanding the
roadmap."* D10 (merged 2026-08-05) says **one** packet closes D3.2 and unblocks decomposition.

**Recommendation: keep D10's one-packet rule. [JUDGEMENT]** The assessment conflates two questions —
*"is the product validated?"* (three is reasonable) and *"what do I build next?"* (one is sufficient).
D9's selection criterion needs a single largest observed failure. Requiring three before *any*
increment means building nothing for months while accumulating evidence about a product you have
stopped improving.

### 3b. The scope analysis contradicts itself

Its paragraph 1 targets *"ideally 50-plus rather than 30 so it reads as a product and not a demo."*
Its paragraph 5 concludes *"finishing the pillars matters more than adding names."* Both cannot drive
the roadmap.

**Recommendation: drop the number. [JUDGEMENT]** *"So it reads as a product"* is an optics argument,
and it is what D9's universe posture (*"breadth is not progress"*) and PRD OQ8 (*"manual expansion, on
demand only"*) both rule out. It also silently resolves the product-vs-hiring fork that the same
document's final paragraph calls unresolved.

**Verification capacity is a harder ceiling than "honestly allows" implies. [VERIFIED]** Seven filers
took five separate hand-verification sessions (2026-07-23/25/26/29, 2026-08-04), each independently
recomputing every model component without importing the scoring code. And the standing rule compounds
it: *SM-1 is a claim about the universe, so expanding the universe reopens it* — every added name must
extend `phase1_golden.yaml` in the same change. 50 names is 50 permanent golden entries, not 50
ingestions.

## 4. Scope and SEDAR+ — the position, corrected

The scope analysis is strongest here and should mostly stand. Three amendments:

1. **Upgrade the SEDAR+ argument from "harder" to "incompatible."** PDF extraction does not merely
   widen the pipeline — a number a model read off a page cannot carry the same provenance as an
   XBRL-tagged fact. Supporting it requires a **second trust tier** with different provenance,
   confidence and display treatment. That is an AD-19 spec change, not an epic. This is a much more
   defensible reason to defer than effort.
2. **Source the premise.** *"No API, no XBRL"* is **[UNVERIFIED]** here. It matches general
   understanding of SEDAR+, but pin it to a date and a source — an unsourced absolute about a filing
   system is exactly what an interviewer probes.
3. **Make the demand signal measurable at N=1.** *"Users … explicitly asking for names you don't
   cover"* presupposes users that do not exist; D3.2 says **user zero**. Reframe as *"user zero hits a
   name outside coverage during a real research decision, more than once"* — measurable today, and it
   slots into the decision packet's §4 and §5. **Fold this into D10 rather than defining it
   separately**, or there will be two competing definitions of one gate.

**Also restate "four working pillars" precisely.** Under D9, Epic 6 is *reverse DCF only — explicitly
a narrow slice of Value, not the full lens* — and Growth (Epic 8) is a headline with no scope. "Four
working pillars" is not the near-term plan; a narrow valuation capability is.

---

## 5. The GenAI track — how the three technologies actually fit

### The asset not yet being used

ThesisTrace has a **deterministic oracle**: scores, accounting identities and filed values are
computable ground truth, and a hand-verified golden dataset across 7 filers and 2 accounting regimes
already exists. That means every model output here can be *mechanically verified* rather than
eyeballed — and it means an evaluation set already exists.

Most GenAI portfolio projects cannot demonstrate evaluation because they have no ground truth. This
one can. **That is the differentiator, and the integration must be wired to it or it is thrown away.**

### The spine: read, explain, admit

Three technologies, three different trust postures toward verified evidence:

| | Technology | Relationship | May it affect a number? |
|---|---|---|---|
| **Read** | **MCP** | How an external model *consumes* verified evidence | Never — returns computed values only |
| **Explain** | **RAG** | How filing narrative gets *attached* to verified numbers | No — prose only, must cite, must abstain |
| **Admit** | **LangGraph** | How new evidence is *admitted* to the system | Indirectly — therefore gated and human-approved |

The framing to defend in an interview is not *"I used three technologies."* It is:

> **One invariant — no model may originate a financial claim — needed three different enforcement
> mechanisms depending on what the model was allowed to touch.**

### MCP — first

Read-only server exposing `get_score`, `get_changes`, `get_provenance`, `get_methodology`, all mapping
1:1 onto endpoints that already exist and are tested. Zero new correctness surface.

The demo is 60 seconds: ask an MCP client to compare two filers on earnings quality and watch it
return deterministic, cited numbers instead of hallucinating.

**The design decision worth discussing:** the tri-state. Most MCP servers return `null` or an error for
missing data; a model consuming `null` will confabulate around it. Return `insufficient_data` as a
typed first-class value **with its reason** ("Beneish cannot resolve: SHOP files no long-term debt
tag") and the consuming model will say so instead. AD-16 already gives you this — it just needs
exposing.

### RAG — attached to change detection, not Q&A

**Do not build filing Q&A.** It is the commodity demo, the heaviest lift, and D9 correctly places it
last.

Build this instead: the diff engine already detects that a score moved (Epic 5, shipped). RAG answers
*why* — retrieve where management discusses it, cite the exact accession and section, and **abstain
when the filing does not say.**

Why this version is stronger:

- **The question is bounded by a verified fact.** Not *"tell me about Cameco"* but *"gross margin fell
  5.91% → 0.13% in FY2021 — find where management addresses this."* A bounded question has a
  checkable answer.
- **Abstention becomes testable.** Construct cases where the filing genuinely does not explain a move
  and assert the system says so. Abstention is the most under-demonstrated RAG skill.
- **Corpus versioning is a real problem here, not a contrived one.** Filings get amended; a 10-K/A
  restates text. Point-in-time retrieval — *"what did the filing say as of the date this score was
  computed?"* — maps directly onto the documented `canonical_facts_amendment_gap`.

**Scope control:** embed *sections* (MD&A, risk factors, specific notes), not whole filings. pgvector
keeps chunks, metadata and vectors transactional in the Postgres already running.

### LangGraph — the mapping agent, reframed

An internal tooling agent with human review is **more** credible enterprise experience than a
user-facing chatbot, because that is what most real enterprise GenAI is.

**The D9 tension largely dissolves once it stops being called a Phase 2 feature.** It is tooling that
makes universe expansion cheap — it does not compete with reverse DCF for the next-increment slot, so
it does not need to win the decision packet's selection at all. **[JUDGEMENT]** This is a genuine
reframe of the addendum's position, which gates it on onboarding being the largest observed failure.

Why LangGraph genuinely earns its place, rather than being imposed:

- Real cycles — propose → check → revise, with state accumulating across attempts
- Conditional routing on a **deterministic** check result, not on model self-assessment
- Bounded retries (cap three, then escalate)
- **Human-in-the-loop via interrupt/checkpoint** — the highest-value LangGraph feature, and the one
  most demos skip

**Blockers to clear first:** both schema issues in §2.

**And the honesty fix:** *"the LLM never touches the numbers"* stops being true the moment this
exists. The addendum's restatement is correct and belongs in `SPEC.md`, not an appendix — a mapping
proposal *can* influence a future deterministic result, and the accurate claim is that it is isolated,
mechanically checked, versioned, and human-approved first.

### The prerequisite nobody listed

**Build the evaluation harness against the LLM rewrite path that already ships.** §3.7 is live in
production and accepts provider output unvalidated. Instrumenting and constraining *that* closes a real
trust gap, gives you an evaluated surface before adding a second one, and is the better anecdote:
*"I audited my own guardrail and found it was advisory, not enforced."*

**LangSmith caveat:** it sends financial filing text to a third-party SaaS. Decide retention and
scrubbing before the first trace.

---

## 6. Strawman — argue with this, do not adopt it

Lettered, not numbered, because these have **not** been slotted into D9's sequence and must not be
until a decision packet exists. Sizes are relative, not estimates.

### Track P — prerequisites (no D9 gate; dominant under either fork)

| | Item | Size |
|---|---|---|
| P1 | Issuer failure boundary in the nightly pipeline (§3.12) | S |
| P2 | Two mapping-schema fixes: widen `source_concept`, add `source_taxonomy` to the dedup key | S |
| P3 | Docker image + one deployed URL with health check, migration step, visible version | M |
| P4 | Evaluation harness + LangSmith tracing, applied to the **existing** rewrite path; enforce §3.7 | M |

### Track G1 — MCP read-only server

- G1.1 Server scaffold, typed output schemas, one tool (`get_score`) end to end
- G1.2 Remaining tools: `get_changes`, `get_provenance`, `get_methodology`
- G1.3 Tri-state as a typed first-class return with reason text
- G1.4 Contract tests asserting MCP output matches the REST endpoint it wraps

### Track G2 — cited change explanation (RAG)

- G2.1 Section-scoped filing corpus + pgvector schema with accession/section anchors and corpus version
- G2.2 Retrieval bounded by a detected score change
- G2.3 Citation enforcement — every claim carries an exact span, or the system abstains
- G2.4 Point-in-time retrieval across amendments
- G2.5 Evaluation set: correct explanation, justified abstention, amended-filing case

### Track G3 — mapping proposal agent (LangGraph)

- G3.1 Proposal schema + staging mapping version; no writes to production tables
- G3.2 Deterministic gate: taxonomy, tag, unit, period, dimensions, sign, identities, filed values
- G3.3 LangGraph `retrieve → propose → check → route → manual_review`, retries capped at three
- G3.4 Human approval + versioned promotion as the **only** path that creates a mapping version
- G3.5 Old-vs-new mapping-version diff review; golden dataset runs only after approval
- G3.6 `SPEC.md` amendment restating the model-risk claim honestly

**Suggested order: P1–P4 → G1 → G2 → G3.** **[JUDGEMENT]** MCP is highest signal per hour and lowest
risk; RAG attaches to shipped work; LangGraph needs both P2 and P4 first.

## 7. Decisions the cloud session needs to make

1. **One packet or three?** (§3a) — recommend one, per D10.
2. **Is there a coverage target at all?** (§3b) — recommend no fixed number; let the packet decide.
3. **Does the GenAI track need to pass D9's gate, or is it tooling running alongside?** This is the
   pivotal one. If tooling, G1–G3 can proceed without waiting on the packet. If a feature, only
   Track P can start now.
4. **Product or hiring artifact?** The scope document calls this unresolved and it still is — but it
   is less binary than presented: **MCP is genuinely both**, and Track P is dominant under either
   branch. The honest sequencing is to do what is dominant, write the packet, and let it decide the
   rest.
5. **Does the demand signal fold into D10, or stand alone?** — recommend fold, to avoid two
   definitions of one gate.

## 8. What was verified, and what was not

**Verified on 2026-08-05** against this repository and a local Postgres holding all 7 filers at
`concepts_v7`: every row in §2; the six stale findings in §1; the five cross-taxonomy collisions and
the 75/75 seed count; the 140 over-length tags; the absence of a failure boundary, a fingerprint, and
rewrite validation.

**Not verified:** the SEDAR+ API/XBRL claim; finding 3.10's current severity (needs a query-count
measurement, not a reading); any estimate of how long a filer takes to hand-verify beyond counting the
sessions in the project history.

## 9. Source documents

- `docs/THESISTRACE-DIRECTION-AND-RISK-ASSESSMENT.md` — 2026-08-02 body, 2026-08-05 hiring addendum
- `_bmad-output/planning-artifacts/foundational-decisions.md` — D3 (status), D5, D7, D8, D9, D10
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — `epic_catalog`, open findings
- `.claude/context/project-context.md` — anti-patterns and learnings, including the ones this brief relies on
