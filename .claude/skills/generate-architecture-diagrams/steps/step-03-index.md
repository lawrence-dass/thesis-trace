# Step 3 — Index, Verify & Preview

## Mandatory rules
- Write a README index so the suite is navigable.
- Verify every diagram renders (structurally valid Mermaid).
- Offer a live preview, but don't publish anything without asking.

## 1. Write `docs/diagrams/README.md`
```markdown
# Application Diagrams (Mermaid)

Color-coded, presentation-ready diagrams of {project}. Reflect the stack as of {date}.

1. [01-system-architecture.md](./01-system-architecture.md) — {one-line summary}
{…one numbered line per diagram that was generated…}

## Stack / Infrastructure

| Layer | Technology / Service | Detail |
|-------|----------------------|--------|
| Frontend | {framework} | {host} |
| Backend  | {framework} | {host} |
| Database | {engine} | {host/region} |
| External | {providers} | {models/APIs} |
| Infra    | {registry / env} | {names} |
| CI/CD    | {system} | {trigger} |
```
Fill only the rows that exist. Use the real values gathered in Step 1.

## 2. Verify
For each `docs/diagrams/*.md`:
- [ ] Contains exactly one ```mermaid block that opens with a valid type keyword.
- [ ] Fences balanced; every `subgraph` has an `end`; every `:::role` has a `classDef`.
- [ ] No placeholder labels remain (`Service A`, `TODO`, `{unknown}` only where truly unknown).
- [ ] README links resolve to files that exist.

Report:
```
DIAGRAM SUITE — docs/diagrams/
  ✓ README.md            (index + stack table)
  ✓ 01-system-architecture.md
  {✓ each generated file}
  Rendered: {N}/{N} valid
```

## 3. Offer a live preview (optional)
Mermaid renders natively in Artifacts. Offer:
> "Want a single-page visual preview of the whole suite? I can publish it as a private
> Artifact you can open in the browser."

If **yes**: build one Markdown page embedding each diagram under its heading and publish
it via the Artifact tool (favicon e.g. 🏛️). If **no**, skip.

## 4. Keeping them current
Remind the user (once):
> "Re-run `generate-architecture-diagrams` after a significant architecture change —
> new service, new endpoint group, changed deploy target — so the diagrams don't drift
> from the code."

## Complete
The suite lives in `docs/diagrams/`, indexed and verified.
