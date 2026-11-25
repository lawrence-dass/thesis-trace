"""Ops 6b: the explanation sentence formats a score exactly as the headline does.

The cases are `frontend/app/components/ui/scoreFormat.vectors.json`, which
`scoreFormat.test.ts` also runs, so a case added for either formatter binds both.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from explanation.score_format import _EDGE_KEYS, band_edges, format_score

VECTORS = json.loads(
    (Path(__file__).resolve().parents[2] / "frontend" / "app" / "components" / "ui" / "scoreFormat.vectors.json").read_text()
)


def _edges(bands: list[dict]) -> list[Decimal]:
    return [Decimal(str(b[k])) for b in bands for k in _EDGE_KEYS if isinstance(b.get(k), (int, float))]


def test_has_cases_to_run() -> None:
    assert len(VECTORS["cases"]) > 15


@pytest.mark.parametrize("case", VECTORS["cases"], ids=lambda c: f"{c['model']} {c['value']}")
def test_matches_the_shared_vectors(case) -> None:
    edges = _edges(VECTORS["bands"][case["bands"]])
    assert format_score(case["model"], case["value"], edges) == case["expected"]


def test_shared_band_fixtures_match_the_specs() -> None:
    """The vectors' bands are the real specs' edges, so the boundary cases test real lines."""
    assert set(_edges(VECTORS["bands"]["beneish"])) == set(band_edges("beneish_v1"))
    assert set(_edges(VECTORS["bands"]["altman"])) == set(band_edges("altman_v1"))
