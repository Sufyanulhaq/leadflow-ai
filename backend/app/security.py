"""Admin sign-in tokens, rate limiting and client addresses."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

TOKEN_TTL_SECONDS = 12 * 3600


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def sign_token(secret: str, ttl: int = TOKEN_TTL_SECONDS, now: float | None = None) -> str:
    payload = _b64(json.dumps({"exp": int((now or time.time()) + ttl)}).encode())
    signature = _b64(hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{signature}"


def verify_token(secret: str, token: str, now: float | None = None) -> bool:
    try:
        payload, signature = token.split(".", 1)
        expected = _b64(hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            return False
        return json.loads(_unb64(payload))["exp"] > (now or time.time())
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return False


def password_matches(given: str, actual: str) -> bool:
    if not actual:
        return False
    return hmac.compare_digest(hashlib.sha256(given.encode()).digest(), hashlib.sha256(actual.encode()).digest())


class RateLimiter:
    """Sliding window held in memory. Fine for one server; a shared store would replace it for several."""

    def __init__(self, clock=time.monotonic):
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._clock = clock

    def allow(self, key: str, limit: int, window_seconds: float) -> bool:
        now = self._clock()
        hits = self._hits[key]
        while hits and now - hits[0] > window_seconds:
            hits.popleft()
        if len(hits) >= limit:
            return False
        hits.append(now)
        return True


def client_ip(request: Request, trust_proxy: bool) -> str:
    if trust_proxy:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def require_admin(request: Request) -> None:
    settings = request.app.state.settings
    if not settings.admin_password:
        raise HTTPException(503, "The admin area is switched off. Set LEADFLOW_ADMIN_PASSWORD to enable it.")
    header = request.headers.get("authorization", "")
    token = header[7:] if header.lower().startswith("bearer ") else ""
    if not token or not verify_token(settings.secret, token):
        raise HTTPException(401, "Please sign in.")
