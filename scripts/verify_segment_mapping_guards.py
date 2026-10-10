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
CANONICALIZE = BACKEND / "canonicalization" / "canonicalize.py"
# Brand figures too: a segment axis must stay a QUALIFIER on a brand row (F1).
TESTS = ["tests/test_segment_mapping.py", "tests/test_brand_figures.py"]

# case -> (replacements, tests that must fail[, module]). The module defaults to
# engine.py; canonicalize.py cases mutate member selection, which runs per call
# but is installed the same way so every case shares one kill contract.
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
        [("    _check_segment_members(segments, members, segment_members, dimensioned)\n", "")],
        ["test_the_loader_rejects_a_segment_that_is_also_a_brand",
         "test_the_loader_rejects_a_segment_on_an_axis_no_rule_reads",
         "test_the_loader_rejects_a_segment_axis_that_brands_resolve_on"],
    ),
    "exclusions_blind_to_segments": (
        [("    _check_exclusions(members + segments, excluded, dimensioned)",
          "    _check_exclusions(members, excluded, dimensioned)")],
        ["test_the_loader_rejects_an_alias_both_segment_and_excluded"],
    ),
    # --- Codex review of #158 ---
    "segment_axis_counts_as_brand_identity": (  # F1
        [("    (m.issuer_cik, m.axis) for m in SEGMENT_MEMBERS if m.axis\n",
          "    (m.issuer_cik, m.axis) for m in SEGMENT_MEMBERS if False\n")],
        ["test_cpbs_segment_axis_is_a_qualifier_on_a_brand_row"],
    ),
    "segment_axis_shared_with_brand_rules": (  # F2
        [("        if shared or (segment.issuer_cik, segment.axis) in brand_axes:",
          "        if False:")],
        ["test_the_loader_rejects_a_segment_axis_that_brands_resolve_on"],
    ),
    "scalar_segment_aliases_accepted": (  # F3
        # Two lines: 13.4a's segment-brand loader carries the same `if`.
        [("            if raw_aliases is not None and not isinstance(raw_aliases, list):\n"
          "                raise ValueError(\n"
          "                    f\"{spec_version}: segment {member_key!r} declares aliases as \"",
          "            if False:\n"
          "                raise ValueError(\n"
          "                    f\"{spec_version}: segment {member_key!r} declares aliases as \"")],
        ["test_the_loader_rejects_scalar_segment_aliases"],
    ),
    "unread_segment_keys_accepted": (  # F4
        [("            unread = sorted(set(body) - _SEGMENT_MEMBER_KEYS)",
          "            unread = []")],
        ["test_the_loader_rejects_segment_keys_no_code_reads"],
    ),
    "original_filing_not_preferred": (  # F5
        [("                0 if originally_filed else 1,\n", "                0,\n")],
        ["test_the_original_filing_wins_even_against_a_more_precise_comparative"],
        CANONICALIZE,
    ),
    "segment_capex_read_as_an_event": (  # F6
        [("        policies[key] = matching[0].period_policy\n",
          "        policies[key] = 'event' if matching[0].canonical_concept == 'segment_capex'"
          " else matching[0].period_policy\n")],
        ["test_segment_capex_is_the_annual_flow_never_a_quarter"],
    ),
}


def _mutated(path: Path, case: str) -> str:
    source = path.read_text()
    for old, new in CASES[case][0]:
        if source.count(old) != 1:
            raise RuntimeError(f"mutation anchor changed for {case}: {old!r}")
        source = source.replace(old, new)
    return source


def _install(name: str, path: Path, source: str, case: str) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__file__ = str(path)  # SPECS_DIR is derived from it
    module.__package__ = name.rpartition(".")[0]
    sys.modules[name] = module
    exec(compile(source, f"<mutated {path.name}: {case}>", "exec"), module.__dict__)
    return module


def install_mutant(case: str) -> None:
    target = CASES[case][2] if len(CASES[case]) > 2 else ENGINE
    importlib.import_module("canonicalization")  # parent package only
    if target == CANONICALIZE:
        importlib.import_module("canonicalization.mappings")  # the real engine
        module = _install("canonicalization.canonicalize", CANONICALIZE,
                          _mutated(CANONICALIZE, case), case)
        assert importlib.import_module("canonicalization.canonicalize") is module
        return
    module = _install("canonicalization.mappings.engine", ENGINE, _mutated(ENGINE, case), case)
    # Now load the package: its __init__ imports `...mappings.engine`, which
    # resolves to the mutant already in sys.modules. Bind the attribute too, so
    # `import canonicalization.mappings.engine as x` returns the same object.
    package = importlib.import_module("canonicalization.mappings")
    package.engine = module
    assert package.MEMBER_RESOLUTION is module.MEMBER_RESOLUTION, "mutant not installed"


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
        result = pytest.main(["-q", "--tb=short", *TESTS], plugins=[reports])
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
