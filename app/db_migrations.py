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
    "003_outbound_nullable_inbound": """
        -- Mensajes manuales (human handoff) no tienen inbound asociado.
        PRAGMA foreign_keys = OFF;
        CREATE TABLE outbound_messages_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inbound_message_id INTEGER REFERENCES inbound_messages(id),
            to_number TEXT NOT NULL,
            body TEXT NOT NULL,
            provider TEXT NOT NULL DEFAULT 'whatsapp',
            provider_message_id TEXT UNIQUE,
            send_status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            sent_at TEXT,
            last_error TEXT
        );
        INSERT INTO outbound_messages_new SELECT * FROM outbound_messages;
        DROP TABLE outbound_messages;
        ALTER TABLE outbound_messages_new RENAME TO outbound_messages;
        CREATE INDEX IF NOT EXISTS idx_outbound_provider_id
            ON outbound_messages(provider_message_id);
        PRAGMA foreign_keys = ON;
    """,
    "004_turnos_flow_state": """
        -- Estado del flujo de turnos por número de teléfono
        CREATE TABLE IF NOT EXISTS turno_flow_states (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT NOT NULL UNIQUE,
            step TEXT NOT NULL DEFAULT 'ask_service',
            date TEXT,
            time TEXT,
            service_id TEXT,
            service_name TEXT,
            duration_minutes INTEGER,
            client_name TEXT,
            client_phone TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            expires_at TEXT NOT NULL DEFAULT (datetime('now', '+10 minutes'))
        );

        CREATE INDEX IF NOT EXISTS idx_turno_flow_phone
            ON turno_flow_states(phone_number);

        CREATE INDEX IF NOT EXISTS idx_turno_flow_expires
            ON turno_flow_states(expires_at);

        -- Turnos confirmados (para recordatorios y cancelaciones)
        CREATE TABLE IF NOT EXISTS confirmed_turnos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT NOT NULL,
            client_name TEXT NOT NULL,
            service_name TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            duration_minutes INTEGER,
            google_event_id TEXT,
            calendar_id TEXT,
            status TEXT NOT NULL DEFAULT 'confirmed',
            reminder_sent INTEGER NOT NULL DEFAULT 0,
            reminder_sent_at TEXT,
            confirmed_at TEXT NOT NULL DEFAULT (datetime('now')),
            cancelled_at TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_confirmed_turnos_phone
            ON confirmed_turnos(phone_number);

        CREATE INDEX IF NOT EXISTS idx_confirmed_turnos_date
            ON confirmed_turnos(date, status);

        CREATE INDEX IF NOT EXISTS idx_confirmed_turnos_reminder
            ON confirmed_turnos(reminder_sent, date)
            WHERE reminder_sent = 0;
    """,
    "005_cancel_turno_id": """
        -- Agregar columna cancel_turno_id a turno_flow_states
        ALTER TABLE turno_flow_states ADD COLUMN cancel_turno_id INTEGER;
    """,
    "006_previous_step": """
        -- Agregar columna previous_step a turno_flow_states para manejar "volver al menú"
        ALTER TABLE turno_flow_states ADD COLUMN previous_step TEXT;
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
