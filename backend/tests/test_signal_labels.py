"""Ops 6b: every signal has a plain-language name, and both apps use the same one."""

from __future__ import annotations

import re
from pathlib import Path

from explanation.signal_labels import SIGNAL_LABEL
from formulas.engine import load_spec

MODEL_SPECS = ("piotroski_v1", "altman_v1", "beneish_v1", "sloan_v1")
PAGE = Path(__file__).resolve().parents[2] / "frontend" / "app" / "company" / "[ticker]" / "page.tsx"


def _frontend_labels() -> dict[str, str]:
    source = PAGE.read_text()
    block = re.search(r"export const SIGNAL_LABEL: Record<string, string> = \{(.*?)\n\};", source, re.S)
    assert block, f"SIGNAL_LABEL not found in {PAGE}"
    return dict(re.findall(r'^\s*([a-z0-9_]+): "([^"]+)",', block.group(1), re.M))


def test_every_spec_signal_has_a_label() -> None:
    keys = {k for spec in MODEL_SPECS for k in load_spec(spec).signal_keys}
    assert len(keys) == 23  # positive control: the specs were actually read
    assert keys - SIGNAL_LABEL.keys() == set()
    assert SIGNAL_LABEL.keys() - keys == set()  # no label for a signal that does not exist


def test_frontend_signal_labels_match_the_backend() -> None:
    frontend = _frontend_labels()
    assert len(frontend) == len(SIGNAL_LABEL)  # parsed every entry, not a partial match
    assert frontend == SIGNAL_LABEL
