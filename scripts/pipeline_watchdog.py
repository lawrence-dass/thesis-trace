"""Ops 7: fail loudly when the nightly pipeline has not SUCCEEDED recently.

A pipeline that fails exits non-zero and GitHub emails about it. A pipeline whose
scheduled trigger never fires produces no signal at all, which is what happened on
2026-11-25. This reads the run history and exits 1 when the newest successful run
finished too long ago, so the watchdog workflow fails and GitHub sends the email.

Standard library only, so the workflow needs no install step:

    gh run list --workflow pipeline.yml --limit 30 \
        --json status,conclusion,createdAt,updatedAt,event,databaseId \
      | python3 scripts/pipeline_watchdog.py --max-age-hours 26
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta

MAX_AGE_HOURS = 26  # nightly at 10:23 UTC, plus slack for a late GitHub schedule


def _when(stamp: str) -> datetime:
    return datetime.fromisoformat(stamp.replace("Z", "+00:00"))


def check(runs: list[dict], now: datetime, max_age_hours: float = MAX_AGE_HOURS) -> tuple[bool, str]:
    """(ok, message). Only a COMPLETED, SUCCESSFUL run counts as fresh: a newer
    failed, cancelled or still-running run says nothing about whether data landed."""
    successes = [r for r in runs if r.get("status") == "completed" and r.get("conclusion") == "success"]
    if not successes:
        return False, "No successful pipeline run in the history. Run pipeline.yml by hand (Actions > Nightly pipeline > Run workflow)."
    latest = max(successes, key=lambda r: _when(r["updatedAt"]))
    finished = _when(latest["updatedAt"])
    age = now - finished
    hours = age.total_seconds() / 3600
    detail = f"last successful run {latest.get('databaseId')} ({latest.get('event')}) finished {finished:%Y-%m-%d %H:%M} UTC, {hours:.1f}h ago"
    if age > timedelta(hours=max_age_hours):
        return False, f"STALE: {detail}; limit {max_age_hours}h. Run pipeline.yml by hand (Actions > Nightly pipeline > Run workflow)."
    return True, f"OK: {detail}."


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--max-age-hours", type=float, default=MAX_AGE_HOURS)
    parser.add_argument("--now", help="ISO time to evaluate at (default: current UTC time)")
    args = parser.parse_args(argv)
    now = _when(args.now) if args.now else datetime.now(UTC)
    ok, message = check(json.load(sys.stdin), now, args.max_age_hours)
    print(message)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
