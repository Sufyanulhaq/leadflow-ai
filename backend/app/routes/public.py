"""What the website visitor can call: chat, and leaving contact details."""

import re
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import triage
from ..db import passage_records
from ..models import Conversation, Delivery, Lead, Message, utcnow
from ..notify import deliver_lead
from ..retrieval import search
from ..security import client_ip

router = APIRouter(prefix="/api")


def get_db(request: Request):
    with Session(request.app.state.engine) as session:
        yield session


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    conversation_id: str | None = Field(default=None, max_length=36)

    @field_validator("message")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Please type a message.")
        return value


class LeadIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    contact: str = Field(min_length=5, max_length=160)
    reason: str = Field(min_length=10, max_length=2000)
    preferred_time: str | None = Field(default=None, max_length=120)
    consent: bool
    conversation_id: str | None = Field(default=None, max_length=36)

    @field_validator("name", "contact", "reason")
    @classmethod
    def strip(cls, value: str) -> str:
        return value.strip()

    @field_validator("contact")
    @classmethod
    def looks_like_contact(cls, value: str) -> str:
        has_email = re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value) is not None
        has_phone = len(re.sub(r"\D", "", value)) >= 7
        if not (has_email or has_phone):
            raise ValueError("Please give an email address or phone number.")
        return value

    @field_validator("consent")
    @classmethod
    def must_consent(cls, value: bool) -> bool:
        if not value:
            raise ValueError("We need your permission to contact you.")
        return value


def _limit(request: Request, bucket: str, limit: int, window: float, message: str) -> None:
    state = request.app.state
    key = f"{bucket}:{client_ip(request, state.settings.trust_proxy)}"
    if not state.limiter.allow(key, limit, window):
        raise HTTPException(429, message)


def _ai_calls_today(db: Session) -> int:
    start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    return db.scalar(select(func.count()).select_from(Message).where(Message.mode == "claude", Message.created_at >= start)) or 0


@router.get("/health")
def health(request: Request):
    state = request.app.state
    return {
        "status": "ok",
        "ai_configured": state.assistant.ai_configured,
        "notifications_configured": bool(state.settings.notify_webhook_url),
        "admin_enabled": bool(state.settings.admin_password),
    }


@router.get("/public/config")
def public_config(request: Request):
    settings = request.app.state.settings
    return {"clinic_name": settings.clinic_name, "clinic_phone": settings.clinic_phone}


@router.post("/chat")
def chat(body: ChatIn, request: Request, db: Session = Depends(get_db)):
    state = request.app.state
    settings = state.settings
    _limit(request, "chat", settings.chat_per_minute, 60, "That is a lot of messages. Please wait a minute and try again.")

    conversation = db.get(Conversation, body.conversation_id) if body.conversation_id else None
    if conversation is None:
        conversation = Conversation(id=str(uuid.uuid4()))
        db.add(conversation)
        db.flush()
    history = [(m.role, m.text) for m in conversation.messages]
    if len(history) >= settings.max_messages_per_conversation:
        raise HTTPException(429, "This conversation is very long. Please start a new one or call the clinic.")

    db.add(Message(conversation_id=conversation.id, role="user", text=body.message, mode="user"))

    if triage.is_emergency(body.message):
        text, answerable, mode, citations = triage.emergency_reply(body.message, settings.clinic_phone), True, "safety", []
        offer_lead = False
    else:
        hits = search(body.message, passage_records(db))
        result = state.assistant.answer(body.message, history, hits, allow_ai=_ai_calls_today(db) < settings.ai_daily_limit)
        text, answerable, mode, citations = result.text, result.answerable, result.mode, result.citations
        offer_lead = (not answerable) or triage.wants_contact(body.message)

    db.add(
        Message(
            conversation_id=conversation.id, role="assistant", text=text, citations=citations, answerable=answerable, mode=mode
        )
    )
    db.commit()
    return {
        "conversation_id": conversation.id,
        "reply": {"text": text, "answerable": answerable, "citations": citations, "mode": mode},
        "offer_lead": offer_lead,
    }


def run_notification(state, lead_id: int) -> None:
    """Background task: tell the team, with retries. Uses its own database session."""
    settings = state.settings
    with Session(state.engine) as session:
        deliver_lead(
            session,
            lead_id,
            webhook_url=settings.notify_webhook_url,
            attempts=settings.notify_attempts,
            backoff=settings.notify_backoff_seconds,
            transport=state.transport,
            sleep=state.sleep,
        )


@router.post("/leads", status_code=201)
def create_lead(body: LeadIn, request: Request, background: BackgroundTasks, db: Session = Depends(get_db)):
    state = request.app.state
    _limit(
        request,
        "lead",
        state.settings.leads_per_hour,
        3600,
        "Too many requests from this connection. Please call the clinic instead.",
    )

    conversation_id = body.conversation_id if body.conversation_id and db.get(Conversation, body.conversation_id) else None
    triaged = triage.triage_lead(body.reason, body.preferred_time)
    lead = Lead(
        conversation_id=conversation_id,
        name=body.name,
        contact=body.contact,
        reason=body.reason,
        preferred_time=(body.preferred_time or "").strip() or None,
        consent_at=utcnow(),
        **triaged,
    )
    lead.delivery = Delivery(status="pending")
    db.add(lead)
    db.commit()
    background.add_task(run_notification, state, lead.id)
    return {"ok": True, "message": "Thank you. The team will be in touch to confirm. If it is urgent, please call the clinic."}
