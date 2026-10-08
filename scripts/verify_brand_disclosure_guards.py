"""Prove Story 13.4e's tests fail on BEHAVIOR when each guarantee is broken.

Run with ``make py F=scripts/verify_brand_disclosure_guards.py``. Same contract as
the 13.4c/13.4d audits: in-memory mutations, one process each, against the test
database; killed only when the named tests fail in the CALL phase on an
AssertionError (or pytest.raises' DID NOT RAISE), with no errors or skips.
"""

from __future__ import annotations

import contextlib
import inspect
import io
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

TESTS = "tests/test_brand_disclosures.py"

CASES = {
    "kind_guard_off": (
        "materialize",
        [("        if spec.allowed_kinds is not None and figure.kind not in spec.allowed_kinds:",
          "        if False:")],
        ["test_a_row_resolving_to_another_kind_is_never_stored_as_a_brand"],
    ),
    "filer_threshold_caveat_dropped": (
        "materialize",
        [("+ ([FILER_THRESHOLD] if FILER_THRESHOLD in spec.caveats else [])", "+ []")],
        ["test_both_spellings_land_under_one_key_as_the_filers_statement",
         "test_run_issuer_commits_the_disclosure_rows"],
    ),
    "loader_allows_any_kind": (
        "parse", [("        if not allowed_kinds or undeclared:", "        if False:")],
        ["test_the_loader_rejects_a_kind_the_mapping_spec_does_not_declare"],
    ),
    "disclosure_stage_not_wired": (
        "pipeline",
        [("    brand_disclosures = await materialize_brand_carrying_values(\n"
          "        session, parsed.cik, formula_version=DISCLOSURE_FORMULA_VERSION\n"
          "    )\n",
          "    brand_disclosures = {'written': 1, 'removed': 0, 'unresolved': 0, 'insufficient': 0}\n")],
        ["test_run_issuer_commits_the_disclosure_rows"],
    ),
}


def mutate(case: str) -> None:
    import brands.store as store
    from pipeline import run

    target, replacements, _ = CASES[case]
    function = {
        "materialize": store.materialize_brand_carrying_values,
        "parse": store.parse_spec,
        "pipeline": run.run_issuer,
    }[target]
    source = inspect.getsource(function)
    for old, new in replacements:
        if source.count(old) != 1:
            raise RuntimeError(f"mutation anchor changed for {case}: {old!r}")
        source = source.replace(old, new)
    namespace = run.__dict__ if target == "pipeline" else store.__dict__
    exec(compile(source, f"<mutation {case}>", "exec"), namespace)
    if target == "parse":
        store.load_carrying_value_spec.cache_clear()
    if target == "materialize":
        # run.py imported the stage BY NAME (13.4d's harness lesson).
        run.materialize_brand_carrying_values = store.materialize_brand_carrying_values


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
    mutate(case)
    expected = set(CASES[case][2])
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
    print(f"All {len(CASES)} brand-disclosure mutations killed.")
