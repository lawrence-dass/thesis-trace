"""Prove Story 13.5a's tests fail on BEHAVIOR when each guarantee is broken.

Run with ``make py F=scripts/verify_segment_mapping_guards.py``.

Most of 13.5a's guarantees execute at IMPORT time — `engine.py` loads the spec
into module constants (MEMBER_RESOLUTION, SEGMENT_MEMBERS, BRAND_MEMBERS) when it
is first imported. Replacing a function afterwards would test nothing. So each
mutation compiles a MUTATED COPY of engine.py's source in memory, registers it as
`canonicalization.mappings.engine` in sys.modules BEFORE the package imports it,
and only then runs the tests. No tracked file is touched. Same kill contract as
the brand audits: named tests fail in the CALL phase on an AssertionError (or
pytest.raises' DID NOT RAISE), with no errors or skips.
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
ENGINE = BACKEND / "canonicalization" / "mappings" / "engine.py"
TESTS = "tests/test_segment_mapping.py"

CASES = {
    "segments_leak_into_brand_members": (
        [("        brand_members=members,\n", "        brand_members=members + segments,\n")],
        ["test_cpb_segments_are_declared_as_segments_never_as_brands"],
    ),
    "segment_not_restricted_to_its_axis": (
        [("                if member.axis and rule.axis != member.axis:", "                if False:")],
        ["test_a_segment_resolves_only_on_its_own_axis"],
    ),
    "brand_resolves_on_segment_axis": (
        [("                if not member.axis and (member.issuer_cik, rule.axis) in segment_axes:",
          "                if False:")],
        ["test_no_brand_member_resolves_on_cpbs_segment_axis"],
    ),
    "custom_tag_taxonomy_ignored": (
        [('                    source_taxonomy=source.get("taxonomy", taxonomy),',
          "                    source_taxonomy=taxonomy,")],
        ["test_both_eras_of_each_switch_resolve_to_one_concept",
         "test_canonicalization_lands_each_segment_year_once_across_the_switch"],
    ),
    "segment_checks_skipped": (
        [("    _check_segment_members(segments, members, dimensioned)\n", "")],
        ["test_the_loader_rejects_a_segment_that_is_also_a_brand",
         "test_the_loader_rejects_a_segment_on_an_axis_no_rule_reads"],
    ),
    "exclusions_blind_to_segments": (
        [("    _check_exclusions(members + segments, excluded, dimensioned)",
          "    _check_exclusions(members, excluded, dimensioned)")],
        ["test_the_loader_rejects_an_alias_both_segment_and_excluded"],
    ),
}


def install_mutated_engine(case: str) -> None:
    source = ENGINE.read_text()
    for old, new in CASES[case][0]:
        if source.count(old) != 1:
            raise RuntimeError(f"mutation anchor changed for {case}: {old!r}")
        source = source.replace(old, new)
    importlib.import_module("canonicalization")  # parent package only
    module = types.ModuleType("canonicalization.mappings.engine")
    module.__file__ = str(ENGINE)  # SPECS_DIR is derived from it
    module.__package__ = "canonicalization.mappings"
    sys.modules[module.__name__] = module
    exec(compile(source, f"<mutated engine: {case}>", "exec"), module.__dict__)


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
    install_mutated_engine(case)
    expected = set(CASES[case][1])
    reports, output = Reports(), io.StringIO()
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
        result = pytest.main(["-q", "--tb=short", TESTS], plugins=[reports])
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
    print(f"All {len(CASES)} segment-mapping mutations killed.")
