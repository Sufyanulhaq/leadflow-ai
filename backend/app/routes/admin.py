"""The clinic's side: sign in, read leads and conversations, edit the knowledge base."""

from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import rebuild_passages
from ..models import Conversation, Document, Lead, Message, iso
from ..security import client_ip, password_matches, require_admin, sign_token
from .public import get_db, run_notification

router = APIRouter(prefix="/api/admin")
protected = APIRouter(dependencies=[Depends(require_admin)])

STATUSES = ("new", "contacted", "booked", "closed")


class LoginIn(BaseModel):
    password: str = Field(min_length=1, max_length=200)


@router.post("/login")
def login(body: LoginIn, request: Request):
    state = request.app.state
    settings = state.settings
    if not settings.admin_password:
        raise HTTPException(503, "The admin area is switched off. Set LEADFLOW_ADMIN_PASSWORD to enable it.")
    key = f"login:{client_ip(request, settings.trust_proxy)}"
    if not state.limiter.allow(key, settings.login_per_minute, 60):
        raise HTTPException(429, "Too many attempts. Please wait a minute.")
    if not password_matches(body.password, settings.admin_password):
        raise HTTPException(401, "That password is not right.")
    return {"token": sign_token(settings.secret)}


def lead_dict(lead: Lead) -> dict:
    delivery = lead.delivery
    return {
        "id": lead.id,
        "name": lead.name,
        "contact": lead.contact,
        "reason": lead.reason,
        "preferred_time": lead.preferred_time,
        "category": lead.category,
        "priority": lead.priority,
        "score": lead.score,
        "summary": lead.summary,
        "status": lead.status,
        "conversation_id": lead.conversation_id,
        "created_at": iso(lead.created_at),
        "consent_at": iso(lead.consent_at),
        "notification": None
        if delivery is None
        else {
            "status": delivery.status,
            "attempts": delivery.attempts,
            "error": delivery.last_error,
            "updated_at": iso(delivery.updated_at),
        },
    }


def message_dict(message: Message) -> dict:
    return {
        "id": message.id,
        "role": message.role,
        "text": message.text,
        "citations": message.citations or [],
        "answerable": message.answerable,
        "mode": message.mode,
        "created_at": iso(message.created_at),
    }


# ---- leads -----------------------------------------------------------------


@protected.get("/leads")
def list_leads(status: str | None = None, limit: int = 100, db: Session = Depends(get_db)):
    query = select(Lead).order_by(Lead.created_at.desc()).limit(max(1, min(limit, 200)))
    if status:
        if status not in STATUSES:
            raise HTTPException(400, "Unknown status.")
        query = query.where(Lead.status == status)
    return [lead_dict(lead) for lead in db.scalars(query)]


class LeadPatch(BaseModel):
    status: Literal["new", "contacted", "booked", "closed"]


@protected.patch("/leads/{lead_id}")
def update_lead(lead_id: int, body: LeadPatch, db: Session = Depends(get_db)):
    lead = db.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(404, "Lead not found.")
    lead.status = body.status
    db.commit()
    return lead_dict(lead)


@protected.post("/leads/{lead_id}/notify")
def resend_notification(lead_id: int, request: Request, background: BackgroundTasks, db: Session = Depends(get_db)):
    if db.get(Lead, lead_id) is None:
        raise HTTPException(404, "Lead not found.")
    background.add_task(run_notification, request.app.state, lead_id)
    return {"ok": True}


# ---- conversations ----------------------------------------------------------


@protected.get("/conversations")
def list_conversations(db: Session = Depends(get_db)):
    conversations = db.scalars(select(Conversation).order_by(Conversation.created_at.desc()).limit(50)).all()
    lead_ids = dict(db.execute(select(Lead.conversation_id, Lead.id).where(Lead.conversation_id.is_not(None))).all())
    result = []
    for conversation in conversations:
        first = next((m.text for m in conversation.messages if m.role == "user"), "")
        result.append(
            {
                "id": conversation.id,
                "created_at": iso(conversation.created_at),
                "messages": len(conversation.messages),
                "preview": first[:120],
                "unanswered": sum(1 for m in conversation.messages if m.role == "assistant" and not m.answerable),
                "lead_id": lead_ids.get(conversation.id),
            }
        )
    return result


@protected.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str, db: Session = Depends(get_db)):
    conversation = db.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(404, "Conversation not found.")
    return {
        "id": conversation.id,
        "created_at": iso(conversation.created_at),
        "messages": [message_dict(m) for m in conversation.messages],
    }


@protected.get("/unanswered")
def unanswered(db: Session = Depends(get_db)):
    """Questions the assistant could not answer: the list of what to add to the knowledge base."""
    missed = db.scalars(
        select(Message).where(Message.role == "assistant", Message.answerable.is_(False)).order_by(Message.id.desc()).limit(100)
    ).all()
    result = []
    for reply in missed:
        question = db.scalar(
            select(Message)
            .where(Message.conversation_id == reply.conversation_id, Message.role == "user", Message.id < reply.id)
            .order_by(Message.id.desc())
            .limit(1)
        )
        result.append(
            {
                "question": question.text if question else "",
                "asked_at": iso(reply.created_at),
                "conversation_id": reply.conversation_id,
            }
        )
    return result


# ---- knowledge base ---------------------------------------------------------


class DocumentIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=20000)


def document_dict(document: Document) -> dict:
    return {
        "id": document.id,
        "title": document.title,
        "content": document.content,
        "passages": len(document.passages),
        "updated_at": iso(document.updated_at),
    }


@protected.get("/documents")
def list_documents(db: Session = Depends(get_db)):
    return [document_dict(d) for d in db.scalars(select(Document).order_by(Document.title))]


@protected.post("/documents", status_code=201)
def create_document(body: DocumentIn, db: Session = Depends(get_db)):
    document = Document(title=body.title.strip(), content=body.content.strip())
    db.add(document)
    db.flush()
    rebuild_passages(db, document)
    db.commit()
    return document_dict(document)


@protected.put("/documents/{document_id}")
def update_document(document_id: int, body: DocumentIn, db: Session = Depends(get_db)):
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(404, "Document not found.")
    document.title, document.content = body.title.strip(), body.content.strip()
    rebuild_passages(db, document)
    db.commit()
    return document_dict(document)


@protected.delete("/documents/{document_id}", status_code=204)
def delete_document(document_id: int, db: Session = Depends(get_db)):
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(404, "Document not found.")
    db.delete(document)
    db.commit()


# ---- overview ---------------------------------------------------------------


@protected.get("/stats")
def stats(request: Request, db: Session = Depends(get_db)):
    def count(query) -> int:
        return db.scalar(query) or 0

    replies = count(select(func.count()).select_from(Message).where(Message.role == "assistant", Message.mode != "safety"))
    answered = count(
        select(func.count())
        .select_from(Message)
        .where(Message.role == "assistant", Message.mode != "safety", Message.answerable.is_(True))
    )
    by_priority = dict(db.execute(select(Lead.priority, func.count()).group_by(Lead.priority)).all())
    by_status = dict(db.execute(select(Lead.status, func.count()).group_by(Lead.status)).all())
    failed = count(select(func.count()).select_from(Lead).join(Lead.delivery).where(Lead.delivery.has(status="failed")))
    return {
        "conversations": count(select(func.count()).select_from(Conversation)),
        "assistant_replies": replies,
        "answered_rate": round(answered / replies, 3) if replies else None,
        "leads": sum(by_priority.values()),
        "leads_by_priority": {k: by_priority.get(k, 0) for k in ("high", "medium", "low")},
        "leads_by_status": {k: by_status.get(k, 0) for k in STATUSES},
        "notifications_failed": failed,
        "ai_configured": request.app.state.assistant.ai_configured,
        "notifications_configured": bool(request.app.state.settings.notify_webhook_url),
    }


router.include_router(protected)
