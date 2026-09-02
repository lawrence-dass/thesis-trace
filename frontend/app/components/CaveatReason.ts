/**
 * A caveated run should never become a blank badge just because an older
 * persisted row predates `score_runs.caveat_reason` or contains malformed
 * whitespace. Keep that state explicit and honest rather than inventing a
 * model-specific explanation.
 */
export const CAVEAT_REASON_UNAVAILABLE = "Reason unavailable for this stored run.";

export function caveatReasonText(reason: string | null | undefined): string {
  const normalized = reason?.trim();
  return normalized || CAVEAT_REASON_UNAVAILABLE;
}
