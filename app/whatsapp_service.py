import re
import traceback
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, List, Any
from app.config import (
    CONVERSATION_MEMORY_MAX_TURNS,
    HANDOFF_TRANSITION_MESSAGE,
    CONTACT_PHONE,
    FALLBACK_MESSAGE,
    BUSINESS_ADDRESS,
    BUSINESS_NAME,
    REMINDERS_ENABLED,
    REMINDER_HOURS_BEFORE,
)
from app.rag_service import answer_question
from app.whatsapp_models import InboundTextMessage
from app.whatsapp_store import store
from app.whatsapp_sender import get_sender
from app.service_config import service_config
from app.db import get_connection

# Importar servicio de calendario (si está disponible)
try:
    from app.calendar_service import (
        get_available_slots,
        create_turn,
        cancel_turn,
        get_turns_by_phone,
        is_calendar_configured,
    )
    CALENDAR_AVAILABLE = True
except ImportError:
    CALENDAR_AVAILABLE = False


# ============================
# HELPERS
# ============================

def normalize_phone_for_meta(phone: str) -> str:
    phone = phone.strip().replace("+", "")
    if phone.startswith("549") and len(phone) == 13:
        return "54" + phone[3:]
    return phone


def _is_greeting(text: str) -> bool:
    greetings = ["hola", "buenas", "buen dia", "buen día", "buenas tardes", "buenas noches", "hey", "hi", "hello", "que tal", "qué tal"]
    clean = text.lower().strip()
    return any(clean.startswith(g) for g in greetings) or clean in ["hola", "buenas"]


def _is_about_turno(text: str) -> bool:
    keywords = [
        "turno", "turnos", "cita", "agendar", "sacar", "reservar", "disponibilidad", 
        "horario", "hora", "quiero ir", "quiero irme", "quiero atenderme", "quiero hacerme",
        "quiero un masaje", "quiero una limpieza", "quiero una manicura", "quiero una pedicura",
        "quiero depilarme", "quiero relajarme", "quiero una sesion", "quiero una sesión",
        "necesito un turno", "necesito una cita", "necesito agendar", "necesito reservar"
    ]
    clean = text.lower()
    return any(k in clean for k in keywords)


def _is_about_cancel(text: str) -> bool:
    keywords = ["cancelar", "cancelo", "cancela", "borrar", "eliminar", "anular", "quitar"]
    clean = text.lower()
    return any(k in clean for k in keywords)


def _is_about_reschedule(text: str) -> bool:
    keywords = ["cambiar", "reprogramar", "mover", "otro dia", "otro día", "otra fecha", "otro horario", "cambio"]
    clean = text.lower()
    return any(k in clean for k in keywords)


def _is_about_list_turns(text: str) -> bool:
    keywords = ["mis turnos", "ver turnos", "listar", "turnos que tengo", "cuando tengo", "que turnos"]
    clean = text.lower()
    return any(k in clean for k in keywords)


def _is_about_services(text: str) -> bool:
    keywords = [
        "servicio", "servicios", "tratamiento", "tratamientos", "masaje", "masajes",
        "facial", "faciales", "corporal", "corporales", "spa", "spa day",
        "depilacion", "depilación", "unas", "uñas", "manicura", "pedicura",
        "limpieza", "hidratacion", "hidratación", "radiofrecuencia", "dermaplaning",
        "exfoliacion", "exfoliación", "envoltura", "velashape", "criolipolisis",
        "esmaltado", "semipermanente", "laser", "láser", "piedras", "calientes"
    ]
    clean = text.lower()
    return any(k in clean for k in keywords)


def _is_about_precios(text: str) -> bool:
    keywords = ["precio", "precios", "costo", "cuesta", "cuanto", "cuánto", "valor", "descuento", "promocion", "promoción", "oferta"]
    clean = text.lower()
    return any(k in clean for k in keywords)


def _is_about_ubicacion(text: str) -> bool:
    keywords = ["direccion", "dirección", "ubicacion", "ubicación", "donde", "dónde", "como llegar", "cómo llegar", "dire", "santa fe", "dirección", "calle"]
    clean = text.lower()
    return any(k in clean for k in keywords)


def _is_menu_return_request(text: str) -> bool:
    """Detecta si el usuario quiere volver al menú principal."""
    keywords = ["menu", "menú", "volver", "inicio", "principal", "atras", "atrás", "0)"]
    clean = text.lower().strip()
    return any(k in clean for k in keywords) or clean == "0" or clean == "z"


def _handle_menu_return_request(service, inbound_id: int, to_number: str, text: str, provider: str, from_number: str, current_step: str) -> Optional[str]:
    """
    Maneja la solicitud de volver al menú principal.
    Si el usuario confirma, vuelve al menú. Si no, vuelve al paso anterior.
    """
    if _is_menu_return_request(text) and current_step != "confirm_menu_return":
        _save_turno_state(
            from_number, "confirm_menu_return",
            previous_step=current_step,
            client_phone=from_number
        )
        body = (
            "¿Deseás volver al menú principal?\n\n"
            "Responde *Sí* para volver o *No* para continuar."
        )
        return service._send_outbound(inbound_id, to_number, body, provider)
    return None


def _parse_button_click(text: str) -> Tuple[Optional[str], Optional[str]]:
    """Detecta si el texto es un click de botón/lista interactiva."""
    match = re.match(r'^\[(\w+)\]\s*(.+)$', text.strip())
    if match:
        return match.group(1), match.group(2).strip()
    return None, None


def _detect_date(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Detecta fecha en el texto. Retorna (YYYY-MM-DD, mensaje_error) o (None, None).
    """
    text_lower = text.lower().strip()
    now = datetime.now()
    
    # Hoy
    if "hoy" in text_lower:
        return now.strftime('%Y-%m-%d'), None
    
    # Mañana
    if "mañana" in text_lower or "manana" in text_lower:
        return (now + timedelta(days=1)).strftime('%Y-%m-%d'), None
    
    # Pasado mañana
    if "pasado mañana" in text_lower or "pasado manana" in text_lower:
        return (now + timedelta(days=2)).strftime('%Y-%m-%d'), None
    
    # Buscar patrones de fecha: 11/06, 11-06, 11/6
    match = re.search(r'(\d{1,2})[\/-](\d{1,2})(?:[\/-](\d{4}))?', text_lower)
    if match:
        day = int(match.group(1))
        month = int(match.group(2))
        year = int(match.group(3)) if match.group(3) else now.year
        
        # Si el mes ya pasó este año, asumir año siguiente
        if month < now.month and year == now.year:
            year += 1
        
        try:
            date = datetime(year, month, day)
            return date.strftime('%Y-%m-%d'), None
        except ValueError:
            return None, "No entendí esa fecha. ¿Podés usar formato DD/MM?"
    
    # Buscar nombres de días
    dias_map = {
        "lunes": 0, "martes": 1, "miércoles": 2, "miercoles": 2, 
        "jueves": 3, "viernes": 4, "sábado": 5, "sabado": 5, "domingo": 6
    }
    
    for dia, dia_num in dias_map.items():
        if dia in text_lower:
            today = now.weekday()
            days_ahead = (dia_num - today) % 7
            if days_ahead == 0:
                days_ahead = 7  # Próxima semana
            target = now + timedelta(days=days_ahead)
            return target.strftime('%Y-%m-%d'), None
    
    return None, None


def _detect_time(text: str, available_slots: List[str] = None) -> Optional[str]:
    """
    Detecta hora en el texto. Puede ser directa (10:00) o letra (a, b, c).
    """
    text_lower = text.lower().strip()
    
    # Si hay slots disponibles, buscar letra (a, b, c)
    if available_slots:
        # Buscar una sola letra que coincida con opciones
        match = re.match(r'^([a-z])\)?$', text_lower)
        if match:
            letter = match.group(1)
            index = ord(letter) - ord('a')
            if 0 <= index < len(available_slots):
                return available_slots[index]
    
    # Buscar patrones de hora: 10:00, 14:30
    match = re.search(r'(\d{1,2}):(\d{2})', text_lower)
    if match:
        return f"{int(match.group(1)):02d}:{match.group(2)}"
    
    # Buscar solo hora: "10", "14hs", "a las 10"
    match = re.search(r'(?:a\s+las\s+)?(\d{1,2})\s*(?:hs|hrs|horas|h)?', text_lower)
    if match:
        hour = int(match.group(1))
        if 6 <= hour <= 23:
            return f"{hour:02d}:00"
    
    return None


def _is_confirmacion(text: str) -> bool:
    text_lower = text.lower().strip()
    confirmaciones = ["si", "sí", "confirmo", "dale", "ok", "perfecto", "bueno", "esta bien", "está bien", "de acuerdo", "agree", "yes", "yep", "va", "va bien", "buenísimo", "genial"]
    return any(c in text_lower for c in confirmaciones)


def _is_cancelacion(text: str) -> bool:
    text_lower = text.lower().strip()
    cancelaciones = ["no", "cancelar", "cancelo", "nope", "nop", "otro", "diferente", "cambiar", "paso", "paso por ahora", "después", "despues", "luego"]
    return any(c in text_lower for c in cancelaciones)


def _is_menu_request(text: str) -> bool:
    return text.lower().strip() in ["menu", "menú", "opciones", "ayuda", "help", "?", "qué puedo hacer", "que puedo hacer"]


# ============================
# PERSISTENCIA EN SQLITE
# ============================

def _get_turno_state(phone: str) -> Optional[Dict[str, Any]]:
    """Obtiene el estado del flujo de turnos desde SQLite."""
    try:
        with get_connection() as conn:
            cur = conn.execute(
                """SELECT * FROM turno_flow_states WHERE phone_number = ?""",
                (phone,)
            )
            row = cur.fetchone()
            if row:
                # Verificar si expiró
                expires = datetime.fromisoformat(row['expires_at'])
                if datetime.now() > expires:
                    _clear_turno_state(phone)
                    return None
                return dict(row)
            return None
    except Exception as e:
        print(f"[ERROR] _get_turno_state: {e}")
        return None


def _save_turno_state(phone: str, step: str, **kwargs):
    """Guarda el estado del flujo de turnos en SQLite."""
    try:
        expires = datetime.now() + timedelta(minutes=10)
        
        with get_connection() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO turno_flow_states 
                   (phone_number, step, date, time, service_id, service_name, 
                    duration_minutes, client_name, client_phone, cancel_turno_id, updated_at, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    phone,
                    step,
                    kwargs.get('date', ''),
                    kwargs.get('time', ''),
                    kwargs.get('service_id', ''),
                    kwargs.get('service_name', ''),
                    kwargs.get('duration_minutes', 0),
                    kwargs.get('client_name', ''),
                    kwargs.get('client_phone', ''),
                    kwargs.get('cancel_turno_id', None),
                    datetime.now().isoformat(),
                    expires.isoformat()
                )
            )
            conn.commit()
    except Exception as e:
        print(f"[ERROR] _save_turno_state: {e}")


def _clear_turno_state(phone: str):
    """Limpia el estado del flujo de turnos."""
    try:
        with get_connection() as conn:
            conn.execute("DELETE FROM turno_flow_states WHERE phone_number = ?", (phone,))
            conn.commit()
    except Exception as e:
        print(f"[ERROR] _clear_turno_state: {e}")


def _save_confirmed_turno(phone: str, client_name: str, service_name: str, 
                         date: str, time: str, duration: int, google_event_id: str = ""):
    """Guarda un turno confirmado en SQLite."""
    try:
        with get_connection() as conn:
            conn.execute(
                """INSERT INTO confirmed_turnos 
                   (phone_number, client_name, service_name, date, time, 
                    duration_minutes, google_event_id, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'confirmed')""",
                (phone, client_name, service_name, date, time, duration, google_event_id)
            )
            conn.commit()
    except Exception as e:
        print(f"[ERROR] _save_confirmed_turno: {e}")


def _get_confirmed_turnos(phone: str) -> List[Dict[str, Any]]:
    """Obtiene los turnos confirmados de un cliente."""
    try:
        with get_connection() as conn:
            cur = conn.execute(
                """SELECT * FROM confirmed_turnos 
                   WHERE phone_number = ? AND status = 'confirmed'
                   ORDER BY date, time""",
                (phone,)
            )
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f"[ERROR] _get_confirmed_turnos: {e}")
        return []


def _cancel_turno_db(phone: str, turno_id: int):
    """Marca un turno como cancelado en SQLite."""
    try:
        with get_connection() as conn:
            conn.execute(
                """UPDATE confirmed_turnos 
                   SET status = 'cancelled', cancelled_at = ?
                   WHERE id = ? AND phone_number = ?""",
                (datetime.now().isoformat(), turno_id, phone)
            )
            conn.commit()
    except Exception as e:
        print(f"[ERROR] _cancel_turno_db: {e}")


# ============================
# VALIDACIONES
# ============================

def _validate_date(date_str: str) -> Tuple[bool, str]:
    """
    Valida que una fecha sea válida para turnos.
    Retorna (is_valid, mensaje_error).
    """
    try:
        date = datetime.strptime(date_str, '%Y-%m-%d')
        now = datetime.now()
        
        # No fechas pasadas
        if date.date() < now.date():
            return False, "No puedo agendar turnos en fechas pasadas. ¿Querés para hoy o mañana?"
        
        # No más de 60 días en el futuro
        if date > now + timedelta(days=60):
            return False, "Solo puedo agendar hasta 60 días en el futuro. ¿Querés una fecha más cercana?"
        
        # Verificar si es feriado
        if service_config.is_holiday(date_str):
            return False, "Ese día es feriado y estamos cerrados. ¿Querés otro día?"
        
        # Verificar si está abierto
        day_name = ['lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado', 'domingo'][date.weekday()]
        if not service_config.is_open(day_name):
            return False, f"Los {day_name} estamos cerrados. ¿Querés otro día?"
        
        return True, ""
    except Exception as e:
        return False, f"No entendí esa fecha. ¿Podés intentar con otra?"


def _validate_time(time_str: str, date_str: str) -> Tuple[bool, str]:
    """
    Valida que un horario sea válido.
    """
    try:
        date = datetime.strptime(date_str, '%Y-%m-%d')
        day_name = ['lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado', 'domingo'][date.weekday()]
        
        apertura, cierre = service_config.get_opening_hours(day_name)
        apertura_min = int(apertura.split(':')[0]) * 60 + int(apertura.split(':')[1])
        cierre_min = int(cierre.split(':')[0]) * 60 + int(cierre.split(':')[1])
        
        hour, minute = map(int, time_str.split(':'))
        time_min = hour * 60 + minute
        
        if time_min < apertura_min:
            return False, f"Abrimos a las {apertura}. ¿Querés a las {apertura}?"
        
        if time_min >= cierre_min:
            return False, f"Cerramos a las {cierre}. ¿Querés un horario antes?"
        
        # Si es hoy, verificar que no sea pasado
        if date.date() == datetime.now().date():
            now_min = datetime.now().hour * 60 + datetime.now().minute
            if time_min < now_min + 30:  # Mínimo 30 min de anticipación
                return False, "Necesito al menos 30 minutos de anticipación. ¿Querés un horario más tarde?"
        
        return True, ""
    except Exception as e:
        return False, "No entendí ese horario. ¿Podés decirlo de otra forma?"


# ============================
# FORMATO DE RESPUESTAS
# ============================

def _format_slots_with_letters(slots: List[str]) -> Tuple[str, List[str]]:
    """
    Formatea horarios con letras a/b/c/d.
    Retorna (texto, lista_ordenada).
    """
    lines = []
    for i, slot in enumerate(slots, 1):
        letter = chr(96 + i)  # a, b, c, d...
        lines.append(f"{letter}) {slot}")
    
    return "\n".join(lines), slots


def _format_services_menu() -> str:
    """Formatea el menú de servicios para selección."""
    services = service_config.get_all_services()
    if not services:
        return "No hay servicios configurados."
    
    by_category = service_config.get_services_by_category()
    lines = ["¿Qué servicio querés? Escribí el nombre o la letra:👇"]
    
    letter_idx = 0
    for category, cat_services in by_category.items():
        lines.append(f"\n*{category}*")
        for service in cat_services:
            letter = chr(97 + letter_idx)
            duration = service.get('duracion_minutos', 0)
            price = service.get('precio', 0)
            lines.append(f"{letter}) {service['nombre']} ({duration} min) - ${price:,}")
            letter_idx += 1
            if letter_idx >= 25:  # Dejar espacio para 'z' como volver al menú
                break
        if letter_idx >= 25:
            break
    
    lines.append(f"\nz) 🏠 Volver al menú principal")
    
    return "\n".join(lines)


# ============================
# WHATSAPP SERVICE
# ============================

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

    def _send_outbound(self, inbound_id: int, to_number: str, body: str, provider: str) -> str:
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

    def _send_interactive_buttons(self, inbound_id: int, to_number: str, body: str, buttons: list, provider: str) -> str:
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

    def _send_interactive_list(self, inbound_id: int, to_number: str, body: str, button_text: str, sections: list, provider: str) -> str:
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

    def _send_greeting_with_menu(self, inbound_id: int, to_number: str, provider: str) -> str:
        """Envia saludo con menu de texto numerado (1-7)."""
        body = (
            f"¡Hola! ✨ Soy Herminda, tu guía en {BUSINESS_NAME}.\n\n"
            f"¿En qué puedo ayudarte? 👇\n\n"
            f"1️⃣ Sacar turno\n"
            f"2️⃣ Ver servicios\n"
            f"3️⃣ Consultar precios\n"
            f"4️⃣ Cómo llegar\n"
            f"5️⃣ Mis turnos\n"
            f"6️⃣ Cancelar turno\n"
            f"7️⃣ Hablar con humano\n\n"
            f"Respondé con el número (1, 2, 3...)"
        )
        return self._send_outbound(inbound_id, to_number, body, provider)

    def _detect_menu_number(self, text: str) -> Optional[int]:
        """Detecta si el usuario eligio una opcion del menu (1-7)."""
        text_lower = text.lower().strip()
        # Buscar numero al inicio del mensaje
        match = re.match(r'^(\d+)', text_lower)
        if match:
            num = int(match.group(1))
            if 1 <= num <= 7:
                return num
        return None

    def _send_rag_answer(self, inbound_id: int, to_number: str, query: str, provider: str, from_number: str) -> str:
        history = store.get_conversation_history(from_number, limit=CONVERSATION_MEMORY_MAX_TURNS)
        result = answer_question(query, conversation_history=history)
        answer = result["answer"]
        if not result["sources"]:
            answer = FALLBACK_MESSAGE
            if CONTACT_PHONE:
                answer += f" WhatsApp: {CONTACT_PHONE}"
        return self._send_outbound(inbound_id=inbound_id, to_number=to_number, body=answer, provider=provider)

    # =====================================================================
    # FLUJO DE TURNOS COMPLETO
    # =====================================================================

    def _check_turno_flow(self, inbound_id: int, to_number: str, text: str, provider: str, from_number: str) -> Optional[str]:
        """
        Gestiona el flujo de reserva de turnos.
        Retorna msg_id si procesó algo, None si no está en flujo.
        """
        
        # Verificar si el calendario está configurado
        calendar_ok = CALENDAR_AVAILABLE and is_calendar_configured()
        
        # Obtener estado actual
        state = _get_turno_state(from_number)
        
        # Si no hay estado activo, verificar si el texto inicia un flujo
        if not state:
            # Si menciona un servicio específico + fecha, iniciar flujo directo
            detected_service = service_config.find_service_by_keyword(text)
            detected_date, date_error = _detect_date(text)
            
            if detected_service and detected_date:
                is_valid, error_msg = _validate_date(detected_date)
                if not is_valid:
                    return self._send_outbound(inbound_id, to_number, error_msg, provider)
                
                # Iniciar flujo saltando a ask_time
                _save_turno_state(
                    from_number, "ask_time",
                    date=detected_date,
                    service_id=detected_service['id'],
                    service_name=detected_service['nombre'],
                    duration_minutes=detected_service['duracion_minutos'],
                    client_phone=from_number
                )
                return self._send_turno_time_options(inbound_id, to_number, provider, detected_date, detected_service['duracion_minutos'])
            
            # Si menciona un servicio, iniciar flujo
            if detected_service:
                _save_turno_state(
                    from_number, "ask_date",
                    service_id=detected_service['id'],
                    service_name=detected_service['nombre'],
                    duration_minutes=detected_service['duracion_minutos'],
                    client_phone=from_number
                )
                body = (
                    f"¡Perfecto! 🎉 Vamos a agendar tu {detected_service['nombre']}.\n\n"
                    f"¿Para qué día querés reservar?\n"
                    f"Podés decirme *hoy*, *mañana*, *pasado mañana*, o un día de la semana (*lunes*, *martes*, etc.)"
                )
                return self._send_outbound(inbound_id, to_number, body, provider)
            
            # Si el texto tiene intención de turno pero no especificó servicio
            if _is_about_turno(text):
                _save_turno_state(from_number, "ask_service", client_phone=from_number)
                body = _format_services_menu()
                return self._send_outbound(inbound_id, to_number, body, provider)
            
            return None
        
        # Hay un estado activo, procesar según el paso
        step = state.get("step", "ask_service")
        
        # Detectar solicitud de volver al menú principal
        menu_return = _handle_menu_return_request(self, inbound_id, to_number, text, provider, from_number, step)
        if menu_return:
            return menu_return
        
        if step == "ask_service":
            # Detectar servicio por nombre o keyword
            detected_service = service_config.find_service_by_keyword(text)
            
            # También buscar por letra si es respuesta a/b/c
            all_services = service_config.get_all_services()
            letter_match = re.match(r'^([a-z])\)?$', text.lower().strip())
            if letter_match and all_services:
                letter = letter_match.group(1)
                index = ord(letter) - ord('a')
                if 0 <= index < len(all_services):
                    detected_service = all_services[index]
            
            if detected_service:
                _save_turno_state(
                    from_number, "ask_date",
                    service_id=detected_service['id'],
                    service_name=detected_service['nombre'],
                    duration_minutes=detected_service['duracion_minutos'],
                    client_phone=from_number
                )
                body = (
                    f"¡Perfecto! 🎉 Vamos a agendar tu {detected_service['nombre']}.\n\n"
                    f"¿Para qué día querés reservar?\n"
                    f"Podés decirme *hoy*, *mañana*, *pasado mañana*, o un día de la semana."
                )
                return self._send_outbound(inbound_id, to_number, body, provider)
            else:
                # No reconoció el servicio, ofrecer opciones de nuevo
                body = (
                    f"No entendí qué servicio querés. Estas son las opciones:\n\n"
                    f"{_format_services_menu()}\n\n"
                    f"¿Cuál te gustaría?"
                )
                return self._send_outbound(inbound_id, to_number, body, provider)
        
        elif step == "ask_date":
            detected_date, date_error = _detect_date(text)
            if detected_date:
                is_valid, error_msg = _validate_date(detected_date)
                if not is_valid:
                    return self._send_outbound(inbound_id, to_number, error_msg, provider)
                
                _save_turno_state(
                    from_number, "ask_time",
                    date=detected_date,
                    service_id=state.get('service_id'),
                    service_name=state.get('service_name'),
                    duration_minutes=state.get('duration_minutes', 60),
                    client_phone=from_number
                )
                return self._send_turno_time_options(
                    inbound_id, to_number, provider, detected_date, 
                    state.get('duration_minutes', 60)
                )
            else:
                body = "No entendí la fecha. ¿Podés decirme *hoy*, *mañana*, o un día de la semana?"
                return self._send_outbound(inbound_id, to_number, body, provider)
        
        elif step == "ask_time":
            date = state.get('date')
            duration = state.get('duration_minutes', 60)
            
            # Obtener slots disponibles para validar
            day_name = ['lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado', 'domingo'][datetime.strptime(date, '%Y-%m-%d').weekday()]
            hours = service_config.get_hours_for_day(day_name)
            
            slots = get_available_slots(
                date, duration, 
                service_config.hours.get('dias', {}),
                service_config.get_interval()
            ) if calendar_ok else _generate_mock_slots(date, hours, duration)
            
            detected_time = _detect_time(text, slots)
            
            if detected_time:
                # Validar horario
                is_valid, error_msg = _validate_time(detected_time, date)
                if not is_valid:
                    return self._send_outbound(inbound_id, to_number, error_msg, provider)
                
                # Verificar disponibilidad
                if slots and detected_time not in slots:
                    body = (
                        f"El horario {detected_time} no está disponible. 😔\n\n"
                        f"Estos son los disponibles:\n"
                        f"{slots_text}\n\n"
                        f"¿Cuál preferís?"
                    )
                    return self._send_outbound(inbound_id, to_number, body, provider)
                
                _save_turno_state(
                    from_number, "ask_name",
                    date=date,
                    time=detected_time,
                    service_id=state.get('service_id'),
                    service_name=state.get('service_name'),
                    duration_minutes=duration,
                    client_phone=from_number
                )
                body = (
                    f"✅ ¡Perfecto! {date} a las {detected_time}.\n\n"
                    f"¿A nombre de quién hacemos la reserva?"
                )
                return self._send_outbound(inbound_id, to_number, body, provider)
            else:
                # No detectó hora, mostrar opciones de nuevo
                return self._send_turno_time_options(inbound_id, to_number, provider, date, duration)
        
        elif step == "ask_name":
            name = text.strip()
            if len(name) > 2:
                _save_turno_state(
                    from_number, "confirm",
                    date=state.get('date'),
                    time=state.get('time'),
                    service_id=state.get('service_id'),
                    service_name=state.get('service_name'),
                    duration_minutes=state.get('duration_minutes'),
                    client_name=name,
                    client_phone=from_number
                )
                
                service_name = state.get('service_name', '')
                date = state.get('date', '')
                time = state.get('time', '')
                duration = state.get('duration_minutes', 0)
                
                body = (
                    f"📋 *Resumen de tu turno:*\n\n"
                    f"📅 Fecha: {date}\n"
                    f"⏰ Hora: {time}\n"
                    f"💆 Servicio: {service_name} ({duration} min)\n"
                    f"👤 Nombre: {name}\n"
                )
                if BUSINESS_ADDRESS:
                    body += f"📍 {BUSINESS_ADDRESS}\n"
                body += (
                    f"\n¿Confirmamos? Responde *Sí* para confirmar o *No* para cambiar algo."
                )
                return self._send_outbound(inbound_id, to_number, body, provider)
            else:
                body = "¿Podés decirme tu nombre y apellido para la reserva?"
                return self._send_outbound(inbound_id, to_number, body, provider)
        
        elif step == "confirm":
            if _is_confirmacion(text):
                # Crear turno en Google Calendar
                result = create_turn(
                    date_str=state.get('date'),
                    time_str=state.get('time'),
                    client_name=state.get('client_name'),
                    client_phone=from_number,
                    service_name=state.get('service_name'),
                    duration_minutes=state.get('duration_minutes')
                )
                
                if result.get('success'):
                    # Guardar en SQLite
                    _save_confirmed_turno(
                        from_number,
                        state.get('client_name'),
                        state.get('service_name'),
                        state.get('date'),
                        state.get('time'),
                        state.get('duration_minutes'),
                        result.get('event_id', '')
                    )
                    
                    body = (
                        f"✅ *¡Turno confirmado!*\n\n"
                        f"📅 {state.get('date')} a las {state.get('time')}\n"
                        f"💆 {state.get('service_name')}\n"
                        f"👤 {state.get('client_name')}\n"
                    )
                    if BUSINESS_ADDRESS:
                        body += f"📍 {BUSINESS_ADDRESS}\n"
                    if CONTACT_PHONE:
                        body += f"📞 {CONTACT_PHONE}\n"
                    if REMINDERS_ENABLED:
                        body += f"\n⏰ Te enviaremos un recordatorio {REMINDER_HOURS_BEFORE} horas antes."
                    body += f"\n¡Te esperamos! 🎉"
                    
                    _clear_turno_state(from_number)
                    return self._send_outbound(inbound_id, to_number, body, provider)
                else:
                    body = (
                        f"Hubo un error al crear el turno: {result.get('error')}\n\n"
                        f"Por favor, contactanos por WhatsApp para completar la reserva."
                    )
                    _clear_turno_state(from_number)
                    return self._send_outbound(inbound_id, to_number, body, provider)
            
            elif _is_cancelacion(text):
                _clear_turno_state(from_number)
                body = "Turno cancelado. ¿Querés intentar de nuevo? Escribí *turno* cuando quieras."
                return self._send_outbound(inbound_id, to_number, body, provider)
            
            else:
                body = "¿Confirmamos el turno? Responde *Sí* o *No*."
                return self._send_outbound(inbound_id, to_number, body, provider)
        
        elif step == "confirm_cancel":
            if _is_confirmacion(text):
                turno_id = state.get('cancel_turno_id')
                if turno_id:
                    # Cancelar en DB
                    _cancel_turno_db(from_number, turno_id)
                    # Cancelar en Google Calendar si hay event_id
                    turnos = _get_confirmed_turnos(from_number)
                    turno_to_cancel = None
                    for t in turnos:
                        if t.get('id') == turno_id:
                            turno_to_cancel = t
                            break
                    if turno_to_cancel and turno_to_cancel.get('google_event_id'):
                        cancel_turn(turno_to_cancel['google_event_id'])
                    
                    _clear_turno_state(from_number)
                    body = "✅ Turno cancelado correctamente. ¿Necesitás algo más?"
                    return self._send_outbound(inbound_id, to_number, body, provider)
                else:
                    _clear_turno_state(from_number)
                    body = "No encontré el turno para cancelar. ¿Necesitás ayuda?"
                    return self._send_outbound(inbound_id, to_number, body, provider)
            elif _is_cancelacion(text):
                _clear_turno_state(from_number)
                body = "Cancelación descartada. ¿Necesitás algo más?"
                return self._send_outbound(inbound_id, to_number, body, provider)
            else:
                body = "¿Confirmamos la cancelación? Responde *Sí* o *No*."
                return self._send_outbound(inbound_id, to_number, body, provider)
        
        elif step == "select_cancel":
            turnos = _get_confirmed_turnos(from_number)
            if not turnos:
                _clear_turno_state(from_number)
                body = "No tenés turnos activos para cancelar."
                return self._send_outbound(inbound_id, to_number, body, provider)
            
            # Detectar selección por letra
            letter_match = re.match(r'^([a-z])\)?$', text.lower().strip())
            if letter_match:
                letter = letter_match.group(1)
                index = ord(letter) - ord('a')
                if 0 <= index < len(turnos):
                    turno = turnos[index]
                    _save_turno_state(
                        from_number, "confirm_cancel",
                        cancel_turno_id=turno['id']
                    )
                    body = (
                        f"¿Querés cancelar este turno?\n\n"
                        f"📅 {turno['date']} a las {turno['time']}\n"
                        f"💆 {turno['service_name']}\n\n"
                        f"Respondé *Sí* para confirmar la cancelación."
                    )
                    return self._send_outbound(inbound_id, to_number, body, provider)
            
            # Si no reconoció, mostrar opciones de nuevo
            lines = ["¿Qué turno querés cancelar?\n"]
            for i, turno in enumerate(turnos, 1):
                letter = chr(96 + i)
                lines.append(f"{letter}) {turno['date']} a las {turno['time']} - {turno['service_name']}")
            lines.append("\nRespondé con la letra del turno.")
            body = "\n".join(lines)
            return self._send_outbound(inbound_id, to_number, body, provider)
        
        elif step == "confirm_menu_return":
            if _is_confirmacion(text):
                _clear_turno_state(from_number)
                body = (
                    f"¡Hola! ✨ Bienvenido a {BUSINESS_NAME}.\n\n"
                    f"¿En qué puedo ayudarte hoy? 👇\n\n"
                    f"1️⃣ Sacar turno\n"
                    f"2️⃣ Ver servicios\n"
                    f"3️⃣ Consultar precios\n"
                    f"4️⃣ Cómo llegar\n"
                    f"5️⃣ Mis turnos\n"
                    f"6️⃣ Cancelar turno\n"
                    f"7️⃣ Hablar con humano\n\n"
                    f"Respondé con el número (1, 2, 3...)"
                )
                return self._send_outbound(inbound_id, to_number, body, provider)
            elif _is_cancelacion(text):
                # Volver al paso anterior
                previous_step = state.get('previous_step', 'ask_service')
                _save_turno_state(
                    from_number, previous_step,
                    date=state.get('date'),
                    time=state.get('time'),
                    service_id=state.get('service_id'),
                    service_name=state.get('service_name'),
                    duration_minutes=state.get('duration_minutes'),
                    client_name=state.get('client_name'),
                    client_phone=from_number
                )
                # Reenviar el mensaje del paso anterior
                if previous_step == "ask_service":
                    body = _format_services_menu()
                    return self._send_outbound(inbound_id, to_number, body, provider)
                elif previous_step == "ask_date":
                    body = (
                        f"¡Perfecto! 🎉 Vamos a agendar tu {state.get('service_name', '')}.\n\n"
                        f"¿Para qué día querés reservar?\n"
                        f"Podés decirme *hoy*, *mañana*, *pasado mañana*, o un día de la semana."
                    )
                    return self._send_outbound(inbound_id, to_number, body, provider)
                elif previous_step == "ask_time":
                    return self._send_turno_time_options(inbound_id, to_number, provider, state.get('date'), state.get('duration_minutes', 60))
                elif previous_step == "ask_name":
                    body = (
                        f"✅ ¡Perfecto! {state.get('date', '')} a las {state.get('time', '')}.\n\n"
                        f"¿A nombre de quién hacemos la reserva?"
                    )
                    return self._send_outbound(inbound_id, to_number, body, provider)
                elif previous_step == "confirm":
                    service_name = state.get('service_name', '')
                    date = state.get('date', '')
                    time = state.get('time', '')
                    duration = state.get('duration_minutes', 0)
                    name = state.get('client_name', '')
                    body = (
                        f"📋 *Resumen de tu turno:*\n\n"
                        f"📅 Fecha: {date}\n"
                        f"⏰ Hora: {time}\n"
                        f"💆 Servicio: {service_name} ({duration} min)\n"
                        f"👤 Nombre: {name}\n"
                    )
                    if BUSINESS_ADDRESS:
                        body += f"📍 {BUSINESS_ADDRESS}\n"
                    body += (
                        f"\n¿Confirmamos? Responde *Sí* para confirmar o *No* para cambiar algo."
                    )
                    return self._send_outbound(inbound_id, to_number, body, provider)
                elif previous_step == "select_cancel":
                    return self._handle_cancel_turno(inbound_id, to_number, text, provider, from_number)
                else:
                    body = _format_services_menu()
                    return self._send_outbound(inbound_id, to_number, body, provider)
            else:
                body = "¿Deseás volver al menú principal? Responde *Sí* o *No*."
                return self._send_outbound(inbound_id, to_number, body, provider)
        
        return None

    def _send_turno_time_options(self, inbound_id: int, to_number: str, provider: str, date: str, duration: int = 60) -> str:
        """Envía las opciones de horarios disponibles para una fecha."""
        
        calendar_ok = CALENDAR_AVAILABLE and is_calendar_configured()
        
        try:
            day_name = ['lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado', 'domingo'][datetime.strptime(date, '%Y-%m-%d').weekday()]
            hours = service_config.get_hours_for_day(day_name)
            
            if not hours.get('abierto', False):
                body = f"No atendemos los {day_name}. ¿Querés otro día?"
                return self._send_outbound(inbound_id, to_number, body, provider)
            
            if calendar_ok:
                slots = get_available_slots(
                    date, duration,
                    service_config.hours.get('dias', {}),
                    service_config.get_interval()
                )
            else:
                slots = _generate_mock_slots(date, hours, duration)
            
            if not slots:
                body = (
                    f"No hay horarios disponibles para {date}. 😔\n\n"
                    f"¿Querés probar con otro día?"
                )
                return self._send_outbound(inbound_id, to_number, body, provider)
            
            # Limitar a 8 opciones para no saturar
            display_slots = slots[:8]
            slots_text, ordered_slots = _format_slots_with_letters(display_slots)
            
            body = (
                f"📅 Horarios disponibles para {date}:\n\n"
                f"{slots_text}\n\n"
                f"z) 🏠 Volver al menú principal\n\n"
                f"¿Qué horario preferís? Respondé con la letra (a, b, c...) o la hora."
            )
            
            return self._send_outbound(inbound_id, to_number, body, provider)
        
        except Exception as e:
            print(f"[ERROR] _send_turno_time_options: {e}")
            body = "Hubo un error al buscar horarios. ¿Podés intentar con otra fecha?"
            return self._send_outbound(inbound_id, to_number, body, provider)

    # =====================================================================
    # CANCELAR TURNOS
    # =====================================================================

    def _handle_cancel_turno(self, inbound_id: int, to_number: str, text: str, provider: str, from_number: str) -> str:
        """Maneja la cancelación de turnos."""
        
        turnos = _get_confirmed_turnos(from_number)
        if not turnos:
            body = "No tenés turnos activos para cancelar."
            return self._send_outbound(inbound_id, to_number, body, provider)
        
        # Si tiene un solo turno, preguntar directo
        if len(turnos) == 1:
            turno = turnos[0]
            body = (
                f"¿Querés cancelar este turno?\n\n"
                f"📅 {turno['date']} a las {turno['time']}\n"
                f"💆 {turno['service_name']}\n\n"
                f"Respondé *Sí* para confirmar la cancelación."
            )
            # Guardar en estado que está esperando confirmación de cancelación
            _save_turno_state(
                from_number, "confirm_cancel",
                cancel_turno_id=turno['id']
            )
            return self._send_outbound(inbound_id, to_number, body, provider)
        
        # Si tiene varios, mostrar lista
        lines = ["¿Qué turno querés cancelar?\n"]
        for i, turno in enumerate(turnos, 1):
            letter = chr(96 + i)
            lines.append(f"{letter}) {turno['date']} a las {turno['time']} - {turno['service_name']}")
        lines.append("\nz) 🏠 Volver al menú principal")
        lines.append("\nRespondé con la letra del turno.")
        
        body = "\n".join(lines)
        _save_turno_state(from_number, "select_cancel")
        return self._send_outbound(inbound_id, to_number, body, provider)

    # =====================================================================
    # LISTAR TURNOS
    # =====================================================================

    def _handle_list_turnos(self, inbound_id: int, to_number: str, provider: str, from_number: str) -> str:
        """Muestra los turnos del cliente."""
        
        turnos = _get_confirmed_turnos(from_number)
        if not turnos:
            body = "No tenés turnos agendados. ¿Querés sacar uno? Escribí *turno*."
            return self._send_outbound(inbound_id, to_number, body, provider)
        
        lines = ["Estos son tus turnos confirmados:\n"]
        for i, turno in enumerate(turnos, 1):
            lines.append(f"{i}. 📅 {turno['date']} a las {turno['time']} - {turno['service_name']}")
        
        body = "\n".join(lines)
        return self._send_outbound(inbound_id, to_number, body, provider)

    # =====================================================================
    # MAIN PROCESSOR
    # =====================================================================

    def process_inbound_by_id(self, inbound_id: int) -> str:
        inbound = store.get_inbound_by_id(inbound_id)
        if not inbound:
            return "[ERROR: inbound no encontrado]"

        if inbound["processing_status"] != "pending":
            return f"[SKIP: estado={inbound['processing_status']}]"

        store.mark_inbound_processing(inbound["provider_message_id"])

        to_number = normalize_phone_for_meta(inbound["from_number"])
        text = inbound["text"]
        from_number = inbound["from_number"]

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
        # 1. DETECTAR CLICK DE BOTÓN (formato antiguo [id] Título)
        # =====================================================================
        button_id, button_title = _parse_button_click(text)
        
        if button_id:
            if button_id == "btn_turno":
                _save_turno_state(from_number, "ask_service", client_phone=from_number)
                body = _format_services_menu()
                store.mark_inbound_done(inbound["provider_message_id"])
                return f"[TURNO FLOW] {self._send_outbound(inbound['id'], to_number, body, inbound['provider'])}"
            
            if button_id == "btn_servicios":
                body = _format_services_menu()
                store.mark_inbound_done(inbound["provider_message_id"])
                return f"[SERVICES] {self._send_outbound(inbound['id'], to_number, body, inbound['provider'])}"
            
            if button_id == "btn_precios":
                query = "¿Cuánto cuestan los tratamientos y servicios?"
                store.mark_inbound_done(inbound["provider_message_id"])
                return f"[RAG precios] {self._send_rag_answer(inbound['id'], to_number, query, inbound['provider'], from_number)}"
        
        # =====================================================================
        # 2. DETECTAR NÚMERO DE MENÚ (1-7)
        # =====================================================================
        menu_num = self._detect_menu_number(text)
        if menu_num:
            if menu_num == 1:  # Sacar turno
                _save_turno_state(from_number, "ask_service", client_phone=from_number)
                body = _format_services_menu()
                store.mark_inbound_done(inbound["provider_message_id"])
                return f"[TURNO FLOW] {self._send_outbound(inbound['id'], to_number, body, inbound['provider'])}"
            
            if menu_num == 2:  # Ver servicios
                body = _format_services_menu()
                store.mark_inbound_done(inbound["provider_message_id"])
                return f"[SERVICES] {self._send_outbound(inbound['id'], to_number, body, inbound['provider'])}"
            
            if menu_num == 3:  # Consultar precios
                query = "¿Cuánto cuestan los tratamientos y servicios?"
                store.mark_inbound_done(inbound["provider_message_id"])
                return f"[RAG precios] {self._send_rag_answer(inbound['id'], to_number, query, inbound['provider'], from_number)}"
            
            if menu_num == 4:  # Cómo llegar
                query = "¿Dónde queda? ¿Cuál es la dirección?"
                store.mark_inbound_done(inbound["provider_message_id"])
                return f"[RAG ubicacion] {self._send_rag_answer(inbound['id'], to_number, query, inbound['provider'], from_number)}"
            
            if menu_num == 5:  # Mis turnos
                return f"[LIST] {self._handle_list_turnos(inbound['id'], to_number, inbound['provider'], from_number)}"
            
            if menu_num == 6:  # Cancelar turno
                return f"[CANCEL] {self._handle_cancel_turno(inbound['id'], to_number, text, inbound['provider'], from_number)}"
            
            if menu_num == 7:  # Hablar con humano
                # Simular handoff
                body = HANDOFF_TRANSITION_MESSAGE
                store.mark_inbound_done(inbound["provider_message_id"])
                return f"[HANDOFF] {self._send_outbound(inbound['id'], to_number, body, inbound['provider'])}"
        
        # =====================================================================
        # 3. MENÚ RÁPIDO (texto)
        # =====================================================================
        if _is_menu_request(text):
            body = (
                f"¿En qué puedo ayudarte? 👇\n\n"
                f"1️⃣ Sacar turno\n"
                f"2️⃣ Ver servicios\n"
                f"3️⃣ Consultar precios\n"
                f"4️⃣ Cómo llegar\n"
                f"5️⃣ Mis turnos\n"
                f"6️⃣ Cancelar turno\n"
                f"7️⃣ Hablar con humano\n\n"
                f"Respondé con el número (1, 2, 3...)"
            )
            store.mark_inbound_done(inbound["provider_message_id"])
            return f"[MENU] {self._send_outbound(inbound['id'], to_number, body, inbound['provider'])}"

        # =====================================================================
        # 3. FLUJO DE TURNOS
        # =====================================================================
        # Verificar si estamos en medio de un flujo de turno
        turno_response = self._check_turno_flow(
            inbound["id"], to_number, text, inbound["provider"], inbound["from_number"]
        )
        if turno_response:
            store.mark_inbound_done(inbound["provider_message_id"])
            return f"[TURNO FLOW] {turno_response}"
        
        # =====================================================================
        # 4. CANCELAR TURNOS
        # =====================================================================
        if _is_about_cancel(text) or _is_about_reschedule(text):
            return f"[CANCEL] {self._handle_cancel_turno(inbound['id'], to_number, text, inbound['provider'], from_number)}"
        
        # =====================================================================
        # 5. LISTAR TURNOS
        # =====================================================================
        if _is_about_list_turns(text):
            return f"[LIST] {self._handle_list_turnos(inbound['id'], to_number, inbound['provider'], from_number)}"

        # =====================================================================
        # 6. SALUDO EXPLÍCITO
        # =====================================================================
        if _is_greeting(text):
            msg_id = self._send_greeting_with_menu(inbound["id"], to_number, inbound["provider"])
            store.mark_inbound_done(inbound["provider_message_id"])
            return f"[GREETING+MENU] {msg_id}"

        # =====================================================================
        # 7. INTENCIONES GENÉRICAS
        # =====================================================================
        if _is_about_services(text):
            body = _format_services_menu()
            store.mark_inbound_done(inbound["provider_message_id"])
            return f"[SERVICES] {self._send_outbound(inbound['id'], to_number, body, inbound['provider'])}"

        if _is_about_precios(text):
            query = "¿Cuánto cuestan los tratamientos y servicios?"
            store.mark_inbound_done(inbound["provider_message_id"])
            return f"[RAG precios] {self._send_rag_answer(inbound['id'], to_number, query, inbound['provider'], from_number)}"

        if _is_about_ubicacion(text):
            query = "¿Dónde queda? ¿Cuál es la dirección?"
            store.mark_inbound_done(inbound["provider_message_id"])
            return f"[RAG ubicacion] {self._send_rag_answer(inbound['id'], to_number, query, inbound['provider'], from_number)}"

        # =====================================================================
        # 8. RAG NORMAL
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


# ============================
# HELPERS ADICIONALES
# ============================

def _generate_mock_slots(date_str: str, hours: Dict, duration: int) -> List[str]:
    """Genera slots simulados cuando no hay Google Calendar."""
    if not hours.get('abierto', False):
        return []
    
    apertura = hours.get('apertura', '10:00')
    cierre = hours.get('cierre', '20:00')
    
    start_hour = int(apertura.split(':')[0])
    start_min = int(apertura.split(':')[1])
    end_hour = int(cierre.split(':')[0])
    end_min = int(cierre.split(':')[1])
    
    slots = []
    current_min = start_hour * 60 + start_min
    end_min_total = end_hour * 60 + end_min
    
    while current_min + duration <= end_min_total:
        h = current_min // 60
        m = current_min % 60
        slots.append(f"{h:02d}:{m:02d}")
        current_min += 30  # intervalo fijo
    
    return slots


whatsapp_service = WhatsAppService()
