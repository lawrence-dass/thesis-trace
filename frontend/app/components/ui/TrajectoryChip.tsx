// Direction of travel for an already-computed score (PRD OQ9, Story 5.5).
//
// Rendered ALONGSIDE the level and never instead of it: a company improving
// from a weak base and one deteriorating from a strong base must stay visibly
// different, which is the entire reason trajectory is shown. The chip is
// deliberately quieter than the band badge beside it — the band is the model's
// own published classification, this is ThesisTrace's annotation, and the
// visual weight has to reflect that difference in authority.
//
// The backend classifies; this maps an already-decided direction to an arrow
// and a tone (AD-8). It never compares values itself.

const DIRECTION_GLYPH: Record<string, string> = {
  improving: "↑",
  deteriorating: "↓",
  stable: "→",
  insufficient_history: "",
};

// Muted deliberately. These are not the tri-state signal colours — a trajectory
// is not a pass/fail, and borrowing that palette would give a presentation rule
// the same visual authority as a model's own verdict.
const DIRECTION_STYLE: Record<string, string> = {
  improving: "text-[var(--color-signal-pass)]",
  deteriorating: "text-[var(--color-signal-fail)]",
  stable: "text-[var(--color-ink-faint)]",
  insufficient_history: "text-[var(--color-ink-faint)]",
};

export type Trajectory = {
  direction: string;
  label: string;
  from_fiscal_year: number | null;
  to_fiscal_year: number;
  from_value: number | null;
  to_value: number | null;
  attribution: string;
  spec_version: string;
};

export function TrajectoryChip({ trajectory }: { trajectory: Trajectory | null | undefined }) {
  if (!trajectory) return null;

  // "We could not compare" is not a direction. Rendering it as a neutral arrow
  // would imply a flat trend where there is simply no prior year (AD-16).
  if (trajectory.direction === "insufficient_history") {
    return (
      <span
        className="text-xs text-[var(--color-ink-faint)]"
        title="No immediately preceding fiscal year to compare against."
      >
        {trajectory.label}
      </span>
    );
  }

  const glyph = DIRECTION_GLYPH[trajectory.direction] ?? "";
  const tone = DIRECTION_STYLE[trajectory.direction] ?? "text-[var(--color-ink-faint)]";
  const years =
    trajectory.from_fiscal_year !== null
      ? `FY${trajectory.from_fiscal_year} → FY${trajectory.to_fiscal_year}`
      : `FY${trajectory.to_fiscal_year}`;

  return (
    <span
      className={`inline-flex items-center gap-1 text-xs ${tone}`}
      // Attribution travels with every direction, so a reader can always find
      // out whose judgment it is without leaving the page.
      title={`${trajectory.label}, ${years}. ${trajectory.attribution}`}
    >
      <span aria-hidden>{glyph}</span>
      <span>{trajectory.label}</span>
      <span className="font-mono text-[var(--color-ink-faint)]">{years}</span>
    </span>
  );
}
