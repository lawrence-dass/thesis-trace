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

const DISPLAY_DOMAIN: Record<string, [number, number]> = {
  piotroski: [0, 9],
  altman: [0.5, 4.5],
  beneish: [-5, 1],
  sloan: [-0.2, 0.3],
};

const TONE_BG: Record<string, string> = {
  pass: "var(--color-signal-pass-bg)",
  fail: "var(--color-signal-fail-bg)",
  caveat: "var(--color-signal-caveat-bg)",
  pending: "var(--color-signal-pending-bg)",
  excluded: "var(--color-signal-excluded-bg)",
  neutral: "var(--color-canvas)",
  brand: "var(--color-canvas)",
};

const TONE_SOLID: Record<string, string> = {
  pass: "var(--color-signal-pass)",
  fail: "var(--color-signal-fail)",
  caveat: "var(--color-signal-caveat)",
  pending: "var(--color-signal-pending)",
  excluded: "var(--color-signal-excluded)",
  neutral: "var(--color-ink-faint)",
  brand: "var(--color-ink-faint)",
};

function clamp(n: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, n));
}

function zoneRange(b: BandClass, lo: number, hi: number): [number, number] {
  return [b.min ?? b.above ?? lo, b.max ?? b.below ?? hi];
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

  const valuePct = clamp(((value - lo) / span) * 100, 0, 100);
  const markerTone = bandTone(bandLabel);

  return (
    <div className="pt-1" title={`${bandLabel ?? value} (${value} on this model's own scale)`}>
      <div className="relative h-1.5 w-full overflow-hidden rounded-full bg-[var(--color-canvas)]">
        {zones.map((z, i) => (
          <div
            key={i}
            className="absolute top-0 h-full"
            style={{
              left: `${z.startPct}%`,
              width: `${Math.max(z.widthPct, 0)}%`,
              backgroundColor: TONE_BG[bandTone(z.label)],
              borderRight: i < zones.length - 1 ? "2px solid var(--color-surface)" : undefined,
            }}
          />
        ))}
        <div
          className="absolute top-1/2 h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full"
          style={{
            left: `${valuePct}%`,
            backgroundColor: TONE_SOLID[markerTone],
            boxShadow: "0 0 0 2px var(--color-surface)",
          }}
        />
      </div>
    </div>
  );
}
