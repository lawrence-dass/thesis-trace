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
EPICS_PATH = REPO_ROOT / "_bmad-output" / "planning-artifacts" / "epics.md"

# The state machine documented at the top of sprint-status.yaml itself.
EPIC_STATUSES = frozenset({"backlog", "in-progress", "done"})
STORY_STATUSES = frozenset({"backlog", "ready-for-dev", "in-progress", "review", "done"})
RETRO_STATUSES = frozenset({"optional", "done"})
DECOMPOSITION_STATES = frozenset({"decomposed", "deferred"})

#: Sections carrying findings that are NOT derivable from epics.md. Named
#: explicitly because bmad-sprint-planning regenerates this file from a template
#: whose preservation rule covers `action_items` alone — running it verbatim
#: would silently drop every other entry here. If a section is deliberately
#: retired, delete it from this list in the same change, so the removal is a
#: reviewed decision rather than an accident.
CURATED_SECTIONS = (
    "action_items",
    "epic_catalog",
    "post_epic_work",
    "d8_ifrs_track",
    "qsr_gross_profit_reverification",
    "story_5_1_debt_maturity_spike",
    "story_6_1_reverse_dcf_coverage_spike",
    "story_6_2_live_verification",
    "shop_local_history_is_not_edgar_coverage",
    "canonical_facts_amendment_gap",
    "shop_convertible_debt_unmapped",
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


def test_deferred_epics_name_a_decision_and_an_exit_condition(status):
    """A deferral with no named decision is indistinguishable from procrastination, and
    one with no exit condition never ends — nothing would ever prompt a re-check."""
    problems = []
    for key, entry in status["epic_catalog"].items():
        if entry.get("decomposition") != "deferred":
            continue
        for field in ("deferred_under", "reason", "decompose_when"):
            if not str(entry.get(field, "")).strip():
                problems.append(f"{key}: deferred but has no {field}")
    assert not problems, "incomplete deferral(s):\n  " + "\n  ".join(problems)


def test_curated_sections_survive(status):
    """bmad-sprint-planning regenerates this file from a template that preserves
    only `action_items`. Everything else here is a finding not derivable from
    epics.md — the debt-maturity spike and its correction, the amendment gap, the
    D8 track. Losing them to a regeneration would be silent and unrecoverable
    except from git."""
    lost = [s for s in CURATED_SECTIONS if s not in status]
    assert not lost, (
        f"curated section(s) missing: {lost}. If a regeneration dropped them, restore "
        "from git; if the removal was deliberate, drop them from CURATED_SECTIONS too."
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
