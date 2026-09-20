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


def test_every_db_test_declares_its_precondition() -> None:
    """A test taking `db_session` must be marked `requires_db`.

    Without the marker it ERRORS instead of skipping when TEST_DATABASE_URL is unset:
    the fixture builds an engine from None. CI always sets the variable, so the gap is
    invisible there and only bites whoever runs the suite without a database —
    deterministic per environment, with the environments disagreeing, which is the
    same shape as the `.env` fallback trap already recorded in project-context.
    Found 2026-09-20 when Docker was down.
    """
    import importlib
    import inspect
    import pathlib

    missing = []
    for path in sorted(pathlib.Path(__file__).parent.glob("test_*.py")):
        module = importlib.import_module(f"tests.{path.stem}")
        # `pytestmark` is a list OR a single MarkDecorator — both are valid pytest.
        declared = getattr(module, "pytestmark", []) or []
        if not isinstance(declared, (list, tuple)):
            declared = [declared]
        module_marks = {getattr(m, "name", "") for m in declared}
        for name, obj in vars(module).items():
            if not name.startswith("test_") or not callable(obj):
                continue
            try:
                params = inspect.signature(obj).parameters
            except (TypeError, ValueError):  # pragma: no cover - builtins
                continue
            if "db_session" not in params:
                continue
            own = getattr(obj, "pytestmark", []) or []
            if not isinstance(own, (list, tuple)):
                own = [own]
            marks = {getattr(m, "name", "") for m in own}
            if not ({"skipif"} & (marks | module_marks)):
                missing.append(f"{path.name}::{name}")
    assert not missing, (
        f"DB tests without @requires_db (they error rather than skip): {missing}"
    )
