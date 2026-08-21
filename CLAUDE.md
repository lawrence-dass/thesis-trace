# CLAUDE.md — Working guidance for ThesisTrace

Run `/session-start` first thing every session — it reads `.claude/handoff/CURRENT.md`
(the single source of truth for resume state) and `.claude/context/project-context.md`
(durable rules/learnings, loaded every session). Run `/session-end` before closing a
window. See `claude-workflow-kit` conventions below.

## Context Management (CRITICAL)

The agent manages its own context budget. These rules constrain **autonomous**
file reading — the user can always ask for any file explicitly.

### Core rule: just-in-time loading
Load a file ONLY when the current task actually needs it. Don't pre-read "to be safe."
Existence and size can be checked without spending tokens (see below).

### Required at session start
- `.claude/handoff/CURRENT.md` — session continuity (run `/session-start`).
- `.claude/context/project-context.md` — durable rules/learnings.

### Never auto-read (unless actively working on it, or the user asks)
- ❌ Large planning docs / specs under `_bmad-output/` — grep for the specific section instead of reading the whole file.
- ❌ `_bmad-output/archive/HANDOFF-*.md` — historical narrative, superseded by `project-context.md` + git/PR history.
- ❌ Slash-command / skill definition files (`.claude/commands/*`, `.claude/skills/*`) — read only when actively invoking or editing one.
- ❌ Config files (`package.json`, `pyproject.toml`, …) unless modifying them.
- ❌ Code files not being actively changed.

### Context budget targets
- **Session start:** < 25,000 tokens (~10% of budget).
- **Red flag:** > 50,000 tokens loaded before real work begins.

### Verify without reading
```bash
test -f file && echo EXISTS || echo MISSING   # existence, 0 tokens
wc -l file                                     # size, 0 content tokens
grep -n "pattern" bigdoc.md                    # locate a section before reading it
```

## Lawrence's standing preferences (honor every session)

1. **Mark the recommended option.** Whenever presenting choices, clearly highlight which one is recommended (and why), for quality development.
2. **Commit frequently** — and always commit at the end of every major task, with a clear message.
3. **Explain in plain language.** After each major task, give an easy-to-read recap of what was done and how to review it, so Lawrence can step away and come back without digging.
4. **Ask for all permissions in one go.** Before starting research or any multi-fetch task, list every web domain, live API fetch, or approval the whole task will need and ask **once**. Never drip-feed one approval at a time — it turns a single task into a chain of interruptions for no added safety, since the activity itself is already approved. Applies equally to the standing "ask before live EDGAR fetch" rule: name all the tickers/CIKs in a single request.

## Project shape

- BMad planning-driven project. Planning artifacts live under `_bmad-output/`.
- Canonical contract: `_bmad-output/specs/spec-thesistrace/SPEC.md` (+ its adopted companions: the architecture spine, the PRD, and `foundational-decisions.md`).
- Deterministic/LLM boundary is inviolable: all scores/numbers are computed deterministically; the LLM only explains and cites, never originates a figure.

## Definition of Done — live-data stories (read before calling one finished)

**Applies to any story that touches SEC EDGAR / Tiingo / Bank-of-Canada ingestion,
concept mapping, a formula spec, or a figure rendered to a user.** Ordinary code
stories use the normal bar: tests pass, lint and types clean, PR green.

The extra bar exists because on this project a green suite has repeatedly meant
nothing. Story 5.4: four real bugs behind 27 passing tests. PR #74: a figure
rendering "0.97B" on two live pages, behind 34 passing tests, a clean `tsc`, and a
written analysis of that exact helper. Rendering the page is what found both.

1. **Verify per-year coverage against live `data.sec.gov` company-facts — never tag
   existence.** A tag can exist and not cover the years you need; filers switch tags
   mid-history (CP's PP&E, FY2021). This is the class the original `shares_outstanding`
   bug belonged to, and it recurs per taxonomy.
2. **Check it is not already answered first.** `engineering-findings.yaml` holds the
   spikes and live verifications; re-fetching wastes a permission ask and risks
   recording a worse answer than the one already there.
3. **A coverage gap may be a DECISION, not a defect** — grep the mapping spec and read
   the `note` before "fixing" it. BCE's debt stopping at FY2023 looks exactly like a
   tag-switch bug and is a live-verified comparability choice.
4. **A gap in every concept at once is a method smell, not a finding.** Real tagging
   gaps are concept-specific. Re-bucket on `end`, not EDGAR's `fy`.
5. **Render it in a browser**, and choose subjects by which code paths they exercise,
   not by convenience. A spot-check only covers the filers you picked — Story 6.6 was
   clean on four and broken on the two not chosen.
6. **Before writing golden entries, confirm the fixture can exercise the new concept.**
   The golden fixtures are trimmed subsets; an entry a fixture cannot reproduce pins an
   outcome while asserting nothing.
7. **Record the verification** in `engineering-findings.yaml`, and **ask for every
   domain, ticker and CIK in one request** (standing preference 4).

Full incident record: `.claude/context/project-context.md`.

## Git workflow (read before making any commit)

Lawrence runs multiple sessions on this repo (desktop and cloud, sometimes overlapping) — a prior collision between two concurrent sessions caused a real divergence (see `_bmad-output/archive/HANDOFF-2026-07-29.md`'s "Real bug found and fixed post-implementation" section for the full story), and a second collision occurred on 2026-08-15 by a different route (rule 5). Rules 1-4 govern what each session commits; rule 5 governs where it works, and the two failures came from those two different places:

1. **Every session works on its own new feature branch — never push directly to `main`.** At the start of a session, `git pull origin main` first, then create a fresh branch (e.g. `claude/<short-task-description>-<date>`). Never reuse an old branch name from a prior session.
2. **Merge back via PR, not a direct push to `main`.** This surfaces any conflict with other concurrent work as a normal PR diff to review, instead of a rejected push discovered after a lot of independent work has piled up.
3. **Pull `main` before starting substantive planning/architecture work specifically** — BMad workflow state (memlogs, spines, specs) can diverge just as easily as source code, and is harder to merge automatically.
4. Push and open the PR at natural checkpoints (end of a story/epic, end of a planning phase) rather than batching a very long uninterrupted run — smaller, more frequent syncs make any real conflict small and easy to see.
5. **Two local sessions must never share one checkout — give each its own `git worktree`.** Rule 1 is not sufficient on its own. A branch is per-repository but the *working directory* is shared, so a second session running `git checkout` switches the files underneath the first one, mid-task, with no warning to either.

   ```bash
   git worktree add ../ThesisTrace-<task> -b claude/<short-task>-<date> origin/main
   git worktree list                      # who currently holds what
   git worktree remove ../ThesisTrace-<task>   # once its PR has merged
   ```

   **This has happened, on 2026-08-15.** Session A committed session B's handover, switched the shared checkout to a new branch and opened PR #76. Session B — still believing it was on its own branch — found five files whose contents were *older* than `HEAD`: committing them would have silently reverted two already-merged PRs (#74's `compactAmount` fix, and #76's own `Badge.test.ts`, which showed as a deletion) inside a commit labelled "session handover". This is the same class of divergence as the 2026-07-29 incident above, reached by a different route.

   **Detecting it after the fact:** `git status` is useless here — the five files showed as five ordinary `M` flags. Read the *direction* of `git diff` instead: if the `-` lines carry NEWER content than the `+` lines, the working tree is behind `HEAD` rather than ahead of it, and committing would revert rather than advance. `git reflog` then shows the checkouts and commits the other session made. **Never resolve this with `git add -A`.** Restore the affected paths from `HEAD` individually, then verify the recovery by running the tests rather than by trusting a clean `git status` — a reverted file and a correct file both produce no output.
