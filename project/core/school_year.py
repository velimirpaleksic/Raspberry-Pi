from __future__ import annotations

import datetime as dt


def school_year_for_date(value: dt.date | dt.datetime | None = None) -> str:
    """Return the school year, rolling over on 1 September."""

    current = value or dt.date.today()
    if isinstance(current, dt.datetime):
        current = current.date()
    start_year = current.year if current.month >= 9 else current.year - 1
    return f"{start_year:04d}/{start_year + 1:04d}"


def current_school_year() -> str:
    return school_year_for_date()
