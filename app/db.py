import sqlite3
from contextlib import contextmanager


def _db_path():
    from app.config import APP_DB_PATH
    return APP_DB_PATH


@contextmanager
def get_connection():
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
        conn.execute("SELECT 1")
