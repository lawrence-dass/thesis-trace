---
name: generate-architecture-diagrams
description: Analyze the actual codebase and generate a color-coded, presentation-ready Mermaid diagram suite (system architecture + adaptive extras) into docs/diagrams/. Grounded in the real stack — real service names, routes, and numbers, never generic boilerplate.
---

# Generate Architecture Diagrams

**Goal:** Read the real project — its stack, layers, routes, data flow, and CI — and
produce a set of **color-coded Mermaid diagrams** in `docs/diagrams/`, with a README
index. The output should look presentation-ready for a stakeholder review or a portfolio
walkthrough, and reflect what is *actually deployed*, not a generic template.

**Your role:** a solutions architect documenting a system you've just read end to end.
Every box, label, and number must trace to something real in the repo. If you don't
know a value, say so in the diagram — never invent a URL, row count, or service name.

---

## What it produces

`docs/diagrams/` containing:

- **`README.md`** — an index of the diagrams + a "Stack / Infrastructure" table.
- **`01-system-architecture.md`** — always generated. The full stack map.
- **Adaptive extras** — generated only when the codebase clearly warrants each:

| File | Generate when… | Mermaid type |
|------|----------------|--------------|
| `02-user-flow.md` | there's a UI with distinct pages/modules | `flowchart TD` |
| `03-data-pipeline.md` | there's ingestion/ETL/seed → store → outputs | `flowchart LR` |
| `04-api-surface.md` | there's an HTTP/RPC API with several endpoint groups | `flowchart TB` |
| `05-<name>-lifecycle.md` | there's a notable multi-service request flow worth tracing | `sequenceDiagram` |
| `06-cicd-pipeline.md` | there's CI/CD config (e.g. `.github/workflows/`) | `flowchart TD` |

Numbers are stable slots — skip a number if that diagram doesn't apply, don't renumber.

---

## Grounding rules (non-negotiable)

- **Read before drawing.** Detect the stack from real files (`package.json`,
  `requirements.txt`/`pyproject.toml`, `go.mod`, `Dockerfile`, IaC, CI configs).
- **Use real identifiers** — actual service names, endpoint paths, table names,
  external providers, deploy targets.
- **Real numbers where available** — row counts, endpoint counts, module counts.
- **Mark the unknown** — if a value isn't discoverable, label it `{unknown}` or omit it.
  Never fabricate.
- **Consistent palette** — every diagram uses the shared `classDef` palette in
  `reference/palette.md` so the suite reads as one visual system.

---

## Execution

Load and run `steps/step-01-analyze.md`. Codebase discovery happens there; nothing is
drawn until the analysis is confirmed with the user.
