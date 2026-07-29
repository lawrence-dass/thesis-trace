# Code Review Checklist

**Validation target:** the staged/committed diff · **Criticality:** HIGH

Run at the end of `/review-code`. Any **Auto-block** item that fails blocks the commit.

> Judge against `.claude/context/project-context.md` for this project's standards,
> security expectations, and NON-NEGOTIABLE domain rules.

## Standards
- [ ] Follows the project's typing/contract/formatting standards.
- [ ] No suppressed type/lint warnings without a justifying comment.
- [ ] Naming is descriptive; no magic numbers (named constants).

## Design & Quality
- [ ] Functions have a single responsibility; reasonable size; clear return types.
- [ ] Error handling is specific; no silent failures; helpful user-facing messages.
- [ ] No dead or commented-out code; comments explain "why", not "what".

## Security  🚫 Auto-block on failure
- [ ] No injection (SQL/command/XSS) — parameterized/escaped.
- [ ] No secrets in code — sourced from env/secret manager.
- [ ] Input validated at boundaries; no sensitive data in logs.
- [ ] Auth/authz present where required.

## Tests  🚫 Auto-block if missing
- [ ] Tests exist for all new code; coverage ≥ target.
- [ ] Edge and error cases covered; tests are readable (arrange/act/assert).
- [ ] No test smells (sleeps, hardcoded dates, order-dependence).

## Domain Rules  🚫 Auto-block on violation
- [ ] Every NON-NEGOTIABLE pattern in `project-context.md` is respected.

## Performance & Maintainability
- [ ] No N+1 queries; heavy I/O is async; no needless API calls in loops.
- [ ] New dependencies justified; imports organized; no circular deps.

## Final
- [ ] Full validation suite (test + type + lint + format) passes.

## Output
```
Code Review: {APPROVED | MINOR ISSUES | NEEDS WORK}

Files: {list}
Issues: {file:line} {severity} — {desc}
Decision: {commit | fix first | block}
```
