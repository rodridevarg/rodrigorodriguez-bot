from app.db import get_connection

MIGRATIONS = {
    "001_initial": """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS inbound_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT NOT NULL DEFAULT 'whatsapp',
            provider_message_id TEXT NOT NULL UNIQUE,
            from_number TEXT NOT NULL,
            text TEXT NOT NULL,
            provider_timestamp TEXT,
            received_at TEXT NOT NULL DEFAULT (datetime('now')),
            processing_status TEXT NOT NULL DEFAULT 'pending',
            attempt_count INTEGER NOT NULL DEFAULT 0,
            claimed_at TEXT,
            processed_at TEXT,
            last_error TEXT
        );

        CREATE TABLE IF NOT EXISTS outbound_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inbound_message_id INTEGER NOT NULL REFERENCES inbound_messages(id),
            to_number TEXT NOT NULL,
            body TEXT NOT NULL,
            provider TEXT NOT NULL DEFAULT 'whatsapp',
            provider_message_id TEXT UNIQUE,
            send_status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            sent_at TEXT,
            last_error TEXT
        );

        CREATE TABLE IF NOT EXISTS message_status_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT NOT NULL DEFAULT 'whatsapp',
            provider_message_id TEXT NOT NULL,
            status TEXT NOT NULL,
            provider_timestamp TEXT,
            received_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_inbound_status
            ON inbound_messages(processing_status, received_at);

        CREATE INDEX IF NOT EXISTS idx_outbound_provider_id
            ON outbound_messages(provider_message_id);

        CREATE INDEX IF NOT EXISTS idx_status_events_provider_id
            ON message_status_events(provider_message_id);
    """,
    "002_conversation_claims": """
        CREATE TABLE IF NOT EXISTS conversation_claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT NOT NULL UNIQUE,
            claimed_by TEXT NOT NULL,
            claimed_at TEXT NOT NULL DEFAULT (datetime('now')),
            released_at TEXT,
            transition_sent INTEGER NOT NULL DEFAULT 0,
            notes TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_claims_phone
            ON conversation_claims(phone_number);

        CREATE INDEX IF NOT EXISTS idx_claims_active
            ON conversation_claims(released_at)
            WHERE released_at IS NULL;
    """,
}


def apply_migrations():
    with get_connection() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "    version TEXT PRIMARY KEY,"
            "    applied_at TEXT NOT NULL DEFAULT (datetime('now'))"
            ")"
        )
        for name, sql in MIGRATIONS.items():
            cur = conn.execute(
                "SELECT 1 FROM schema_migrations WHERE version = ?", (name,)
            )
            if cur.fetchone():
                continue
            conn.executescript(sql)
            conn.execute(
                "INSERT INTO schema_migrations(version) VALUES (?)", (name,)
            )
            conn.commit()
