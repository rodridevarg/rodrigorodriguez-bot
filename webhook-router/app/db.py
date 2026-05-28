import sqlite3
from pathlib import Path
from app.config import DB_PATH, DATA_DIR


def init_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS phone_routing (
            phone_number_id TEXT PRIMARY KEY,
            client_slug TEXT NOT NULL,
            target_url TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def get_route(phone_number_id: str):
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "SELECT client_slug, target_url FROM phone_routing WHERE phone_number_id = ?",
        (phone_number_id,),
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def register_route(phone_number_id: str, client_slug: str, target_url: str) -> bool:
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT OR REPLACE INTO phone_routing (phone_number_id, client_slug, target_url) VALUES (?, ?, ?)",
            (phone_number_id, client_slug, target_url),
        )
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def unregister_route(phone_number_id: str) -> bool:
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    try:
        cursor.execute(
            "DELETE FROM phone_routing WHERE phone_number_id = ?",
            (phone_number_id,),
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception:
        return False
    finally:
        conn.close()


def list_routes():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "SELECT phone_number_id, client_slug, target_url, created_at FROM phone_routing ORDER BY created_at"
    )
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows
