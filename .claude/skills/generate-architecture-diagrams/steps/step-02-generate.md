# Step 2 — Generate the Diagrams

## Mandatory rules
- Load `reference/palette.md` and use its `classDef` palette + type guidance.
- Every node label uses **real** identifiers from Step 1. No placeholders like "Service A".
- Every `:::role` you tag must have a matching `classDef` line at the bottom of the block.
- One file per diagram, numbered per the approved plan. Create `docs/diagrams/` if needed.
- After each file, sanity-check the Mermaid (see checklist at the end).

## For each approved diagram

Write `docs/diagrams/{NN}-{name}.md` as:
```
# {Human Title}

​```mermaid
{diagram body}
​```
```

### 01 — System Architecture (`flowchart LR`)
A `subgraph` per layer (frontend, backend, data, external, infra, CI/CD — only those
present). Tag nodes with roles. Draw the real edges: user → frontend pages → API groups
→ data/external; data sources → seed → store; CI → registry → runtime. Put versions,
hostnames, and counts in `<br/>` sub-labels.

### 02 — User Flow (`flowchart TD`)
Start node → navigation → a `{decision}` for the user's primary goal → one branch per
page/module → the insight/outcome each yields → a shared finish node.

### 03 — Data Pipeline (`flowchart LR`)
`subgraph` stages: Sources → Load/Prepare → Store (tables) → Query layer → Outputs.
Show which source feeds which table, which table feeds which query, which query feeds
which UI output.

### 04 — API Surface (`flowchart TB`)
Frontend node → one `subgraph` per endpoint group, listing the real routes
(`"GET /api/…"`). Draw which groups hit the datastore vs external services.

### 05 — {name} Lifecycle (`sequenceDiagram`)
`autonumber`. One `participant` per real service. Use `alt`/`opt` for branches and
`rect rgb(...)` tinting for phases. End by persisting/returning the result.

### 06 — CI/CD Pipeline (`flowchart TD`)
Trigger → `subgraph` of ordered build/deploy steps → registry → runtime. Follow the
diagram with the real **secrets** and **trigger conditions** as small tables (like the
CI steps you read in Step 1).

## Per-diagram sanity check
Before moving on, verify:
- [ ] The ```mermaid fences are balanced and the block opens with a valid type keyword.
- [ ] Every `:::role` has a `classDef role …;` line.
- [ ] `subgraph` blocks are closed with `end`.
- [ ] Node ids are unique; labels with special chars are quoted (`"GET /api/x"`).
- [ ] Labels contain real names/numbers, not placeholders.

## Next step
When all approved diagrams are written, load `steps/step-03-index.md`.
