"""Prove exclusion regressions fail on behavior, not collection/import errors.

Run with ``make py F=scripts/verify_exclusion_guards.py``. Each mutation runs in
a separate process against the test database. No tracked source is rewritten.
The validator mutation uses the actual pre-13.4b checker with a signature adapter;
the other mutations remove one guard or restore the former alias-only behavior.
"""

from __future__ import annotations

import ast
import contextlib
import inspect
import io
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

LEGACY_BASE = "b882f658d2f82bf4a95c93680b6ac75f9ff50575"
UNIT = "tests/test_brand_member_mapping.py"
PIPELINE = "tests/test_member_canonicalization.py"
CASES = {
    "caller_scope": (
        [f"{PIPELINE}::test_canonicalization_flags_an_excluded_member_outside_its_verified_scope"],
        2, "assert 0 == 1",
    ),
    "predicate_scope": (
        [f"{UNIT}::test_an_exclusion_does_not_suppress_its_member_on_another_axis",
         f"{UNIT}::test_an_exclusion_with_source_concepts_does_not_suppress_another_concept"],
        2, "assert not True",
    ),
    "validator_reachability": (
        [f"{UNIT}::test_an_exclusion_on_an_axis_no_rule_reads_is_rejected",
         f"{UNIT}::test_an_exclusion_is_unreachable_when_only_another_filers_rule_reads_its_axis",
         f"{UNIT}::test_an_exclusion_naming_a_concept_no_rule_reads_is_rejected"],
        3, "DID NOT RAISE",
    ),
    "loader_reachability": (
        [UNIT, "-k", "test_the_loader_rejects_an_invalid_exclusion "
         "and not missing_axis and not scalar_concepts"],
        3, "DID NOT RAISE",
    ),
    "missing_axis": (
        [f"{UNIT}::test_an_exclusion_without_an_axis_is_rejected_at_load"],
        1, "DID NOT RAISE",
    ),
    "collisions": ([UNIT, "-k", "collid"], 6, "DID NOT RAISE"),
}


def replace_function(function, *replacements: tuple[str, str]) -> None:
    source = inspect.getsource(function)
    for old, new in replacements:
        if source.count(old) != 1:
            raise RuntimeError(f"mutation anchor changed in {function.__name__}")
        source = source.replace(old, new)
    original = getattr(function, "__wrapped__", function)
    exec(compile(source, "<in-memory exclusion mutation>", "exec"),
         original.__globals__)


def mutate(case: str) -> None:
    import canonicalization.canonicalize as canonicalizer
    import canonicalization.mappings.engine as engine

    if case == "caller_scope":
        canonicalizer._legacy_exclusion_aliases = {
            (entry.issuer_cik, alias) for entry in engine.EXCLUDED_MEMBERS for alias in entry.aliases
        }
        replace_function(canonicalizer._canonicalize_members,
                         ("not is_excluded(issuer_cik, rf.concept, axis, member)",
                          "(issuer_cik, member) not in _legacy_exclusion_aliases"))
    elif case == "predicate_scope":
        def alias_only(issuer, concept, axis, member, *, index=engine.EXCLUSION_INDEX):
            return any(cik == issuer and alias == member for cik, _, alias in index)
        engine.is_excluded = alias_only
    elif case == "validator_reachability":
        source = subprocess.check_output([
            "git", "show", f"{LEGACY_BASE}:backend/canonicalization/mappings/engine.py"
        ], text=True)
        node = next(node for node in ast.parse(source).body
                    if isinstance(node, ast.FunctionDef) and node.name == "_check_exclusions")
        node.name = "_legacy_check_exclusions"
        exec(compile(ast.Module(body=[node], type_ignores=[]), "<pre-13.4b checker>", "exec"),
             engine.__dict__)
        legacy = engine._legacy_check_exclusions
        engine._check_exclusions = lambda members, excluded, dimensioned: legacy(members, excluded)
    elif case == "loader_reachability":
        replace_function(engine.load_mapping_spec,
                         ("    _check_exclusions(members, excluded, dimensioned)\n", ""))
    elif case == "missing_axis":
        # Compatibility with the new required constructor field; no axis decision
        # is invented. The old parser never required or checked this field.
        replace_function(engine._parse_excluded_members, ('''            if not body.get("axis"):
                raise ValueError(
                    f"{spec_version}: excluded member {member_key!r} declares no axis — an "
                    "exclusion speaks only for the axis it was verified on"
                )
''', ""), ('axis=body["axis"]', 'axis=body.get("axis")'))
    elif case == "collisions":
        engine.build_exclusion_index = lambda entries: {
            (entry.issuer_cik, entry.axis, alias): entry for entry in entries for alias in entry.aliases
        }


class Reports:
    def __init__(self):
        self.failures = {}
        self.errors = []
        self.skipped = []

    def pytest_runtest_logreport(self, report):
        if report.skipped:
            self.skipped.append(report.nodeid)
        if report.failed:
            if report.when == "call":
                self.failures[report.nodeid] = report.longreprtext
            else:
                self.errors.append(report.longreprtext)

    def pytest_collectreport(self, report):
        if report.failed:
            self.errors.append(report.longreprtext)


def run_case(case: str) -> int:
    import pytest

    mutate(case)
    arguments, expected, reason = CASES[case]
    reports, output = Reports(), io.StringIO()
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
        result = pytest.main(["-q", "--tb=short", *arguments], plugins=[reports])
    if (result != pytest.ExitCode.TESTS_FAILED or reports.errors or reports.skipped
            or len(reports.failures) != expected
            or any(reason not in failure for failure in reports.failures.values())):
        print(output.getvalue())
        print(f"FAILED AUDIT: {case}; expected {expected} behavioral failures containing {reason!r}")
        return 1
    print(f"KILLED {case}: {expected} behavioral failures; no skips or collection/setup errors")
    for nodeid in reports.failures:
        print(f"  {nodeid}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--case":
        raise SystemExit(run_case(sys.argv[2]))
    for case in CASES:
        result = subprocess.run([sys.executable, __file__, "--case", case], check=False)
        if result.returncode:
            raise SystemExit(result.returncode)
    print("All six exclusion mutations killed.")
