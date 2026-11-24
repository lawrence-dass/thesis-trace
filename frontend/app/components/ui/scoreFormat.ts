/** Display formatting for a model's aggregate score.
 *
 *  Scores are stored at the formula specs' `ratio_places: 6` and were rendered
 *  at full precision, so a headline read "74.998229" (SHOP's FY2025 Altman Z).
 *  Headlines now show two decimals; Piotroski, a 0-9 count, shows a whole
 *  number. The exact stored value stays available: callers put it in a `title`
 *  tooltip, and the expanded breakdown and methodology pages keep full
 *  precision.
 *
 *  Two rules keep the shortened number honest:
 *
 *  1. Rounding is decimal ROUND_HALF_EVEN on the value's own digits, the policy
 *     the scoring engine uses (AD-15). It never goes through `toFixed`, which
 *     breaks ties on the binary representation (see `format.ts`).
 *  2. A rounded number must never land on a band boundary the exact value does
 *     not sit on. Beneish's -1.78 line is the risk: an exact -1.7849 is below it
 *     ("no manipulation flag"), but printed at two decimals it reads -1.78, the
 *     boundary itself, beside a badge that seems to disagree. When that would
 *     happen, decimals are added until the number clears the boundary, up to the
 *     stored precision.
 */

import type { BandClass } from "./Gauge";

const STORED_PLACES = 6;
const HEADLINE_PLACES: Record<string, number> = { piotroski: 0 };
const DEFAULT_PLACES = 2;

/** The value as an exact integer count of millionths. A stored score has at
 *  most six decimals, so `toFixed(6)` recovers its decimal digits exactly: the
 *  binary error of a JSON-parsed six-decimal number is far below half a
 *  millionth. */
function toMillionths(value: number): bigint {
  const [whole, frac = ""] = value.toFixed(STORED_PLACES).replace("-", "").split(".");
  const magnitude = BigInt(whole) * 10n ** BigInt(STORED_PLACES) + BigInt(frac.padEnd(STORED_PLACES, "0"));
  return value < 0 ? -magnitude : magnitude;
}

/** Round a count of millionths to `places` decimals, half-even, returning the
 *  rounded count still in millionths. */
function roundHalfEven(millionths: bigint, places: number): bigint {
  const step = 10n ** BigInt(STORED_PLACES - places);
  const negative = millionths < 0n;
  const abs = negative ? -millionths : millionths;
  let quotient = abs / step;
  const remainder = abs % step;
  const twice = remainder * 2n;
  if (twice > step || (twice === step && quotient % 2n === 1n)) quotient += 1n;
  const rounded = quotient * step;
  return negative ? -rounded : rounded;
}

function render(millionths: bigint, places: number): string {
  const negative = millionths < 0n;
  const abs = negative ? -millionths : millionths;
  const scale = 10n ** BigInt(STORED_PLACES);
  const whole = abs / scale;
  const frac = (abs % scale).toString().padStart(STORED_PLACES, "0").slice(0, places);
  const body = places > 0 ? `${whole}.${frac}` : `${whole}`;
  // A value that rounds to zero prints unsigned, not "-0.00".
  return negative && abs !== 0n ? `-${body}` : body;
}

function boundaries(bands: BandClass[]): bigint[] {
  const out: bigint[] = [];
  for (const b of bands) {
    for (const edge of [b.min, b.max, b.above, b.below]) {
      if (typeof edge === "number" && Number.isFinite(edge)) out.push(toMillionths(edge));
    }
  }
  return out;
}

export function formatScore(model: string, value: number, bands: BandClass[] = []): string {
  const exact = toMillionths(value);
  const edges = boundaries(bands);
  for (let places = HEADLINE_PLACES[model] ?? DEFAULT_PLACES; places <= STORED_PLACES; places++) {
    const rounded = roundHalfEven(exact, places);
    const misleads = edges.some((edge) => rounded === edge && exact !== edge);
    if (!misleads) return render(rounded, places);
  }
  return render(exact, STORED_PLACES);
}

/** The full stored value, for a `title` tooltip beside a shortened headline. */
export function exactScore(value: number): string {
  return String(value);
}
