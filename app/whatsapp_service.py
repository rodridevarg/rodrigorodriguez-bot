import re
import traceback
from typing import Dict, Optional, Tuple
from app.config import (
    CONVERSATION_MEMORY_MAX_TURNS,
    HANDOFF_TRANSITION_MESSAGE,
    CONTACT_PHONE,
    FALLBACK_MESSAGE,
)
from app.rag_service import answer_question
from app.whatsapp_models import InboundTextMessage
from app.whatsapp_store import store
from app.whatsapp_sender import get_sender


def normalize_phone_for_meta(phone: str) -> str:
    phone = phone.strip().replace("+", "")
    if phone.startswith("549") and len(phone) == 13:
        return "54" + phone[3:]
    return phone


def _is_greeting(text: str) -> bool:
    greetings = ["hola", "buenas", "buen dia", "buen día", "buenas tardes", "buenas noches", "hey", "hi", "hello"]
    clean = text.lower().strip()
    return any(clean.startswith(g) for g in greetings)


def _is_about_insurance(text: str) -> bool:
    keywords = ["obra social", "obras sociales", "prepaga", "osde", "swiss", "galeno", "medicus", "pami", "iomaa", "sipssa", "cobertura"]
    clean = text.lower()
    return any(k in clean for k in keywords)


def _is_about_services(text: str) -> bool:
    keywords = ["servicio", "servicios", "estudio", "estudios", "laboratorio", "analisis", "análisis", "ecografia", "radiografia"]
    clean = text.lower()
    return any(k in clean for k in keywords)


def _is_about_turno(text: str) -> bool:
    keywords = ["turno", "turnos", "cita", "agendar", "sacar", "reservar"]
    clean = text.lower()
    return any(k in clean for k in keywords)


def _parse_button_click(text: str) -> Tuple[Optional[str], Optional[str]]:
    """Detecta si el texto es un click de botón/lista interactiva.
    
    Formato: '[btn_id] Título del botón' o '[row_id] Título de la fila'
    
    Returns: (button_id, button_title) o (None, None) si no es botón.
    """
    match = re.match(r'^\[([\w_\-]+)\]\s*(.+)$', text.strip())
    if match:
        return match.group(1), match.group(2).strip()
    return None, None


def _rag_query_for_button(button_id: str, button_title: str) -> str:
    """Genera una query de RAG específica para cada botón."""
    queries = {
        # Botones de bienvenida
        "btn_turno": "Quiero sacar un turno médico, ¿cómo hago?",
        "btn_precios": "¿Cuánto cuestan las consultas y estudios? Precios particulares y con obra social.",
        "btn_obras": "¿Qué obras sociales y prepagas aceptan?",
        
        # Obras sociales
        "os_osde": "Tengo OSDE, ¿qué copago tengo que pagar? ¿cómo atienden con OSDE?",
        "os_swiss": "Tengo Swiss Medical, ¿qué copago tengo que pagar? ¿cómo atienden con Swiss Medical?",
        "os_galeno": "Tengo Galeno, ¿qué copago tengo que pagar? ¿cómo atienden con Galeno?",
        "os_medicus": "Tengo Medicus, ¿qué copago tengo que pagar? ¿cómo atienden con Medicus?",
        "os_omint": "Tengo Omint, ¿qué copago tengo que pagar? ¿cómo atienden con Omint?",
        "os_pami": "Tengo PAMI, ¿cómo puedo atenderme? ¿necesito autorización?",
        "os_ioma": "Tengo IOMA, ¿cómo puedo atenderme? ¿necesito orden médica?",
        "os_sipssa": "Tengo SIPSSA, ¿qué copago tengo? ¿cómo atienden con SIPSSA?",
        "os_apross": "Tengo APROSS, ¿qué copago tengo? ¿cómo atienden con APROSS?",
        "os_otras": "Tengo otra obra social que no está en la lista, ¿cómo puedo saber si la aceptan?",
        
        # Servicios y estudios
        "srv_consulta": "Quiero información sobre la consulta médica general de primera vez.",
        "srv_control": "Quiero información sobre la consulta de control o seguimiento.",
        "srv_checkup": "Quiero información sobre el check-up anual completo.",
        "srv_online": "Quiero información sobre la telemedicina o consulta online.",
        "srv_lab": "Quiero información sobre los estudios de laboratorio, análisis de sangre y orina. ¿necesito ayuno?",
        "srv_eco": "Quiero información sobre la ecografía. ¿cómo me preparo?",
        "srv_rx": "Quiero información sobre la radiografía.",
        "srv_ecg": "Quiero información sobre el electrocardiograma.",
    }
    
    return queries.get(button_id, button_title)


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

    def _send_interactive_buttons(
        self, inbound_id: int, to_number: str, body: str, buttons: list, provider: str
    ) -> str:
        outbound_id = store.create_outbound_message(
            inbound_message_id=inbound_id,
            to_number=to_number,
            body=body,
            provider=provider,
        )
        try:
            send_result = self.sender.send_interactive_buttons(to_number, body, buttons)
            provider_msg_id = send_result.get("message_id")
            if provider_msg_id:
                store.mark_outbound_sent(outbound_id, provider_msg_id)
                return provider_msg_id
            else:
                return self._send_outbound(inbound_id, to_number, body, provider)
        except Exception as e:
            print(f"[ERROR botones: {e}]")
            traceback.print_exc()
            return self._send_outbound(inbound_id, to_number, body, provider)

    def _send_interactive_list(
        self, inbound_id: int, to_number: str, body: str, button_text: str, sections: list, provider: str
    ) -> str:
        outbound_id = store.create_outbound_message(
            inbound_message_id=inbound_id,
            to_number=to_number,
            body=body,
            provider=provider,
        )
        try:
            send_result = self.sender.send_interactive_list(to_number, body, button_text, sections)
            provider_msg_id = send_result.get("message_id")
            if provider_msg_id:
                store.mark_outbound_sent(outbound_id, provider_msg_id)
                return provider_msg_id
            else:
                return self._send_outbound(inbound_id, to_number, body, provider)
        except Exception as e:
            print(f"[ERROR lista: {e}]")
            traceback.print_exc()
            return self._send_outbound(inbound_id, to_number, body, provider)

    def _send_greeting_with_buttons(self, inbound_id: int, to_number: str, provider: str) -> str:
        body = (
            "¡Hola! 👋 Soy la Secretaria Virtual del Centro Médico Demostración.\n\n"
            "¿En qué puedo ayudarte hoy?"
        )
        buttons = [
            {"reply": {"id": "btn_turno", "title": "🗓️ Sacar turno"}},
            {"reply": {"id": "btn_obras", "title": "💳 Obras sociales"}},
            {"reply": {"id": "btn_precios", "title": "💰 Precios"}},
        ]
        return self._send_interactive_buttons(inbound_id, to_number, body, buttons, provider)

    def _send_insurance_list(self, inbound_id: int, to_number: str, provider: str) -> str:
        body = "Estas son las obras sociales y prepagas que aceptamos. Seleccioná la tuya para ver el copago:"
        sections = [
            {
                "title": "Prepagas principales",
                "rows": [
                    {"id": "os_osde", "title": "OSDE", "description": "210/310 sin copago"},
                    {"id": "os_swiss", "title": "Swiss Medical", "description": "SMG sin copago"},
                    {"id": "os_galeno", "title": "Galeno", "description": "Oro sin copago"},
                    {"id": "os_medicus", "title": "Medicus", "description": "Selecta sin copago"},
                    {"id": "os_omint", "title": "Omint", "description": "Según plan"},
                ],
            },
            {
                "title": "Obras sociales",
                "rows": [
                    {"id": "os_pami", "title": "PAMI", "description": "Con autorización previa"},
                    {"id": "os_ioma", "title": "IOMA", "description": "Con orden médica"},
                    {"id": "os_sipssa", "title": "SIPSSA", "description": "Sin copago"},
                    {"id": "os_apross", "title": "APROSS", "description": "Sin copago"},
                    {"id": "os_otras", "title": "Otras", "description": "Consultá por WhatsApp"},
                ],
            },
        ]
        return self._send_interactive_list(inbound_id, to_number, body, "Ver obras sociales", sections, provider)

    def _send_services_list(self, inbound_id: int, to_number: str, provider: str) -> str:
        body = "Estos son nuestros servicios y estudios. Seleccioná uno para más información:"
        sections = [
            {
                "title": "Consultas",
                "rows": [
                    {"id": "srv_consulta", "title": "Consulta general", "description": "Primera vez - $25.000"},
                    {"id": "srv_control", "title": "Consulta de control", "description": "Seguimiento - $18.000"},
                    {"id": "srv_checkup", "title": "Check-up anual", "description": "Completo - $30.000"},
                    {"id": "srv_online", "title": "Telemedicina", "description": "Online - $15.000"},
                ],
            },
            {
                "title": "Estudios",
                "rows": [
                    {"id": "srv_lab", "title": "Laboratorio", "description": "Análisis de sangre, orina"},
                    {"id": "srv_eco", "title": "Ecografía", "description": "Abdominal y otras"},
                    {"id": "srv_rx", "title": "Radiografía", "description": "Tórax y otras"},
                    {"id": "srv_ecg", "title": "Electrocardiograma", "description": "ECG en reposo"},
                ],
            },
        ]
        return self._send_interactive_list(inbound_id, to_number, body, "Ver servicios", sections, provider)

    def _send_rag_answer(
        self, inbound_id: int, to_number: str, query: str, provider: str, from_number: str
    ) -> str:
        """Envía una respuesta del RAG para una query específica."""
        history = store.get_conversation_history(
            from_number, limit=CONVERSATION_MEMORY_MAX_TURNS
        )
        
        result = answer_question(query, conversation_history=history)
        answer = result["answer"]
        
        if not result["sources"]:
            answer = FALLBACK_MESSAGE
            if CONTACT_PHONE:
                answer += f" WhatsApp: {CONTACT_PHONE}"
        
        msg_id = self._send_outbound(
            inbound_id=inbound_id,
            to_number=to_number,
            body=answer,
            provider=provider,
        )
        return msg_id

    def _was_last_outbound_a_list(self, from_number: str, list_type: str) -> bool:
        """Verifica si el último mensaje enviado por el bot fue una lista interactiva.
        
        list_type: 'insurance' o 'services'
        """
        history = store.get_conversation_history(from_number, limit=1)
        if not history:
            return False
        
        last_answer = history[0].get("answer", "")
        
        if list_type == "insurance":
            return "obras sociales" in last_answer.lower() and "seleccioná" in last_answer.lower()
        elif list_type == "services":
            return "servicios" in last_answer.lower() and "seleccioná" in last_answer.lower()
        
        return False

    def process_inbound_by_id(self, inbound_id: int) -> str:
        inbound = store.get_inbound_by_id(inbound_id)
        if not inbound:
            return "[ERROR: inbound no encontrado]"

        if inbound["processing_status"] != "pending":
            return f"[SKIP: estado={inbound['processing_status']}]"

        store.mark_inbound_processing(inbound["provider_message_id"])

        to_number = normalize_phone_for_meta(inbound["from_number"])
        text = inbound["text"]

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
                store.mark_inbound_done(inbound["provider_message_id"])
                return "[HANDOFF SILENT] Conversación reclamada, sin respuesta."

        # =====================================================================
        # 1. DETECTAR CLICK DE BOTÓN (formato: [id] Título)
        # =====================================================================
        button_id, button_title = _parse_button_click(text)
        
        if button_id:
            # Botones de bienvenida
            if button_id == "btn_obras":
                msg_id = self._send_insurance_list(inbound["id"], to_number, inbound["provider"])
                store.mark_inbound_done(inbound["provider_message_id"])
                return f"[INSURANCE LIST] {msg_id}"
            
            if button_id == "btn_turno" or button_id == "btn_precios":
                query = _rag_query_for_button(button_id, button_title)
                msg_id = self._send_rag_answer(
                    inbound["id"], to_number, query, inbound["provider"], inbound["from_number"]
                )
                store.mark_inbound_done(inbound["provider_message_id"])
                return f"[RAG {button_id}] {msg_id}"
            
            # Items de lista de obras sociales (os_*)
            if button_id.startswith("os_"):
                query = _rag_query_for_button(button_id, button_title)
                msg_id = self._send_rag_answer(
                    inbound["id"], to_number, query, inbound["provider"], inbound["from_number"]
                )
                store.mark_inbound_done(inbound["provider_message_id"])
                return f"[RAG {button_id}] {msg_id}"
            
            # Items de lista de servicios (srv_*)
            if button_id.startswith("srv_"):
                query = _rag_query_for_button(button_id, button_title)
                msg_id = self._send_rag_answer(
                    inbound["id"], to_number, query, inbound["provider"], inbound["from_number"]
                )
                store.mark_inbound_done(inbound["provider_message_id"])
                return f"[RAG {button_id}] {msg_id}"
        
        # =====================================================================
        # 2. SALUDO EXPLÍCITO
        # =====================================================================
        if _is_greeting(text):
            msg_id = self._send_greeting_with_buttons(inbound["id"], to_number, inbound["provider"])
            store.mark_inbound_done(inbound["provider_message_id"])
            return f"[GREETING+BUTTONS] {msg_id}"

        # =====================================================================
        # 3. INTENCIONES GENÉRICAS (solo si NO fue un click de botón)
        # =====================================================================
        # Anti-loop: si ya enviamos una lista recientemente, no enviar otra
        if _is_about_insurance(text):
            if not self._was_last_outbound_a_list(inbound["from_number"], "insurance"):
                msg_id = self._send_insurance_list(inbound["id"], to_number, inbound["provider"])
                store.mark_inbound_done(inbound["provider_message_id"])
                return f"[INSURANCE LIST] {msg_id}"
            else:
                # Ya enviamos lista, ir al RAG directo
                query = f"Información sobre obra social: {text}"
                msg_id = self._send_rag_answer(
                    inbound["id"], to_number, query, inbound["provider"], inbound["from_number"]
                )
                store.mark_inbound_done(inbound["provider_message_id"])
                return f"[RAG insurance-fallback] {msg_id}"

        if _is_about_services(text):
            if not self._was_last_outbound_a_list(inbound["from_number"], "services"):
                msg_id = self._send_services_list(inbound["id"], to_number, inbound["provider"])
                store.mark_inbound_done(inbound["provider_message_id"])
                return f"[SERVICES LIST] {msg_id}"
            else:
                query = f"Información sobre servicio: {text}"
                msg_id = self._send_rag_answer(
                    inbound["id"], to_number, query, inbound["provider"], inbound["from_number"]
                )
                store.mark_inbound_done(inbound["provider_message_id"])
                return f"[RAG services-fallback] {msg_id}"

        # =====================================================================
        # 4. RAG NORMAL (cualquier otra pregunta)
        # =====================================================================
        msg_id = self._send_rag_answer(
            inbound["id"], to_number, text, inbound["provider"], inbound["from_number"]
        )
        
        if msg_id.startswith("[ERROR"):
            store.mark_inbound_failed(inbound["provider_message_id"], msg_id)
            return msg_id
        else:
            store.mark_inbound_done(inbound["provider_message_id"])
            return msg_id

    def send_manual_reply(self, phone_number: str, body: str) -> str:
        to_number = normalize_phone_for_meta(phone_number)
        outbound_id = store.create_outbound_message(
            inbound_message_id=None,
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
