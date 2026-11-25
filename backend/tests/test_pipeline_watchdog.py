"""Ops 7: the watchdog's freshness decision, and the exit code the workflow relies on."""

from __future__ import annotations

import importlib.util
import io
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "pipeline_watchdog.py"
_spec = importlib.util.spec_from_file_location("pipeline_watchdog", SCRIPT)
watchdog = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(watchdog)

NOW = datetime(2026, 11, 26, 16, 17, tzinfo=UTC)


def _run(
    started: str,
    conclusion: str | None = "success",
    status: str = "completed",
    rid: int = 1,
    created: str = "2026-01-01T00:00:00Z",
    updated: str = "2026-12-31T00:00:00Z",
) -> dict:
    """createdAt and updatedAt default to values far from startedAt on purpose, so a
    check that read either field instead would give a different answer."""
    return {
        "databaseId": rid,
        "event": "schedule",
        "status": status,
        "conclusion": conclusion,
        "createdAt": created,
        "startedAt": started,
        "updatedAt": updated,
    }


def test_a_recent_success_passes() -> None:  # positive control
    ok, message = watchdog.check([_run("2026-11-26T10:23:00Z")], NOW)
    assert ok
    assert message.startswith("OK")


def test_boundary_is_exactly_the_limit() -> None:
    assert watchdog.check([_run("2026-11-25T14:17:00Z")], NOW, 26)[0] is True  # exactly 26h
    assert watchdog.check([_run("2026-11-25T14:16:00Z")], NOW, 26)[0] is False  # 26h01m


def test_updated_at_moved_by_log_deletion_does_not_look_fresh() -> None:
    """Codex's case: finished Nov 24, updatedAt advanced by housekeeping on Nov 26."""
    run = _run("2026-11-24T10:23:00Z", created="2026-11-24T10:23:00Z", updated="2026-11-26T16:00:00Z")
    ok, message = watchdog.check([run], NOW)
    assert not ok
    assert "53.9h ago" in message  # measured from startedAt, not the moved updatedAt


def test_a_rerun_counts_from_its_new_start_not_its_creation() -> None:
    """A failed nightly re-run successfully today keeps its old createdAt."""
    run = _run("2026-11-26T09:00:00Z", created="2026-11-20T10:23:00Z")
    assert watchdog.check([run], NOW)[0] is True


def test_a_missed_scheduled_run_alerts_the_same_afternoon() -> None:
    """Yesterday's 10:23 run succeeded, today's never started: the 16:17 slot sees ~30h."""
    ok, message = watchdog.check([_run("2026-11-25T10:23:00Z")], NOW)
    assert not ok
    assert "Run pipeline.yml by hand" in message


def test_a_late_success_is_caught_at_the_next_morning_slot() -> None:
    """Same-day detection is conditional. The 2026-11-25 incident's last success was a
    manual run at 15:50 on 11-24: 24.5h old at 16:17 on 11-25 (inside the limit), so
    the miss is caught at 04:17 on 11-26 (36.5h)."""
    runs = [{**_run("2026-11-24T15:50:06Z"), "event": "workflow_dispatch"}]
    assert watchdog.check(runs, datetime(2026, 11, 25, 16, 17, tzinfo=UTC))[0] is True
    assert watchdog.check(runs, datetime(2026, 11, 26, 4, 17, tzinfo=UTC))[0] is False


def test_a_newer_failed_run_does_not_count_as_fresh() -> None:
    runs = [_run("2026-11-24T10:23:00Z", rid=1), _run("2026-11-26T10:23:00Z", conclusion="failure", rid=2)]
    assert watchdog.check(runs, NOW)[0] is False


def test_an_in_progress_run_does_not_count_as_fresh() -> None:
    runs = [_run("2026-11-24T10:23:00Z", rid=1), _run("2026-11-26T16:00:00Z", conclusion=None, status="in_progress", rid=2)]
    assert watchdog.check(runs, NOW)[0] is False


def test_newest_success_wins_whatever_the_list_order() -> None:
    runs = [_run("2026-11-20T10:23:00Z", rid=1), _run("2026-11-26T10:23:00Z", rid=2), _run("2026-11-22T10:23:00Z", rid=3)]
    ok, message = watchdog.check(runs, NOW)
    assert ok
    assert "run 2 " in message


def test_no_history_is_stale() -> None:
    assert watchdog.check([], NOW)[0] is False


@pytest.mark.parametrize(
    ("runs", "code"),
    [([_run("2026-11-26T10:23:00Z")], 0), ([_run("2026-11-24T10:23:00Z")], 1), ([], 1)],
    ids=["fresh", "stale", "empty"],
)
def test_cli_exit_code_is_what_fails_the_workflow(monkeypatch, capsys, runs, code) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(runs)))
    assert watchdog.main(["--now", "2026-11-26T16:17:00Z"]) == code
    assert capsys.readouterr().out.strip()  # always says why
