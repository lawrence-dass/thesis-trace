"""What a stored observation date is allowed to be.

An observation date records WHEN a quote or rate was actually observed. Until
2026-08-11 ingestion stored both under the filer's FISCAL-YEAR-END instead, so any
filer whose year ended on a weekend carried a quote dated to a day the market was
shut — confirmed reachable for BCE, Cameco, CP, OTEX, QSR and Suncor.

The label was wrong, not the price: `select_fye_close` had already picked the last
real trading day's close, so the figure was right and its date was not. That makes
this a provenance defect rather than a numeric one — and provenance is exactly what
the reverse-DCF card publishes ("observed on {date}"), so a Sunday on that line is a
citation that cannot be true.

WEEKENDS ONLY, DELIBERATELY. A full exchange calendar would also catch statutory
holidays, but it needs a dependency and a maintained holiday list per venue. This
guard exists to make one specific defect impossible — dating an observation to a
fiscal-year-end — and every fiscal-year-end in the universe is 31 December or
30 June, neither of which is ever a weekday market holiday. A weekday holiday would
still slip through; that is a known and accepted limit, recorded here rather than
left for someone to discover.
"""

from __future__ import annotations

from datetime import date

#: Saturday and Sunday, in `date.weekday()` terms.
_WEEKEND = (5, 6)


class NonTradingObservationDate(ValueError):
    """Raised when something tries to store an observation dated to a closed market."""


def is_weekend(value: date) -> bool:
    return value.weekday() in _WEEKEND


def assert_tradeable_observation_date(value: date, *, what: str) -> None:
    """Refuse an observation date that lands on a weekend.

    Raises rather than warning or silently correcting. A silent correction would
    guess the real date, and a warning would be a rule nothing enforces — the
    failure mode this repository keeps rediscovering. If a provider ever genuinely
    returns a weekend-dated observation, that is a data defect worth stopping on.
    """
    if is_weekend(value):
        raise NonTradingObservationDate(
            f"{what} would be stored with observation date {value} "
            f"({value.strftime('%A')}), when the market was shut. An observation date "
            "is when the quote was actually observed — it is not the fiscal-year-end. "
            "Pass the provider's own date for the row."
        )


def previous_trading_day(value: date) -> date:
    """The nearest weekday on or before `value`.

    Used ONLY to describe which day a mislabelled row should have carried, never to
    write one: the backfill verifies the date against the provider rather than
    trusting this. Holidays are not modelled — see the module docstring.
    """
    result = value
    while is_weekend(result):
        result = date.fromordinal(result.toordinal() - 1)
    return result
