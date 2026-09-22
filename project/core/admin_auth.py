from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass

from project.core import config
from project.core.runtime_settings import get_setting, set_setting


SCHEME = "pbkdf2_sha256"
ITERATIONS = 310_000


@dataclass(frozen=True)
class LoginAttempt:
    allowed: bool
    authenticated: bool
    remaining_attempts: int
    lock_seconds: int = 0


class AdminLoginGuard:
    def __init__(self, max_attempts: int = 5, lock_seconds: int = 60) -> None:
        self.max_attempts = max(1, int(max_attempts))
        self.lock_seconds = max(1, int(lock_seconds))
        self.failures = 0
        self.locked_until = 0.0

    def attempt(self, password: str, *, now: float | None = None) -> LoginAttempt:
        current = time.monotonic() if now is None else float(now)
        remaining_lock = max(0, int(self.locked_until - current + 0.999))
        if remaining_lock:
            return LoginAttempt(False, False, 0, remaining_lock)
        if verify_admin_password(password):
            self.failures = 0
            self.locked_until = 0.0
            return LoginAttempt(True, True, self.max_attempts)
        self.failures += 1
        if self.failures >= self.max_attempts:
            self.failures = 0
            self.locked_until = current + self.lock_seconds
            return LoginAttempt(False, False, 0, self.lock_seconds)
        return LoginAttempt(True, False, self.max_attempts - self.failures)


def toggled_secret_mask(current: str) -> str:
    return "" if current else "●"


def validate_admin_password(password: str) -> tuple[bool, str]:
    value = str(password or "")
    if len(value) < 8:
        return False, "Лозинка мора имати најмање 8 знакова."
    if len(value) > 64:
        return False, "Лозинка може имати највише 64 знака."
    if any(ch.isspace() for ch in value):
        return False, "Лозинка не смије садржати размак."
    if not value.isascii() or not all(ch.isalnum() for ch in value):
        return False, "Лозинка може садржати само латинична слова и бројеве."
    return True, ""


def hash_admin_password(password: str, *, salt: bytes | None = None, iterations: int = ITERATIONS) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"{SCHEME}:{iterations}:{salt.hex()}:{digest.hex()}"


def verify_admin_password(password: str, encoded: str | None = None) -> bool:
    value = encoded or get_admin_password_hash()
    try:
        scheme, raw_iterations, salt_hex, digest_hex = value.split(":", 3)
        if scheme != SCHEME:
            return False
        candidate = hashlib.pbkdf2_hmac(
            "sha256", str(password or "").encode("utf-8"), bytes.fromhex(salt_hex), int(raw_iterations)
        ).hex()
        return hmac.compare_digest(candidate, digest_hex)
    except (AttributeError, TypeError, ValueError):
        return False


def get_admin_password_hash() -> str:
    runtime = str(get_setting("admin_password_hash", "") or "").strip()
    return runtime or config.ADMIN_PASSWORD_HASH


def set_admin_password(password: str) -> tuple[bool, str]:
    valid, message = validate_admin_password(password)
    if not valid:
        return False, message
    set_setting("admin_password_hash", hash_admin_password(password))
    return True, ""
