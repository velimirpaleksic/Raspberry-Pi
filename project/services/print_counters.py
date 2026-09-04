from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from project.core import config


STORE_VERSION = 1
MAX_RECENT_JOB_IDS = 2000
_LOCK = threading.RLock()


class CounterStoreError(RuntimeError):
    pass


@dataclass(frozen=True)
class CounterSnapshot:
    counts: dict[str, int]
    updated_at: str = ""

    @property
    def total(self) -> int:
        return sum(self.counts.values())

    def count_for(self, reason: str) -> int:
        return int(self.counts.get(_clean_reason(reason), 0))


def _clean_reason(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _empty_store() -> dict[str, Any]:
    return {
        "version": STORE_VERSION,
        "counts": {},
        "recent_job_ids": [],
        "updated_at": "",
    }


def _read_store_unlocked() -> dict[str, Any]:
    path = config.PRINT_COUNTERS_FILE
    if not path.exists():
        return _empty_store()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise CounterStoreError(f"Brojač se ne može pročitati: {exc}") from exc
    if not isinstance(payload, dict):
        raise CounterStoreError("Brojač nema ispravan JSON objekat.")

    raw_counts = payload.get("counts")
    if not isinstance(raw_counts, dict):
        raise CounterStoreError("Brojač nema ispravnu listu vrijednosti.")

    counts: dict[str, int] = {}
    for raw_reason, raw_value in raw_counts.items():
        reason = _clean_reason(raw_reason)
        if not reason or isinstance(raw_value, bool):
            raise CounterStoreError("Brojač sadrži neispravnu stavku.")
        try:
            value = int(raw_value)
        except (TypeError, ValueError) as exc:
            raise CounterStoreError(f"Brojač za '{reason}' nije cijeli broj.") from exc
        if value < 0:
            raise CounterStoreError(f"Brojač za '{reason}' ne može biti negativan.")
        counts[reason] = value

    raw_job_ids = payload.get("recent_job_ids") or []
    if not isinstance(raw_job_ids, list):
        raise CounterStoreError("Lista već prebrojanih poslova nije ispravna.")
    recent_job_ids = [_clean_reason(value) for value in raw_job_ids if _clean_reason(value)]
    return {
        "version": STORE_VERSION,
        "counts": counts,
        "recent_job_ids": recent_job_ids[-MAX_RECENT_JOB_IDS:],
        "updated_at": str(payload.get("updated_at") or ""),
    }


def _write_store_unlocked(payload: dict[str, Any]) -> None:
    path = config.PRINT_COUNTERS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = Path(str(path) + ".tmp")
    data = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    try:
        with temp_path.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            temp_path.chmod(0o600)
        except OSError:
            pass
        temp_path.replace(path)
    except Exception as exc:
        try:
            temp_path.unlink(missing_ok=True)
        except Exception:
            pass
        raise CounterStoreError(f"Brojač se ne može sačuvati: {exc}") from exc


def _snapshot(payload: dict[str, Any]) -> CounterSnapshot:
    stored_counts = dict(payload.get("counts") or {})
    ordered: dict[str, int] = {}
    for reason in config.RAZLOZI:
        clean_reason = _clean_reason(reason)
        ordered[clean_reason] = int(stored_counts.pop(clean_reason, 0))
    for reason in sorted(stored_counts, key=str.casefold):
        ordered[reason] = int(stored_counts[reason])
    return CounterSnapshot(ordered, str(payload.get("updated_at") or ""))


def _mark_updated(payload: dict[str, Any]) -> None:
    payload["version"] = STORE_VERSION
    payload["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_print_counters() -> CounterSnapshot:
    with _LOCK:
        return _snapshot(_read_store_unlocked())


def increment_print_counter(reason: str, *, job_id: str = "") -> CounterSnapshot:
    clean_reason = _clean_reason(reason)
    clean_job_id = _clean_reason(job_id)
    if not clean_reason:
        raise CounterStoreError("Razlog potvrde nije naveden.")

    with _LOCK:
        payload = _read_store_unlocked()
        recent_job_ids = list(payload["recent_job_ids"])
        if clean_job_id and clean_job_id in recent_job_ids:
            return _snapshot(payload)

        counts = dict(payload["counts"])
        counts[clean_reason] = int(counts.get(clean_reason, 0)) + 1
        payload["counts"] = counts
        if clean_job_id:
            recent_job_ids.append(clean_job_id)
            payload["recent_job_ids"] = recent_job_ids[-MAX_RECENT_JOB_IDS:]
        _mark_updated(payload)
        _write_store_unlocked(payload)
        return _snapshot(payload)


def set_print_counter(reason: str, value: int) -> CounterSnapshot:
    clean_reason = _clean_reason(reason)
    if not clean_reason:
        raise CounterStoreError("Razlog potvrde nije naveden.")
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise CounterStoreError("Vrijednost brojača mora biti cijeli broj 0 ili veći.")

    with _LOCK:
        payload = _read_store_unlocked()
        counts = dict(payload["counts"])
        counts[clean_reason] = value
        payload["counts"] = counts
        _mark_updated(payload)
        _write_store_unlocked(payload)
        return _snapshot(payload)


def reset_print_counters(reason: str | None = None) -> CounterSnapshot:
    clean_reason = _clean_reason(reason) if reason is not None else ""
    with _LOCK:
        payload = _read_store_unlocked()
        counts = dict(payload["counts"])
        if reason is None:
            all_reasons = {*counts, *(_clean_reason(value) for value in config.RAZLOZI)}
            counts = {value: 0 for value in all_reasons if value}
        else:
            if not clean_reason:
                raise CounterStoreError("Razlog potvrde nije naveden.")
            counts[clean_reason] = 0
        payload["counts"] = counts
        _mark_updated(payload)
        _write_store_unlocked(payload)
        return _snapshot(payload)


def resolve_reason_selector(selector: str) -> str:
    clean_selector = _clean_reason(selector)
    if clean_selector.isdigit():
        index = int(clean_selector)
        if 1 <= index <= len(config.RAZLOZI):
            return config.RAZLOZI[index - 1]
        raise CounterStoreError(f"Redni broj razloga mora biti od 1 do {len(config.RAZLOZI)}.")

    folded = clean_selector.casefold()
    for reason in config.RAZLOZI:
        if _clean_reason(reason).casefold() == folded:
            return reason
    raise CounterStoreError("Razlog nije pronađen. Koristi redni broj prikazan komandom /counts.")


def format_print_counters(snapshot: CounterSnapshot) -> str:
    lines = ["Brojač odštampanih potvrda:", f"Ukupno: {snapshot.total}", ""]
    configured = set(config.RAZLOZI)
    for index, reason in enumerate(config.RAZLOZI, start=1):
        lines.append(f"{index}. {reason}: {snapshot.count_for(reason)}")
    archived = [(reason, value) for reason, value in snapshot.counts.items() if reason not in configured and value]
    if archived:
        lines.append("")
        lines.append("Ranije stavke:")
        lines.extend(f"- {reason}: {value}" for reason, value in archived)
    if snapshot.updated_at:
        lines.extend(["", f"Posljednja promjena: {snapshot.updated_at}"])
    return "\n".join(lines)
