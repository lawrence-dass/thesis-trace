"""Prove Story 13.5b's tests fail on BEHAVIOR when each guarantee is broken.

Run with ``make py F=scripts/verify_segment_payload_guards.py``.

Each case compiles a MUTATED COPY of `segments/store.py` in memory and registers
it as `segments.store` in sys.modules BEFORE anything imports it, so
`pipeline/run.py`'s `from segments.store import materialize_segment_payloads`
binds the mutant too (a patched function would leave that name on the original).
No tracked file is touched. Kill contract as the other audits: the named tests
fail in the CALL phase on an AssertionError (or DID NOT RAISE), with no errors
or skips.
"""

from __future__ import annotations

import contextlib
import importlib
import io
import subprocess
import sys
import types
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))
STORE = BACKEND / "segments" / "store.py"
TESTS = ["tests/test_segment_payloads.py"]

CASES = {
    "qualified_rows_silently_dropped": (  # D-l
        [("            groups[(axis, row.member_key, row.canonical_concept, row.fiscal_year)]"
          ".append(row)",
          "            if not _qualifiers(row, axis):\n"
          "                groups[(axis, row.member_key, row.canonical_concept, row.fiscal_year)]"
          ".append(row)")],
        ["test_a_qualified_row_vetoes_its_segment_year",
         "test_a_value_that_turns_insufficient_loses_every_source_field"],
    ),
    "superseded_rows_read": (
        [("                    CanonicalMemberFact.superseded.is_(False),\n", "")],
        ["test_only_segment_rows_of_the_running_version_become_payloads",
         "test_a_segment_year_that_stops_resolving_is_removed"],
    ),
    "mapping_version_blind_read": (
        [("                    CanonicalMemberFact.mapping_version == MAPPING_VERSION,\n", "")],
        ["test_only_segment_rows_of_the_running_version_become_payloads"],
    ),
    "undeclared_members_read": (
        [("                    CanonicalMemberFact.member_key.in_(members),\n", "")],
        ["test_only_segment_rows_of_the_running_version_become_payloads"],
    ),
    "non_segment_concepts_read": (
        [("                    CanonicalMemberFact.canonical_concept.in_(concepts),\n", "")],
        ["test_only_segment_rows_of_the_running_version_become_payloads"],
    ),
    "stale_rows_kept": (
        [("    removed = (await session.execute(stale)).rowcount or 0",
          "    removed = 0")],
        ["test_a_segment_year_that_stops_resolving_is_removed"],
    ),
    "stale_delete_crosses_versions": (
        [("        SegmentPayload.mapping_version == MAPPING_VERSION,\n    )", "    )")],
        ["test_rows_under_another_mapping_version_are_never_touched"],
    ),
    "upsert_keeps_old_provenance": (
        [("            set_={c: statement.excluded[c] for c in values if c not in _KEY_COLUMNS},",
          "            set_={c: statement.excluded[c] for c in values if c not in _KEY_COLUMNS"
          " | {'source_member_fact_id', 'accession_number', 'member_as_filed', 'unit',"
          " 'period_end'}},")],
        ["test_a_value_that_turns_insufficient_loses_every_source_field"],
    ),
    "value_rounded": (
        [("                value=row.value,  # the filed amount, carried exactly",
          "                value=round(row.value),")],
        ["test_each_filed_segment_year_lands_once_with_its_provenance"],
    ),
    "provenance_dropped": (
        [("                accession_number=row.accession_number,",
          "                accession_number=None,")],
        ["test_each_filed_segment_year_lands_once_with_its_provenance",
         "test_run_issuer_materializes_filed_segment_rows_before_commit"],
    ),
    "inputs_ignore_segment_members": (
        [("            m.member_key for m in SEGMENT_MEMBERS if m.issuer_cik == issuer_cik"
          " and m.axis == axis",
          "            m.member_key for m in SEGMENT_MEMBERS if m.issuer_cik == issuer_cik"
          " and m.axis == axis and m.member_key != 'snacks'")],
        ["test_cpbs_inputs_are_its_segment_rules_and_members"],
    ),
}


def install_mutant(case: str) -> None:
    source = STORE.read_text()
    for old, new in CASES[case][0]:
        if source.count(old) != 1:
            raise RuntimeError(f"mutation anchor changed for {case}: {old!r}")
        source = source.replace(old, new)
    importlib.import_module("segments")  # parent package only
    module = types.ModuleType("segments.store")
    module.__file__ = str(STORE)
    module.__package__ = "segments"
    sys.modules["segments.store"] = module
    exec(compile(source, f"<mutated store.py: {case}>", "exec"), module.__dict__)
    from pipeline import run

    assert run.materialize_segment_payloads is module.materialize_segment_payloads, "not bound"


class Reports:
    def __init__(self):
        self.failures: dict[str, str] = {}
        self.errors: list[str] = []
        self.skipped: list[str] = []

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(self, item, call):
        outcome = yield
        report = outcome.get_result()
        if report.when == "call" and report.failed:
            excinfo = call.excinfo
            did_not_raise = (
                excinfo is not None
                and excinfo.errisinstance(pytest.fail.Exception)
                and "DID NOT RAISE" in str(excinfo.value)
            )
            if excinfo is None or not (excinfo.errisinstance(AssertionError) or did_not_raise):
                self.errors.append(f"{item.nodeid}: non-AssertionError failure: {excinfo}")

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
    install_mutant(case)
    expected = set(CASES[case][1])
    reports, output = Reports(), io.StringIO()
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
        result = pytest.main(["-q", "--tb=short", "-p", "no:randomly", *TESTS], plugins=[reports])
    failed = {nodeid.split("::")[-1].split("[")[0] for nodeid in reports.failures}
    if (result != pytest.ExitCode.TESTS_FAILED or reports.errors or reports.skipped
            or not expected <= failed):
        print(output.getvalue()[-3000:])
        print(f"FAILED AUDIT: {case}; expected {sorted(expected)}, failed {sorted(failed)}")
        return 1
    print(f"KILLED {case}: {len(reports.failures)} failing ({', '.join(sorted(failed))})")
    return 0


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--case":
        raise SystemExit(run_case(sys.argv[2]))
    failures = 0
    for case in CASES:
        failures += subprocess.run([sys.executable, __file__, "--case", case], check=False).returncode != 0
    if failures:
        raise SystemExit(f"{failures} mutation(s) survived")
    print(f"All {len(CASES)} segment-payload mutations killed.")
