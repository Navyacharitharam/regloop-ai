"""FR-5 Policy Pull Requests Router"""
import uuid
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from db.database import get_db, WorkspaceSession, Obligation, GapAnalysis, PolicyPullRequest, AuditRecord
from services.ai_service import generate_pull_requests

router = APIRouter()

@router.post("/{session_id}/generate")
async def generate(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(WorkspaceSession).where(WorkspaceSession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")

    obs = [_ob_dict(o) for o in (await db.execute(select(Obligation).where(Obligation.session_id == session_id))).scalars().all()]
    gaps = [_gap_dict(g) for g in (await db.execute(select(GapAnalysis).where(GapAnalysis.session_id == session_id))).scalars().all()]
    if not gaps:
        raise HTTPException(400, "Run gap analysis first")

    await db.execute(delete(PolicyPullRequest).where(PolicyPullRequest.session_id == session_id))
    await db.commit()

    try:
        raw = await generate_pull_requests(obs, gaps, session.matrix_data or [])
    except Exception as e:
        raise HTTPException(500, f"AI PR generation failed: {str(e)}")

    prs = []
    for i, pr in enumerate(raw):
        obj = PolicyPullRequest(
            id=pr.get("id") or f"PPR-{str(i+1).zfill(3)}",
            session_id=session_id,
            obligation_id=pr.get("obligation_id", ""),
            title=pr.get("title", ""),
            gap_description=pr.get("gap_description", ""),
            regulatory_citation=pr.get("regulatory_citation", ""),
            suggested_owner=pr.get("suggested_owner", "Chief Compliance Officer"),
            risk_level=pr.get("risk_level", "Medium"),
            confidence=float(pr.get("confidence", 0.8)),
            before_text=pr.get("before_text", ""),
            after_text=pr.get("after_text", ""),
            status="pending",
        )
        db.add(obj)
        prs.append(obj)
        db.add(AuditRecord(
            id=str(uuid.uuid4()), session_id=session_id,
            obligation_id=obj.obligation_id, event_type="pr_created",
            event_data={"pr_id": obj.id, "title": obj.title, "risk": obj.risk_level},
            actor="RegLoop AI – PR Generator",
        ))

    await db.commit()
    return {"generated": len(prs), "pull_requests": [_serialize(p) for p in prs]}


@router.get("/{session_id}")
async def list_prs(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PolicyPullRequest).where(PolicyPullRequest.session_id == session_id))
    return {"pull_requests": [_serialize(p) for p in result.scalars().all()]}

def _ob_dict(o): return {"id": o.id, "statement": o.statement, "domain": o.domain, "source": o.source}
def _gap_dict(g): return {"id": g.id, "obligation_id": g.obligation_id, "coverage": g.coverage, "risk_level": g.risk_level, "explanation": g.explanation, "cited_source": g.cited_source}
def _serialize(p): return {
    "id": p.id, "obligation_id": p.obligation_id, "title": p.title,
    "gap_description": p.gap_description, "regulatory_citation": p.regulatory_citation,
    "suggested_owner": p.suggested_owner, "risk_level": p.risk_level,
    "confidence": p.confidence, "before_text": p.before_text, "after_text": p.after_text,
    "status": p.status,
}
