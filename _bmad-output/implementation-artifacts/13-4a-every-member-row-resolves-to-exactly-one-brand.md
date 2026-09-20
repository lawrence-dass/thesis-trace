# Story 13.4a: Every member row resolves to exactly one brand

Status: ready-for-dev

## Story

As Lawrence (developer),
I want one brand identity per stored member row, whatever axis carries it,
so that a consumer never labels four different brands with the same name, and never treats a
member key as a brand for a filer where it is not one.

## Scope boundary (read first)

**This story adds NO figure.** It adds a read-time resolution from a stored
`canonical_member_facts` row to a brand identity, and the spec declarations that resolution needs.
Nothing it writes changes any stored value. Every later story in Epic 13 that names a brand reads
through it.

**Explicitly out of scope** (each has a home):
- Computing or materializing per-brand carrying value → 13.4c.
- Axis-scoping `excluded_members` → 13.4b (`story_13_3_member_exclusions_are_not_axis_scoped`).
- Normalizing the segment axis into `context_key` the way the mapped axis is normalized → **see
  Dev Notes "Deferred: the segment-rename exposure"**. It is a write-path change with a migration
  and a backfill; putting it here would make this story a second 13.3.
- Rendering anything → 13.7b / 13.8a.

## Acceptance Criteria

1. **One resolution, every filer.** A single function resolves `(issuer_cik, member_key,
   context_key)` from a `canonical_member_facts` row to a brand identity carrying a stable
   `brand_key`, a `label`, and a `kind`. Every current-version row for CPB, ZTS and QSR passes
   through it and gets exactly one answer.

2. **The brand is read from whichever axis carries it.** For CPB and ZTS the brand is in
   `member_key`; for QSR all 30 rows share `member_key: "trade_names"` and the brand is the
   `us-gaap:StatementBusinessSegmentsAxis` member inside `context_key`
   (`story_13_3_multi_axis_member_identity_verified`). The resolution returns four distinct brands
   for QSR — Burger King, Tim Hortons, Popeyes, Firehouse Subs — not four rows called "Trade
   names".

3. **The label comes from the spec's own words, never from a tag name.** No `split(":")`, no
   strip-`Member`, no camel-case-to-words at read time. A brand the spec has not declared is
   unresolved (AC 5), never a label derived from its tag.

4. **A member key is not a brand name.** The resolution carries an explicit `kind` per declared
   member, and a consumer can tell a named brand from a non-brand row without pattern-matching a
   label:
   - `named_brand` — CPB's `kettle`, `raos`, `pace`, … and each QSR segment brand;
   - `aggregate` — CPB's `all_trademarks`, **and ZTS's `brands`**, which its own spec note already
     calls "one aggregate Brands member rather than naming individual acquired brands" while the
     mapping files it as a named brand (the conformance rule: the note is true and nothing
     executes it);
   - `residual` — CPB's `other_trade_names`;
   - `disclosure` — CPB's `within_ten_percent_coverage`.

5. **Unresolvable is `insufficient_data`, never a guess (AD-16).** A row whose brand cannot be
   resolved — an undeclared QSR segment member, or a filer with no declarations — returns an
   explicit unresolved status that no layer coerces into a label, a `member_key`, or a blank
   string. The caller cannot accidentally get a truthy label.

6. **Identity is keyed per filer.** Resolution and labels key on `(issuer_cik, brand_key)`.
   `MEMBER_LABELS` in `engine.py` is currently keyed on `member_key` alone; two filers using one
   generic member (`us-gaap:TradeNamesMember` is already used by QSR, and the spec's own comment
   warns it "can be used by two filers for different assets") would collide silently. Fixed here,
   with a test that fails on the collision.

7. **An extra qualifier axis does not create a second brand.** CPB's `allied_brands` and
   `pop_secret` carrying-value rows also carry
   `us-gaap:FairValueByMeasurementFrequencyAxis: us-gaap:FairValueMeasurementsNonrecurringMember`.
   Both resolve to the same brand as their unqualified siblings; the qualifier is preserved in the
   row and ignored by identity.

8. **Declarations are live-grounded and reasoned.** Each new segment-brand declaration names the
   member as filed, the axis it was observed on, and the filing years it covers, checked against
   the rows already in the dev store (`concepts_v17`) — not against a tag that "looks right". Every
   declaration carries a `note` stating the argument, per the BCE-debt precedent.

9. **The spec version is bumped, not amended.** The dev database already holds `concepts_v17`
   rows, and a spec is frozen the moment any database stamps its version, merged or not
   (`story_13_3_multi_axis_member_identity_verified`). The declarations land in a new
   `us-gaap_v17.yaml` behind `concepts_v18`, with the registry HISTORY entry stating that this
   version changes no figure. Confirmed by Lawrence 2026-09-20 — see Dev Notes "Decision".

10. **Tests fail before the fix.** Each of AC 2, 4, 5, 6 and 7 has a test that was confirmed red
    against the pre-change code. The QSR test asserts four distinct brands from rows that
    currently share one `member_key`.

## Tasks / Subtasks

- [x] **1. Confirm the versioning decision** (AC: 9) — **done 2026-09-20: bump.** `us-gaap_v17` +
      `concepts_v18`. See Dev Notes "Decision".
- [ ] **2. Declare the identities in the spec** (AC: 3, 4, 6, 8, 9)
  - [ ] Copy `us-gaap_v16.yaml` → `us-gaap_v17.yaml`; never edit v16.
  - [ ] Add QSR's four segment brands under a new per-filer block keyed on
        `us-gaap:StatementBusinessSegmentsAxis`, each with stable key, label, aliases (as filed),
        `kind: named_brand`, and a `note` naming the years observed.
  - [ ] Add `kind` to every existing `brand_members` entry. ZTS's `brands` is `aggregate`;
        `all_trademarks` is `aggregate`; `other_trade_names` is `residual`;
        `within_ten_percent_coverage` is `disclosure`; everything else is `named_brand`.
  - [ ] Bump `registry.yaml` to the next `mapping_version` with a HISTORY entry stating that no
        stored figure changes.
- [ ] **3. Load and validate the declarations** (AC: 3, 6, 8)
  - [ ] Extend the loader in `mappings/engine.py`: a `SegmentBrandMember` (or equivalent) dataclass
        and its `_load_*`, following `_load_brand_members`.
  - [ ] Reject at load: a declaration with no aliases, no label, or an unknown `kind`; an alias
        claimed by two brands within one filer.
  - [ ] Re-key `MEMBER_LABELS` on `(issuer_cik, member_key)` and update its callers.
- [ ] **4. Write the resolver** (AC: 1, 2, 5, 7)
  - [ ] New module `backend/canonicalization/mappings/brand_identity.py`, exported from
        `canonicalization/mappings/__init__.py`.
  - [ ] Resolution order: the filer's declared segment axis inside `context_key` first (QSR), then
        `member_key` (CPB, ZTS). Unknown on both → unresolved.
  - [ ] Return type makes the unresolved case impossible to read as a label (AC 5).
  - [ ] Ignore every axis that is not the mapped axis or a declared brand-bearing axis (AC 7).
- [ ] **5. Tests** (AC: 10) — new `backend/tests/test_brand_identity.py`
  - [ ] QSR's rows resolve to four distinct brands (AC 2).
  - [ ] ZTS's `brands` resolves `kind: aggregate`, not `named_brand` (AC 4).
  - [ ] CPB's residual, total and 10%-disclosure members resolve to their own kinds (AC 4).
  - [ ] An undeclared segment member resolves unresolved, and no code path yields `"trade_names"`
        as a label (AC 5).
  - [ ] Two filers declaring the same member key keep distinct labels (AC 6).
  - [ ] The two fair-value-qualified CPB rows resolve to the same brand as their siblings (AC 7).
  - [ ] A DB test over the seeded store: every current-version row resolves, or is an
        explicitly-declared non-brand kind — no silent gap.
  - [ ] Record, in the commit message or the story's Completion Notes, that each test was seen red
        first.
- [ ] **6. Re-run canonicalization under the new version** (AC: 9)
  - [ ] `make py F=...` against the dev DB; confirm the new-version row count and per-brand shape
        match `concepts_v17` exactly (22 groups / 96 rows — see Dev Notes), i.e. the bump moved no
        figure.
- [ ] **7. Close out**
  - [ ] `make test` green, `make lint` clean.
  - [ ] Record the identity verification in `engineering-findings.yaml`.
  - [ ] Commit, push, open the PR, and hand over a Codex review prompt (do not merge).

## Dev Notes

### Current state — what exists, what does not

| Thing | State |
|---|---|
| `canonical_member_facts` table + model | **Exists** (Story 13.3), `backend/app/models.py:210`. Key is `(issuer_cik, canonical_concept, member_key, fiscal_year, mapping_version, context_key)` partial-unique on `NOT superseded`. |
| `member_key` / `member_as_filed` / `axis_as_filed` / `dimensions` / `context_key` | **Exist.** `dimensions` is verbatim; `context_key` is the same context with only the *mapped* axis normalized to `member_key` (`canonicalize.py:155 _dimension_identity`). |
| `brand_members` with `label`, `aliases`, `maps_to`, `note` | **Exists**, `us-gaap_v16.yaml:813`, per CIK. |
| `MEMBER_LABELS` | **Exists**, `engine.py:667` — keyed on `member_key` alone. **AC 6 changes this.** |
| QSR's segment brands (`qsr:BurgerKingMember` et al.) | **Not declared anywhere.** Verified: no hit for `BurgerKing`, `TimHortons`, `Popeyes`, `FirehouseSubs` or `StatementBusinessSegmentsAxis` in `us-gaap_v16.yaml`. This is the story's central gap. |
| A `kind` per member | **Does not exist.** Inferred today by a label word-blacklist in `test_every_brand_member_is_a_brand_or_an_explicit_aggregate` (`test_brand_member_mapping.py:327`), which ZTS's label "Brands" passes while being an aggregate. |
| Any consumer of `CanonicalMemberFact` | **None outside canonicalization and its tests.** This story creates the first read path; there is no existing reader to keep compatible. |

### The live data this must resolve (dev store, `concepts_v17`, 96 current rows)

```
CPB  0000016732  member_key carries the brand
  brand_intangible_carrying_value           allied_brands(1, +FairValue axis) cape_cod(4)
                                            kettle(5) lance(5) pace(6) pacific_foods(6)
                                            pop_secret(1, +FairValue axis) raos(3)
                                            snyders_of_hanover(6)
  brand_intangible_carrying_value_residual  other_trade_names(5)      <- residual
  brand_intangible_carrying_value_total     all_trademarks(6)         <- aggregate
  brand_intangible_impairment               allied_brands(2) late_july(1) pop_secret(1)
                                            snyders_of_hanover(1)
  brand_intangible_acquired                 raos(1)
  trade_names_within_ten_percent_of_...     within_ten_percent_coverage(4)  <- disclosure
ZTS  0001555280  brands(8)                                            <- aggregate, not a brand
QSR  0001618756  member_key is "trade_names" for ALL 30 rows; brand is in context_key
                 qsr:BurgerKingMember(8) qsr:TimHortonsMember(8)
                 qsr:PopeyesLouisianaKitchenMember(8) qsr:FirehouseSubsMember(6)
```

Values behind QSR's rows, from the live verification — useful to pin a test row unambiguously,
**not** to compute anything: FY2019 Tim Hortons 6,534M / Burger King 2,117M / Popeyes 1,355M;
FY2024 Tim Hortons 5,972M / Burger King 2,068M / Popeyes 1,355M / Firehouse Subs 816M (acquired
December 2021, hence 6 rows not 8). No undimensioned-by-segment total row exists beside them, so
there is no double count.

Re-query with:
`make psql Q="select issuer_cik, canonical_concept, member_key, context_key from canonical_member_facts where not superseded and mapping_version='concepts_v17'"`

### Decision — versioning (Lawrence, 2026-09-20)

**Bump: `us-gaap_v17` + `concepts_v18`.** The declarations go in the versioned taxonomy spec
beside `brand_members`, and the registry HISTORY entry states explicitly that no stored figure
changes.

The rejected alternative was a separately versioned `brand_identity_v1.yaml` outside
`mapping_version`, argued on the grounds that identity is read-time and produces no stored fact, so
folding it into `mapping_version` restamps rows whose values did not change. Rejected because it
adds a second versioning axis for one file, splits labels across two homes (`label` already lives
in the versioned spec), and rests on the same "it changes nothing, so amending is safe" reasoning
that in 13.3 left six unreproducible `concepts_v14` rows in the dev store. Bumping is cheap; the
precedent is not.

Concretely: copy `us-gaap_v16.yaml` → `us-gaap_v17.yaml` and add `segment_brand_members` (QSR's
four, keyed on `us-gaap:StatementBusinessSegmentsAxis`) plus `kind` on every `brand_members` entry;
point `registry.yaml` at it under `mapping_version: concepts_v18`. Task 6's check — same 22 groups
/ 96 rows, same values, new stamp — is what proves the bump moved nothing.

### Deferred: the segment-rename exposure

`BrandMember.aliases` exists because CPB renamed Kettle's member three times in four filings, and
`_dimension_identity` normalizes the *mapped* axis so a rename does not split one brand's series.
The segment axis gets no such normalization: if QSR renames `qsr:BurgerKingMember`, `context_key`
changes and the new row will not supersede the old one — two current rows for one brand-year.
Declaring segment aliases (Task 2) makes both spellings resolve to one brand at **read** time,
which is all this story claims. Closing it on the **write** path needs a `context_key` migration
and a backfill, which is a figure-moving change and belongs with 13.4c or its own story. Record it
in `engineering-findings.yaml` as open when closing this story; do not fix it here.

### Constraints that must survive from the parent story (13.4)

The Epic 13 re-cut dropped constraints that the old 13.4/13.6/13.8 stated once — three of five
review findings on `#142` were exactly that. These apply here:

- **AD-1/NFR-8 — every computation on the write path.** This story computes nothing, so it does not
  bind yet; do not smuggle a computed figure into the resolver to "save a step" in 13.4c.
- **AD-16 — tri-state, never a defaulted value.** AC 5 is this rule. A missing brand is
  `insufficient_data` propagated verbatim; no layer coerces it.
- **AD-19 — provenance reaches the member.** `member_as_filed` and `dimensions` stay verbatim; the
  resolver must not overwrite, normalize away, or drop them. 13.7a carries this forward.
- **The conformance rule.** A `kind`, a `note` or a validation that nothing executes is decoration.
  Every declaration this story adds must be *read* by the resolver or *rejected* by the loader —
  an inert declaration reads exactly like an enforced one.

### Testing

- `make test` (refuses to run unless `TEST_DATABASE_URL` is set and distinct from `DATABASE_URL` —
  the guard lives in `backend/tests/conftest.py` beside the `drop_all`). Single file:
  `make test-one T=tests/test_brand_identity.py`.
- Docker: `make db-up` (the container had exited; it is running again as of 2026-09-20).
- Follow `test_brand_member_mapping.py`'s convention: **pin every expectation to a value read out
  of a real filing**, never to the shape of the spec file. A test that reads the spec and asserts
  the spec is a tautology.
- A unit test over a lookup structurally cannot catch a wiring fault — 13.3 shipped a mapping that
  resolved perfectly in unit tests and wrote zero rows because AD-3 rule 0 sat after the lookup.
  The DB test in Task 5 (every current row resolves or is a declared non-brand) is the one that
  proves the resolver is reachable.
- **Golden fixtures are 13.6a/13.6b's job.** Do not add golden entries here; the harness cannot
  express a dimensioned fact yet, and an entry a fixture cannot reproduce pins an outcome while
  asserting nothing.

### Definition of Done

This story touches concept mapping, so the live-data DoD in `CLAUDE.md` applies — with one honest
narrowing: it renders nothing and computes nothing, so **DoD item 5 (render it in a browser) has no
subject** and is carried by 13.8a. Items 1-4 and 6-8 apply as written. Re-fetching live EDGAR is
**not** expected: the identities are verifiable against the dev store's existing `concepts_v17`
rows, which were themselves live-verified on 2026-09-17. If a live fetch does become necessary,
name every ticker and CIK in one request first (CPB 0000016732, ZTS 0001555280, QSR 0001618756).

### Project Structure Notes

- New: `backend/canonicalization/mappings/brand_identity.py`,
  `backend/canonicalization/mappings/specs/us-gaap_v17.yaml`,
  `backend/tests/test_brand_identity.py`.
- Modified: `backend/canonicalization/mappings/engine.py` (loader + `MEMBER_LABELS` key),
  `backend/canonicalization/mappings/__init__.py` (export),
  `backend/canonicalization/mappings/specs/registry.yaml` (version bump).
- **No migration.** No table, column or stored value changes. If the work starts generating one,
  stop — that is the segment-rename scope creeping in.
- Branch: `claude/13-4a-brand-identity-2026-09-20` (already created). PR, never a direct push to
  `main`. Hand over a Codex review prompt when the PR is up; do not merge.

### References

- `_bmad-output/planning-artifacts/epics.md:1468` — Story 13.4a acceptance criteria
- `_bmad-output/planning-artifacts/epics.md:1297` — Epic 13 objective; QSR is the lead test case
- `_bmad-output/implementation-artifacts/engineering-findings.yaml:5493` —
  `story_13_3_multi_axis_member_identity_verified` (the multi-axis finding this story exists for)
- `_bmad-output/implementation-artifacts/engineering-findings.yaml:5570` —
  `story_13_3_member_exclusions_are_not_axis_scoped` (13.4b's, not this story's)
- `_bmad-output/implementation-artifacts/engineering-findings.yaml:5388` —
  `story_13_3_zts_non_brand_intangibles_land_as_brand_value` (why `kind` is data, not a note)
- `backend/app/models.py:210` — `CanonicalMemberFact`, both member columns and the unique key
- `backend/canonicalization/canonicalize.py:155` — `_dimension_identity`, the mapped-axis
  normalization the segment axis does not get
- `backend/canonicalization/mappings/engine.py:127` — `BrandMember`; `:360` `_load_brand_members`;
  `:396` `_check_exclusions`; `:667` `MEMBER_LABELS`
- `backend/canonicalization/mappings/specs/us-gaap_v16.yaml:669` — `brand_intangible_*` concepts;
  `:813` `brand_members`; `:940` `excluded_members`
- `backend/canonicalization/mappings/specs/registry.yaml` — AD-2 version rules and HISTORY
- `ARCHITECTURE-SPINE.md` AD-16 (tri-state), AD-19 (provenance), AD-1 (write-path computation) —
  `_bmad-output/planning-artifacts/architecture/architecture-ThesisTrace-2026-07-19/`
- `CLAUDE.md` — Story workflow (one outcome; ship the fix, defer the finding), live-data Definition
  of Done, Running things (`make`), Git workflow
- `.claude/context/project-context.md` — 2026-09-17 and 2026-09-20 learnings

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
