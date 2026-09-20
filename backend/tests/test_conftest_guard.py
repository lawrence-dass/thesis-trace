"""The DB fixtures drop every table; this guards what they are pointed at.

2026-09-20: a review found the Makefile's string comparison let
`.../thesistrace?sslmode=disable` through beside `DATABASE_URL=.../thesistrace`.
A full run started against the dev store and survived only because asyncpg rejects
that parameter. These cases are the ones a string comparison gets wrong.
"""

from __future__ import annotations

import pytest

from tests.conftest import _database_identity, _resolve_test_db_url

DEV = "postgresql+asyncpg://postgres:pw@localhost:5432/thesistrace"


@pytest.mark.parametrize(
    "same_db",
    [
        "postgresql+asyncpg://postgres:pw@localhost:5432/thesistrace?sslmode=disable",
        "postgresql+asyncpg://postgres:pw@localhost/thesistrace",  # default port spelled out
        "postgresql+asyncpg://other:other@localhost:5432/thesistrace",  # different creds
        "postgresql://postgres:pw@localhost:5432/thesistrace",  # different driver prefix
    ],
)
def test_a_test_url_addressing_the_dev_database_is_refused(same_db: str) -> None:
    with pytest.raises(RuntimeError, match="development database"):
        _resolve_test_db_url({"TEST_DATABASE_URL": same_db, "DATABASE_URL": DEV})


def test_a_genuinely_separate_database_is_allowed() -> None:
    separate = DEV + "_test"
    assert _resolve_test_db_url({"TEST_DATABASE_URL": separate, "DATABASE_URL": DEV}) == separate


def test_the_identity_ignores_credentials_and_query_but_not_the_name() -> None:
    assert _database_identity(DEV) == ("localhost", "5432", "thesistrace")
    assert _database_identity(DEV + "?x=1") == _database_identity(DEV)
    assert _database_identity(DEV + "_test") != _database_identity(DEV)


def test_absent_or_blank_test_url_still_resolves_to_none() -> None:
    assert _resolve_test_db_url({"DATABASE_URL": DEV}) is None
    assert _resolve_test_db_url({"TEST_DATABASE_URL": "", "DATABASE_URL": DEV}) is None
