# Handover — 2026-10-08 05:10 | Claude Opus 5

## Mode
Task complete — Story 13.4a merged (2 rounds); PR queue cleared; nothing mid-flight. Next
session's focus is NOT the next story: see **Open: BMad drift**.

## Focus
- **Task**: Story 13.4a, then the Codex round it triggered, then the stale-PR queue
- **Branch**: `main` (all four PRs merged); this handover lands on
  `claude/session-handover-2026-10-08`
- **State**: complete
- **Progress**: Epic 13 at 4/17

## Resume Point
**NOT Story 13.4b yet.** Lawrence, 2026-10-08: the process feels like it is drifting away from
how BMad is meant to drive the work. Fix the method before consuming more of it. Three steps,
in order, in **Open: BMad drift** below. Story 13.4b is next *after* that, and its resume
notes are intact: run `bmad-create-story` first (`test_an_active_story_has_a_story_file` fails
if 13.4b leaves `backlog` without its file), and read `_check_brand_identity` in
`mappings/engine.py` first — the axis-reachability check 13.4a round 2 added is the pattern
13.4b needs.

## Uncommitted Files
None — working tree clean.

## What Happened This Session
- 13.4a round 1 merged (#144), then the Codex round on `ff1e1d1` returned 11 findings — all
  verified before fixing. Four contradicted 13.4a's own ACs, so rule 3 made them this story's
  work, not a new story: round 2 (#145). Detail in
  `engineering-findings.yaml#story_13_4a_codex_round_found_four_acs_unmet` and the story file's
  **Round 2** section.
- #139 merged. **#140 closed unmerged** — its 2026-09-11 base would have reverted six PRs; its
  one new finding was re-verified and copied onto main via #146. See the comment on #140.
- Docker returned: 563 tests pass with no skips, 96/96 dev-store rows resolve under the
  stricter rule, v17-vs-v18 IDENTICAL under the now-sound comparison.

## Decisions Made
- A defect contradicting a story's own ACs reopens that story; it is not a new story
  (rule 3 read literally). Hence 13.4a round 2 rather than a `13.4a-1`.
- Pushed back on Codex's "version-blind resolution violates AD-2": AD-2 governs stored
  facts, and identity is computed at read time and stored nowhere. Deferred to 13.4c.
- Lawrence, 2026-10-04: merge 13.4a round 1 before its Codex review. The review then ran
  post-merge and its findings became round 2.

## Context Needed
- **`ThesisTrace-envfile` worktree is stale** — its PR #139 is merged and it is clean.
  `git worktree remove ../ThesisTrace-envfile` when no session is in it.
- **VS Code contends for `.git/index.lock`.** Wrap git writes in
  `until [ ! -f .git/index.lock ]; do sleep 1; done` or a retry loop.
- **Never run the mutation harness on uncommitted work** — it restores with `git checkout`
  and discarded a full set of fixes this session. Commit first.
- Squash-merging a branch that another branch was cut from rewrites the second one's merge
  base; expect a conflict even when content is identical.

## Open: BMad drift (do this before 13.4b)
Checked 2026-10-08 against registry.npmjs.org (`bmad-method`):
- **Installed 6.10.0** (published 2026-07-03, installed 2026-07-17, `lastUpdated` identical so
  never upgraded). **Latest 6.12.1** (2026-10-04). Missed stable releases: 6.11.0, 6.12.0,
  6.12.1. The ~108 versions between are near-daily `-next` prereleases, not stable ones.
- **A skills-vs-install mismatch was HYPOTHESISED AND DISPROVED** — do not re-investigate it.
  Every `.claude/skills/bmad-*` carries the install-day timestamp (Jul 17 16:15:55), the same
  as `_bmad/_config/manifest.yaml`, including the consolidated `bmad-prd` / `bmad-spec` /
  `bmad-architecture` and the DEPRECATED `bmad-create-prd` shims. 6.10.0 already shipped those.
- **The version gap does not explain the drift.** 6.11.0 landed 2026-08-10 and 6.12.0 on
  2026-09-04; the process problems (13.3 at 19 commits/8 days, story files lapsing after
  Epic 5) predate both and are already diagnosed in `CLAUDE.md`'s Story workflow section.
- **The likely real cause: two override channels, only one of which the skills read.**
  `_bmad/custom/` holds only the untouched install-day `config.toml` / `config.user.toml`, so
  every behavioural rule lives in `CLAUDE.md` — which steers the agent and NOT the skills.
  `bmad-customize` writes `_bmad/custom/<skill>.toml`, which `resolve_customization.py` reads.

**Steps, in order:** (1) move `CLAUDE.md`'s story-workflow / DoD rules into `_bmad/custom/*.toml`
via `bmad-customize` — local, zero-risk, and the step most likely to stop the drift; (2) read the
6.11.0 and 6.12.0 release notes for story/PRD template and config-schema changes BEFORE
upgrading — `_bmad-output/` holds ~12 weeks of artifacts shaped by 6.10.0 conventions and an
upgrade could orphan them; (3) then decide on the upgrade.

## Next Action
Load `.claude/skills/bmad-customize` and audit which of `CLAUDE.md`'s Story workflow and
Definition-of-Done rules belong in `_bmad/custom/bmad-create-story.toml` and
`_bmad/custom/bmad-dev-story.toml`. Do NOT upgrade BMad in the same session.

## References
- `_bmad-output/planning-artifacts/epics.md:1488` (`### Story 13.4b`)
- `_bmad-output/implementation-artifacts/sprint-status.yaml:219`
- `_bmad-output/implementation-artifacts/engineering-findings.yaml` —
  `story_13_3_member_exclusions_are_not_axis_scoped` (13.4b's own),
  `story_13_4a_codex_round_found_four_acs_unmet` (what round 2 taught)
- `backend/canonicalization/mappings/engine.py` — `_check_brand_identity`
- `CLAUDE.md` — Story workflow rule 3, Git workflow, Running things
- `.claude/context/project-context.md` (2026-10-07 learnings)
- `_bmad/_config/manifest.yaml` (installed 6.10.0), `_bmad/custom/` (empty of real overrides),
  `.claude/skills/bmad-customize` — for **Open: BMad drift**

---
*Generated by /session-end — 2026-10-08 05:10*
