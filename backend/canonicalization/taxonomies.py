"""Supported annual filing forms and financial-reporting taxonomies.

Single place naming which EDGAR reporting regimes the pipeline understands, so
adding one is a data change here rather than an edit to four scattered literals
across ingestion, canonicalization and the pipeline orchestrator.

Two regimes are supported:

- **10-K / `us-gaap`** — US domestic filers, and foreign filers that elect to
  report US-style (all four Phase-1 companies: CP, QSR, OTEX, SHOP).
- **40-F / `ifrs-full`** — Canadian MJDS filers reporting under IFRS. Added
  2026-07-29 after live verification against `data.sec.gov` that these filings
  carry richly-tagged financial facts (Suncor 234 concepts, Cameco 250, BCE 288,
  all 2017-2025) and that the four models resolve from them. This reverses the
  *blanket* IFRS exclusion in foundational decision D6, whose stated reason —
  that IFRS filers "would break the formulas" — held for some concepts but not
  in general: Cameco resolves all four models from directly-filed tags.

  What D6 got right is that coverage varies **per filer, not per taxonomy**, and
  for reasons intrinsic to IFRS presentation rather than tagging quality:
  IAS 1 permits expenses by **nature** instead of by **function**, so a
  by-nature filer has no SG&A line to tag at all (Suncor), which leaves
  Beneish's SGAI unresolvable. That is the same shape as CP's missing COGS under
  us-gaap, and is handled the same way — `insufficient_data`, never a guess.

Adding a regime means appending here, then supplying its `MappingRule`s. It does
NOT require touching scoring, the formula engine, the read API, or the frontend:
those consume canonical concepts and are already taxonomy-blind.
"""

from __future__ import annotations

# Annual report forms whose facts the pipeline ingests. `fp == "FY"` is checked
# separately; this is the form-type gate only.
ANNUAL_FORM_TYPES: frozenset[str] = frozenset(
    {
        "10-K",
        "10-K/A",
        "40-F",
        "40-F/A",
    }
)

# Original (unamended) annual forms. Fiscal-year-end determination uses only
# these: an amendment's own fiscal_year_end can be dated to the amendment rather
# than the period it restates (confirmed live 2026-07-23 on CP's 10-K/A rows).
ORIGINAL_ANNUAL_FORM_TYPES: frozenset[str] = frozenset({"10-K", "40-F"})

# amendment form -> the original form it supersedes for selection purposes.
AMENDMENT_TO_ORIGINAL: dict[str, str] = {
    "10-K/A": "10-K",
    "40-F/A": "40-F",
}

# Taxonomies carrying genuine financial-statement facts.
#
# Deliberately EXCLUDES `dei`, `srt` and `ffd`. `dei` is the load-bearing
# exclusion: cover-page facts are dated to the FILING date, not the fiscal-year
# end, and including them in the (fy, end) candidate pool silently misfiled
# whole fiscal years (SHOP FY2024 read as 2023-12-31; CP FY2025 as 2026-02-25).
# See ingestion.company_facts.parse_company_facts for the full incident.
FINANCIAL_TAXONOMIES: frozenset[str] = frozenset(
    {
        "us-gaap",
        "ifrs-full",
    }
)


def is_amendment(form_type: str) -> bool:
    """True for an amended annual form (e.g. 10-K/A, 40-F/A)."""
    return form_type in AMENDMENT_TO_ORIGINAL


def supersedes(candidate_form: str, existing_form: str) -> bool:
    """True when `candidate_form` should replace `existing_form` for the same
    fiscal year — i.e. an original filing displacing a previously-seen amendment.

    Mirrors AD-3's as-originally-filed-over-restated principle. Only compares
    within a regime: a 40-F never displaces a 10-K, since a filer reports under
    one regime at a time and a cross-regime collision would mean something else
    is wrong.
    """
    return is_amendment(existing_form) and AMENDMENT_TO_ORIGINAL[existing_form] == candidate_form
