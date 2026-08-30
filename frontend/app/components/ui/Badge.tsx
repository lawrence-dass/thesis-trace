// Semantic status pill. The variant vocabulary mirrors the backend's already-
// computed enums (SignalStatus: pass/fail/insufficient_data; Applicability:
// computed/excluded_out_of_scope/computed_with_caveat — AD-16, AD-20) so a
// state is always rendered the same way everywhere. This maps an existing
// classification to a color; it never invents or recomputes one (AD-8).
import type { ReactNode } from "react";
import { AlertIcon, CheckIcon, DashIcon, SlashCircleIcon, XIcon } from "./icons";

export type BadgeVariant = "pass" | "fail" | "caveat" | "pending" | "excluded" | "brand" | "neutral";

const VARIANT_STYLE: Record<BadgeVariant, string> = {
  pass: "text-[var(--color-signal-pass)] bg-[var(--color-signal-pass-bg)] border-[var(--color-signal-pass-border)]",
  fail: "text-[var(--color-signal-fail)] bg-[var(--color-signal-fail-bg)] border-[var(--color-signal-fail-border)]",
  caveat: "text-[var(--color-signal-caveat)] bg-[var(--color-signal-caveat-bg)] border-[var(--color-signal-caveat-border)]",
  pending: "text-[var(--color-signal-pending)] bg-[var(--color-signal-pending-bg)] border-[var(--color-signal-pending-border)]",
  excluded: "text-[var(--color-signal-excluded)] bg-[var(--color-signal-excluded-bg)] border-[var(--color-signal-excluded-border)]",
  brand: "text-[var(--color-brand-badge)] bg-[var(--color-brand-50)] border-[var(--color-brand-100)]",
  neutral: "text-[var(--color-ink-muted)] bg-[var(--color-canvas)] border-[var(--color-border)]",
};

const VARIANT_ICON: Partial<Record<BadgeVariant, ReactNode>> = {
  pass: <CheckIcon className="h-3 w-3" />,
  fail: <XIcon className="h-3 w-3" />,
  pending: <DashIcon className="h-3 w-3" />,
  excluded: <SlashCircleIcon className="h-3 w-3" />,
  caveat: <AlertIcon className="h-3 w-3" />,
};

export function Badge({
  variant = "neutral",
  icon = true,
  children,
}: {
  variant?: BadgeVariant;
  icon?: boolean;
  children: ReactNode;
}) {
  return (
    // Story 11.2: terminal-precision typography — uppercase + tracked, tighter
    // padding than the SaaS-era pill. Icons (not the mockup's plain "●" dot)
    // stay: they carry the pass/fail/caveat/pending/excluded distinction in
    // SHAPE as well as color, which a uniform dot would not (Accessibility
    // Floor, same principle Gauge.tsx already documents for its own zones).
    <span
      className={`inline-flex items-center gap-1 rounded-[var(--radius-pill)] border px-2 py-0.5 text-[0.6875rem] font-medium uppercase tracking-[var(--tracking-label)] ${VARIANT_STYLE[variant]}`}
    >
      {icon && VARIANT_ICON[variant]}
      {children}
    </span>
  );
}

/** Signal tri-state (AD-16) -> badge variant. */
export function signalVariant(status: string): BadgeVariant {
  if (status === "pass") return "pass";
  if (status === "fail") return "fail";
  return "pending"; // insufficient_data
}

/** Sector/model applicability (AD-20) -> badge variant. */
export function applicabilityVariant(applicability: string): BadgeVariant {
  if (applicability === "excluded_out_of_scope") return "excluded";
  if (applicability === "computed_with_caveat") return "caveat";
  if (applicability === "computed") return "pass";
  return "pending";
}

export function applicabilityLabel(applicability: string): string {
  if (applicability === "excluded_out_of_scope") return "Out of scope";
  if (applicability === "computed_with_caveat") return "Caveat";
  if (applicability === "computed") return "Computed";
  return "Unavailable";
}

/**
 * Visual-only tone hint for the backend's own cited band vocabulary (FR-9,
 * AD-12). All four models, as emitted by `backend/formulas/specs/*.yaml`:
 *
 *   Piotroski  Strong / Middle / Weak
 *   Altman     Safe / Grey / Distress
 *   Beneish    "Manipulation risk flagged" / "No manipulation flag"
 *   Sloan      "Low accruals (higher quality)" / "High accruals (lower quality)"
 *
 * This colors an already-fixed, backend-authored string for scannability — it
 * does not classify or recompute anything new. An unrecognized label (e.g. a
 * future model's band copy) safely falls back to neutral rather than guessing.
 *
 * Two pairs are separated only by how SPECIFIC a search term is, and each is one
 * loosened string away from inverting a result: "no manipulation" must not be
 * shortened to "manipulation" (both Beneish labels contain it), and "low accrual"
 * must not be shortened to "low" ("lower quality" contains it). `Badge.test.ts`
 * pins all ten labels and both near-misses — the omission of Beneish from this
 * comment survived a 2026-07-29 audit precisely because nothing enforced it.
 */
export function bandTone(label: string | null): BadgeVariant {
  if (!label) return "neutral";
  const l = label.toLowerCase();
  if (l.includes("strong") || l.includes("safe") || l.includes("low accrual") || l.includes("no manipulation")) {
    return "pass";
  }
  if (l.includes("weak") || l.includes("distress") || l.includes("high accrual") || l.includes("manipulation risk")) {
    return "fail";
  }
  if (l.includes("middle") || l.includes("grey") || l.includes("gray")) return "caveat";
  return "neutral";
}
