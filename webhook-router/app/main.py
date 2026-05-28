import json
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse, JSONResponse
from app.config import (
    META_VERIFY_TOKEN,
    META_APP_SECRET,
    META_VALIDATE_SIGNATURE,
    ADMIN_API_KEY,
    HTTP_TIMEOUT_SECONDS,
    validate_runtime_config,
)
from app.db import init_db, get_route, register_route, unregister_route, list_routes
from app.webhook_signature import validate_meta_signature, META_SIGNATURE_HEADER

app = FastAPI(title="Webhook Router - Multi-Cliente")


def _validate_admin_key(request: Request):
    api_key = request.headers.get("X-Admin-Key")
    if not api_key or api_key != ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing admin key")


def _extract_phone_number_id(payload: dict) -> str:
    """Extrae el phone_number_id del payload de Meta."""
    try:
        entries = payload.get("entry", [])
        if not entries:
            return ""
        changes = entries[0].get("changes", [])
        if not changes:
            return ""
        value = changes[0].get("value", {})
        metadata = value.get("metadata", {})
        return metadata.get("phone_number_id", "")
    except Exception:
        return ""


@app.on_event("startup")
def _startup():
    validate_runtime_config()
    init_db()


@app.get("/health")
def health():
    return {"status": "ok", "service": "webhook-router"}


# ============================================================
# Meta Webhook endpoints
# ============================================================
@app.get("/webhook")
async def webhook_get(request: Request):
    params = dict(request.query_params)
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode != "subscribe":
        return JSONResponse({"error": "Invalid mode"}, status_code=400)
    if token != META_VERIFY_TOKEN:
        return JSONResponse({"error": "Invalid verify token"}, status_code=403)
    return PlainTextResponse(challenge)


@app.post("/webhook")
async def webhook_post(request: Request):
    raw_body = await request.body()

    if META_VALIDATE_SIGNATURE:
        signature = request.headers.get(META_SIGNATURE_HEADER, "")
        if not validate_meta_signature(raw_body, signature, META_APP_SECRET):
            return JSONResponse({"error": "Invalid signature"}, status_code=403)

    try:
        payload_dict = json.loads(raw_body)
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    phone_number_id = _extract_phone_number_id(payload_dict)
    if not phone_number_id:
        return JSONResponse(
            {"status": "received", "routed": False, "reason": "no_phone_number_id"},
            status_code=200,
        )

    route = get_route(phone_number_id)
    if not route:
        return JSONResponse(
            {
                "status": "received",
                "routed": False,
                "reason": "no_route_found",
                "phone_number_id": phone_number_id,
            },
            status_code=200,
        )

    target_url = route["target_url"]

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
            response = await client.post(
                target_url,
                content=raw_body,
                headers={
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
        return JSONResponse(
            {
                "status": "received",
                "routed": True,
                "client_slug": route["client_slug"],
                "target_url": target_url,
            },
            status_code=200,
        )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Target timeout")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Target returned {e.response.status_code}")
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Target unreachable")


# ============================================================
# Admin endpoints
# ============================================================
from pydantic import BaseModel


class RegisterRequest(BaseModel):
    phone_number_id: str
    client_slug: str
    target_url: str


class UnregisterRequest(BaseModel):
    phone_number_id: str


@app.post("/admin/register")
async def admin_register(request: Request, body: RegisterRequest):
    _validate_admin_key(request)
    ok = register_route(body.phone_number_id, body.client_slug, body.target_url)
    return {"status": "registered" if ok else "error", "phone_number_id": body.phone_number_id}


@app.post("/admin/unregister")
async def admin_unregister(request: Request, body: UnregisterRequest):
    _validate_admin_key(request)
    ok = unregister_route(body.phone_number_id)
    return {"status": "unregistered" if ok else "not_found", "phone_number_id": body.phone_number_id}


@app.get("/admin/routes")
async def admin_list_routes(request: Request):
    _validate_admin_key(request)
    return {"routes": list_routes()}
