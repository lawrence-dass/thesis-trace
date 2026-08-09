"""Guards on the test harness itself.

`conftest.db_session` runs `drop_all` on whatever URL it resolves. That makes the
resolution rule a safety control, not a convenience, so it is pinned here rather
than left to a comment — the same reasoning that put the sprint-status ledger under
test after it failed three times unnoticed.
"""

from __future__ import annotations

from pathlib import Path

from tests.conftest import _resolve_test_db_url

CONFTEST = Path(__file__).parent / "conftest.py"

DEV = "postgresql+asyncpg://user@localhost:5432/thesistrace"
TEST = "postgresql+asyncpg://user@localhost:5432/thesistrace_test"


def test_database_url_is_not_a_fallback_for_the_destructive_fixture():
    """THE INCIDENT THIS ENCODES. `conftest` used to read
    `TEST_DATABASE_URL or DATABASE_URL`. Anyone who exported only `DATABASE_URL` —
    the ordinary way to run the application — silently handed their DEV database to
    a fixture that drops every table. It happened once; `.env` keeps the two as
    separate values because of it.

    The dangerous direction is silence: with the fallback the suite RAN against the
    wrong database, without it the suite SKIPS. A skip is visible in the output; a
    wiped dev database is discovered later.
    """
    assert _resolve_test_db_url({"DATABASE_URL": DEV}) is None
    assert _resolve_test_db_url({"DATABASE_URL": DEV, "TEST_DATABASE_URL": TEST}) == TEST
    assert _resolve_test_db_url({"TEST_DATABASE_URL": TEST}) == TEST
    assert _resolve_test_db_url({}) is None


def test_a_blank_test_database_url_counts_as_absent():
    """An exported-but-empty variable must not read as configured. `create_async_engine("")`
    fails obscurely at fixture setup rather than skipping cleanly, which turns a
    misconfiguration into a confusing error instead of a clear one."""
    assert _resolve_test_db_url({"TEST_DATABASE_URL": ""}) is None


def test_ci_still_exercises_the_db_tests():
    """Removing the fallback must not silently un-run ~90 DB-backed tests in CI.

    CI sets BOTH variables at the same throwaway service container — deliberately,
    because Alembic's `env.py` reads `DATABASE_URL` while these fixtures read
    `TEST_DATABASE_URL`. If a future edit drops `TEST_DATABASE_URL` from the
    workflow, every DB test would skip and the suite would still report green. That
    is the exact shape of failure this file exists to prevent, so it is asserted
    against the workflow rather than assumed.
    """
    ci = (Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ci.yml").read_text()
    assert "TEST_DATABASE_URL:" in ci, (
        "ci.yml no longer sets TEST_DATABASE_URL — every DB-backed test would skip "
        "while CI still reported success"
    )


def test_the_fallback_has_not_been_reintroduced():
    """Belt and braces on the source itself. The pure function above can stay correct
    while a well-meaning edit reintroduces the fallback at the call site, which is how
    the original bug would return."""
    source = CONFTEST.read_text()
    assert 'os.getenv("DATABASE_URL")' not in source, (
        "conftest.py reads DATABASE_URL again — db_session drops every table on the "
        "URL it resolves, so this must stay TEST_DATABASE_URL only"
    )
