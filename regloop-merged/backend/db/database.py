"""
Database layer — SQLite (dev) / PostgreSQL (prod)
Async SQLAlchemy ORM with proper enums and ReviewDecision as separate table.
"""
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy import Column, String, Float, Text, DateTime, JSON, ForeignKey
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./regloop.db")

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class WorkspaceSession(Base):
    __tablename__ = "workspace_sessions"
    id              = Column(String, primary_key=True)
    created_at      = Column(DateTime, default=datetime.utcnow)
    status          = Column(String, default="pending")  # pending|analyzing|complete|error
    regulation_name = Column(String)
    regulation_text = Column(Text)
    policy_names    = Column(JSON)   # list[str]
    policy_texts    = Column(JSON)   # dict name->text
    matrix_data     = Column(JSON)   # list[dict] parsed CSV rows


class Obligation(Base):
    __tablename__ = "obligations"
    id          = Column(String, primary_key=True)   # OBL-001 style
    session_id  = Column(String, ForeignKey("workspace_sessions.id"))
    statement   = Column(Text)
    full_text   = Column(Text)
    source      = Column(String)
    domain      = Column(String)
    confidence  = Column(Float)
    notes       = Column(Text, default="")
    created_at  = Column(DateTime, default=datetime.utcnow)


class PolicyMapping(Base):
    __tablename__ = "policy_mappings"
    id            = Column(String, primary_key=True)
    session_id    = Column(String, ForeignKey("workspace_sessions.id"))
    obligation_id = Column(String, ForeignKey("obligations.id"))
    policy_name   = Column(String)
    policy_section= Column(String)
    excerpt       = Column(Text)
    confidence    = Column(Float)
    rationale     = Column(Text, default="")
    created_at    = Column(DateTime, default=datetime.utcnow)


class GapAnalysis(Base):
    __tablename__ = "gap_analyses"
    id                  = Column(String, primary_key=True)   # GAP-001
    session_id          = Column(String, ForeignKey("workspace_sessions.id"))
    obligation_id       = Column(String, ForeignKey("obligations.id"))
    coverage            = Column(String)   # Fully Covered | Partially Covered | Not Covered
    risk_level          = Column(String)   # High | Medium | Low
    explanation         = Column(Text)
    cited_source        = Column(String)
    recommended_action  = Column(Text, default="")
    created_at          = Column(DateTime, default=datetime.utcnow)


class PolicyPullRequest(Base):
    __tablename__ = "policy_pull_requests"
    id                  = Column(String, primary_key=True)   # PPR-001
    session_id          = Column(String, ForeignKey("workspace_sessions.id"))
    obligation_id       = Column(String, ForeignKey("obligations.id"))
    title               = Column(String)
    gap_description     = Column(Text)
    regulatory_citation = Column(String)
    suggested_owner     = Column(String)
    risk_level          = Column(String)
    confidence          = Column(Float)
    before_text         = Column(Text)
    after_text          = Column(Text)
    implementation_steps= Column(JSON, default=list)
    estimated_effort    = Column(String, default="1-2 weeks")
    status              = Column(String, default="pending")
    created_at          = Column(DateTime, default=datetime.utcnow)


class ReviewDecision(Base):
    """Separate table — reviewer can re-submit and update the decision."""
    __tablename__ = "review_decisions"
    id            = Column(String, primary_key=True)
    session_id    = Column(String, ForeignKey("workspace_sessions.id"))
    pr_id         = Column(String, ForeignKey("policy_pull_requests.id"))
    action        = Column(String)   # Approved | Rejected | Modified | Escalated
    reviewer      = Column(String, default="Compliance Analyst")
    note          = Column(Text, default="")
    modified_text = Column(Text, default="")
    created_at    = Column(DateTime, default=datetime.utcnow)
    updated_at    = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AuditRecord(Base):
    __tablename__ = "audit_records"
    id            = Column(String, primary_key=True)
    session_id    = Column(String, ForeignKey("workspace_sessions.id"))
    obligation_id = Column(String, nullable=True)
    event_type    = Column(String)  # extracted|mapped|gap_detected|pr_created|reviewed
    event_data    = Column(JSON)
    actor         = Column(String, default="RegLoop AI")
    created_at    = Column(DateTime, default=datetime.utcnow)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
