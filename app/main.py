import json
import time
from collections import defaultdict
from typing import List

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import PlainTextResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel
from app.config import (
    META_VERIFY_TOKEN,
    DEBUG,
    WHATSAPP_MODE,
    ADMIN_API_KEY,
    validate_runtime_config,
)
from app.db import init_db
from app.db_migrations import apply_migrations
from app.whatsapp_parser import parse_webhook_get, parse_webhook_post
from app.whatsapp_service import whatsapp_service
from app.whatsapp_store import store
from app.webhook_signature import validate_meta_signature, META_SIGNATURE_HEADER
from app.rag_service import answer_question

app = FastAPI(title="Rodrigo Rodriguez - Secretaria Virtual")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.mount("/chat", StaticFiles(directory="ui", html=True), name="ui")


@app.get("/")
def root_redirect():
    return RedirectResponse(url="/chat/index.html")


@app.get("/admin")
def admin_panel():
    from fastapi.responses import FileResponse
    return FileResponse("ui/admin/index.html")


class SimpleRateLimiter:
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.clients = defaultdict(list)

    def is_allowed(self, client_id: str):
        now = time.time()
        window_start = now - self.window_seconds
        requests = [t for t in self.clients[client_id] if t > window_start]
        self.clients[client_id] = requests
        if len(requests) >= self.max_requests:
            retry_after = int(self.window_seconds - (now - requests[0]))
            return False, max(retry_after, 1)
        requests.append(now)
        return True, 0


_rate_limiter = None
_public_rate_limiter = None


def _get_rate_limiter():
    global _rate_limiter
    if _rate_limiter is None:
        import app.config as _cfg
        _rate_limiter = SimpleRateLimiter(
            max_requests=getattr(_cfg, "ASK_RATE_LIMIT_REQUESTS", 20),
            window_seconds=getattr(_cfg, "ASK_RATE_LIMIT_WINDOW_SECONDS", 60),
        )
    return _rate_limiter


def _get_public_rate_limiter():
    global _public_rate_limiter
    if _public_rate_limiter is None:
        _public_rate_limiter = SimpleRateLimiter(
            max_requests=10,
            window_seconds=60,
        )
    return _public_rate_limiter


class AskRequest(BaseModel):
    question: str


class Source(BaseModel):
    id: str
    title: str


class AskResponse(BaseModel):
    question: str
    answer: str
    sources: List[Source]


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _validate_api_key(request: Request):
    import app.config as _cfg
    expected = getattr(_cfg, "ASK_API_KEY", None)
    if not expected:
        raise HTTPException(status_code=503, detail="Ask API not configured")
    api_key = request.headers.get("X-API-Key")
    if not api_key or api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


@app.on_event("startup")
def _startup():
    validate_runtime_config()
    init_db()
    apply_migrations()


@app.get("/health")
def health():
    import app.config as _cfg
    ask_configured = bool(getattr(_cfg, "ASK_API_KEY", None))
    return {
        "status": "ok",
        "mode": WHATSAPP_MODE,
        "webhook_mode": getattr(_cfg, "WEBHOOK_MODE", "inline"),
        "services": {
            "db": "ok",
            "llm": "configured" if _cfg.LLM_API_KEY else "not_configured",
            "vector_store": "configured",
            "ask_api": "configured" if ask_configured else "not_configured",
        },
    }


@app.get("/webhook")
async def webhook_get(request: Request):
    params = dict(request.query_params)
    parsed = parse_webhook_get(params)

    if not parsed:
        return JSONResponse({"error": "Missing parameters"}, status_code=400)

    if parsed["mode"] != "subscribe":
        return JSONResponse({"error": "Invalid mode"}, status_code=400)

    if parsed["verify_token"] != META_VERIFY_TOKEN:
        return JSONResponse({"error": "Invalid verify token"}, status_code=403)

    return PlainTextResponse(parsed["challenge"])


@app.post("/webhook")
async def webhook_post(request: Request):
    raw_body = await request.body()

    import app.config as _cfg
    if _cfg.META_VALIDATE_SIGNATURE:
        signature = request.headers.get(META_SIGNATURE_HEADER, "")
        if not validate_meta_signature(raw_body, signature, _cfg.META_APP_SECRET or ""):
            return JSONResponse({"error": "Invalid signature"}, status_code=403)

    try:
        payload_dict = json.loads(raw_body)
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    payload = parse_webhook_post(payload_dict)

    responses = []

    for msg in payload["messages"]:
        if DEBUG:
            print(f"[WEBHOOK] Mensaje de {msg.from_number}: {msg.text[:60]}...")

        import app.config as _cfg
        if _cfg.WEBHOOK_MODE == "async":
            status = whatsapp_service.receive_inbound_text(msg)
            if status == "duplicado":
                response_id = "[duplicado ignorado]"
            else:
                response_id = "[pendiente - worker lo procesará]"
        else:
            response_id = whatsapp_service.handle_inbound_text(msg)

        responses.append({
            "type": "message",
            "from": msg.from_number,
            "text_preview": msg.text[:60],
            "response_id": response_id,
        })

    for st in payload["statuses"]:
        store.log_status(
            provider=st.provider,
            provider_message_id=st.message_id,
            status=st.status,
            provider_timestamp=st.timestamp,
        )
        if DEBUG:
            print(f"[WEBHOOK] Estado: {st.message_id} -> {st.status}")
        responses.append({
            "type": "status",
            "message_id": st.message_id,
            "status": st.status,
        })

    return JSONResponse({"status": "received", "processed": responses})


@app.post("/ask")
def ask_endpoint(request: Request, body: AskRequest):
    _validate_api_key(request)

    client_ip = _get_client_ip(request)
    limiter = _get_rate_limiter()
    allowed, retry_after = limiter.is_allowed(client_ip)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )

    try:
        result = answer_question(body.question)
    except Exception:
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")

    return AskResponse(
        question=body.question,
        answer=result["answer"],
        sources=[Source(**s) for s in result["sources"]],
    )


@app.post("/ask-public")
def ask_public_endpoint(request: Request, body: AskRequest):
    client_ip = _get_client_ip(request)
    limiter = _get_public_rate_limiter()
    allowed, retry_after = limiter.is_allowed(client_ip)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )

    try:
        result = answer_question(body.question)
    except Exception:
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")

    return AskResponse(
        question=body.question,
        answer=result["answer"],
        sources=[Source(**s) for s in result["sources"]],
    )


# ============================================================
# Admin endpoints (human handoff)
# ============================================================
class ClaimRequest(BaseModel):
    claimed_by: str = "admin"
    notes: str = ""


class ReplyRequest(BaseModel):
    body: str


def _validate_admin_key(request: Request):
    if not ADMIN_API_KEY:
        raise HTTPException(status_code=503, detail="Admin API not configured")
    api_key = request.headers.get("X-Admin-Key")
    if not api_key or api_key != ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing admin key")


@app.get("/admin/conversations")
def admin_conversations(request: Request):
    _validate_admin_key(request)
    return {"conversations": store.get_conversations_summary(limit=100)}


@app.get("/admin/conversations/{phone}")
def admin_conversation_detail(phone: str, request: Request):
    _validate_admin_key(request)
    return {
        "phone": phone,
        "history": store.get_full_conversation(phone, limit=100),
        "claimed": store.is_claimed(phone),
    }


@app.post("/admin/conversations/{phone}/claim")
def admin_claim_conversation(phone: str, request: Request, body: ClaimRequest):
    _validate_admin_key(request)
    ok = store.claim_conversation(phone, body.claimed_by, body.notes)
    return {"status": "claimed" if ok else "error", "phone": phone}


@app.post("/admin/conversations/{phone}/release")
def admin_release_conversation(phone: str, request: Request):
    _validate_admin_key(request)
    ok = store.release_conversation(phone)
    return {"status": "released" if ok else "not_found", "phone": phone}


@app.post("/admin/conversations/{phone}/reply")
def admin_reply_conversation(phone: str, request: Request, body: ReplyRequest):
    _validate_admin_key(request)
    msg_id = whatsapp_service.send_manual_reply(phone, body.body)
    return {"status": "sent" if not msg_id.startswith("[") else "error", "message_id": msg_id}


if __name__ == "__main__":
    import uvicorn
    print("[START] Iniciando Rodrigo Rodriguez - Secretaria Virtual")
    print(f"   Modo WhatsApp: {WHATSAPP_MODE}")
    print(f"   URL: http://0.0.0.0:8000")
    print(f"   UI Web:      http://127.0.0.1:8000/chat")
    print(f"   Admin:       http://127.0.0.1:8000/admin")
    print(f"   Health:      http://127.0.0.1:8000/health")
    print(f"   Webhook:     http://127.0.0.1:8000/webhook")
    print(f"   Ask API:     http://127.0.0.1:8000/ask")
    print(f"   Ask Public:  http://127.0.0.1:8000/ask-public")
    if WHATSAPP_MODE == "fake":
        print("   [WARN] Usando FAKE sender (simulacion)")
    uvicorn.run(app, host="0.0.0.0", port=8000)
