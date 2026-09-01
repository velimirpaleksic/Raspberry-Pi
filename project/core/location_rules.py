from __future__ import annotations

import unicodedata


def normalize_location_key(value: str) -> str:
    """Return a stable lookup key without changing the displayed value."""

    normalized = unicodedata.normalize("NFKC", str(value or ""))
    return " ".join(normalized.strip().split()).casefold()


PLACE_TO_MUNICIPALITY = {
    normalize_location_key("Kasindo"): "Источна Илиџа",
    normalize_location_key("Касиндо"): "Источна Илиџа",
}


def municipality_for_place(value: str) -> str:
    return PLACE_TO_MUNICIPALITY.get(normalize_location_key(value), "")
