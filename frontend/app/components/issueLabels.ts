/** Human-readable names for `data_quality_issues.issue_type`.
 *
 * Shared deliberately: the issue types are rendered in two places — the
 * company report's Integrity & Evidence panel and the What-Changed diff — and
 * when the map lived only in `WhatChanged.tsx` the report rendered the raw
 * snake_case identifier instead. Story 13.3 made that visible by adding
 * `unmapped_member`, which lands six times on CPB's page.
 *
 * Unknown types fall back to the raw identifier rather than to a generic label:
 * a new writer's issues must still be legible before anyone thinks to add them
 * here, and a silent "Other" would hide that a type is unlabelled.
 */
export const ISSUE_LABEL: Record<string, string> = {
  identity_violation: "Accounting identity check",
  ambiguous_selection: "Ambiguous source selection",
  ambiguous_member_selection: "Ambiguous member selection",
  unmapped_member: "Unmapped XBRL member",
  source_conflict: "Conflicting sources",
};

export function issueLabel(issueType: string): string {
  if (Object.prototype.hasOwnProperty.call(ISSUE_LABEL, issueType)) {
    return ISSUE_LABEL[issueType];
  }
  const baseType = issueType.split(":", 1)[0];
  return Object.prototype.hasOwnProperty.call(ISSUE_LABEL, baseType)
    ? ISSUE_LABEL[baseType]
    : issueType;
}
