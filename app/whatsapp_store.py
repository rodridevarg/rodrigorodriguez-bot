from typing import List, Dict, Optional
from app.db import get_connection


class SQLiteWhatsAppStore:
    def register_inbound_message(
        self,
        provider: str,
        provider_message_id: str,
        from_number: str,
        text: str,
        provider_timestamp: Optional[str] = None,
    ) -> bool:
        with get_connection() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO inbound_messages
                        (provider, provider_message_id, from_number, text, provider_timestamp)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (provider, provider_message_id, from_number, text, provider_timestamp),
                )
                conn.commit()
                return True
            except Exception:
                conn.rollback()
                return False

    def mark_inbound_processing(self, provider_message_id: str) -> bool:
        with get_connection() as conn:
            cur = conn.execute(
                """
                UPDATE inbound_messages
                SET processing_status = 'processing',
                    attempt_count = attempt_count + 1,
                    claimed_at = datetime('now')
                WHERE provider_message_id = ?
                """,
                (provider_message_id,),
            )
            conn.commit()
            return cur.rowcount > 0

    def mark_inbound_done(self, provider_message_id: str) -> bool:
        with get_connection() as conn:
            cur = conn.execute(
                """
                UPDATE inbound_messages
                SET processing_status = 'done',
                    processed_at = datetime('now'),
                    last_error = NULL
                WHERE provider_message_id = ?
                """,
                (provider_message_id,),
            )
            conn.commit()
            return cur.rowcount > 0

    def mark_inbound_failed(self, provider_message_id: str, error: str) -> bool:
        with get_connection() as conn:
            cur = conn.execute(
                """
                UPDATE inbound_messages
                SET processing_status = 'failed',
                    last_error = ?
                WHERE provider_message_id = ?
                """,
                (error, provider_message_id),
            )
            conn.commit()
            return cur.rowcount > 0

    def is_processed(self, provider_message_id: str) -> bool:
        with get_connection() as conn:
            cur = conn.execute(
                "SELECT 1 FROM inbound_messages WHERE provider_message_id = ?",
                (provider_message_id,),
            )
            return cur.fetchone() is not None

    def get_inbound_by_provider_id(self, provider_message_id: str) -> Optional[Dict]:
        with get_connection() as conn:
            cur = conn.execute(
                "SELECT * FROM inbound_messages WHERE provider_message_id = ?",
                (provider_message_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def get_inbound_by_id(self, inbound_id: int) -> Optional[Dict]:
        with get_connection() as conn:
            cur = conn.execute(
                "SELECT * FROM inbound_messages WHERE id = ?",
                (inbound_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def get_recent_inbound(self, limit: int = 10) -> List[Dict]:
        with get_connection() as conn:
            cur = conn.execute(
                """
                SELECT * FROM inbound_messages
                ORDER BY received_at DESC
                LIMIT ?
                """,
                (limit,),
            )
            return [dict(row) for row in cur.fetchall()]

    def get_pending_inbounds(self, limit: int = 10) -> List[Dict]:
        with get_connection() as conn:
            cur = conn.execute(
                """
                SELECT * FROM inbound_messages
                WHERE processing_status = 'pending'
                ORDER BY received_at ASC
                LIMIT ?
                """,
                (limit,),
            )
            return [dict(row) for row in cur.fetchall()]

    def get_conversation_history(
        self, from_number: str, limit: int = 20
    ) -> List[Dict]:
        with get_connection() as conn:
            cur = conn.execute(
                """
                SELECT
                    im.text AS question,
                    om.body AS answer,
                    im.received_at
                FROM inbound_messages im
                JOIN outbound_messages om ON om.inbound_message_id = im.id
                WHERE im.from_number = ?
                    AND im.processing_status = 'done'
                    AND om.send_status = 'sent'
                ORDER BY im.received_at DESC, im.id DESC
                LIMIT ?
                """,
                (from_number, limit),
            )
            rows = [dict(row) for row in cur.fetchall()]
            rows.reverse()
            return rows

    def create_outbound_message(
        self,
        inbound_message_id: int,
        to_number: str,
        body: str,
        provider: str = "whatsapp",
    ) -> int:
        with get_connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO outbound_messages (inbound_message_id, to_number, body, provider)
                VALUES (?, ?, ?, ?)
                """,
                (inbound_message_id, to_number, body, provider),
            )
            conn.commit()
            return cur.lastrowid

    def mark_outbound_sent(
        self, outbound_id: int, provider_message_id: str
    ) -> bool:
        with get_connection() as conn:
            cur = conn.execute(
                """
                UPDATE outbound_messages
                SET provider_message_id = ?,
                    send_status = 'sent',
                    sent_at = datetime('now'),
                    last_error = NULL
                WHERE id = ?
                """,
                (provider_message_id, outbound_id),
            )
            conn.commit()
            return cur.rowcount > 0

    def mark_outbound_failed(self, outbound_id: int, error: str) -> bool:
        with get_connection() as conn:
            cur = conn.execute(
                """
                UPDATE outbound_messages
                SET send_status = 'failed',
                    last_error = ?
                WHERE id = ?
                """,
                (error, outbound_id),
            )
            conn.commit()
            return cur.rowcount > 0

    def log_status(
        self,
        provider: str,
        provider_message_id: str,
        status: str,
        provider_timestamp: Optional[str] = None,
    ) -> None:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO message_status_events
                    (provider, provider_message_id, status, provider_timestamp)
                VALUES (?, ?, ?, ?)
                """,
                (provider, provider_message_id, status, provider_timestamp),
            )
            conn.commit()


store = SQLiteWhatsAppStore()
