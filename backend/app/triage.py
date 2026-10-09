"""Rule-based safety and lead triage. Deterministic, so it works with no AI at all."""

from __future__ import annotations

import re


def _has(text: str, terms: tuple[str, ...]) -> bool:
    """Whole-word match, so 'ai' never matches inside 'email'."""
    pattern = r"\b(?:" + "|".join(re.escape(t) for t in terms) + r")\b"
    return re.search(pattern, text.lower()) is not None


EMERGENCY_TERMS = (
    "emergency",
    "chest pain",
    "can't breathe",
    "cannot breathe",
    "difficulty breathing",
    "trouble breathing",
    "unconscious",
    "uncontrolled bleeding",
    "won't stop bleeding",
    "swollen face",
    "face is swollen",
    "swelling in my throat",
    "swollen throat",
    "stroke",
    "overdose",
    "suicidal",
    "kill myself",
    "end my life",
)
_SELF_HARM = ("suicidal", "kill myself", "end my life")

BOOKING_TERMS = (
    "book",
    "booking",
    "appointment",
    "appointments",
    "callback",
    "call me",
    "ring me",
    "quote",
    "register",
    "consultation",
    "consultations",
    "availability",
    "available slot",
)
URGENT_TERMS = (
    "pain",
    "toothache",
    "abscess",
    "swelling",
    "swollen",
    "broken",
    "chipped",
    "cracked",
    "knocked out",
    "bleeding",
    "urgent",
    "urgently",
    "asap",
    "today",
    "tonight",
    "tomorrow",
    "can't walk",
    "cannot walk",
    "locked",
    "sprain",
    "sprained",
)
PHYSIO_TERMS = (
    "physio",
    "physiotherapy",
    "back pain",
    "lower back",
    "upper back",
    "neck",
    "knee",
    "shoulder",
    "hip",
    "ankle",
    "sprain",
    "sprained",
    "injury",
    "rehab",
    "sports",
    "sciatica",
    "posture",
    "muscle",
)
DENTAL_TERMS = (
    "tooth",
    "teeth",
    "dental",
    "dentist",
    "filling",
    "crown",
    "hygienist",
    "whitening",
    "braces",
    "invisalign",
    "veneers",
    "implant",
    "implants",
    "gum",
    "gums",
    "toothache",
    "denture",
    "root canal",
    "check-up",
    "checkup",
)


def is_emergency(message: str) -> bool:
    return _has(message, EMERGENCY_TERMS)


def emergency_reply(message: str, clinic_phone: str) -> str:
    if _has(message, _SELF_HARM):
        return (
            "I'm really sorry you're feeling this way. Please talk to someone now: "
            "Samaritans are free on 116 123, any time. If you are in immediate danger, call 999."
        )
    return (
        "This sounds like it could be an emergency. Please call 999 now. "
        f"For urgent advice that is not life-threatening, call NHS 111 or the clinic on {clinic_phone}. "
        "I'm not able to give medical advice."
    )


def wants_contact(message: str) -> bool:
    return _has(message, BOOKING_TERMS)


def triage_lead(reason: str, preferred_time: str | None) -> dict:
    """Return category, priority, score and a short summary for the team."""
    text = reason
    urgent = _has(text, URGENT_TERMS)
    booking = _has(text, BOOKING_TERMS)
    physio = _has(text, PHYSIO_TERMS)
    dental = _has(text, DENTAL_TERMS)

    if dental and not physio:
        category = "Dental"
    elif physio and not dental:
        category = "Physiotherapy"
    elif dental and physio:
        category = "Dental and physiotherapy"
    else:
        category = "General enquiry"

    score = 30
    if urgent:
        score += 40
    if booking:
        score += 20
    if preferred_time:
        score += 10
    score = min(score, 100)
    priority = "high" if urgent else "medium" if booking or preferred_time else "low"

    summary = re.sub(r"\s+", " ", reason).strip()
    if len(summary) > 200:
        summary = summary[:197].rsplit(" ", 1)[0] + "..."
    return {"category": category, "priority": priority, "score": score, "summary": summary}
