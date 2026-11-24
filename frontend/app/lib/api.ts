// Read-API client shared by every page (AD-8: presentation only).
//
// Every API read goes through Next.js's data cache rather than straight to the
// API. The data only changes when the nightly batch pipeline runs (AD-1), so a
// visitor never needs a live round-trip, and the free-tier Render API's ~45s
// cold start stops being something a visitor can see.
//
// The pages themselves still render per request: the root layout reads the
// theme cookie server-side (see its comment for why), which rules out static
// pages. That costs a few milliseconds per render, not resilience: a cached
// response is served stale-while-revalidate, and a failed background refresh
// keeps the last good response. The build fills the cache for every covered
// company up front (company/[ticker] generateStaticParams). Verified 2026-11-24
// against a production build: with the API stopped, every page served in full.
//
// The one rule that keeps the cache clean: an UNREACHABLE API THROWS rather than
// resolving to a fallback value. A thrown fetch is never written to the cache;
// a fallback rendered as "Backend unreachable" would look like real data.
// `not_available` is not an error: it is a 200 the API returns for a ticker it
// does not cover, and pages render it as before.

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// How long a cached response counts as fresh. After that it is still served,
// and refreshed in the background; a failed refresh keeps the old response.
// There is deliberately no on-demand revalidation route: that PURGES the cache,
// and a purge while the API is asleep took every page to a 500 (2026-11-24).
export const REVALIDATE_SECONDS = 3600;

export class ApiUnavailableError extends Error {
  constructor(path: string, cause: string) {
    super(`Read API unavailable for ${path}: ${cause}`);
    this.name = "ApiUnavailableError";
  }
}

export async function apiGet<T>(path: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, { next: { revalidate: REVALIDATE_SECONDS } });
  } catch (err) {
    throw new ApiUnavailableError(path, err instanceof Error ? err.message : String(err));
  }
  if (!res.ok) throw new ApiUnavailableError(path, `HTTP ${res.status}`);
  return (await res.json()) as T;
}

// For data a page needs at BUILD time (the landing list, the tickers to
// prerender). CI builds the app with no API running (.github/workflows/ci.yml
// sets ALLOW_OFFLINE_BUILD=1): there, and only there, an unreachable API yields
// the fallback, so the build still proves the app compiles. On Vercel the flag
// is unset, so an unreachable API fails the build — which leaves the previous
// deployment serving, instead of shipping an empty site. A sleeping free-tier
// API is not "unreachable": the request waits out the cold start and succeeds.
export async function apiGetAtBuild<T>(path: string, offlineFallback: T): Promise<T> {
  try {
    return await apiGet<T>(path);
  } catch (err) {
    if (process.env.ALLOW_OFFLINE_BUILD === "1") return offlineFallback;
    throw err;
  }
}
