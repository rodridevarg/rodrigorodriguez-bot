import json
from typing import List, Dict, Optional, Any, Tuple
from pathlib import Path
from app.config import SERVICES_CONFIG_PATH, HOURS_CONFIG_PATH


class ServiceConfig:
    """Configuración de servicios replicable para cualquier negocio."""
    
    def __init__(self):
        self.services = []
        self.hours = {}
        self._load_services()
        self._load_hours()
    
    def _load_services(self):
        """Carga la configuración de servicios desde JSON."""
        if SERVICES_CONFIG_PATH.exists():
            try:
                with open(SERVICES_CONFIG_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.services = data.get('servicios', [])
            except Exception as e:
                print(f"[WARN] Error al cargar services.json: {e}")
                self.services = []
    
    def _load_hours(self):
        """Carga la configuración de horarios desde JSON."""
        if HOURS_CONFIG_PATH.exists():
            try:
                with open(HOURS_CONFIG_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.hours = data
            except Exception as e:
                print(f"[WARN] Error al cargar horarios.json: {e}")
                self.hours = {}
    
    def get_all_services(self) -> List[Dict[str, Any]]:
        """Retorna todos los servicios configurados."""
        return self.services
    
    def get_service_by_id(self, service_id: str) -> Optional[Dict[str, Any]]:
        """Busca un servicio por su ID."""
        for service in self.services:
            if service.get('id') == service_id:
                return service
        return None
    
    def find_service_by_keyword(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Busca un servicio por keywords. Retorna el servicio con mayor coincidencia.
        """
        text_lower = text.lower().strip()
        
        # Primero buscar coincidencia exacta en nombre
        for service in self.services:
            if service['nombre'].lower() in text_lower:
                return service
        
        # Luego buscar en keywords
        for service in self.services:
            for keyword in service.get('keywords', []):
                if keyword.lower() in text_lower:
                    return service
        
        return None
    
    def find_services_by_category(self, category: str) -> List[Dict[str, Any]]:
        """Busca servicios por categoría."""
        return [s for s in self.services if s.get('categoria', '').lower() == category.lower()]
    
    def get_categories(self) -> List[str]:
        """Retorna todas las categorías únicas."""
        categories = set()
        for service in self.services:
            categories.add(service.get('categoria', 'Otros'))
        return sorted(list(categories))
    
    def get_services_by_category(self) -> Dict[str, List[Dict[str, Any]]]:
        """Retorna servicios agrupados por categoría."""
        result = {}
        for service in self.services:
            cat = service.get('categoria', 'Otros')
            if cat not in result:
                result[cat] = []
            result[cat].append(service)
        return result
    
    def get_hours_for_day(self, day_name: str) -> Dict[str, Any]:
        """
        Retorna la configuración de horarios para un día.
        day_name: lunes, martes, miercoles, jueves, viernes, sabado, domingo
        """
        if not self.hours or 'dias' not in self.hours:
            return {'abierto': False}
        
        return self.hours['dias'].get(day_name.lower(), {'abierto': False})
    
    def is_open(self, day_name: str) -> bool:
        """Verifica si el negocio está abierto un día específico."""
        hours = self.get_hours_for_day(day_name)
        return hours.get('abierto', False)
    
    def get_opening_hours(self, day_name: str) -> Tuple[str, str]:
        """
        Retorna (apertura, cierre) para un día.
        """
        hours = self.get_hours_for_day(day_name)
        if not hours.get('abierto', False):
            return ('00:00', '00:00')
        return (hours.get('apertura', '00:00'), hours.get('cierre', '00:00'))
    
    def get_default_duration(self) -> int:
        """Retorna la duración por defecto de un turno."""
        return self.hours.get('duracion_turno_default', 60)
    
    def get_interval(self) -> int:
        """Retorna el intervalo entre turnos en minutos."""
        return self.hours.get('intervalo_minutos', 30)
    
    def get_holidays(self) -> List[str]:
        """Retorna lista de feriados en formato YYYY-MM-DD."""
        return self.hours.get('feriados', [])
    
    def is_holiday(self, date_str: str) -> bool:
        """Verifica si una fecha es feriado."""
        return date_str in self.get_holidays()
    
    def format_services_list(self) -> str:
        """Formatea la lista de servicios para mostrar al usuario."""
        if not self.services:
            return "No hay servicios configurados."
        
        lines = []
        by_category = self.get_services_by_category()
        
        for category, services in by_category.items():
            lines.append(f"*{category}*")
            for service in services:
                duration = service.get('duracion_minutos', 0)
                price = service.get('precio', 0)
                lines.append(f"  • {service['nombre']} ({duration} min) - ${price:,}")
            lines.append("")
        
        return "\n".join(lines)
    
    def format_services_as_options(self, services: List[Dict[str, Any]]) -> Tuple[str, Dict[str, str]]:
        """
        Formatea servicios como opciones a/b/c/d.
        Retorna (texto, mapeo_letra_id).
        """
        lines = []
        mapping = {}
        
        for i, service in enumerate(services, 1):
            letter = chr(96 + i)  # a, b, c, d...
            duration = service.get('duracion_minutos', 0)
            price = service.get('precio', 0)
            lines.append(f"{letter}) {service['nombre']} ({duration} min) - ${price:,}")
            mapping[letter] = service['id']
        
        return "\n".join(lines), mapping


# Instancia global
service_config = ServiceConfig()
