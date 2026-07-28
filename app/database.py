import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path


def database_path() -> Path:
    path = Path(os.getenv("DATABASE_PATH", "./data/loyalty.db"))
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


@contextmanager
def connect():
    conn = sqlite3.connect(database_path(), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with connect() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS admins (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              username TEXT NOT NULL UNIQUE COLLATE NOCASE,
              password_hash BLOB NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS customers (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT NOT NULL,
              phone TEXT NOT NULL UNIQUE,
              points INTEGER NOT NULL DEFAULT 0 CHECK(points >= 0),
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS point_history (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              customer_id INTEGER NOT NULL,
              change INTEGER NOT NULL,
              balance_after INTEGER NOT NULL CHECK(balance_after >= 0),
              note TEXT NOT NULL DEFAULT '',
              actor TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(customer_id) REFERENCES customers(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS history_customer_idx
              ON point_history(customer_id, id DESC);
            """
        )

