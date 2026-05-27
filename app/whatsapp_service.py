import traceback
from typing import Dict, Optional
from app.config import CONVERSATION_MEMORY_MAX_TURNS, HANDOFF_TRANSITION_MESSAGE
from app.rag_service import answer_question
from app.whatsapp_models import InboundTextMessage
from app.whatsapp_store import store
from app.whatsapp_sender import get_sender


def normalize_phone_for_meta(phone: str) -> str:
    phone = phone.strip().replace("+", "")
    if phone.startswith("549") and len(phone) == 13:
        return "54" + phone[3:]
    return phone


class WhatsAppService:
    def __init__(self):
        self.sender = get_sender()

    def receive_inbound_text(self, msg: InboundTextMessage) -> str:
        is_new = store.register_inbound_message(
            provider=msg.provider,
            provider_message_id=msg.message_id,
            from_number=msg.from_number,
            text=msg.text,
            provider_timestamp=msg.timestamp,
        )

        if not is_new:
            return "duplicado"

        return "nuevo"

    def _send_outbound(
        self, inbound_id: int, to_number: str, body: str, provider: str
    ) -> str:
        outbound_id = store.create_outbound_message(
            inbound_message_id=inbound_id,
            to_number=to_number,
            body=body,
            provider=provider,
        )
        try:
            send_result = self.sender.send_text(to_number, body)
            provider_msg_id = send_result.get("message_id")
            if provider_msg_id:
                store.mark_outbound_sent(outbound_id, provider_msg_id)
                return provider_msg_id
            else:
                error_msg = f"[ERROR al enviar: {send_result.get('error_body', 'sin ID de mensaje')}]"
                store.mark_outbound_failed(outbound_id, error_msg)
                return error_msg
        except Exception as e:
            error_msg = f"[ERROR al enviar: {e}]"
            store.mark_outbound_failed(outbound_id, error_msg)
            print(error_msg)
            traceback.print_exc()
            return error_msg

    def process_inbound_by_id(self, inbound_id: int) -> str:
        inbound = store.get_inbound_by_id(inbound_id)
        if not inbound:
            return "[ERROR: inbound no encontrado]"

        if inbound["processing_status"] != "pending":
            return f"[SKIP: estado={inbound['processing_status']}]"

        store.mark_inbound_processing(inbound["provider_message_id"])

        to_number = normalize_phone_for_meta(inbound["from_number"])

        # Human handoff check
        if store.is_claimed(inbound["from_number"]):
            if store.should_send_transition(inbound["from_number"]):
                msg_id = self._send_outbound(
                    inbound_id=inbound["id"],
                    to_number=to_number,
                    body=HANDOFF_TRANSITION_MESSAGE,
                    provider=inbound["provider"],
                )
                store.mark_transition_sent(inbound["from_number"])
                store.mark_inbound_done(inbound["provider_message_id"])
                return f"[HANDOFF TRANSITION] {msg_id}"
            else:
                # Already notified, stay silent
                store.mark_inbound_done(inbound["provider_message_id"])
                return "[HANDOFF SILENT] Conversación reclamada, sin respuesta."

        # Normal bot flow
        history = store.get_conversation_history(
            inbound["from_number"], limit=CONVERSATION_MEMORY_MAX_TURNS
        )

        result = answer_question(inbound["text"], conversation_history=history)
        answer = result["answer"]

        if not result["sources"]:
            answer = (
                "No encontré esa información con seguridad. "
                "Escribime por WhatsApp y te ayudo: +54 9 2477 614405"
            )

        msg_id = self._send_outbound(
            inbound_id=inbound["id"],
            to_number=to_number,
            body=answer,
            provider=inbound["provider"],
        )

        if msg_id.startswith("[ERROR"):
            store.mark_inbound_failed(inbound["provider_message_id"], msg_id)
            return msg_id
        else:
            store.mark_inbound_done(inbound["provider_message_id"])
            return msg_id

    def send_manual_reply(self, phone_number: str, body: str) -> str:
        to_number = normalize_phone_for_meta(phone_number)
        # Create a dummy inbound reference (id=0) since this is manual
        outbound_id = store.create_outbound_message(
            inbound_message_id=0,
            to_number=to_number,
            body=body,
            provider="whatsapp",
        )
        try:
            send_result = self.sender.send_text(to_number, body)
            provider_msg_id = send_result.get("message_id")
            if provider_msg_id:
                store.mark_outbound_sent(outbound_id, provider_msg_id)
                return provider_msg_id
            else:
                error_msg = f"[ERROR al enviar: {send_result.get('error_body', 'sin ID de mensaje')}]"
                store.mark_outbound_failed(outbound_id, error_msg)
                return error_msg
        except Exception as e:
            error_msg = f"[ERROR al enviar: {e}]"
            store.mark_outbound_failed(outbound_id, error_msg)
            print(error_msg)
            traceback.print_exc()
            return error_msg

    def handle_inbound_text(self, msg: InboundTextMessage) -> str:
        status = self.receive_inbound_text(msg)
        if status == "duplicado":
            return "[duplicado ignorado]"

        inbound = store.get_inbound_by_provider_id(msg.message_id)
        if not inbound:
            return "[ERROR: no se encontró inbound después de insertar]"

        return self.process_inbound_by_id(inbound["id"])


whatsapp_service = WhatsAppService()
