import uuid
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from app.config import (
    WHATSAPP_MODE,
    META_ACCESS_TOKEN,
    META_PHONE_NUMBER_ID,
    META_GRAPH_VERSION,
)


class WhatsAppSender(ABC):
    @abstractmethod
    def send_text(self, to: str, body: str) -> Dict:
        ...

    @abstractmethod
    def send_interactive_buttons(
        self, to: str, body: str, buttons: List[Dict]
    ) -> Dict:
        ...

    @abstractmethod
    def send_interactive_list(
        self, to: str, body: str, button_text: str, sections: List[Dict]
    ) -> Dict:
        ...


class FakeWhatsAppSender(WhatsAppSender):
    def send_text(self, to: str, body: str) -> Dict:
        fake_id = f"fake-{uuid.uuid4().hex[:8]}"
        print(f"[FAKE SENDER] to={to} | body={body[:80]}... | id={fake_id}")
        return {
            "provider": "fake",
            "to": to,
            "body": body,
            "message_id": fake_id,
        }

    def send_interactive_buttons(
        self, to: str, body: str, buttons: List[Dict]
    ) -> Dict:
        fake_id = f"fake-btn-{uuid.uuid4().hex[:8]}"
        titles = [b.get("reply", {}).get("title", "?") for b in buttons]
        print(f"[FAKE SENDER BUTTONS] to={to} | body={body[:60]}... | buttons={titles} | id={fake_id}")
        return {
            "provider": "fake",
            "to": to,
            "body": body,
            "message_id": fake_id,
            "buttons": titles,
        }

    def send_interactive_list(
        self, to: str, body: str, button_text: str, sections: List[Dict]
    ) -> Dict:
        fake_id = f"fake-list-{uuid.uuid4().hex[:8]}"
        print(f"[FAKE SENDER LIST] to={to} | body={body[:60]}... | btn={button_text} | id={fake_id}")
        return {
            "provider": "fake",
            "to": to,
            "body": body,
            "message_id": fake_id,
        }


class MetaWhatsAppSender(WhatsAppSender):
    def __init__(self):
        if not META_ACCESS_TOKEN or not META_PHONE_NUMBER_ID:
            raise ValueError(
                "Faltan META_ACCESS_TOKEN o META_PHONE_NUMBER_ID. "
                "Completá las credenciales en .env y usá WHATSAPP_MODE=meta"
            )
        self._base_url = f"https://graph.facebook.com/{META_GRAPH_VERSION}/{META_PHONE_NUMBER_ID}/messages"
        self._headers = {
            "Authorization": f"Bearer {META_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        }

    def _post(self, payload: Dict) -> Dict:
        import httpx
        try:
            response = httpx.post(self._base_url, headers=self._headers, json=payload, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            return {
                "success": True,
                "message_id": data.get("messages", [{}])[0].get("id"),
                "data": data,
            }
        except httpx.HTTPStatusError as e:
            error_body = ""
            try:
                error_body = e.response.text
            except Exception:
                pass
            print(f"[META SENDER ERROR] HTTP {e.response.status_code}: {error_body}")
            return {"success": False, "error": True, "status_code": e.response.status_code, "error_body": error_body}
        except Exception as e:
            print(f"[META SENDER ERROR] {e}")
            return {"success": False, "error": True, "error_message": str(e)}

    def send_text(self, to: str, body: str) -> Dict:
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"body": body},
        }
        result = self._post(payload)
        return {
            "provider": "meta",
            "to": to,
            "body": body,
            "message_id": result.get("message_id"),
            "error": result.get("error"),
            "error_body": result.get("error_body"),
        }

    def send_interactive_buttons(
        self, to: str, body: str, buttons: List[Dict]
    ) -> Dict:
        # Validate button titles (max 20 chars for Meta API)
        valid_buttons = []
        for btn in buttons[:3]:  # Max 3 reply buttons
            reply = btn.get("reply", {})
            title = reply.get("title", "")[:20]  # Meta limit
            btn_id = reply.get("id", f"btn_{len(valid_buttons)}")
            valid_buttons.append({
                "type": "reply",
                "reply": {"id": btn_id, "title": title},
            })

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": body[:1024]},  # Meta limit
                "action": {"buttons": valid_buttons},
            },
        }

        result = self._post(payload)
        return {
            "provider": "meta",
            "to": to,
            "body": body,
            "message_id": result.get("message_id"),
            "error": result.get("error"),
            "error_body": result.get("error_body"),
        }

    def send_interactive_list(
        self, to: str, body: str, button_text: str, sections: List[Dict]
    ) -> Dict:
        # Validate section rows (max 10 rows total for Meta API)
        valid_sections = []
        total_rows = 0
        for section in sections:
            rows = []
            for row in section.get("rows", []):
                if total_rows >= 10:
                    break
                rows.append({
                    "id": row.get("id", f"row_{total_rows}"),
                    "title": row.get("title", "Opción")[:24],  # Meta limit
                    "description": row.get("description", "")[:72],  # Meta limit
                })
                total_rows += 1
            if rows:
                valid_sections.append({
                    "title": section.get("title", "Opciones")[:24],
                    "rows": rows,
                })

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "list",
                "body": {"text": body[:1024]},
                "action": {
                    "button": button_text[:20],
                    "sections": valid_sections,
                },
            },
        }

        result = self._post(payload)
        return {
            "provider": "meta",
            "to": to,
            "body": body,
            "message_id": result.get("message_id"),
            "error": result.get("error"),
            "error_body": result.get("error_body"),
        }


def get_sender() -> WhatsAppSender:
    if WHATSAPP_MODE == "meta":
        return MetaWhatsAppSender()
    return FakeWhatsAppSender()
