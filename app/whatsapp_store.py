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
        inbound_message_id: Optional[int],
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

    # ---------------------------------------------------------
    # Conversation claim / human handoff
    # ---------------------------------------------------------
    def claim_conversation(
        self, phone_number: str, claimed_by: str, notes: Optional[str] = None
    ) -> bool:
        with get_connection() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO conversation_claims
                        (phone_number, claimed_by, notes, transition_sent)
                    VALUES (?, ?, ?, 0)
                    ON CONFLICT(phone_number) DO UPDATE SET
                        claimed_by = excluded.claimed_by,
                        claimed_at = datetime('now'),
                        released_at = NULL,
                        transition_sent = 0,
                        notes = COALESCE(excluded.notes, conversation_claims.notes)
                    """,
                    (phone_number, claimed_by, notes),
                )
                conn.commit()
                return True
            except Exception:
                conn.rollback()
                return False

    def release_conversation(self, phone_number: str) -> bool:
        with get_connection() as conn:
            cur = conn.execute(
                """
                UPDATE conversation_claims
                SET released_at = datetime('now')
                WHERE phone_number = ? AND released_at IS NULL
                """,
                (phone_number,),
            )
            conn.commit()
            return cur.rowcount > 0

    def is_claimed(self, phone_number: str) -> bool:
        with get_connection() as conn:
            cur = conn.execute(
                """
                SELECT 1 FROM conversation_claims
                WHERE phone_number = ? AND released_at IS NULL
                """,
                (phone_number,),
            )
            return cur.fetchone() is not None

    def get_active_claims(self) -> List[Dict]:
        with get_connection() as conn:
            cur = conn.execute(
                """
                SELECT * FROM conversation_claims
                WHERE released_at IS NULL
                ORDER BY claimed_at DESC
                """
            )
            return [dict(row) for row in cur.fetchall()]

    def mark_transition_sent(self, phone_number: str) -> bool:
        with get_connection() as conn:
            cur = conn.execute(
                """
                UPDATE conversation_claims
                SET transition_sent = 1
                WHERE phone_number = ? AND released_at IS NULL
                """,
                (phone_number,),
            )
            conn.commit()
            return cur.rowcount > 0

    def should_send_transition(self, phone_number: str) -> bool:
        with get_connection() as conn:
            cur = conn.execute(
                """
                SELECT transition_sent FROM conversation_claims
                WHERE phone_number = ? AND released_at IS NULL
                """,
                (phone_number,),
            )
            row = cur.fetchone()
            return row is not None and not row["transition_sent"]

    def get_conversations_summary(self, limit: int = 50) -> List[Dict]:
        with get_connection() as conn:
            cur = conn.execute(
                """
                SELECT
                    im.from_number,
                    im.text AS last_message,
                    im.received_at,
                    im.processing_status,
                    CASE WHEN cc.released_at IS NULL AND cc.phone_number IS NOT NULL
                         THEN 'claimed'
                         ELSE 'bot'
                    END AS control,
                    cc.claimed_by,
                    cc.claimed_at
                FROM inbound_messages im
                LEFT JOIN conversation_claims cc
                    ON cc.phone_number = im.from_number
                    AND cc.released_at IS NULL
                WHERE im.id = (
                    SELECT MAX(id) FROM inbound_messages
                    WHERE from_number = im.from_number
                )
                ORDER BY im.received_at DESC
                LIMIT ?
                """,
                (limit,),
            )
            return [dict(row) for row in cur.fetchall()]

    def get_full_conversation(self, phone_number: str, limit: int = 100) -> List[Dict]:
        # Meta normaliza los numeros al enviar (ej. 54911... -> 5411...).
        # Buscamos outbound con ambas variantes para no perder mensajes.
        def _normalize(p: str) -> str:
            p = p.strip().replace("+", "")
            if p.startswith("549") and len(p) == 13:
                return "54" + p[3:]
            return p

        normalized = _normalize(phone_number)
        variants = list(dict.fromkeys([phone_number, normalized]))
        placeholders = ",".join("?" for _ in variants)

        with get_connection() as conn:
            cur = conn.execute(
                f"""
                SELECT
                    'inbound' AS direction,
                    im.text AS content,
                    im.received_at AS ts,
                    NULL AS send_status
                FROM inbound_messages im
                WHERE im.from_number = ?
                UNION ALL
                SELECT
                    'outbound' AS direction,
                    om.body AS content,
                    COALESCE(om.sent_at, om.created_at) AS ts,
                    om.send_status
                FROM outbound_messages om
                WHERE om.to_number IN ({placeholders})
                ORDER BY ts DESC
                LIMIT ?
                """,
                (phone_number, *variants, limit),
            )
            rows = [dict(row) for row in cur.fetchall()]
            rows.reverse()
            return rows


store = SQLiteWhatsAppStore()
