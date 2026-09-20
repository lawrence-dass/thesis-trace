"""Guards on `sprint-status.yaml`, the BMad tracking ledger.

This file exists because that ledger has now failed three times, and every failure
was caught by a human happening to look rather than by anything automatic:

  * It sat UNPARSEABLE by any YAML reader for ~2 days (2026-08-02 to 08-04) — an
    unterminated quoted string in `d8_ifrs_track`. Nothing noticed, because
    nothing ever parsed it.
  * Four of five `action_items` were recorded `open` while already satisfied
    (reconciled 2026-07-29), which would have sent a fresh session chasing
    solved problems.
  * Epic 5 had NO structured entry at all while five of its stories shipped. Its
    status lived in a prose comment, invisible to every tool (fixed 2026-08-05).
  * Every epic in the file was NAMELESS to a parser: Epics 6-9 carried their titles
    in trailing `#` comments and Epics 1-5 carried none at all, while the reason
    Epics 6-9 had no stories was a prose comment. `epic_catalog` moved all three
    into data (added 2026-08-05).

The common cause is that the file is read by humans and agents but validated by
nothing. These tests are deliberately cheap and structural — they do not judge
whether a status is *true*, only that the ledger is internally coherent and
agrees with `epics.md`, which is what all three failures violated.

Intentionally strict about one thing: adding a story to `epics.md` without
tracking it here FAILS. That is the drift guard, not a nuisance.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
STATUS_PATH = REPO_ROOT / "_bmad-output" / "implementation-artifacts" / "sprint-status.yaml"
FINDINGS_PATH = (
    REPO_ROOT / "_bmad-output" / "implementation-artifacts" / "engineering-findings.yaml"
)
EPICS_PATH = REPO_ROOT / "_bmad-output" / "planning-artifacts" / "epics.md"

# The state machine documented at the top of sprint-status.yaml itself.
EPIC_STATUSES = frozenset({"backlog", "blocked", "in-progress", "done"})
STORY_STATUSES = frozenset({"backlog", "ready-for-dev", "in-progress", "review", "done"})
RETRO_STATUSES = frozenset({"optional", "done"})
DECOMPOSITION_STATES = frozenset({"decomposed", "deferred"})

#: Sections carrying findings that are NOT derivable from epics.md. They lived in
#: sprint-status.yaml until 2026-08-20 because bmad-sprint-planning regenerates
#: that file from a template whose preservation rule covers `action_items` alone,
#: and this list was the only thing standing between a regeneration and their
#: silent loss. They now live in engineering-findings.yaml, which nothing
#: regenerates — but the list is still enforced, so a section can only disappear
#: if it is dropped from here in the same change: a reviewed decision, not an
#: accident. The tracker is checked too, to catch a finding re-added to it.
#: Sections that must survive in the TRACKER. `action_items` is the one thing
#: bmad-sprint-planning's template preserves on its own; `epic_catalog` is not,
#: and carries every epic title plus the deferral reason behind each `blocked`.
TRACKER_CURATED = ("action_items", "epic_catalog")

CURATED_SECTIONS = (
    "post_epic_work",
    "d8_ifrs_track",
    "qsr_gross_profit_reverification",
    "story_5_1_debt_maturity_spike",
    "story_6_1_reverse_dcf_coverage_spike",
    "story_6_2_live_verification",
    "reverse_dcf_capital_intensity_distortion",
    "story_6_5_open_deviations",
    "story_6_6_browser_verification",
    "story_6_7_golden_coverage",
    "market_price_dates_labelled_as_fiscal_year_end",
    "shop_local_history_is_not_edgar_coverage",
    "canonical_facts_amendment_gap",
    "shop_convertible_debt_unmapped",
    # Moved out of the tracker's own sections on 2026-08-20 — see the note above
    # `TRACKER_CURATED`. Protected here for the same reason as the rest.
    "epic_decomposition_rationale",
    "action_item_evidence",
    "ambiguity_flagging_had_no_idempotency_key",
    "story_10_1_browser_verification",
    "story_10_1_codex_review",
    "story_10_2_browser_verification",
    "story_10_2_codex_review",
    "story_10_3_browser_verification",
    "story_12_1_coverage_spike",
    "story_12_2_ingestion",
    "story_12_3_canonicalization",
    "story_12_4_golden_dataset",
    "story_12_5_pipeline_inclusion_and_browser_verification",
    # Added 2026-09-09 by an /optimize-context audit, which found TWENTY of the
    # 47 findings unprotected — everything appended since ~Story 10.4. The guard
    # below only checked listed -> exists, never exists -> listed, so it kept
    # passing while silently covering less and less. That is the conformance rule
    # again (project-context.md, 2026-08-13): the file header promised "a section
    # may only disappear if CURATED_SECTIONS drops it in the same change", which
    # was true only of the sections somebody remembered to add.
    # `test_every_finding_is_curated` now enforces the other direction.
    "story_10_4_browser_verification",
    "story_10_5_browser_verification",
    "story_10_6_browser_verification",
    "story_10_7_full_universe_verification",
    "story_11_8_full_universe_verification",
    "story_11_9_methodology_pages",
    "story_11_9_code_review_and_fixes",
    "story_11_9_code_review_round_2",
    "verdict_grid_caveat_reason_missing",
    "q1_6_capex_vs_da_live_verification",
    "otex_capex_sign_error_fy2007_fy2009",
    "zts_stale_reverse_dcf_cash_gap",
    "q3_3_achieved_vs_implied_growth_live_verification",
    "otex_shares_outstanding_scale_error_fy2007_fy2009",
    "company_facts_api_carries_no_segment_dimensions",
    "segment_data_reachable_but_raos_is_not_a_segment",
    "cpb_segment_members_stable_but_tags_switch",
    "segment_and_brand_intangible_tagging_across_filers",
    "acquisition_epic_scoped_to_us_gaap_filers",
    "dimensioned_facts_would_contaminate_consolidated_canonical_facts",
    "ad3_decimals_tiebreak_has_never_had_data",
    "story_13_3_brand_member_live_verification",
    "story_13_3_first_live_pipeline_run",
    "story_13_3_data_quality_issues_are_write_only",
    "story_13_3_zts_non_brand_intangibles_land_as_brand_value",
    "story_13_3_multi_axis_member_identity_verified",
    "story_13_3_member_exclusions_are_not_axis_scoped",
)

pytestmark = pytest.mark.skipif(
    not STATUS_PATH.exists() or not EPICS_PATH.exists(),
    reason="BMad planning artifacts not present in this checkout",
)


class _StrictLoader(yaml.SafeLoader):
    """SafeLoader that REJECTS duplicate mapping keys instead of silently
    keeping the last one.

    PyYAML's default behaviour is last-wins, with no warning. For
    engineering-findings.yaml that is a content-replacement hole underneath
    `test_every_finding_is_curated`: a second section reusing a curated name
    silently replaces the first one's entire contents, while both directional
    curation guards keep passing because the KEY is still present and still
    listed. Raised by the 2026-09-09 Codex review of PR #133, which correctly
    identified that curating names protects names, not findings.
    """


def _no_duplicate_keys(loader, node, deep=False):  # noqa: ANN001
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping", node.start_mark,
                f"duplicate key {key!r} — a later section would silently replace the "
                "earlier one's contents", key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_StrictLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _no_duplicate_keys
)


def _kebab(title: str) -> str:
    """`epics.md` story title -> sprint-status key suffix.

    Mirrors bmad-sprint-planning's own conversion: drop the trailing em-dash
    aside and any parenthetical (FR ref, OQ ref), then kebab-case the remainder.
    """
    title = title.split("—")[0].split("(")[0]
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def _epic_title(heading: str) -> str:
    """`epics.md` epic heading -> the title `epic_catalog` should carry.

    Strips only the italic `*(headline only — do not decompose yet)*` aside, which
    is a decomposition marker rather than part of the epic's name. Deliberately does
    NOT strip parentheses in general: Epic 1 really is called "Foundation & First
    Evidence (Walking Skeleton)". This is why it cannot reuse `_kebab`'s cruder
    split, which exists for story keys where the aside is always droppable.
    """
    return re.sub(r"\*\([^)]*\)\*", "", heading).strip()


@pytest.fixture(scope="module")
def status() -> dict:
    return yaml.safe_load(STATUS_PATH.read_text())


@pytest.fixture(scope="module")
def findings() -> dict:
    return yaml.safe_load(FINDINGS_PATH.read_text())


def test_sprint_status_is_parseable_yaml_at_all():
    """Deliberately does NOT use the `status` fixture.

    An unparseable file makes that fixture raise, which pytest reports as an ERROR
    on every test in this module — the suite goes red, but the one message that
    names the actual problem never appears, because the test meant to report it
    never runs. Loading the file directly here means a parse failure surfaces as a
    single clean assertion naming the file and the YAML error, with the rest as
    follow-on noise.

    This is the exact failure that went unnoticed for two days.
    """
    try:
        parsed = yaml.safe_load(STATUS_PATH.read_text())
    except yaml.YAMLError as exc:
        pytest.fail(
            f"{STATUS_PATH.name} is not parseable YAML — every agent and tool reading it "
            f"is flying blind:\n{exc}"
        )
    assert isinstance(parsed, dict), f"{STATUS_PATH.name} did not parse to a mapping"


@pytest.fixture(scope="module")
def declared() -> tuple[dict[str, int], set[int]]:
    """({story_key: epic_number}, {epic_numbers}) as declared in epics.md."""
    text = EPICS_PATH.read_text()
    stories = {}
    # The letter suffix is how a story SPLIT records its lineage (13.4 -> 13.4a..13.4e,
    # the 2026-09-18 re-cut; reslint's 29-2a/29-2b is the same convention). Without it
    # here, a lettered story is declared in epics.md, matches neither the missing-story
    # check below nor the orphan check, and is tracked by nothing — meaning parked where
    # nothing reads it, which is this file's oldest failure mode.
    for m in re.finditer(r"^### Story (\d+)\.(\d+[a-z]?):\s*(.+)$", text, re.M):
        epic, story, title = m.group(1), m.group(2), m.group(3).replace("*", "").strip()
        stories[f"{epic}-{story}-{_kebab(title)}"] = int(epic)
    epics = set(stories.values()) | {
        int(m.group(1)) for m in re.finditer(r"^#{2,3} Epic (\d+)", text, re.M)
    }
    return stories, epics


def _story_keys(dev_status: dict) -> set[str]:
    return {k for k in dev_status if STORY_KEY.match(k)}


def test_development_status_section_exists(status):
    assert "development_status" in status, "no development_status section to track anything with"


def test_every_epic_in_epics_md_is_tracked(status, declared):
    _, epics = declared
    missing = sorted(e for e in epics if f"epic-{e}" not in status["development_status"])
    assert not missing, (
        f"epics.md declares Epic(s) {missing} with no entry in sprint-status.yaml. "
        "Epic 5 was invisible to every tool for exactly this reason."
    )


def test_every_epic_has_a_retrospective_entry(status, declared):
    _, epics = declared
    missing = sorted(e for e in epics if f"epic-{e}-retrospective" not in status["development_status"])
    assert not missing, f"no retrospective entry for Epic(s) {missing}"


def test_every_declared_story_is_tracked(status, declared):
    stories, _ = declared
    missing = sorted(set(stories) - _story_keys(status["development_status"]))
    assert not missing, (
        f"epics.md declares {len(missing)} story/stories absent from sprint-status.yaml: "
        f"{missing[:5]}. Add them, or the ledger understates the work."
    )


def test_no_tracked_story_is_absent_from_epics_md(status, declared):
    stories, _ = declared
    orphans = sorted(_story_keys(status["development_status"]) - set(stories))
    assert not orphans, (
        f"sprint-status.yaml tracks {orphans[:5]}, which epics.md does not declare — "
        "either a renamed story title or a stale key."
    )


def test_all_status_values_are_legal(status):
    """A value outside the state machine is silently meaningless to every reader.
    `epic-5-retrospective: backlog` shipped on 2026-08-05 and was exactly this."""
    illegal = []
    for key, value in status["development_status"].items():
        if key.endswith("-retrospective"):
            allowed = RETRO_STATUSES
        elif re.fullmatch(r"epic-\d+", key):
            allowed = EPIC_STATUSES
        else:
            allowed = STORY_STATUSES
        if value not in allowed:
            illegal.append(f"{key}: {value!r} (allowed: {sorted(allowed)})")
    assert not illegal, "illegal status value(s):\n  " + "\n  ".join(illegal)


def test_epic_status_agrees_with_its_stories(status, declared):
    """A `done` epic with open stories, or an `in-progress` epic with none, is the
    drift that made four of five action items wrong."""
    _, epics = declared
    dev = status["development_status"]
    problems = []
    for epic in sorted(epics):
        own = {k: v for k, v in dev.items() if k.startswith(f"{epic}-")}
        if not own:
            # No stories to agree with. Whether that is deliberate is not this test's
            # question — `test_decomposition_state_matches_whether_stories_actually_exist`
            # requires the catalog to declare it, so the case is no longer unexamined.
            continue
        epic_status = dev.get(f"epic-{epic}")
        all_done = all(v == "done" for v in own.values())
        if epic_status == "done" and not all_done:
            open_stories = sorted(k for k, v in own.items() if v != "done")
            problems.append(f"epic-{epic} is 'done' but {open_stories} are not")
        if epic_status == "in-progress" and all_done:
            problems.append(f"epic-{epic} is 'in-progress' but every story is done")
        if epic_status == "backlog" and any(v != "backlog" for v in own.values()):
            problems.append(f"epic-{epic} is 'backlog' but has started stories")
    assert not problems, "epic/story status disagreement:\n  " + "\n  ".join(problems)


def test_blocked_status_agrees_with_the_catalog(status, declared):
    """`blocked` and `decomposition: deferred` are the same fact in two files, so
    something has to hold them together.

    Before `blocked` existed (2026-08-14) the state machine's only word for Epics
    7-9 was `backlog` — which means the opposite — while their real gate sat in
    `epic_catalog`. A reader who checked `development_status`, the obvious field,
    got the wrong answer, and two handovers asserted "Nothing blocks Epic 7".

    Adding the enum value without this test would have reproduced the very bug it
    was added to fix: one more field carrying meaning that nothing keeps true.
    The binding is deliberately BOTH ways — a deferred epic left as `backlog` is
    the original bug, and a `blocked` epic with no recorded deferral is an epic
    nobody can start for a reason nobody wrote down.
    """
    _, epics = declared
    dev = status["development_status"]
    catalog = status["epic_catalog"]
    problems = []
    for epic in sorted(epics):
        key = f"epic-{epic}"
        entry = catalog.get(key, {})
        deferred = entry.get("decomposition") == "deferred"
        blocked = dev.get(key) == "blocked"
        if deferred and not blocked:
            problems.append(
                f"{key}: catalog defers it under {entry.get('deferred_under')!r} but "
                f"development_status says {dev.get(key)!r} — a reader checking the "
                "status field would think it can be picked up"
            )
        if blocked and not deferred:
            problems.append(
                f"{key}: development_status says 'blocked' but the catalog does not "
                "declare `decomposition: deferred`, so no decision is on record for why"
            )
    assert not problems, "blocked/deferred disagreement:\n  " + "\n  ".join(problems)


@pytest.fixture(scope="module")
def epic_titles() -> dict[int, set[str]]:
    """{epic_number: every title epics.md gives it}.

    An epic is headed twice — once in the Phase 2 Epic List (`### Epic N:`) and once
    as its own detailed section (`## Epic N:`) — so a rename applied in only one place
    surfaces here as a set of size 2, which the catalog test then rejects.
    """
    text = EPICS_PATH.read_text()
    titles: dict[int, set[str]] = {}
    for m in re.finditer(r"^#{2,3} Epic (\d+):\s*(.+)$", text, re.M):
        titles.setdefault(int(m.group(1)), set()).add(_epic_title(m.group(2)))
    return titles


def test_epic_catalog_covers_exactly_the_tracked_epics(status, declared):
    """The catalog and `development_status` are two views of one set of epics. An epic
    in one and not the other is how the old trailing-comment titles went stale."""
    _, epics = declared
    catalog = status["epic_catalog"]
    missing = sorted(e for e in epics if f"epic-{e}" not in catalog)
    orphaned = sorted(set(catalog) - {f"epic-{e}" for e in epics})
    assert not missing, f"epic_catalog has no entry for Epic(s) {missing}"
    assert not orphaned, f"epic_catalog describes {orphaned}, which epics.md does not declare"


def test_epic_catalog_titles_match_epics_md(status, epic_titles):
    """The title is duplicated across two files, so something has to hold them
    together — the same reason `test_comment_header_metadata_matches_the_parsed_fields`
    exists for the duplicated header block."""
    problems = []
    for key, entry in status["epic_catalog"].items():
        number = int(key.removeprefix("epic-"))
        declared_titles = epic_titles.get(number, set())
        if entry.get("title") not in declared_titles:
            problems.append(
                f"{key}: catalog says {entry.get('title')!r}, epics.md heading(s) say "
                f"{sorted(declared_titles)}"
            )
    assert not problems, "epic title drift between sprint-status.yaml and epics.md:\n  " + "\n  ".join(
        problems
    )


def test_decomposition_state_matches_whether_stories_actually_exist(status, declared):
    """The point of the whole section: an epic with no stories must SAY it is deferred,
    so a decomposition nobody got round to can no longer masquerade as a deliberate one.

    Before `decomposition` existed, the only record that Epics 6-9 were deliberately
    storyless was a prose comment, and the epic/story agreement test simply skipped any
    epic with no stories — meaning a genuine oversight and a deliberate deferral were
    byte-for-byte identical to every reader, human or otherwise.
    """
    dev = status["development_status"]
    problems = []
    for key, entry in status["epic_catalog"].items():
        state = entry.get("decomposition")
        if state not in DECOMPOSITION_STATES:
            problems.append(f"{key}: decomposition={state!r} (allowed: {sorted(DECOMPOSITION_STATES)})")
            continue
        number = key.removeprefix("epic-")
        has_stories = any(k.startswith(f"{number}-") for k in dev)
        if has_stories and state != "decomposed":
            problems.append(f"{key}: has tracked stories but is marked {state!r}")
        if not has_stories and state != "deferred":
            problems.append(
                f"{key}: marked {state!r} but no story is tracked for it — either the "
                "stories were never mirrored from epics.md, or this should be 'deferred'"
            )
    assert not problems, "decomposition state disagrees with reality:\n  " + "\n  ".join(problems)


def test_deferred_epics_name_a_decision_and_an_exit_condition(status, findings):
    """A deferral with no named decision is indistinguishable from procrastination, and
    one with no exit condition never ends — nothing would ever prompt a re-check.

    The guarantee is unchanged since 2026-08-20; only where it is satisfied moved. The
    tracker keeps the two STRUCTURAL fields (`deferred_under`, `decompose_when`), and
    the discursive `reason` — why this epic specifically, 30-73 words apiece — now
    lives in engineering-findings.yaml. Requiring it there rather than dropping it
    matters: it is the field that distinguishes a considered deferral from an
    unexamined one, and this is now the binding that keeps the two files in step.
    """
    problems = []
    rationale = findings.get("epic_decomposition_rationale", {})
    for key, entry in status["epic_catalog"].items():
        if entry.get("decomposition") != "deferred":
            continue
        for field in ("deferred_under", "decompose_when"):
            if not str(entry.get(field, "")).strip():
                problems.append(f"{key}: deferred but has no {field} in sprint-status.yaml")
        if not str(rationale.get(key, {}).get("reason", "")).strip():
            problems.append(
                f"{key}: deferred but has no `reason` under "
                "engineering-findings.yaml#epic_decomposition_rationale"
            )
    assert not problems, "incomplete deferral(s):\n  " + "\n  ".join(problems)


def test_curated_sections_survive(findings, status):
    """Every finding is still on record, and none has drifted back into the tracker.

    These sections were kept alive inside sprint-status.yaml for months because
    bmad-sprint-planning regenerates that file and preserves only `action_items`;
    this list was the only thing that would have caught their loss. Since
    2026-08-20 they live in engineering-findings.yaml, which nothing regenerates.
    The list is still enforced because the original risk has only moved, not gone:
    a section can be deleted by hand as easily as by a generator, and either way
    the loss is silent and recoverable only from git.
    """
    lost = [f"{s} (engineering-findings.yaml)" for s in CURATED_SECTIONS if s not in findings]
    lost += [f"{s} (sprint-status.yaml)" for s in TRACKER_CURATED if s not in status]
    assert not lost, (
        f"curated section(s) missing: {lost}. If a regeneration or an edit dropped "
        "them, restore from git; if the removal was deliberate, drop them from "
        "CURATED_SECTIONS / TRACKER_CURATED in the same change."
    )
    strayed = [s for s in CURATED_SECTIONS if s in status]
    assert not strayed, (
        f"finding(s) back in sprint-status.yaml: {strayed}. The tracker records what "
        "is DONE and what is LEFT; findings belong in engineering-findings.yaml."
    )


def test_every_finding_is_curated(findings):
    """The other direction of the guard above — and the reason it was needed.

    That test checks listed -> exists. It never checked exists -> listed, so a
    finding appended without being added to CURATED_SECTIONS was simply not
    protected, and nothing said so. On 2026-09-09 an /optimize-context audit found
    TWENTY of 47 findings in that state: everything appended since roughly Story
    10.4, including all five of the 2026-09-08 acquisition-epic gate findings and
    all three defects found live on 2026-09-02.

    The guard had been degrading for weeks while passing every run, which is this
    project's most-repeated bug class in its purest form: the file header promised
    "a section may only disappear if CURATED_SECTIONS drops it in the same change"
    and that was true only of the sections somebody remembered to list. Nothing
    failed when the promise was false. Confirmed to bite before being committed.
    """
    uncurated = sorted(k for k in findings if k not in CURATED_SECTIONS)
    assert not uncurated, (
        f"finding(s) not in CURATED_SECTIONS: {uncurated}. Every top-level section of "
        "engineering-findings.yaml must be listed there, or its loss is silent. Add "
        "the name in the same change that adds the finding."
    )


def test_no_finding_is_silently_replaced_by_a_duplicate_key():
    """Curating a NAME protects the name, not the finding behind it.

    PyYAML's default loader takes the last of two duplicate top-level keys with
    no warning, so a second section reusing a curated name replaces the first
    one's entire contents while BOTH directional curation guards keep passing.
    Raised by the 2026-09-09 Codex review of PR #133, which found this hole
    under the guard added earlier that same day.

    Deliberately loads the file itself rather than using the `findings` fixture:
    by the time PyYAML has resolved duplicates into a dict, the evidence is gone.
    """
    try:
        yaml.load(FINDINGS_PATH.read_text(), Loader=_StrictLoader)
    except yaml.constructor.ConstructorError as exc:
        pytest.fail(f"{FINDINGS_PATH.name} has a duplicate top-level key:\n{exc}")


def test_the_tracker_holds_only_tracking(status):
    """The split of 2026-08-20 is enforced, not merely performed.

    sprint-status.yaml reached 1,279 lines — 14 finding sections against ~115 lines
    of actual status — one story at a time, each addition individually reasonable.
    Nothing resisted it, so nothing stopped it, and the file lost the ability to
    answer the only question it exists to answer. This test is what resists it now:
    a new top-level key here has to be a deliberate change to this allow-list.
    """
    allowed = {
        "generated", "last_updated", "project", "project_key", "tracking_system",
        "story_location", "development_status", "epic_catalog", "action_items",
    }
    extra = sorted(set(status) - allowed)
    assert not extra, (
        f"unexpected top-level key(s) in sprint-status.yaml: {extra}. A finding, "
        "spike or verification belongs in engineering-findings.yaml. If this really "
        "is tracking data, add it to `allowed` here in the same change."
    )


def test_status_at_a_glance_matches_the_data(status):
    """The header summary is the first thing a human reads. Nothing generated it at
    read time, so it can state a number the file below it contradicts.

    It did, within hours of being written: closing the last action item on 2026-08-20
    left the header reading "Open action items: 1" above a section with none. That is
    the project's signature failure — one field carries the meaning, another carries
    the answer a reader actually sees — and writing a summary without binding it would
    have been a fresh instance of the very bug the `blocked` status was added to close.
    """
    text = STATUS_PATH.read_text()
    dev = status["development_status"]
    stories = {k: v for k, v in dev.items() if re.match(r"^\d+-", k)}
    epics = {k: v for k, v in dev.items() if re.fullmatch(r"epic-\d+", k)}
    expected = {
        "stories done": (sum(v == "done" for v in stories.values()), len(stories)),
        "epics complete": (sum(v == "done" for v in epics.values()), len(epics)),
    }
    m = re.search(
        r"STATUS AT A GLANCE \((\d+) of (\d+) stories done, (\d+) of (\d+) epics complete\)",
        text,
    )
    assert m, "the STATUS AT A GLANCE header is missing or its wording changed"
    got = {
        "stories done": (int(m.group(1)), int(m.group(2))),
        "epics complete": (int(m.group(3)), int(m.group(4))),
    }
    assert got == expected, f"header says {got}, development_status says {expected}"

    m2 = re.search(r"Open action items: (\d+)\.", text)
    assert m2, "the header no longer states an open action-item count"
    open_items = sum(a["status"] != "done" for a in status["action_items"])
    assert int(m2.group(1)) == open_items, (
        f"header says {m2.group(1)} open action item(s), action_items has {open_items}"
    )


def test_comment_header_metadata_matches_the_parsed_fields(status):
    """The file carries its metadata TWICE — once as `#` comments for humans, once
    as real YAML keys. Nothing keeps the two in step, so they drift silently."""
    text = STATUS_PATH.read_text()
    for field in ("generated", "last_updated", "project"):
        commented = re.search(rf"^#\s*{field}:\s*(\S+)", text, re.M)
        if commented is None:
            continue
        assert commented.group(1) == str(status[field]), (
            f"header comment says {field}={commented.group(1)} but the YAML field "
            f"says {status[field]} — the two copies have drifted"
        )


# --- the story file is the exit condition (2026-09-18) -----------------------

# Stories from this one onward must carry a story file before leaving `backlog`.
# A cutoff rather than a blanket rule: everything before it was implemented straight
# from epics.md prose, and back-filling 60 files would be fiction, not enforcement.
STORY_FILE_REQUIRED_FROM = (13, 4)

# The ONE definition of a story key, so the recognizers cannot drift apart. A single
# lowercase suffix letter is a split story (13.4a); anything else — uppercase, two
# letters, a stray dot — is a typo, and a typo that merely fails to MATCH is a story
# tracked by nothing, which is this file's oldest failure mode.
STORY_KEY = re.compile(r"^\d+-\d+[a-z]?-[a-z0-9-]+$")


def test_every_story_shaped_key_is_well_formed(status) -> None:
    """A key that looks like a story but does not parse is rejected, not skipped."""
    malformed = [
        key
        for key in status["development_status"]
        if re.match(r"^\d+[-.]", key) and not STORY_KEY.match(key)
    ]
    assert not malformed, (
        f"malformed story keys (expected `<epic>-<story><letter?>-<kebab-title>`): {malformed}"
    )


def test_an_active_story_has_a_story_file(status, declared) -> None:
    """CLAUDE.md's story workflow rule 1, enforced rather than stated.

    The story file's task checklist is what tells a session the story is FINISHED;
    without one, a story ends when verification stops finding things, which against
    live SEC data is never. Story 13.3 ran 19 commits over 8 days and was "complete"
    seven days before it merged, while reslint — same methodology, same author, a
    story file for every story — averages 1.15 commits per story.

    Keyed off `story_location` and the story key, which is how the two existing
    files are already named.
    """
    stories, _ = declared
    location = REPO_ROOT / status["story_location"]
    missing = []
    for key, value in status["development_status"].items():
        if not STORY_KEY.match(key) or value == "backlog":
            continue
        epic_part, number_part = key.split("-")[:2]
        # "4a" sorts immediately after "4": a split story inherits its parent's position.
        epic, number = int(epic_part), int(number_part.rstrip("abcdefghijklmnopqrstuvwxyz"))
        if (epic, number) < STORY_FILE_REQUIRED_FROM:
            continue
        if not (location / f"{key}.md").is_file():
            missing.append(f"{key} (status: {value})")
    assert not missing, (
        "these stories left `backlog` with no story file in "
        f"{status['story_location']}: {missing}. Run bmad-create-story first — the "
        "numbered ACs and task checklist are the story's exit condition (CLAUDE.md, "
        "Story workflow rule 1)."
    )


def test_the_per_epic_glance_lines_match_the_data(status) -> None:
    """The header's PER-EPIC counts, not just its totals.

    `test_status_at_a_glance_matches_the_data` guards the two totals on the header
    line; the per-epic table under it was guarded by nothing, and the 2026-09-18
    re-cut left `Epic 13 ... 2/8` sitting above a development_status holding 17
    stories. Every other epic's line was accurate — the counts are maintained, just
    not enforced, which is this file's recurring shape: meaning parked where nothing
    reads it.
    """
    text = STATUS_PATH.read_text()
    totals: dict[int, int] = {}
    done: dict[int, int] = {}
    for key, value in status["development_status"].items():
        m = re.match(r"^(\d+)-(\d+[a-z]?)-", key)
        if not m:
            continue
        epic = int(m.group(1))
        totals[epic] = totals.get(epic, 0) + 1
        done[epic] = done.get(epic, 0) + (value == "done")

    # EVERY row, including the `no stories` ones. Matching only `x/y` rows left Epics
    # 7-9 unchecked, so a stale or missing row there passed in silence — the same
    # "unparsed means unguarded" shape as the totals this test was added for.
    lines = list(re.finditer(r"^#   Epic (\d+)\s+\S+\s+(\d+/\d+|no stories)", text, re.M))
    assert lines, "the per-epic glance table is missing or its shape changed"
    listed = {int(m.group(1)) for m in lines}
    tracked = {
        int(key.split("-")[1])
        for key in status["development_status"]
        if re.fullmatch(r"epic-\d+", key)
    }
    assert listed == tracked, (
        f"glance table lists epics {sorted(listed)}; development_status tracks "
        f"{sorted(tracked)} — a missing row is an epic nobody reports on"
    )
    wrong = []
    for m in lines:
        epic = int(m.group(1))
        actual = (done.get(epic, 0), totals.get(epic, 0))
        claim = m.group(2)
        if claim == "no stories":
            if totals.get(epic, 0):
                wrong.append(f"Epic {epic}: header says 'no stories', data has {actual[1]}")
            continue
        if tuple(int(x) for x in claim.split("/")) != actual:
            wrong.append(f"Epic {epic}: header {claim}, data {actual[0]}/{actual[1]}")
    assert not wrong, f"glance table disagrees with development_status: {wrong}"
