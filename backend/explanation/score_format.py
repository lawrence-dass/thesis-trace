"""Display rule for a model's aggregate score inside explanation text (Ops 6b).

The Python twin of `frontend/app/components/ui/scoreFormat.ts` (Ops 3), so the
sentence under a card cannot print a score the headline above it rounds
differently. `test_score_format.py` runs the TypeScript test vectors.

1. Two decimals; Piotroski, a 0-9 count, is a whole number.
2. Decimal ROUND_HALF_EVEN on the stored digits (AD-15). A value that rounds
   to zero prints unsigned.
3. A rounded number never lands on a band boundary the exact value does not
   sit on. Decimals are added until it clears, up to the stored six.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import ROUND_HALF_EVEN, Decimal

from formulas.engine import load_spec

STORED_PLACES = 6
HEADLINE_PLACES = {"piotroski": 0}
DEFAULT_PLACES = 2
_EDGE_KEYS = ("min", "max", "above", "below")


def _quantum(places: int) -> Decimal:
    return Decimal(1).scaleb(-places)


def _exact(value: float | Decimal) -> Decimal:
    # A stored score has at most six decimals; str() of the parsed float recovers them.
    return Decimal(str(value)).quantize(_quantum(STORED_PLACES), rounding=ROUND_HALF_EVEN)


def band_edges(formula_version: str) -> list[Decimal]:
    """Every finite boundary in a formula spec's bands, at stored precision."""
    classes = (load_spec(formula_version).raw.get("bands") or {}).get("classes") or []
    return [_exact(c[k]) for c in classes for k in _EDGE_KEYS if isinstance(c.get(k), (int, float))]


def _render(value: Decimal, places: int) -> str:
    text = f"{value:.{places}f}"
    return text[1:] if text.startswith("-") and value == 0 else text


def format_score(model: str, value: float | Decimal, edges: Iterable[Decimal] = ()) -> str:
    exact = _exact(value)
    edges = list(edges)
    for places in range(HEADLINE_PLACES.get(model, DEFAULT_PLACES), STORED_PLACES + 1):
        rounded = exact.quantize(_quantum(places), rounding=ROUND_HALF_EVEN)
        if not any(rounded == edge and exact != edge for edge in edges):
            return _render(rounded, places)
    return _render(exact, STORED_PLACES)
