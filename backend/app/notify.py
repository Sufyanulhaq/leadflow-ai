"""Telling the team about a new lead, with retries and a record of every attempt.

The webhook payload is Slack's incoming-webhook shape ({"text": ...}), which many
other tools also accept. Retries follow the same rules as Pulse's webhooks:
network errors, 408, 429 and 5xx are retried with doubling delays; other
responses stop at once; redirects are never followed.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from urllib.parse import urlparse

import httpx
from sqlalchemy.orm import Session

from .models import Delivery, Lead, utcnow

log = logging.getLogger("leadflow.notify")

RETRYABLE_STATUS = {408, 429}
MAX_RETRY_AFTER = 30.0

# A transport takes (url, payload) and returns (status_code, retry_after_header_or_None).
Transport = Callable[[str, dict], tuple[int, str | None]]


def http_post(url: str, payload: dict) -> tuple[int, str | None]:
    response = httpx.post(url, json=payload, timeout=8.0, follow_redirects=False)
    return response.status_code, response.headers.get("retry-after")


def webhook_url_allowed(url: str) -> bool:
    """The URL is operator configuration, but still insist on HTTPS (plain HTTP only for localhost)."""
    parsed = urlparse(url)
    if parsed.scheme == "https" and parsed.hostname:
        return True
    return parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}


def _slack_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_payload(lead: Lead) -> dict:
    when = f"\nPreferred time: {_slack_escape(lead.preferred_time)}" if lead.preferred_time else ""
    text = (
        f"*New {lead.priority} priority lead* ({_slack_escape(lead.category)}, score {lead.score}/100)\n"
        f"{_slack_escape(lead.name)}: {_slack_escape(lead.contact)}{when}\n"
        f"> {_slack_escape(lead.summary)}"
    )
    return {"text": text}


def _retry_delay(base: float, attempt: int, retry_after: str | None) -> float:
    delay = base * (2 ** (attempt - 1))
    if retry_after:
        try:
            delay = max(delay, min(float(retry_after), MAX_RETRY_AFTER))
        except ValueError:
            pass
    return delay


def deliver_lead(
    session: Session,
    lead_id: int,
    *,
    webhook_url: str,
    attempts: int,
    backoff: float,
    transport: Transport = http_post,
    sleep: Callable[[float], None] = time.sleep,
) -> Delivery | None:
    """Send the notification for one lead and record the outcome on its delivery row."""
    lead = session.get(Lead, lead_id)
    if lead is None:
        return None
    delivery = lead.delivery or Delivery(lead=lead)
    session.add(delivery)

    if not webhook_url or not webhook_url_allowed(webhook_url):
        delivery.status = "skipped"
        delivery.last_error = (
            "No valid notification webhook is configured." if not webhook_url else "The webhook URL must use https."
        )
        session.commit()
        return delivery

    payload = build_payload(lead)
    delivery.status = "pending"
    delivery.attempts = 0
    delivery.last_error = None
    for attempt in range(1, attempts + 1):
        retry_after: str | None = None
        delivery.attempts = attempt
        try:
            status, retry_after = transport(webhook_url, payload)
        except httpx.HTTPError as exc:
            # Record the error type only: the message can contain the secret webhook URL.
            error, retryable = f"Network error ({type(exc).__name__})", True
        else:
            if 200 <= status < 300:
                delivery.status, delivery.last_error = "sent", None
                session.commit()
                return delivery
            error, retryable = f"The webhook answered with status {status}", status in RETRYABLE_STATUS or status >= 500
        delivery.last_error = error
        session.commit()
        if not retryable or attempt == attempts:
            break
        sleep(_retry_delay(backoff, attempt, retry_after))

    delivery.status = "failed"
    delivery.updated_at = utcnow()
    session.commit()
    log.warning("Notification for lead %s failed after %s attempt(s): %s", lead_id, delivery.attempts, delivery.last_error)
    return delivery
