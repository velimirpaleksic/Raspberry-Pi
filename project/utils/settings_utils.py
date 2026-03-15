from __future__ import annotations

import datetime
import hashlib
import re

_DJELOVODNI_RE = re.compile(r"^(?P<prefix>\d+)-(?P<counter>\d+)/(?:20)?(?P<year>\d{2,4})$")


def hash_pin(pin: str) -> str:
    return hashlib.sha256(pin.encode("utf-8")).hexdigest()


def parse_seed_djelovodni_broj(raw: str) -> tuple[str, int, int]:
    """Parse legacy env djelovodni broj into structured settings.

    Example: ``01-743/25`` -> ("01", 743, 2025)
    """
    m = _DJELOVODNI_RE.match((raw or "").strip())
    if not m:
        return "01", 743, datetime.datetime.now().year

    prefix = m.group("prefix")
    counter = int(m.group("counter"))
    year_raw = int(m.group("year"))
    year = year_raw if year_raw >= 1000 else 2000 + year_raw
    return prefix, counter, year
