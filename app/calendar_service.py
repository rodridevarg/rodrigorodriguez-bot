import os
import json
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Any

# Google Calendar imports
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False

from app.config import GOOGLE_CALENDAR_ID, GOOGLE_SERVICE_ACCOUNT_JSON

# Scopes para Google Calendar
SCOPES = ['https://www.googleapis.com/auth/calendar']


def get_calendar_service():
    """Crea el servicio de Google Calendar con Service Account."""
    if not GOOGLE_AVAILABLE:
        print("[WARN] google-api-python-client no instalado. Calendar deshabilitado.")
        return None
    
    if not GOOGLE_SERVICE_ACCOUNT_JSON or not GOOGLE_CALENDAR_ID:
        print("[WARN] GOOGLE_SERVICE_ACCOUNT_JSON o GOOGLE_CALENDAR_ID no configurados.")
        return None
    
    try:
        # Si es un string JSON, parsearlo
        if GOOGLE_SERVICE_ACCOUNT_JSON.startswith('{'):
            credentials_info = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
        else:
            # Es un path a un archivo
            with open(GOOGLE_SERVICE_ACCOUNT_JSON, 'r') as f:
                credentials_info = json.load(f)
        
        credentials = service_account.Credentials.from_service_account_info(
            credentials_info, scopes=SCOPES)
        
        service = build('calendar', 'v3', credentials=credentials)
        return service
    except Exception as e:
        print(f"[ERROR] No se pudo crear servicio de Google Calendar: {e}")
        return None


def get_available_slots(date_str: str, duration_minutes: int = 60, opening_hours: Dict = None, interval_minutes: int = 30) -> List[str]:
    """
    Obtiene los horarios disponibles para una fecha específica.
    
    Args:
        date_str: Fecha en formato 'YYYY-MM-DD'
        duration_minutes: Duración del turno en minutos
        opening_hours: Dict con horarios de apertura (ej: {'lunes': {'apertura': '10:00', 'cierre': '20:00', 'abierto': True}})
        interval_minutes: Intervalo entre turnos (ej: 30 para 10:00, 10:30, 11:00)
    
    Returns:
        Lista de horarios disponibles en formato 'HH:00'
    """
    service = get_calendar_service()
    
    # Si no hay Google Calendar configurado, devolver horarios por defecto basados en opening_hours
    if not service:
        return _generate_default_slots(date_str, duration_minutes, opening_hours, interval_minutes)
    
    try:
        # Convertir fecha string a datetime
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # Obtener horarios del día
        day_name = ['lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado', 'domingo'][date.weekday()]
        
        if not opening_hours or day_name not in opening_hours:
            return []
        
        day_config = opening_hours[day_name]
        if not day_config.get('abierto', True):
            return []  # Cerrado
        
        start_hour = int(day_config['apertura'].split(':')[0])
        start_minute = int(day_config['apertura'].split(':')[1])
        end_hour = int(day_config['cierre'].split(':')[0])
        end_minute = int(day_config['cierre'].split(':')[1])
        
        # Crear rangos de tiempo para consultar eventos
        start_datetime = datetime.combine(date, datetime.min.time().replace(hour=start_hour, minute=start_minute))
        end_datetime = datetime.combine(date, datetime.min.time().replace(hour=end_hour, minute=end_minute))
        
        # Agregar timezone (UTC-3 para Argentina)
        tz = timezone(timedelta(hours=-3))
        start_datetime = start_datetime.replace(tzinfo=tz)
        end_datetime = end_datetime.replace(tzinfo=tz)
        
        # Consultar eventos existentes
        events_result = service.events().list(
            calendarId=GOOGLE_CALENDAR_ID,
            timeMin=start_datetime.isoformat(),
            timeMax=end_datetime.isoformat(),
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        # Horarios ocupados (como sets de minutos desde medianoche)
        occupied_ranges = []
        for event in events:
            start = event['start'].get('dateTime')
            end = event['end'].get('dateTime')
            if start and end:
                start_dt = datetime.fromisoformat(start.replace('Z', '+00:00')).astimezone(tz)
                end_dt = datetime.fromisoformat(end.replace('Z', '+00:00')).astimezone(tz)
                start_minutes = start_dt.hour * 60 + start_dt.minute
                end_minutes = end_dt.hour * 60 + end_dt.minute
                occupied_ranges.append((start_minutes, end_minutes))
        
        # Generar horarios disponibles
        available_slots = []
        current_minutes = start_hour * 60 + start_minute
        end_minutes = end_hour * 60 + end_minute
        
        while current_minutes + duration_minutes <= end_minutes:
            # Verificar si este slot está ocupado
            is_occupied = False
            for occ_start, occ_end in occupied_ranges:
                # Hay overlap si: (start < occ_end) y (end > occ_start)
                slot_end = current_minutes + duration_minutes
                if current_minutes < occ_end and slot_end > occ_start:
                    is_occupied = True
                    break
            
            if not is_occupied:
                hour = current_minutes // 60
                minute = current_minutes % 60
                available_slots.append(f"{hour:02d}:{minute:02d}")
            
            current_minutes += interval_minutes
        
        return available_slots
    
    except Exception as e:
        print(f"[ERROR] Error al obtener horarios disponibles: {e}")
        return []


def _generate_default_slots(date_str: str, duration_minutes: int, opening_hours: Dict, interval_minutes: int) -> List[str]:
    """Genera slots por defecto sin Google Calendar."""
    try:
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        day_name = ['lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado', 'domingo'][date.weekday()]
        
        if not opening_hours or day_name not in opening_hours:
            return []
        
        day_config = opening_hours[day_name]
        if not day_config.get('abierto', True):
            return []
        
        start_hour = int(day_config['apertura'].split(':')[0])
        start_minute = int(day_config['apertura'].split(':')[1])
        end_hour = int(day_config['cierre'].split(':')[0])
        end_minute = int(day_config['cierre'].split(':')[1])
        
        available_slots = []
        current_minutes = start_hour * 60 + start_minute
        end_minutes = end_hour * 60 + end_minute
        
        while current_minutes + duration_minutes <= end_minutes:
            hour = current_minutes // 60
            minute = current_minutes % 60
            available_slots.append(f"{hour:02d}:{minute:02d}")
            current_minutes += interval_minutes
        
        return available_slots
    except Exception as e:
        print(f"[ERROR] Error al generar slots por defecto: {e}")
        return []


def create_turn(
    date_str: str,
    time_str: str,
    client_name: str,
    client_phone: str,
    service_name: str,
    duration_minutes: int = 60,
    notes: str = ""
) -> Dict[str, Any]:
    """
    Crea un turno (evento) en Google Calendar.
    
    Returns:
        Dict con 'success' (bool), 'event_id', 'event_link' o 'error'
    """
    service = get_calendar_service()
    if not service:
        return {
            'success': False,
            'error': 'Google Calendar no está configurado. Contacta al administrador.'
        }
    
    try:
        # Parsear fecha y hora
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        hour, minute = map(int, time_str.split(':'))
        
        start_datetime = datetime.combine(date, datetime.min.time().replace(hour=hour, minute=minute))
        end_datetime = start_datetime + timedelta(minutes=duration_minutes)
        
        # Agregar timezone
        tz = timezone(timedelta(hours=-3))
        start_datetime = start_datetime.replace(tzinfo=tz)
        end_datetime = end_datetime.replace(tzinfo=tz)
        
        # Crear evento
        event_body = {
            'summary': f'Turno: {service_name} - {client_name}',
            'description': f'Cliente: {client_name}\nTeléfono: {client_phone}\nServicio: {service_name}\nDuración: {duration_minutes} min\nNotas: {notes}',
            'start': {
                'dateTime': start_datetime.isoformat(),
                'timeZone': 'America/Argentina/Buenos_Aires',
            },
            'end': {
                'dateTime': end_datetime.isoformat(),
                'timeZone': 'America/Argentina/Buenos_Aires',
            },
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'email', 'minutes': 1440},  # 24 horas antes
                    {'method': 'popup', 'minutes': 60},   # 1 hora antes
                ],
            },
        }
        
        event = service.events().insert(calendarId=GOOGLE_CALENDAR_ID, body=event_body).execute()
        
        return {
            'success': True,
            'event_id': event.get('id'),
            'event_link': event.get('htmlLink')
        }
    
    except Exception as e:
        print(f"[ERROR] Error al crear turno: {e}")
        return {
            'success': False,
            'error': f'No se pudo crear el turno: {str(e)}'
        }


def cancel_turn(event_id: str) -> Dict[str, Any]:
    """Cancela un turno (evento) en Google Calendar."""
    service = get_calendar_service()
    if not service:
        return {
            'success': False,
            'error': 'Google Calendar no está configurado.'
        }
    
    try:
        service.events().delete(calendarId=GOOGLE_CALENDAR_ID, eventId=event_id).execute()
        return {'success': True}
    except Exception as e:
        print(f"[ERROR] Error al cancelar turno: {e}")
        return {
            'success': False,
            'error': f'No se pudo cancelar el turno: {str(e)}'
        }


def get_turns_by_phone(phone: str, days: int = 30) -> List[Dict[str, Any]]:
    """Obtiene los turnos de un cliente por número de teléfono."""
    service = get_calendar_service()
    if not service:
        return []
    
    try:
        tz = timezone(timedelta(hours=-3))
        now = datetime.now(tz)
        future = now + timedelta(days=days)
        
        events_result = service.events().list(
            calendarId=GOOGLE_CALENDAR_ID,
            timeMin=now.isoformat(),
            timeMax=future.isoformat(),
            singleEvents=True,
            orderBy='startTime',
            q=phone
        ).execute()
        
        events = events_result.get('items', [])
        
        turns = []
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            turns.append({
                'id': event['id'],
                'summary': event.get('summary', ''),
                'start': start,
                'description': event.get('description', ''),
                'link': event.get('htmlLink', '')
            })
        
        return turns
    
    except Exception as e:
        print(f"[ERROR] Error al buscar turnos: {e}")
        return []


def get_turns_for_reminders(hours_before: int = 24) -> List[Dict[str, Any]]:
    """
    Obtiene turnos que necesitan recordatorio.
    Busca turnos que están exactamente 'hours_before' horas en el futuro.
    
    Args:
        hours_before: Horas antes del turno para enviar recordatorio
    
    Returns:
        Lista de turnos que necesitan recordatorio
    """
    service = get_calendar_service()
    if not service:
        return []
    
    try:
        tz = timezone(timedelta(hours=-3))
        now = datetime.now(tz)
        target_start = now + timedelta(hours=hours_before)
        target_end = target_start + timedelta(minutes=59)
        
        events_result = service.events().list(
            calendarId=GOOGLE_CALENDAR_ID,
            timeMin=target_start.isoformat(),
            timeMax=target_end.isoformat(),
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        turns = []
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            # Extraer teléfono de la descripción
            description = event.get('description', '')
            phone = ''
            for line in description.split('\n'):
                if 'Teléfono:' in line or 'Telefono:' in line:
                    phone = line.split(':')[-1].strip()
                    break
            
            turns.append({
                'id': event['id'],
                'summary': event.get('summary', ''),
                'start': start,
                'phone': phone,
                'description': description,
            })
        
        return turns
    
    except Exception as e:
        print(f"[ERROR] Error al buscar turnos para recordatorios: {e}")
        return []


def is_calendar_configured() -> bool:
    """Verifica si Google Calendar está configurado y funcionando."""
    return get_calendar_service() is not None
