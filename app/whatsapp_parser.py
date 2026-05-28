from typing import List, Dict, Any, Optional
from app.whatsapp_models import InboundTextMessage, StatusEvent


def parse_webhook_get(params: Dict[str, Any]) -> Optional[Dict[str, str]]:
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode and token and challenge:
        return {
            "mode": mode,
            "verify_token": token,
            "challenge": challenge,
        }
    return None


def _extract_phone_number_id(value: Dict[str, Any]) -> str:
    metadata = value.get("metadata", {})
    if isinstance(metadata, dict):
        return metadata.get("phone_number_id", "")
    return ""


def parse_webhook_post(payload: Dict[str, Any]) -> Dict[str, Any]:
    messages: List[InboundTextMessage] = []
    statuses: List[StatusEvent] = []
    phone_number_id = ""

    if not isinstance(payload, dict):
        return {"messages": messages, "statuses": statuses, "phone_number_id": phone_number_id}

    if payload.get("object") != "whatsapp_business_account":
        return {"messages": messages, "statuses": statuses, "phone_number_id": phone_number_id}

    entries = payload.get("entry", [])
    if not isinstance(entries, list):
        return {"messages": messages, "statuses": statuses, "phone_number_id": phone_number_id}

    for entry in entries:
        changes = entry.get("changes", [])
        if not isinstance(changes, list):
            continue

        for change in changes:
            value = change.get("value", {})
            if not isinstance(value, dict):
                continue

            if not phone_number_id:
                phone_number_id = _extract_phone_number_id(value)

            raw_messages = value.get("messages", [])
            if isinstance(raw_messages, list):
                for msg in raw_messages:
                    parsed = _parse_inbound_message(msg)
                    if parsed:
                        messages.append(parsed)

            raw_statuses = value.get("statuses", [])
            if isinstance(raw_statuses, list):
                for st in raw_statuses:
                    parsed = _parse_status(st)
                    if parsed:
                        statuses.append(parsed)

    return {"messages": messages, "statuses": statuses, "phone_number_id": phone_number_id}


def _parse_inbound_message(msg: Dict[str, Any]) -> Optional[InboundTextMessage]:
    if not isinstance(msg, dict):
        return None

    msg_type = msg.get("type")
    if msg_type != "text":
        return None

    text_body = msg.get("text", {}).get("body")
    if not text_body:
        return None

    from_number = msg.get("from")
    message_id = msg.get("id")
    timestamp = msg.get("timestamp")

    if not from_number or not message_id:
        return None

    return InboundTextMessage(
        from_number=from_number,
        message_id=message_id,
        text=text_body,
        timestamp=timestamp or "",
    )


def _parse_status(st: Dict[str, Any]) -> Optional[StatusEvent]:
    if not isinstance(st, dict):
        return None

    status = st.get("status")
    message_id = st.get("id")
    timestamp = st.get("timestamp")

    if not status or not message_id:
        return None

    return StatusEvent(
        status=status,
        message_id=message_id,
        timestamp=timestamp or "",
    )
