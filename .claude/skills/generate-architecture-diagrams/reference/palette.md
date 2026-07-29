# Shared Diagram Palette & Type Guide

Reuse this across every diagram in the suite so the whole set reads as one visual
system. Paste the `classDef` lines you use at the bottom of each diagram's ```mermaid
block, and tag nodes with `:::role`.

## Color palette (semantic roles)

| Role | `classDef` line |
|------|-----------------|
| **actor** (users, external people) | `classDef actor fill:#F3E8FF,stroke:#7E22CE,color:#3B0764,stroke-width:2px;` |
| **frontend** (UI, client) | `classDef frontend fill:#DBEAFE,stroke:#2563EB,color:#1E3A8A,stroke-width:1.5px;` |
| **backend** (API, services) | `classDef backend fill:#DCFCE7,stroke:#16A34A,color:#14532D,stroke-width:1.5px;` |
| **database** (stores, tables) | `classDef database fill:#FEF3C7,stroke:#D97706,color:#78350F,stroke-width:1.5px;` |
| **table** (individual tables) | `classDef table fill:#EDE9FE,stroke:#7C3AED,color:#4C1D95,stroke-width:1.5px;` |
| **source** (raw data, files) | `classDef source fill:#FFF7ED,stroke:#EA580C,color:#9A3412,stroke-width:1.5px;` |
| **llm / external API** | `classDef llm fill:#FCE7F3,stroke:#DB2777,color:#831843,stroke-width:1.5px;` |
| **infra** (registries, envs) | `classDef infra fill:#E0F2FE,stroke:#0284C7,color:#0C4A6E,stroke-width:1.5px;` |
| **cicd** (pipeline steps) | `classDef cicd fill:#DBEAFE,stroke:#2563EB,color:#1E3A8A,stroke-width:1.2px;` |

Flow-only accent roles (for user-flow / pipeline diagrams):

| Role | `classDef` line |
|------|-----------------|
| **start** | `classDef start fill:#DCFCE7,stroke:#16A34A,color:#14532D,stroke-width:2px;` |
| **finish** | `classDef finish fill:#DBEAFE,stroke:#2563EB,color:#1E3A8A,stroke-width:2px;` |
| **decision** | `classDef decision fill:#FCE7F3,stroke:#DB2777,color:#831843,stroke-width:1.5px;` |
| **action / process** | `classDef action fill:#FEF3C7,stroke:#D97706,color:#78350F,stroke-width:1.5px;` |
| **insight / output** | `classDef insight fill:#F3E8FF,stroke:#7E22CE,color:#3B0764,stroke-width:1.5px;` |

**Rule:** only include `classDef` lines for roles you actually use in that diagram, and
make sure every `:::role` you tag has a matching `classDef`.

## Choosing the diagram type

| Showing… | Use |
|----------|-----|
| Static component/layer map | `flowchart LR` with a `subgraph` per layer |
| A user's decision journey | `flowchart TD` with `{decision}` diamonds |
| Data moving through stages | `flowchart LR` (sources → store → API → outputs) |
| Endpoints grouped by owner | `flowchart TB` with a `subgraph` per group |
| A timed multi-service exchange | `sequenceDiagram` (use `alt`/`opt`/`rect` for branches) |
| A build/deploy pipeline | `flowchart TD`, linear steps |

## Conventions

- Use `subgraph` blocks to group by layer/module; name them for the real service
  (`subgraph BE["Flask API — Azure Container Apps"]`).
- Use `[( )]` for stores, `(( ))` for start/end, `{ }` for decisions.
- Put real detail in `<br/>` sub-labels (versions, row counts, hostnames).
- Keep one diagram = one concern. Don't cram the whole system into one chart beyond
  the system-architecture map.
