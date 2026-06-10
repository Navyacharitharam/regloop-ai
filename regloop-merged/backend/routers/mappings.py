"""FR-3 Policy Mapping Router"""
import uuid
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from db.database import get_db, WorkspaceSession, Obligation, PolicyMapping, AuditRecord
from services.ai_service import map_policies

router = APIRouter()

@router.post("/{session_id}/map")
async def map(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(WorkspaceSession).where(WorkspaceSession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")

    obs_result = await db.execute(select(Obligation).where(Obligation.session_id == session_id))
    obligations = [_ob_dict(o) for o in obs_result.scalars().all()]
    if not obligations:
        raise HTTPException(400, "Run obligation extraction first")

    await db.execute(delete(PolicyMapping).where(PolicyMapping.session_id == session_id))
    await db.commit()

    try:
        raw = await map_policies(obligations, session.policy_texts or {})
    except Exception as e:
        raise HTTPException(500, f"AI mapping failed: {str(e)}")

    mappings = []
    for i, m in enumerate(raw):
        obj = PolicyMapping(
            id=str(uuid.uuid4()),
            session_id=session_id,
            obligation_id=m.get("obligation_id", ""),
            policy_name=m.get("policy_name", ""),
            policy_section=m.get("policy_section", ""),
            excerpt=m.get("excerpt", ""),
            confidence=float(m.get("confidence", 0.7)),
            rationale=m.get("rationale", ""),
        )
        db.add(obj)
        mappings.append(obj)
        db.add(AuditRecord(
            id=str(uuid.uuid4()), session_id=session_id,
            obligation_id=obj.obligation_id, event_type="mapped",
            event_data={"policy": obj.policy_name, "section": obj.policy_section, "confidence": obj.confidence},
            actor="RegLoop AI – Policy Mapper",
        ))

    await db.commit()
    return {"mapped": len(mappings), "mappings": [_serialize(m) for m in mappings]}


@router.get("/{session_id}")
async def list_mappings(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PolicyMapping).where(PolicyMapping.session_id == session_id))
    return {"mappings": [_serialize(m) for m in result.scalars().all()]}

def _ob_dict(o): return {"id": o.id, "statement": o.statement, "domain": o.domain, "source": o.source}
def _serialize(m): return {"id": m.id, "obligation_id": m.obligation_id, "policy_name": m.policy_name, "policy_section": m.policy_section, "excerpt": m.excerpt, "confidence": m.confidence, "rationale": m.rationale}
