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
)

pytestmark = pytest.mark.skipif(
    not STATUS_PATH.exists() or not EPICS_PATH.exists(),
    reason="BMad planning artifacts not present in this checkout",
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
    for m in re.finditer(r"^### Story (\d+)\.(\d+):\s*(.+)$", text, re.M):
        epic, story, title = m.group(1), m.group(2), m.group(3).replace("*", "").strip()
        stories[f"{epic}-{story}-{_kebab(title)}"] = int(epic)
    epics = set(stories.values()) | {
        int(m.group(1)) for m in re.finditer(r"^#{2,3} Epic (\d+)", text, re.M)
    }
    return stories, epics


def _story_keys(dev_status: dict) -> set[str]:
    return {k for k in dev_status if re.match(r"^\d+-\d+-", k)}


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
