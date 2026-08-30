// Range meter for a model's aggregate value against its own published bands
// (FR-9/FR-11 teaching aid). Zone colors and the marker's color both derive
// from the backend's own band_label via bandTone() — this never reclassifies
// anything, it only visually positions an already-computed value and an
// already-computed classification (AD-8: presentation only).
//
// DISPLAY_DOMAIN below is a *visual scaling range only* — how wide to draw the
// bar — not a scoring boundary. The zone boundaries themselves (min/max/above/
// below) come live from /api/methodology/{model}'s `bands`, the same source
// the backend classification itself is derived from, so this can't drift out
// of sync the way a hardcoded threshold could.
import { bandTone } from "./Badge";

export type BandClass = { label: string; min?: number; max?: number; above?: number; below?: number };

// Exported so any OTHER component needing "where does this value sit in this
// model's own range" (e.g. VerdictGlyph.tsx) reads the identical domain
// rather than an independently hand-copied one — the "two code paths must
// not answer the same question from different sources" lesson (Epic 6
// retrospective, the currency-source bug).
export const DISPLAY_DOMAIN: Record<string, [number, number]> = {
  piotroski: [0, 9],
  altman: [0.5, 4.5],
  beneish: [-5, 1],
  sloan: [-0.2, 0.3],
};

export const TONE_BG: Record<string, string> = {
  pass: "var(--color-signal-pass-bg)",
  fail: "var(--color-signal-fail-bg)",
  caveat: "var(--color-signal-caveat-bg)",
  pending: "var(--color-signal-pending-bg)",
  excluded: "var(--color-signal-excluded-bg)",
  neutral: "var(--color-canvas)",
  brand: "var(--color-canvas)",
};

export const TONE_SOLID: Record<string, string> = {
  pass: "var(--color-signal-pass)",
  fail: "var(--color-signal-fail)",
  caveat: "var(--color-signal-caveat)",
  pending: "var(--color-signal-pending)",
  excluded: "var(--color-signal-excluded)",
  neutral: "var(--color-ink-faint)",
  brand: "var(--color-ink-faint)",
};

export function clamp(n: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, n));
}

function zoneRange(b: BandClass, lo: number, hi: number): [number, number] {
  return [b.min ?? b.above ?? lo, b.max ?? b.below ?? hi];
}

/** Where `value` sits in `model`'s own DISPLAY_DOMAIN, as 0-100. The same
 * question Gauge answers internally for its marker position — extracted so
 * VerdictGlyph's spoke length can never drift from what the gauge shows for
 * the same value. */
export function domainPct(model: string, value: number): number {
  const [lo, hi] = DISPLAY_DOMAIN[model] ?? [value - 1, value + 1];
  return clamp(((value - lo) / (hi - lo)) * 100, 0, 100);
}

export function Gauge({
  model,
  value,
  bandLabel,
  bands,
}: {
  model: string;
  value: number;
  bandLabel: string | null;
  bands: BandClass[];
}) {
  const domain = DISPLAY_DOMAIN[model] ?? [value - 1, value + 1];
  const [lo, hi] = domain;
  const span = hi - lo;

  const zones = bands.map((b) => {
    const [rawStart, rawEnd] = zoneRange(b, lo, hi);
    const zoneStart = clamp(rawStart, lo, hi);
    const zoneEnd = clamp(rawEnd, lo, hi);
    return { label: b.label, startPct: ((zoneStart - lo) / span) * 100, widthPct: ((zoneEnd - zoneStart) / span) * 100 };
  });

  const valuePct = domainPct(model, value);
  const markerTone = bandTone(bandLabel);

  return (
    <div className="pt-1" title={`${bandLabel ?? value} (${value} on this model's own scale)`}>
      {/* Tick-marked horizontal band (DESIGN.md Components: a measurement
          instrument, not a radial "hero dial") — zone boundaries render as a
          visible tick, not just a color transition, so the classification
          zones read as shape even without color (Accessibility Floor).
          Story 11.2: flat readout treatment, not a rounded-pill meter — a
          bordered rectangular track (matching Card/Badge's own flat corners)
          and a vertical needle marker instead of a filled dot, reading as an
          instrument-panel gauge rather than a SaaS progress bar. Band-boundary
          math above (zoneRange/domainPct/clamp) is untouched by this story. */}
      <div className="relative h-2 w-full overflow-hidden rounded-[var(--radius-chip)] border border-[var(--color-border)] bg-[var(--color-canvas)]">
        {zones.map((z, i) => (
          <div
            key={i}
            className="absolute top-0 h-full"
            style={{
              left: `${z.startPct}%`,
              width: `${Math.max(z.widthPct, 0)}%`,
              backgroundColor: TONE_BG[bandTone(z.label)],
              borderRight: i < zones.length - 1 ? "2px solid var(--color-border-strong)" : undefined,
            }}
          />
        ))}
        <div
          className="absolute top-1/2 w-[2px] -translate-x-1/2 -translate-y-1/2"
          style={{
            left: `${valuePct}%`,
            height: "calc(100% + 6px)",
            backgroundColor: TONE_SOLID[markerTone],
            boxShadow: "0 0 0 1px var(--color-surface)",
          }}
        />
      </div>
    </div>
  );
}
