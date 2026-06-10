"""FR-2 Obligation Extraction Router"""
import uuid
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from db.database import get_db, WorkspaceSession, Obligation, AuditRecord
from services.ai_service import extract_obligations

router = APIRouter()


@router.post("/{session_id}/extract")
async def extract(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(WorkspaceSession).where(WorkspaceSession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")

    await db.execute(delete(Obligation).where(Obligation.session_id == session_id))
    await db.commit()

    try:
        raw = await extract_obligations(session.regulation_text, session.regulation_name)
    except Exception as e:
        raise HTTPException(500, f"AI extraction failed: {str(e)}")

    obligations = []
    for i, ob in enumerate(raw):
        # FIX: Use bare OBL-001 style IDs so downstream AI stages can reference them
        ob_id = ob.get("id") or f"OBL-{str(i+1).zfill(3)}"
        # Normalise — strip any prefix AI might hallucinate
        if "-OBL-" in ob_id:
            ob_id = "OBL-" + ob_id.split("-OBL-")[-1]

        obj = Obligation(
            id=ob_id,
            session_id=session_id,
            statement=ob.get("statement", ""),
            full_text=ob.get("full_text", ob.get("fullText", "")),
            source=ob.get("source", ""),
            domain=ob.get("domain", "General"),
            confidence=float(ob.get("confidence", 0.8)),
            notes=ob.get("notes", ""),
        )
        db.add(obj)
        obligations.append(obj)

        db.add(AuditRecord(
            id=str(uuid.uuid4()),
            session_id=session_id,
            obligation_id=obj.id,
            event_type="extracted",
            event_data={"obligation_id": obj.id, "statement": obj.statement, "source": obj.source},
            actor="RegLoop AI – Obligation Extractor",
        ))

    await db.commit()
    return {"extracted": len(obligations), "obligations": [_serialize(o) for o in obligations]}


@router.get("/{session_id}")
async def list_obligations(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Obligation).where(Obligation.session_id == session_id))
    return {"obligations": [_serialize(o) for o in result.scalars().all()]}


def _serialize(o: Obligation) -> dict:
    return {
        "id": o.id, "statement": o.statement, "full_text": o.full_text,
        "source": o.source, "domain": o.domain, "confidence": o.confidence,
        "notes": o.notes, "created_at": o.created_at.isoformat() if o.created_at else None,
    }
