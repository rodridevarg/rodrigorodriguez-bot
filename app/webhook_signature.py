import hmac
import hashlib


META_SIGNATURE_HEADER = "x-hub-signature-256"
META_SIGNATURE_PREFIX = "sha256="


def validate_meta_signature(raw_body: bytes, signature_header: str, app_secret: str) -> bool:
    if not app_secret:
        return False

    if not signature_header:
        return False

    if not signature_header.startswith(META_SIGNATURE_PREFIX):
        return False

    expected = signature_header[len(META_SIGNATURE_PREFIX):]

    try:
        computed = hmac.new(
            app_secret.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
    except Exception:
        return False

    return hmac.compare_digest(expected, computed)
