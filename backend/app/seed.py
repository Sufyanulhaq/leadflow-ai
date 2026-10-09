"""Fictional demo content for "Brightside Dental & Physio". Not a real clinic, and none of this is real advice.

Run with:  python -m app.seed
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import load_settings
from .db import init_db, make_engine, rebuild_passages
from .models import Document

DEMO_DOCUMENTS = [
    (
        "Opening hours",
        "Brightside is open Monday to Friday from 8am to 6pm, and Saturday from 9am to 1pm. "
        "We are closed on Sundays and bank holidays.\n\n"
        "Physiotherapy appointments are available Monday to Friday only, from 8am to 5pm.",
    ),
    (
        "Prices: dental",
        "A new patient check-up and examination costs £65. A routine check-up for existing patients costs £45. "
        "A scale and polish with the hygienist costs £60. White fillings start from £90 per tooth.\n\n"
        "Teeth whitening is £250 for a full course. Prices are a guide, and the dentist will confirm "
        "your treatment plan and cost before any work starts.",
    ),
    (
        "Prices: physiotherapy",
        "An initial physiotherapy assessment lasts 45 minutes and costs £60. Follow-up sessions last 30 minutes and cost £45. "
        "A course of six follow-up sessions is £240.",
    ),
    (
        "Booking and cancellations",
        "You can ask for an appointment through this chat, or by calling the clinic on 01234 567890. "
        "The team confirms every appointment by phone or email.\n\n"
        "Please give 24 hours' notice if you need to cancel or move an appointment. "
        "Appointments cancelled with less notice may be charged at half the usual fee.",
    ),
    (
        "New patients",
        "We welcome new patients. For your first visit please arrive 10 minutes early, and bring photo identification "
        "and a list of any medicines you take. You will be asked to complete a short medical history form.\n\n"
        "No referral is needed to see our physiotherapists, although some insurance providers ask for one.",
    ),
    (
        "Payment and insurance",
        "We accept card payments and cash. We do not offer monthly payment plans for treatments under £500. "
        "For larger dental treatment, ask the team about interest-free instalments.\n\n"
        "We can provide receipts for private health insurance claims, but we do not bill insurers directly.",
    ),
    (
        "Children and accessibility",
        "Children are welcome from the age of 3 for check-ups. Our ground floor treatment rooms are step-free, "
        "and there is an accessible toilet. Please tell us in advance if you need extra support.",
    ),
    (
        "Parking and travel",
        "There is free parking for patients behind the clinic for up to two hours. "
        "The clinic is a five-minute walk from the town centre bus station.",
    ),
]


def seed_demo(db: Session) -> int:
    """Add the demo documents if the knowledge base is empty. Returns how many were added."""
    if db.scalar(select(func.count()).select_from(Document)):
        return 0
    for title, content in DEMO_DOCUMENTS:
        document = Document(title=title, content=content)
        db.add(document)
        db.flush()
        rebuild_passages(db, document)
    db.commit()
    return len(DEMO_DOCUMENTS)


if __name__ == "__main__":
    engine = make_engine(load_settings().database_url)
    init_db(engine)
    with Session(engine) as session:
        added = seed_demo(session)
    print(f"Added {added} demo documents." if added else "The knowledge base already has content; nothing added.")
