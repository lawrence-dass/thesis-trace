"""Prove Story 13.4d's tests fail on BEHAVIOR when each guarantee is broken.

Run with ``make py F=scripts/verify_brand_impairment_guards.py``. Same contract as
scripts/verify_brand_figure_guards.py (13.4c): each mutation is applied in memory,
in its own process, against the test database; it counts as killed only if the
named tests fail in the CALL phase on AssertionError, with no errors or skips.

Not mutated, deliberately: dropping `figure` from the impairment stage's stale
delete is an EQUIVALENT mutant. That delete also filters on the impairment
formula_version, which no carrying-value row carries, and the impairment row set
is a superset of the carrying-value brand-years — so isolation holds by
construction and no test can tell the mutant apart.
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

TESTS = "tests/test_brand_impairments.py"
CPB_TEST = "test_cpb_charges_land_per_brand_and_uncharged_years_are_not_zero"

# case -> (target, [(old, new), ...], tests that must fail)
CASES = {
    "level_not_stored": (
        "materialize", [('"level": level,', '"level": None,')],
        [CPB_TEST, "test_zts_rows_are_filer_only_and_carry_no_figure",
         "test_qsr_rows_say_the_filer_tags_no_impairment",
         "test_run_issuer_commits_impairment_rows_after_carrying_value"],
    ),
    "absence_reason_ignores_level": (
        "materialize", [("reason = NO_CHARGE_REASON[level]", 'reason = NO_CHARGE_REASON["brand"]')],
        ["test_zts_rows_are_filer_only_and_carry_no_figure",
         "test_qsr_rows_say_the_filer_tags_no_impairment"],
    ),
    "undeclared_filer_gets_a_guessed_level": (
        "materialize", [("level = spec.levels.get(issuer_cik)",
                         'level = spec.levels.get(issuer_cik, "brand")')],
        ["test_an_undeclared_filer_gets_no_guessed_level"],
    ),
    "row_set_not_from_carrying_value": (
        "materialize", [("BrandFigure.figure == carrying.figure,", 'BrandFigure.figure == "none",')],
        [CPB_TEST, "test_zts_rows_are_filer_only_and_carry_no_figure",
         "test_qsr_rows_say_the_filer_tags_no_impairment"],
    ),
    "charge_without_carrying_row_dropped": (
        "materialize", [("        if figure is None:  # a charge on a brand-year with no carrying value (D-g)\n",
                         "        if figure is None:\n            continue\n        if figure is None:\n")],
        [CPB_TEST],
    ),
    "disagreeing_charges_become_a_pick": (
        "materialize", [("winner, reason = _choose(figure, common.basis)",
                         "winner, reason = figure.candidates[0], None")],
        ["test_two_disagreeing_charges_are_insufficient_never_a_pick"],
    ),
    "no_stale_deletion": (
        "materialize", [("removed = (await session.execute(stale)).rowcount or 0", "removed = 0")],
        ["test_an_impairment_row_whose_brand_year_vanished_is_removed"],
    ),
    "loader_skips_the_brand_level_check": (
        "parse", [('        if levels.get(cik) != "brand":', "        if False:")],
        ["test_the_loader_rejects_a_level_or_reason_the_pipeline_contradicts"],
    ),
    "loader_skips_the_reason_check": (
        "parse", [("    if reasons != applied:", "    if False:")],
        ["test_the_loader_rejects_a_level_or_reason_the_pipeline_contradicts"],
    ),
    "impairment_runs_before_carrying_value": (
        "pipeline", [
            ("    brand_impairments = await materialize_brand_impairments(session, parsed.cik)\n", ""),
            ("    brands = await materialize_brand_carrying_values(session, parsed.cik)\n",
             "    brand_impairments = await materialize_brand_impairments(session, parsed.cik)\n"
             "    brands = await materialize_brand_carrying_values(session, parsed.cik)\n"),
        ],
        ["test_run_issuer_commits_impairment_rows_after_carrying_value"],
    ),
}


def mutate(case: str) -> None:
    import brands.impairment as impairment
    from pipeline import run

    target, replacements, _ = CASES[case]
    function = {
        "materialize": impairment.materialize_brand_impairments,
        "parse": impairment.parse_impairment_spec,
        "pipeline": run.run_issuer,
    }[target]
    source = inspect.getsource(function)
    for old, new in replacements:
        if source.count(old) != 1:
            raise RuntimeError(f"mutation anchor changed for {case}: {old!r}")
        source = source.replace(old, new)
    namespace = run.__dict__ if target == "pipeline" else impairment.__dict__
    exec(compile(source, f"<mutation {case}>", "exec"), namespace)
    if target == "parse":
        impairment.load_impairment_spec.cache_clear()
    if target == "materialize":
        # run.py imported the function BY NAME before this mutation; without the
        # rebind the pipeline test would exercise the original, not the mutant.
        run.materialize_brand_impairments = impairment.materialize_brand_impairments


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
            # pytest.raises' "DID NOT RAISE" is a behavioral failure (the guard did not
            # fire), raised as pytest's Failed outcome rather than AssertionError.
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
    print(f"All {len(CASES)} brand-impairment mutations killed.")
