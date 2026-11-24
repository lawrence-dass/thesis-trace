# Ops 1: The live demo survives a sleeping API

Status: review
Date: 2026-11-24
Scope: operations (no figure, mapping or formula changes — the live-data DoD does not apply)

## Why

On 2026-11-24 the public demo was down: the free Supabase project had auto-paused
(no writes for a week, because the Render cron was never deployed on the free tier),
so every company page returned 500. Separately, every page fetched with
`cache: "no-store"`, so even when healthy each visit waited out Render's ~45s free-tier
cold start. Budget constraint: stays at $0/month.

## Acceptance criteria

1. With the read API stopped, every page that has been rendered once (including at
   build) still serves its full content.
2. That holds after the cache has passed its freshness window and a background refresh
   has failed.
3. An unreachable API is never cached as content: no "Backend unreachable" page or
   empty company list gets stored.
4. CI's frontend build still passes with no API running; a Vercel build with the API
   truly unreachable fails (so the previous deployment keeps serving).
5. The batch pipeline runs nightly at $0, applies migrations first, and its run fails
   visibly when any filer fails.
6. Nightly writes keep the Supabase project from auto-pausing.

## Tasks

- [x] `frontend/app/lib/api.ts`: one read client; every fetch uses the data cache
      (1h stale-while-revalidate); unreachable API throws (AC 1-3)
- [x] Landing, company, methodology, compare pages use it; primary data throws,
      supplementary data still degrades (AC 3)
- [x] `company/[ticker]` `generateStaticParams` fills the cache for every ticker at build (AC 1)
- [x] `app/error.tsx`: retry page for the only remaining failure (no cached copy + API down)
- [x] `ALLOW_OFFLINE_BUILD` fallback for CI only (AC 4)
- [x] `.github/workflows/pipeline.yml`: daily 10:00 UTC + manual trigger; migrate, run (AC 5, 6)
- [x] `pipeline.run.main` exits non-zero listing failed tickers (AC 5)
- [x] Verified against a local production build (below)
- [ ] Lawrence: restore Supabase, add Actions secrets, deploy (see the PR description)

## Verification (local production build, local API on :8001, 2026-11-24)

| Check | Result |
|---|---|
| API up: all 15 pages | 200, content |
| API stopped, entries fresh | 15/15 served in full, incl. never-visited `/company/CP` |
| API stopped, entries past a 10s window, background refresh failed | 15/15 served in full |
| Build, flag set, no API | exit 0 |
| Build, no flag, no API | exit 1 (`ApiUnavailableError`) |

## Findings, decided in-story

- **Pages cannot be static.** The root layout reads the theme cookie server-side
  (a documented decision, see `layout.tsx`), so every route renders per request. The
  data cache gives the resilience instead; page-level ISR was not needed. Adding
  `generateStaticParams` to a route with no build-time params (methodology) made it
  fail with `DYNAMIC_SERVER_USAGE` at request time — removed, and noted in the file.
- **No on-demand revalidation.** `revalidatePath` PURGES cached responses: triggered
  while the API was down, every company page went to 500. The pipeline therefore does
  not ping the site; new scores appear within the hourly window.
