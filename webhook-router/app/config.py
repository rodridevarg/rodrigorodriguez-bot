import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", PROJECT_ROOT / "data"))
DB_PATH = Path(os.getenv("DB_PATH", DATA_DIR / "router.sqlite3"))

META_VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN", "")
META_APP_SECRET = os.getenv("META_APP_SECRET", "")
META_VALIDATE_SIGNATURE = os.getenv("META_VALIDATE_SIGNATURE", "true").lower() == "true"

ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")

HTTP_TIMEOUT_SECONDS = int(os.getenv("HTTP_TIMEOUT_SECONDS", "10"))


def validate_runtime_config():
    missing = []
    if not META_VERIFY_TOKEN:
        missing.append("META_VERIFY_TOKEN")
    if not META_APP_SECRET:
        missing.append("META_APP_SECRET")
    if not ADMIN_API_KEY:
        missing.append("ADMIN_API_KEY")
    if missing:
        raise RuntimeError(
            f"Faltan variables de entorno criticas: {', '.join(missing)}"
        )
