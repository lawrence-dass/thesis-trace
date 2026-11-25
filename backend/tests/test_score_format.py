"""Ops 6b: the explanation sentence formats a score exactly as the headline does.

The vectors are `frontend/app/components/ui/scoreFormat.test.ts`, one for one, so
the Python and TypeScript rules cannot quietly disagree.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from explanation.score_format import band_edges, format_score

BENEISH = [Decimal("-1.78")]
ALTMAN = [Decimal("1.81"), Decimal("2.99")]


@pytest.mark.parametrize(
    ("model", "value", "edges", "expected"),
    [
        # two decimals for a ratio model (SHOP FY2025 Altman Z)
        ("altman", 74.998229, [], "75.00"),
        ("beneish", -1.981461, [], "-1.98"),
        ("sloan", -0.055096, [], "-0.06"),
        # Piotroski, a 0-9 count, is a whole number (stored as 9.0)
        ("piotroski", 5, [], "5"),
        ("piotroski", 9.0, [], "9"),
        # half-even on the decimal digits
        ("sloan", 0.125, [], "0.12"),
        ("sloan", 0.135, [], "0.14"),
        ("altman", 1.005, [], "1.00"),
        ("altman", 1.015, [], "1.02"),
        # never a negative zero
        ("sloan", -0.001, [], "0.00"),
        # boundary guard: Beneish -1.78
        ("beneish", -1.7849, BENEISH, "-1.785"),
        ("beneish", -1.7801, BENEISH, "-1.7801"),
        ("beneish", -1.78, BENEISH, "-1.78"),
        ("beneish", -2.5, BENEISH, "-2.50"),
        # boundary guard: Altman 1.81 and 2.99
        ("altman", 2.994, ALTMAN, "2.994"),
        ("altman", 1.8149, ALTMAN, "1.815"),
        ("altman", 3.4, ALTMAN, "3.40"),
    ],
)
def test_matches_the_frontend_vectors(model, value, edges, expected) -> None:
    assert format_score(model, value, edges) == expected


def test_band_edges_come_from_the_spec() -> None:
    assert band_edges("beneish_v1") == [Decimal("-1.78"), Decimal("-1.78")]
    assert sorted(set(band_edges("altman_v1"))) == ALTMAN


def test_real_boundary_cases_from_ops_3() -> None:
    """The two live per-year cards on which Ops 3's guard fires."""
    assert format_score("altman", 2.98734, band_edges("altman_v1")) == "2.987"  # OTEX FY2013
    assert format_score("beneish", -1.78136, band_edges("beneish_v1")) == "-1.781"  # CCJ FY2018
