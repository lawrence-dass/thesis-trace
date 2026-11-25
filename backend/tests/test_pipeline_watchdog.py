"""Ops 7: the watchdog's freshness decision."""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "pipeline_watchdog.py"
_spec = importlib.util.spec_from_file_location("pipeline_watchdog", SCRIPT)
watchdog = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(watchdog)

NOW = datetime(2026, 11, 26, 16, 17, tzinfo=UTC)


def _run(updated: str, conclusion: str | None = "success", status: str = "completed", rid: int = 1) -> dict:
    return {
        "databaseId": rid,
        "event": "schedule",
        "status": status,
        "conclusion": conclusion,
        "createdAt": updated,
        "updatedAt": updated,
    }


def test_a_recent_success_passes() -> None:  # positive control
    ok, message = watchdog.check([_run("2026-11-26T10:30:00Z")], NOW)
    assert ok
    assert message.startswith("OK")


def test_boundary_is_exactly_the_limit() -> None:
    at_limit = watchdog.check([_run("2026-11-25T14:17:00Z")], NOW, 26)  # exactly 26h
    past_limit = watchdog.check([_run("2026-11-25T14:16:00Z")], NOW, 26)  # 26h01m
    assert at_limit[0] is True
    assert past_limit[0] is False


def test_a_missed_scheduled_run_alerts_the_same_afternoon() -> None:
    """Yesterday's 10:23 run succeeded, today's never started: the 16:17 slot sees ~30h."""
    ok, message = watchdog.check([_run("2026-11-25T10:30:00Z")], NOW)
    assert not ok
    assert "Run pipeline.yml by hand" in message


def test_the_2026_11_25_incident_alerts_at_the_next_morning_slot() -> None:
    """The real history: only a manual run at 15:52 on 11-24. At 16:17 on 11-25 that
    is 24.4h old, inside the limit, so the miss is caught at 04:17 on 11-26 (36.4h)."""
    runs = [{**_run("2026-11-24T15:52:06Z"), "event": "workflow_dispatch"}]
    assert watchdog.check(runs, datetime(2026, 11, 25, 16, 17, tzinfo=UTC))[0] is True
    assert watchdog.check(runs, datetime(2026, 11, 26, 4, 17, tzinfo=UTC))[0] is False


def test_a_newer_failed_run_does_not_count_as_fresh() -> None:
    runs = [_run("2026-11-24T10:30:00Z", rid=1), _run("2026-11-26T10:30:00Z", conclusion="failure", rid=2)]
    assert watchdog.check(runs, NOW)[0] is False


def test_an_in_progress_run_does_not_count_as_fresh() -> None:
    runs = [_run("2026-11-24T10:30:00Z", rid=1), _run("2026-11-26T16:00:00Z", conclusion=None, status="in_progress", rid=2)]
    assert watchdog.check(runs, NOW)[0] is False


def test_newest_success_wins_whatever_the_list_order() -> None:
    runs = [_run("2026-11-20T10:30:00Z", rid=1), _run("2026-11-26T10:30:00Z", rid=2), _run("2026-11-22T10:30:00Z", rid=3)]
    ok, message = watchdog.check(runs, NOW)
    assert ok
    assert "run 2 " in message


def test_no_history_is_stale() -> None:
    assert watchdog.check([], NOW)[0] is False
