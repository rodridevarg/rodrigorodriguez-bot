import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent


def _env_path(var_name: str, default: Path) -> Path:
    val = os.getenv(var_name)
    return Path(val) if val else default


DATA_DIR = _env_path("DATA_DIR", PROJECT_ROOT / "data")
DOCS_DIR = _env_path("DOCS_DIR", DATA_DIR / "docs")
CHROMA_DIR = _env_path("CHROMA_DIR", DATA_DIR / "chroma")
APP_DB_PATH = _env_path("APP_DB_PATH", DATA_DIR / "app.sqlite3")

LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_BASE_URL = os.getenv("LLM_BASE_URL")
LLM_MODEL = os.getenv("LLM_MODEL")
TOP_K = int(os.getenv("TOP_K", "3"))
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

WHATSAPP_MODE = os.getenv("WHATSAPP_MODE", "fake")
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")
META_PHONE_NUMBER_ID = os.getenv("META_PHONE_NUMBER_ID")
META_WABA_ID = os.getenv("META_WABA_ID")
META_APP_SECRET = os.getenv("META_APP_SECRET")
META_VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN")
META_GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v23.0")
META_VALIDATE_SIGNATURE = os.getenv("META_VALIDATE_SIGNATURE", "false").lower() == "true"
PUBLIC_WEBHOOK_URL = os.getenv("PUBLIC_WEBHOOK_URL")

WEBHOOK_MODE = os.getenv("WEBHOOK_MODE", "inline")

ASK_API_KEY = os.getenv("ASK_API_KEY")
ASK_RATE_LIMIT_REQUESTS = int(os.getenv("ASK_RATE_LIMIT_REQUESTS", "20"))
ASK_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("ASK_RATE_LIMIT_WINDOW_SECONDS", "60"))

CONVERSATION_MEMORY_MAX_TURNS = int(os.getenv("CONVERSATION_MEMORY_MAX_TURNS", "20"))
CONVERSATION_ACTIVE_CONTEXT_TURNS = int(os.getenv("CONVERSATION_ACTIVE_CONTEXT_TURNS", "8"))


def validate_runtime_config():
    missing = []

    if not LLM_API_KEY:
        missing.append("LLM_API_KEY")
    if not LLM_BASE_URL:
        missing.append("LLM_BASE_URL")
    if not LLM_MODEL:
        missing.append("LLM_MODEL")

    if WHATSAPP_MODE == "meta":
        if not META_ACCESS_TOKEN:
            missing.append("META_ACCESS_TOKEN (requerido en modo meta)")
        if not META_PHONE_NUMBER_ID:
            missing.append("META_PHONE_NUMBER_ID (requerido en modo meta)")
        if not META_VERIFY_TOKEN:
            missing.append("META_VERIFY_TOKEN (requerido en modo meta)")

    if missing:
        raise RuntimeError(
            f"Faltan variables de entorno críticas: {', '.join(missing)}"
        )
