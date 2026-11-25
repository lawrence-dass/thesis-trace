# Ops 6a: The explanation endpoint never calls the LLM

Status: review
Date: 2026-11-24
Scope: ordinary code story (no figure changes; the deterministic text is what
every page already renders)

## Why

`GET /api/companies/{t}/explanation?polish_text=true` is public and
unauthenticated, and it made one Claude call **per explanation**, sequentially:
48 for SHOP, 84 for OTEX, 78 for AAPL (dev store, 2026-11-24). `LLM_API_KEY` is
set on Render, so anyone who finds the URL spends credits, about 80 calls per
request. No page uses the flag: the company page fetches `/explanation` without
it, so the spend buys nothing a visitor sees.

Lawrence chose (2026-11-24) to move polishing to the write path, where the
pipeline polishes each explanation once and the read serves stored text. That
needs a migration and a pipeline stage, so it is split out as **Ops 6b**. This
story closes the live exposure first.

## Acceptance criteria

1. No request to `/explanation` can reach the LLM, whatever `polish_text` says
   and whether or not `LLM_API_KEY` is set.
2. `polish_text` is still accepted (no 422) so existing callers do not break,
   and the response reports `llm_rewrite: false`.
3. The response body is otherwise unchanged: the deterministic text and citations.
4. A test proves AC 1 with a key configured and `polish` instrumented, and it is
   shown to fail when the old call is restored (a mutation check).

## Tasks

- [x] `backend/api/routes.py`: drop the read-path `polish` call (AC 1-3)
- [x] Test: key set, `polish_text=true`, zero LLM calls, deterministic text (AC 4).
      It instruments `_call_anthropic`, the seam `polish()` resolves at call time,
      so a re-added `from explanation.llm import polish` is caught too.
- [x] Mutation check: restoring the call fails the test at `assert calls == []`
- [x] `make test` 694 passed; `make lint` clean
- [ ] PR; after merge, **Manual Deploy on Render** (auto-deploy is off)

## Out of scope (Ops 6b)

- Polishing on the write path and storing the result, keyed by a hash of the
  deterministic text, the model and the prompt version.
- Checking that the polished text keeps every number and citation. Today that
  rests on the system prompt alone (AD-7).
