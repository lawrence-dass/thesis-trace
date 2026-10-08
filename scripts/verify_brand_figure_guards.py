"""Prove Story 13.4c's tests fail on BEHAVIOR when each guarantee is broken.

Run with ``make py F=scripts/verify_brand_figure_guards.py``. Each mutation is
applied in memory, in its own process, against the test database; no tracked file
is rewritten (never_run_a_mutation_harness_on_uncommitted_work). A mutation counts
as killed only if the required tests fail in the CALL phase on AssertionError;
every other failure must also be an AssertionError. An import, collection or
setup error, another exception, or a skip fails the audit. The original nine
cases are retained, with nine supplemental guards added after the PR review.
Same shape as scripts/verify_exclusion_guards.py (PR #154).
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

TESTS = "tests/test_brand_figures.py"
CASES = {
    # (anchor, replacement) in brands/store.py source, the tests that must fail.
    "precedence_reversed": (
        "choose", ("for basis in rules.precedence:", "for basis in reversed(rules.precedence):"),
        ["test_carrying_value_beats_fair_value_for_one_brand_year"],
    ),
    "basis_ignores_context": (
        "basis", ("    if not qualifiers:\n", "    if True:\n"),
        ["test_basis_is_recorded_from_the_context",
         "test_an_undeclared_qualifier_blocks_a_declared_row",
         "test_carrying_value_beats_fair_value_for_one_brand_year"],
    ),
    "inputs_not_from_spec": (
        "materialize",
        ("CanonicalMemberFact.canonical_concept.in_(spec.inputs),",
         "CanonicalMemberFact.canonical_concept.like('brand_intangible_%'),"),
        ["test_only_declared_inputs_are_read"],
    ),
    "no_stale_deletion": (
        "materialize", ("removed = (await session.execute(stale)).rowcount or 0",
                        "removed = 0"),
        ["test_only_declared_inputs_are_read",
         "test_a_brand_year_that_stops_resolving_is_removed"],
    ),
    "stale_deletion_ignores_version": (
        "materialize", ("        BrandFigure.mapping_version == MAPPING_VERSION,\n    )",
                        "    )"),
        ["test_rows_under_another_version_pair_are_never_touched"],
    ),
    "no_version_filter": (
        "materialize", ("CanonicalMemberFact.mapping_version == MAPPING_VERSION,", ""),
        ["test_only_the_running_mapping_version_is_read"],
    ),
    "tie_is_a_pick": (
        "choose", ("        if len(values) == 1:", "        if True:"),
        ["test_two_unqualified_rows_with_different_values_are_insufficient"],
    ),
    "no_pre_acquisition_caveat": (
        "pre", ("        if first_value == 0 and", "        if False and"),
        ["test_pre_acquisition_zero_is_annotated_and_never_altered"],
    ),
    "pre_acquisition_any_zero": (
        "pre", ("        if first_value == 0 and any(value is not None and value > 0 for _, value in series[1:]):",
                "        if True:"),
        ["test_pre_acquisition_zero_is_annotated_and_never_altered"],
    ),
}

SUPPLEMENTAL_CASES = {
    "unknown_qualifier_is_ignored": (
        "choose", ("    if unknown:\n", "    if False:\n"),
        ["test_an_undeclared_qualifier_blocks_a_declared_row"],
    ),
    "insufficient_earliest_year_is_skipped": (
        "pre", ("        by_brand[brand_key].append((year, value))",
                "        if value is not None:\n            by_brand[brand_key].append((year, value))"),
        ["test_an_insufficient_earliest_year_does_not_shift_the_caveat"],
    ),
    "computed_at_is_not_refreshed": (
        "materialize", ("                if column not in {\n",
                        "                if column not in {\n                    'computed_at',\n"),
        ["test_recomputation_refreshes_value_source_and_computed_at"],
    ),
    "truncate_filed_decimal": (
        "materialize", ("value=round_ratio(to_decimal(winner.row.value), spec.formula),",
                        "value=int(winner.row.value),"),
        ["test_materialization_preserves_a_filed_fractional_amount"],
    ),
    "stale_deletion_ignores_figure": (
        "materialize", ("        BrandFigure.figure == spec.figure,\n", ""),
        ["test_stale_deletion_preserves_other_figures_formulas_and_issuers"],
    ),
    "stale_deletion_ignores_formula": (
        "materialize", ("        BrandFigure.formula_version == spec.formula.formula_version,\n", ""),
        ["test_stale_deletion_preserves_other_figures_formulas_and_issuers"],
    ),
    "stale_deletion_ignores_issuer": (
        "materialize", ("        BrandFigure.issuer_cik == issuer_cik,\n", ""),
        ["test_stale_deletion_preserves_other_figures_formulas_and_issuers"],
    ),
    "brand_stage_before_canonicalization": (
        "pipeline_before", ("    brands = await materialize_brand_carrying_values(session, parsed.cik)\n", ""),
        ["test_run_issuer_materializes_filed_brand_rows_before_commit"],
    ),
    "brand_stage_after_commit": (
        "pipeline_after", ("    brands = await materialize_brand_carrying_values(session, parsed.cik)\n", ""),
        ["test_run_issuer_materializes_filed_brand_rows_before_commit"],
    ),
}
ALL_CASES = CASES | SUPPLEMENTAL_CASES


def mutate(case: str) -> None:
    import brands.store as store
    from pipeline import run

    target, (old, new), _ = ALL_CASES[case]
    function = {
        "materialize": store.materialize_brand_carrying_values,
        "basis": store._basis,
        "choose": store._choose,
        "pre": store._pre_acquisition_years,
        "pipeline_before": run.run_issuer,
        "pipeline_after": run.run_issuer,
    }[target]
    source = inspect.getsource(function)
    if source.count(old) != 1:
        raise RuntimeError(f"mutation anchor changed for {case}")
    mutated = source.replace(old, new)
    if target.startswith("pipeline_"):
        anchor = ("    await canonicalize_issuer(session, parsed.cik)\n"
                  if target == "pipeline_before" else "    await session.commit()\n")
        if mutated.count(anchor) != 1:
            raise RuntimeError(f"pipeline mutation anchor changed for {case}")
        mutated = mutated.replace(anchor, old + anchor if target == "pipeline_before" else anchor + old)
    namespace = run.__dict__ if target.startswith("pipeline_") else store.__dict__
    exec(compile(mutated, f"<mutation {case}>", "exec"), namespace)


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
            if call.excinfo is None or not call.excinfo.errisinstance(AssertionError):
                self.errors.append(f"{item.nodeid}: non-AssertionError failure: {call.excinfo}")

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
    expected = set(ALL_CASES[case][2])
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
    for case in ALL_CASES:
        failures += subprocess.run([sys.executable, __file__, "--case", case], check=False).returncode != 0
    if failures:
        raise SystemExit(f"{failures} mutation(s) survived")
    print(f"All {len(CASES)} required brand-figure mutations killed; "
          f"all {len(SUPPLEMENTAL_CASES)} supplemental mutations killed.")
