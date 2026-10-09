from __future__ import annotations

from sqlalchemy import Engine, create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from .models import Base, Document, Passage
from .retrieval import PassageRecord, chunk


def normalise_url(url: str) -> str:
    """Hosts hand out postgres:// URLs; SQLAlchemy wants the driver named."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


def make_engine(url: str) -> Engine:
    url = normalise_url(url)
    options: dict = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False}
        if url in {"sqlite://", "sqlite:///:memory:"}:
            options["poolclass"] = StaticPool
    return create_engine(url, **options)


def init_db(engine: Engine) -> None:
    Base.metadata.create_all(engine)


def rebuild_passages(db: Session, document: Document) -> None:
    """Re-split a document into passages. Ids are stable (d3p0, d3p1, ...) so the assistant can cite them."""
    document.passages.clear()
    db.flush()
    for ordinal, text in enumerate(chunk(document.content)):
        document.passages.append(Passage(id=f"d{document.id}p{ordinal}", ordinal=ordinal, text=text))
    db.flush()


def passage_records(db: Session) -> list[PassageRecord]:
    rows = db.execute(select(Passage, Document.title).join(Document, Passage.document_id == Document.id)).all()
    return [PassageRecord(p.id, title, p.text) for p, title in rows]
