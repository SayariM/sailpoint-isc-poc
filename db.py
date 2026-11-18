"""Storage engine: a local SQLite file by default, Postgres when DATABASE_URL is set.

Accounts, per-user progress and applications all live in one database so they survive
restarts on hosts with a temporary disk (set DATABASE_URL to a hosted Postgres).
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from typing import Any, Iterator

from sqlalchemy import Column, Float, LargeBinary, MetaData, String, Table, Text, create_engine, text
from sqlalchemy.engine import Connection as SAConnection
from sqlalchemy.engine import Engine

metadata = MetaData()

# Column order matters: auth.py inserts positionally.
Table(
    "users",
    metadata,
    Column("user_id", String(64), primary_key=True),
    Column("name", Text, nullable=False),
    Column("salt", LargeBinary, nullable=False),
    Column("pw_hash", LargeBinary, nullable=False),
    Column("role", String(16), nullable=False),
    Column("created", String(32), nullable=False),
)
Table(
    "attempts",
    metadata,
    Column("user_id", String(64), nullable=False, index=True),
    Column("ts", Float, nullable=False),
)
Table(
    "progress",
    metadata,
    Column("user_id", String(64), primary_key=True),
    Column("slug", String(128), primary_key=True),
    Column("page", String(64), nullable=False),
    Column("updated", String(32), nullable=False),
)
Table(
    "applications",
    metadata,
    Column("slug", String(128), primary_key=True),
    Column("owner_id", String(64), index=True),
    Column("data", Text, nullable=False),
    Column("updated", String(32), nullable=False),
)

_engines: dict[str, Engine] = {}
_lock = threading.Lock()


def _url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        import interview

        interview.STATE_DIR.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{(interview.STATE_DIR / 'app.db').as_posix()}"
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


def is_sqlite() -> bool:
    return _url().startswith("sqlite")


def engine() -> Engine:
    url = _url()
    with _lock:
        eng = _engines.get(url)
        if eng is None:
            args = {"timeout": 30} if url.startswith("sqlite") else {}
            eng = create_engine(url, pool_pre_ping=True, connect_args=args)
            metadata.create_all(eng)
            _engines[url] = eng
            if url.startswith("sqlite"):
                import_legacy(eng)
    return eng


class _Row:
    """A result row readable by column name or position."""

    def __init__(self, row: Any) -> None:
        self._row = row

    def __getitem__(self, key: int | str) -> Any:
        value = self._row._mapping[key] if isinstance(key, str) else self._row[key]
        return bytes(value) if isinstance(value, memoryview) else value


class _Result:
    def __init__(self, result: Any) -> None:
        self._result = result

    def fetchone(self) -> _Row | None:
        row = self._result.fetchone()
        return _Row(row) if row is not None else None

    def fetchall(self) -> list[_Row]:
        return [_Row(r) for r in self._result.fetchall()]


class Connection:
    """Runs SQL written with ? placeholders on either SQLite or Postgres."""

    def __init__(self, conn: SAConnection) -> None:
        self._conn = conn

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> _Result:
        pieces = sql.split("?")
        named = pieces[0] + "".join(f":p{i}{piece}" for i, piece in enumerate(pieces[1:]))
        result = self._conn.execute(text(named), {f"p{i}": v for i, v in enumerate(params)})
        return _Result(result)


@contextmanager
def connection() -> Iterator[Connection]:
    """A transaction: committed on success, rolled back on error."""
    with engine().begin() as conn:
        yield Connection(conn)


# ---------------------------------------------------------------- applications

_UPSERT_APP = (
    "INSERT INTO applications (slug, owner_id, data, updated) VALUES (?, ?, ?, ?) "
    "ON CONFLICT (slug) DO UPDATE SET owner_id = excluded.owner_id, "
    "data = excluded.data, updated = excluded.updated"
)


def put_app(state: dict[str, Any]) -> None:
    with connection() as con:
        con.execute(
            _UPSERT_APP,
            (
                state["slug"],
                state.get("owner_id"),
                json.dumps(state, ensure_ascii=False),
                state.get("updated", ""),
            ),
        )


def get_app(slug: str) -> dict[str, Any] | None:
    with connection() as con:
        row = con.execute("SELECT data FROM applications WHERE slug = ?", (slug,)).fetchone()
    return json.loads(row["data"]) if row else None


def app_exists(slug: str) -> bool:
    with connection() as con:
        return con.execute("SELECT 1 FROM applications WHERE slug = ?", (slug,)).fetchone() is not None


def list_apps() -> list[dict[str, Any]]:
    with connection() as con:
        rows = con.execute("SELECT data FROM applications ORDER BY slug").fetchall()
    return [json.loads(r["data"]) for r in rows]


# ---------------------------------------------------------------- legacy import

def import_legacy(eng: Engine) -> dict[str, int]:
    """Copy data from the older file-based layout (state/*.json, state/users.db).

    Safe to repeat: rows that already exist are left untouched.
    """
    import interview

    counts = {"applications": 0, "users": 0, "progress": 0}
    folder = interview.STATE_DIR
    if not folder.exists():
        return counts

    with eng.begin() as conn:
        con = Connection(conn)
        for path in sorted(folder.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if not isinstance(data, dict) or "answers" not in data:
                continue
            data["slug"] = path.stem
            if con.execute("SELECT 1 FROM applications WHERE slug = ?", (path.stem,)).fetchone():
                continue
            con.execute(
                "INSERT INTO applications (slug, owner_id, data, updated) VALUES (?, ?, ?, ?)",
                (path.stem, data.get("owner_id"), json.dumps(data, ensure_ascii=False), data.get("updated", "")),
            )
            counts["applications"] += 1

        legacy = folder / "users.db"
        if legacy.exists():
            old = sqlite3.connect(legacy)
            try:
                for table, key, sql in (
                    ("users", 6, "INSERT INTO users VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (user_id) DO NOTHING"),
                    (
                        "progress",
                        4,
                        "INSERT INTO progress VALUES (?, ?, ?, ?) ON CONFLICT (user_id, slug) DO NOTHING",
                    ),
                ):
                    try:
                        rows = old.execute(f"SELECT * FROM {table}").fetchall()
                    except sqlite3.OperationalError:
                        continue
                    for row in rows:
                        if len(row) != key:
                            continue
                        before = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                        con.execute(sql, tuple(row))
                        after = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                        counts[table] += after - before
            finally:
                old.close()
    return counts
