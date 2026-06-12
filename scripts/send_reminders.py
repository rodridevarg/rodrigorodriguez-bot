"""
Sistema de recordatorios de turnos.

Este script se ejecuta periódicamente (ej: cada hora) para enviar recordatorios
de turnos que están próximos a ocurrir.

Uso:
    python scripts/send_reminders.py

Configuración en .env:
    REMINDERS_ENABLED=true
    REMINDER_HOURS_BEFORE=24
    REMINDER_CONFIRMATION_REQUIRED=true
"""

import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from datetime import datetime, timedelta, timezone
from app.db import get_connection
from app.config import (
    REMINDERS_ENABLED, 
    REMINDER_HOURS_BEFORE,
    REMINDER_CONFIRMATION_REQUIRED,
    CONTACT_PHONE,
    BUSINESS_NAME
)
from app.calendar_service import get_turns_for_reminders
from app.whatsapp_sender import get_sender


def send_reminders():
    """Busca y envía recordatorios de turnos próximos."""
    
    if not REMINDERS_ENABLED:
        print("[REMINDERS] Sistema de recordatorios deshabilitado.")
        return
    
    print(f"[REMINDERS] Buscando turnos para recordar ({REMINDER_HOURS_BEFORE}hs antes)...")
    
    # Obtener turnos desde Google Calendar
    turns = get_turns_for_reminders(REMINDER_HOURS_BEFORE)
    
    if not turns:
        print("[REMINDERS] No hay turnos para recordar.")
        return
    
    sender = get_sender()
    sent_count = 0
    
    for turn in turns:
        try:
            phone = turn.get('phone', '')
            if not phone:
                continue
            
            # Verificar si ya se envió recordatorio
            event_id = turn.get('id', '')
            with get_connection() as conn:
                cur = conn.execute(
                    """SELECT 1 FROM confirmed_turnos 
                       WHERE google_event_id = ? AND reminder_sent = 1""",
                    (event_id,)
                )
                if cur.fetchone():
                    continue
            
            # Parsear fecha/hora
            start_str = turn.get('start', '')
            start_dt = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
            start_dt = start_dt.astimezone(timezone(timedelta(hours=-3)))
            
            date_str = start_dt.strftime('%d/%m/%Y')
            time_str = start_dt.strftime('%H:%M')
            
            # Extraer nombre del servicio del summary
            summary = turn.get('summary', '')
            service_name = 'tu turno'
            if ' - ' in summary:
                service_name = summary.split(' - ')[0].replace('Turno: ', '')
            
            # Construir mensaje
            body = (
                f"⏰ *Recordatorio de turno*\n\n"
                f"Hola! Te recordamos que mañana ({date_str}) a las {time_str} "
                f"tenés tu {service_name}.\n\n"
            )
            
            if REMINDER_CONFIRMATION_REQUIRED:
                body += (
                    f"¿Confirmás que venís? Respondé *Sí* para confirmar.\n\n"
                    f"Si no podés asistir, por favor avisanos para liberar el lugar."
                )
            else:
                body += f"¡Te esperamos! 🎉"
            
            if CONTACT_PHONE:
                body += f"\n\n📞 {CONTACT_PHONE}"
            
            # Enviar mensaje
            result = sender.send_text(phone, body)
            
            if result.get('message_id'):
                # Marcar como enviado
                with get_connection() as conn:
                    conn.execute(
                        """UPDATE confirmed_turnos 
                           SET reminder_sent = 1, reminder_sent_at = ?
                           WHERE google_event_id = ?""",
                        (datetime.now().isoformat(), event_id)
                    )
                    conn.commit()
                sent_count += 1
                print(f"[REMINDERS] Enviado a {phone} para {date_str} {time_str}")
            
        except Exception as e:
            print(f"[ERROR] Error enviando recordatorio: {e}")
            continue
    
    print(f"[REMINDERS] Completado. {sent_count} recordatorios enviados.")


if __name__ == "__main__":
    send_reminders()
