"""Ops 6b: every signal has a plain-language name, and both apps use the same one.

The frontend's map is `frontend/app/lib/signalLabels.json` (both pages import
it), so this compares parsed JSON to the backend dict: an added, removed,
renamed or commented-out entry cannot hide from a parser, because there is none.
"""

from __future__ import annotations

import json
from pathlib import Path

from explanation.signal_labels import SIGNAL_LABEL
from formulas.engine import load_spec

MODEL_SPECS = ("piotroski_v1", "altman_v1", "beneish_v1", "sloan_v1")
FRONTEND_LABELS = Path(__file__).resolve().parents[2] / "frontend" / "app" / "lib" / "signalLabels.json"


def test_every_spec_signal_has_a_label() -> None:
    keys = {k for spec in MODEL_SPECS for k in load_spec(spec).signal_keys}
    assert len(keys) == 23  # positive control: the specs were actually read
    assert keys - SIGNAL_LABEL.keys() == set()
    assert SIGNAL_LABEL.keys() - keys == set()  # no label for a signal that does not exist


def test_frontend_signal_labels_equal_the_backend() -> None:
    frontend = json.loads(FRONTEND_LABELS.read_text())
    assert frontend == SIGNAL_LABEL
