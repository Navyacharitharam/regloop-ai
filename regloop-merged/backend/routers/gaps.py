"""FR-4 Gap Analysis Router"""
import uuid
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from db.database import get_db, WorkspaceSession, Obligation, PolicyMapping, GapAnalysis, AuditRecord
from services.ai_service import analyze_gaps

router = APIRouter()

@router.post("/{session_id}/analyze")
async def analyze(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(WorkspaceSession).where(WorkspaceSession.id == session_id))
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Session not found")

    obs = [_ob_dict(o) for o in (await db.execute(select(Obligation).where(Obligation.session_id == session_id))).scalars().all()]
    maps = [_map_dict(m) for m in (await db.execute(select(PolicyMapping).where(PolicyMapping.session_id == session_id))).scalars().all()]
    if not obs:
        raise HTTPException(400, "Run extraction and mapping first")

    await db.execute(delete(GapAnalysis).where(GapAnalysis.session_id == session_id))
    await db.commit()

    try:
        raw = await analyze_gaps(obs, maps)
    except Exception as e:
        raise HTTPException(500, f"AI gap analysis failed: {str(e)}")

    gaps = []
    for i, g in enumerate(raw):
        obj = GapAnalysis(
            id=g.get("id") or f"GAP-{str(i+1).zfill(3)}",
            session_id=session_id,
            obligation_id=g.get("obligation_id", ""),
            coverage=g.get("coverage", "Not Covered"),
            risk_level=g.get("risk_level", "Medium"),
            explanation=g.get("explanation", ""),
            cited_source=g.get("cited_source", ""),
        )
        db.add(obj)
        gaps.append(obj)
        db.add(AuditRecord(
            id=str(uuid.uuid4()), session_id=session_id,
            obligation_id=obj.obligation_id, event_type="gap_detected",
            event_data={"coverage": obj.coverage, "risk_level": obj.risk_level, "explanation": obj.explanation[:200]},
            actor="RegLoop AI – Gap Analyzer",
        ))

    await db.commit()
    return {"analyzed": len(gaps), "gaps": [_serialize(g) for g in gaps]}


@router.get("/{session_id}")
async def list_gaps(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(GapAnalysis).where(GapAnalysis.session_id == session_id))
    return {"gaps": [_serialize(g) for g in result.scalars().all()]}

def _ob_dict(o): return {"id": o.id, "statement": o.statement, "domain": o.domain, "source": o.source}
def _map_dict(m): return {"obligation_id": m.obligation_id, "policy_section": m.policy_section, "excerpt": m.excerpt, "confidence": m.confidence}
def _serialize(g): return {"id": g.id, "obligation_id": g.obligation_id, "coverage": g.coverage, "risk_level": g.risk_level, "explanation": g.explanation, "cited_source": g.cited_source}
