"""Cliente simple para la API de Conversiones de Meta (CAPI)."""

import hashlib
import json
import time
import uuid
from typing import Optional

import requests

from app.config import (
    DEBUG,
    META_CONVERSION_API_TOKEN,
    META_CONVERSION_PIXEL_ID,
    META_GRAPH_VERSION,
)

META_CAPI_URL = (
    f"https://graph.facebook.com/{META_GRAPH_VERSION}/{META_CONVERSION_PIXEL_ID}/events"
)


def _hash(value: Optional[str]) -> Optional[str]:
    """Hashea un valor con SHA-256 para enviarlo a Meta de forma segura."""
    if not value:
        return None
    return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()


def send_conversion_event(
    event_name: str,
    event_id: str,
    event_source_url: str,
    client_user_agent: str,
    client_ip_address: Optional[str] = None,
    fbp: Optional[str] = None,
    fbc: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    value: Optional[float] = None,
    currency: Optional[str] = None,
) -> dict:
    """Envía un evento a la API de Conversiones de Meta.

    Args:
        event_name: Nombre del evento (ej. Contact, Lead, PageView).
        event_id: ID único del evento para deduplicación con el Pixel del navegador.
        event_source_url: URL donde ocurrió el evento.
        client_user_agent: User-Agent del navegador.
        client_ip_address: IP del cliente.
        fbp: Valor de la cookie _fbp.
        fbc: Valor de la cookie _fbc (si viene de un clic de anuncio).
        email: Email del usuario (se hashea antes de enviar).
        phone: Teléfono del usuario (se hashea antes de enviar).
        value: Valor monetario opcional.
        currency: Moneda opcional (ISO 4217).

    Returns:
        Dict con la respuesta de Meta o un dict de error.
    """
    if not META_CONVERSION_API_TOKEN or not META_CONVERSION_PIXEL_ID:
        if DEBUG:
            print("[CAPI] Token o Pixel ID no configurados, omitiendo envío")
        return {"skipped": True, "reason": "missing_token_or_pixel"}

    user_data = {}
    if client_ip_address:
        user_data["client_ip_address"] = client_ip_address
    if client_user_agent:
        user_data["client_user_agent"] = client_user_agent
    if fbp:
        user_data["fbp"] = fbp
    if fbc:
        user_data["fbc"] = fbc

    hashed_email = _hash(email)
    if hashed_email:
        user_data["em"] = hashed_email
    hashed_phone = _hash(phone)
    if hashed_phone:
        user_data["ph"] = hashed_phone

    event = {
        "event_name": event_name,
        "event_time": int(time.time()),
        "event_id": event_id,
        "event_source_url": event_source_url,
        "action_source": "website",
        "user_data": user_data,
    }

    custom_data = {}
    if value is not None:
        custom_data["value"] = value
    if currency:
        custom_data["currency"] = currency
    if custom_data:
        event["custom_data"] = custom_data

    payload = {
        "data": [event],
        "access_token": META_CONVERSION_API_TOKEN,
    }

    try:
        response = requests.post(
            META_CAPI_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as exc:
        error_msg = str(exc)
        if hasattr(exc, "response") and exc.response is not None:
            try:
                error_msg = exc.response.text
            except Exception:
                pass
        if DEBUG:
            print(f"[CAPI] Error enviando evento: {error_msg}")
        return {"error": error_msg}
