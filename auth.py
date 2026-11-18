"""User accounts: SQLite store with salted scrypt password hashes, roles and access checks."""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import interview

# Roles reuse the schema's audience ids so a role decides which questions a user sees.
ROLES = {"owner": "Application owner", "iam": "ISC developer", "admin": "Admin"}
SELF_SERVICE_ROLES = ("owner", "iam")

USER_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._@+-]{2,63}$")
MIN_PASSWORD = 8
MAX_FAILS = 5
LOCK_SECONDS = 300

DB_PATH: Path | None = None


class AuthError(ValueError):
    """A problem the user can fix, safe to show as-is."""


def _path() -> Path:
    return DB_PATH or interview.STATE_DIR / "users.db"


@contextmanager
def _db() -> Iterator[sqlite3.Connection]:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    try:
        con.execute(
            "CREATE TABLE IF NOT EXISTS users ("
            "user_id TEXT PRIMARY KEY, name TEXT NOT NULL, salt BLOB NOT NULL, "
            "pw_hash BLOB NOT NULL, role TEXT NOT NULL, created TEXT NOT NULL)"
        )
        con.execute("CREATE TABLE IF NOT EXISTS attempts (user_id TEXT NOT NULL, ts REAL NOT NULL)")
        yield con
        con.commit()
    finally:
        con.close()


def _derive(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)


def _norm(user_id: str) -> str:
    return user_id.strip().lower()


def _public(row: sqlite3.Row) -> dict[str, Any]:
    return {k: row[k] for k in ("user_id", "name", "role", "created")}


def _check_password(password: str) -> None:
    if len(password) < MIN_PASSWORD:
        raise AuthError(f"Password must be at least {MIN_PASSWORD} characters.")


def _configured_admins() -> set[str]:
    return {a.strip().lower() for a in os.getenv("ADMIN_USER_IDS", "").split(",") if a.strip()}


def register(user_id: str, name: str, password: str, role: str) -> dict[str, Any]:
    uid = _norm(user_id)
    name = name.strip()
    if not USER_ID_RE.match(uid):
        raise AuthError("User ID must be 3-64 characters: letters, numbers and . _ @ + -")
    if not name:
        raise AuthError("Enter your name.")
    if role not in SELF_SERVICE_ROLES:
        raise AuthError("Pick a role.")
    _check_password(password)

    salt = secrets.token_bytes(16)
    digest = _derive(password, salt)
    admins = _configured_admins()
    try:
        with _db() as con:
            first = con.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
            # With no admin list configured, the first account becomes the admin.
            if uid in admins or (not admins and first):
                role = "admin"
            con.execute(
                "INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)",
                (uid, name, salt, digest, role, datetime.now(timezone.utc).isoformat(timespec="seconds")),
            )
    except sqlite3.IntegrityError:
        raise AuthError("That User ID is already taken.") from None
    return get_user(uid)  # type: ignore[return-value]


def login(user_id: str, password: str) -> dict[str, Any]:
    uid = _norm(user_id)
    now = time.time()
    locked = failed = False
    user: dict[str, Any] | None = None
    with _db() as con:
        con.execute("DELETE FROM attempts WHERE ts < ?", (now - LOCK_SECONDS,))
        recent = con.execute("SELECT COUNT(*) FROM attempts WHERE user_id = ?", (uid,)).fetchone()[0]
        if recent >= MAX_FAILS:
            locked = True
        else:
            row = con.execute("SELECT * FROM users WHERE user_id = ?", (uid,)).fetchone()
            # Hash even for unknown users so response time does not reveal which IDs exist.
            digest = _derive(password, row["salt"] if row else b"\0" * 16)
            if row and hmac.compare_digest(digest, row["pw_hash"]):
                con.execute("DELETE FROM attempts WHERE user_id = ?", (uid,))
                user = _public(row)
            else:
                con.execute("INSERT INTO attempts VALUES (?, ?)", (uid, now))
                failed = True
    if locked:
        raise AuthError("Too many failed attempts. Try again in a few minutes.")
    if failed or user is None:
        raise AuthError("Incorrect User ID or password.")
    return user


def get_user(user_id: str) -> dict[str, Any] | None:
    with _db() as con:
        row = con.execute("SELECT * FROM users WHERE user_id = ?", (_norm(user_id),)).fetchone()
    return _public(row) if row else None


def list_users() -> list[dict[str, Any]]:
    with _db() as con:
        rows = con.execute("SELECT * FROM users ORDER BY user_id").fetchall()
    return [_public(r) for r in rows]


def set_role(user_id: str, role: str) -> None:
    if role not in ROLES:
        raise AuthError("Unknown role.")
    uid = _norm(user_id)
    with _db() as con:
        row = con.execute("SELECT role FROM users WHERE user_id = ?", (uid,)).fetchone()
        if row is None:
            raise AuthError("No such user.")
        if row["role"] == "admin" and role != "admin":
            admins = con.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'").fetchone()[0]
            if admins <= 1:
                raise AuthError("There must be at least one admin.")
        con.execute("UPDATE users SET role = ? WHERE user_id = ?", (role, uid))


def _set_password(user_id: str, password: str) -> None:
    salt = secrets.token_bytes(16)
    with _db() as con:
        con.execute(
            "UPDATE users SET salt = ?, pw_hash = ? WHERE user_id = ?",
            (salt, _derive(password, salt), _norm(user_id)),
        )


def change_password(user_id: str, old: str, new: str) -> None:
    _check_password(new)
    try:
        login(user_id, old)
    except AuthError as exc:
        if "Too many" in str(exc):
            raise
        raise AuthError("Current password is incorrect.") from None
    _set_password(user_id, new)


def reset_password(user_id: str) -> str:
    """Admin action: set a random temporary password and return it once."""
    if get_user(user_id) is None:
        raise AuthError("No such user.")
    temp = secrets.token_urlsafe(9)
    _set_password(user_id, temp)
    return temp


def can_access(user: dict[str, Any], state: dict[str, Any]) -> bool:
    uid = user["user_id"]
    return (
        user["role"] == "admin"
        or state.get("owner_id") == uid
        or uid in state.get("shared_with", [])
    )


def can_manage(user: dict[str, Any], state: dict[str, Any]) -> bool:
    return user["role"] == "admin" or state.get("owner_id") == user["user_id"]
