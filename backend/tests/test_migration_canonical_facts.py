"""Safety checks for the canonical-facts supersession migration."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


MIGRATION = Path(__file__).parents[2] / "db" / "migrations" / "versions" / (
    "c7e1f4a92b06_canonical_facts_supersession.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("canonical_facts_supersession", MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Result:
    def __init__(self, value):
        self.value = value

    def scalar(self):
        return self.value


class _Connection:
    def __init__(self, value):
        self.value = value
        self.statement = None

    def execute(self, statement):
        self.statement = str(statement)
        return _Result(self.value)


def test_downgrade_refuses_any_superseded_history_before_schema_changes(monkeypatch) -> None:
    migration = _load_migration()
    connection = _Connection(1)

    monkeypatch.setattr(migration.op, "get_bind", lambda: connection)
    monkeypatch.setattr(
        migration.op,
        "drop_index",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("index must not be dropped")),
    )

    with pytest.raises(RuntimeError, match="superseded rows exist"):
        migration.downgrade()
    assert "WHERE superseded" in connection.statement
