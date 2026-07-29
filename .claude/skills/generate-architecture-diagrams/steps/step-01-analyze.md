# Step 1 — Analyze the Codebase

## Mandatory rules
- READ real files before concluding anything. Do not guess the stack.
- Record concrete identifiers (service names, hosts, routes, tables) — you'll put them in the diagrams.
- Decide which diagrams apply based on evidence, not ambition.
- Never fabricate. If a value isn't in the repo, mark it `{unknown}`.

## Discovery sequence

### 1. Detect the stack
Inspect whatever exists:
```bash
ls -la
for f in package.json requirements.txt pyproject.toml go.mod Cargo.toml pom.xml \
         Dockerfile docker-compose.yml; do test -f "$f" && echo "FOUND $f"; done
find . -maxdepth 2 -iname "*.tf" -o -iname "*.bicep" 2>/dev/null | grep -v node_modules | head
ls .github/workflows/ 2>/dev/null
```
Read the ones that exist. Note: languages, frameworks, key libraries, and versions.

### 2. Identify the layers
Map the project onto these (some may be absent):
- **Frontend / client** — UI framework, pages/modules, where it's hosted.
- **Backend / API** — framework, service modules, where it runs.
- **Data** — database(s), tables, seed/ETL scripts, raw sources.
- **External services** — LLM/API providers, third-party integrations.
- **Infra** — registries, container envs, hosting targets.
- **CI/CD** — pipelines, triggers, deploy steps.

### 3. Enumerate the API surface (if any)
Grep for route/endpoint definitions in the project's idiom, e.g.:
```bash
grep -rnE "@(app|router|blueprint)\.(get|post|put|delete)|\.route\(|app\.(get|post)\(|Route\(" \
  --include=*.py --include=*.ts --include=*.js --include=*.go . 2>/dev/null | grep -v node_modules | head -60
```
Group endpoints by module/prefix. Count them.

### 4. Trace data flow (if applicable)
Find raw sources (CSV/XLSX/seed files), the load/seed script, the schema/tables, and
which API queries read which tables, feeding which UI outputs.

### 5. Read CI/CD (if present)
Read `.github/workflows/*` (or equivalent). Capture: trigger conditions, build steps,
registry, deploy target, required secrets.

### 6. Spot a lifecycle worth a sequence diagram
Is there a request that fans out across services (e.g. UI → API → DB + external API →
back)? If yes, note the participants and the branch conditions.

## Decide the diagram set

`01-system-architecture` is **always** produced. For each extra, include it only if the
evidence is there:

```
DIAGRAM PLAN
────────────────────────────────────────
✓ 01 system-architecture   (always)
{✓/–} 02 user-flow          — {UI with distinct pages? yes/no}
{✓/–} 03 data-pipeline      — {ingestion→store→outputs present? yes/no}
{✓/–} 04 api-surface        — {multiple endpoint groups? N endpoints}
{✓/–} 05 {name}-lifecycle   — {notable multi-service flow? which}
{✓/–} 06 cicd-pipeline      — {CI config present? which file}
```

## Present findings & confirm
Show the user:
1. **Detected stack** (layer by layer, with real names/versions).
2. **The diagram plan** above, with the reason for each include/skip.
3. Ask: **"Generate these diagrams? (adjust the list, or approve)"**

Do NOT draw anything until the plan is approved.

## Next step
On approval, load `steps/step-02-generate.md`.
