"""Ops 4: `scripts/trial_filers.py` must refuse BEFORE any company is fetched.

The script's whole safety claim is ordering: every TICKER:CIK pair is checked
against SEC's ticker map first, and the pipeline (which fetches company facts,
Inline XBRL and Tiingo prices) runs only if all of them match. A regression that
started on the first valid candidate before reaching a later mismatch would
still exit non-zero, so these tests assert that the pipeline was never entered,
not merely that the script failed.

Candidates are MSFT and NKE because they are NOT in PHASE1_UNIVERSE; a ticker
that is gets refused earlier, while parsing (tested separately below).
"""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "trial_filers.py"


def _load():
    spec = importlib.util.spec_from_file_location("trial_filers", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _TickerMap:
    """Stands in for httpx.AsyncClient; serves only SEC's ticker map."""

    requests: list[str] = []

    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc) -> None:
        return None

    async def get(self, url, headers=None):
        _TickerMap.requests.append(url)

        class _Resp:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict:
                return {
                    "0": {"cik_str": 789019, "ticker": "MSFT", "title": "MICROSOFT CORP"},
                    "1": {"cik_str": 320187, "ticker": "NKE", "title": "NIKE, Inc."},
                }

        return _Resp()


@pytest.fixture
def trial(monkeypatch):
    module = _load()
    calls: list[list] = []

    async def fake_main(entries=None) -> None:
        calls.append(list(entries))

    async def no_throttle() -> None:
        return None

    _TickerMap.requests = []
    monkeypatch.setattr(module, "main", fake_main)
    monkeypatch.setattr(module, "_throttle", no_throttle)
    monkeypatch.setattr(module, "_user_agent", lambda: "test")
    monkeypatch.setattr(module.httpx, "AsyncClient", _TickerMap)
    return module, calls


def test_a_later_mismatch_stops_the_whole_batch_before_any_fetch(trial) -> None:
    module, calls = trial
    # MSFT is valid and listed FIRST; NKE's CIK is wrong.
    with pytest.raises(SystemExit, match="NKE"):
        asyncio.run(module.run(["MSFT:0000789019", "NKE:0000099999"]))
    assert calls == [], "the pipeline ran for a batch containing an unconfirmed CIK"
    assert len(_TickerMap.requests) == 1  # only the ticker map was requested


def test_a_ticker_missing_from_secs_map_is_refused(trial) -> None:
    module, calls = trial
    with pytest.raises(SystemExit, match="ZZZZ"):
        asyncio.run(module.run(["MSFT:0000789019", "ZZZZ:0000000001"]))
    assert calls == []


def test_an_existing_universe_ticker_is_refused_before_any_network(trial) -> None:
    module, calls = trial
    # SHOP is already in PHASE1_UNIVERSE: refused while parsing arguments.
    with pytest.raises(SystemExit, match="already in the universe"):
        asyncio.run(module.run(["MSFT:0000789019", "SHOP:0001594805"]))
    assert calls == []
    assert _TickerMap.requests == []


def test_confirm_only_never_enters_the_pipeline(trial) -> None:
    module, calls = trial
    asyncio.run(module.run(["--confirm-only", "MSFT:0000789019"]))
    assert calls == []


def test_a_fully_confirmed_batch_runs_with_secs_titles(trial) -> None:
    """Positive control: without it, the refusals above would pass vacuously."""
    module, calls = trial
    asyncio.run(module.run(["MSFT:0000789019", "NKE:0000320187"]))
    assert len(calls) == 1
    assert [(e.ticker, e.cik, e.name) for e in calls[0]] == [
        ("MSFT", "0000789019", "MICROSOFT CORP"),
        ("NKE", "0000320187", "NIKE, Inc."),
    ]
