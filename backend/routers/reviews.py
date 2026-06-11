"""FR-6 Human Review Workflow Router"""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from utils import validate_uuid
from db.database import get_db, PolicyPullRequest, ReviewDecision, AuditRecord

router = APIRouter()

class ReviewRequest(BaseModel):
    action: str           # Approved | Rejected | Modified | Escalated
    reviewer: str = "Compliance Analyst"
    note: Optional[str] = None
    modified_text: Optional[str] = None

VALID_ACTIONS = {"Approved", "Rejected", "Modified", "Escalated"}
ACTION_NORMALISE = {
    "Approve":  "Approved",
    "Reject":   "Rejected",
    "Modify":   "Modified",
    "Escalate": "Escalated",
    "Approved": "Approved",
    "Rejected": "Rejected",
    "Modified": "Modified",
    "Escalated":"Escalated",
}


@router.post("/{session_id}/pr/{pr_id}")
async def submit_review(
    session_id: str, pr_id: str, body: ReviewRequest,
    db: AsyncSession = Depends(get_db),
):
    session_id = validate_uuid(session_id)
    # Normalise action
    action = ACTION_NORMALISE.get(body.action)
    if not action:
        raise HTTPException(400, f"action must be one of {sorted(VALID_ACTIONS)}")

    result = await db.execute(
        select(PolicyPullRequest).where(
            PolicyPullRequest.id == pr_id,
            PolicyPullRequest.session_id == session_id,
        )
    )
    pr = result.scalar_one_or_none()
    if not pr:
        raise HTTPException(404, "Pull request not found")

    # Upsert review decision — supports re-review / override of prior decisions
    rev_result = await db.execute(select(ReviewDecision).where(ReviewDecision.pr_id == pr_id))
    review = rev_result.scalar_one_or_none()
    if review:
        review.action        = action
        review.reviewer      = body.reviewer
        review.note          = body.note or ""
        review.modified_text = body.modified_text or ""
        review.updated_at    = datetime.now(timezone.utc)
    else:
        review = ReviewDecision(
            id=str(uuid.uuid4()),
            session_id=session_id,
            pr_id=pr_id,
            action=action,
            reviewer=body.reviewer,
            note=body.note or "",
            modified_text=body.modified_text or "",
        )
        db.add(review)

    pr.status = action.lower()

    # If reviewer modified the text, update the PR so audit trail reflects human-approved version
    if action == "Modified" and body.modified_text:
        pr.after_text = body.modified_text

    db.add(AuditRecord(
        id=str(uuid.uuid4()),
        session_id=session_id,
        obligation_id=pr.obligation_id,
        event_type="reviewed",
        event_data={
            "pr_id": pr_id, "action": action,
            "reviewer": body.reviewer, "note": body.note,
        },
        actor=body.reviewer,
    ))

    await db.commit()
    return {"pr_id": pr_id, "action": action, "reviewer": body.reviewer, "status": "recorded"}


@router.get("/{session_id}")
async def list_reviews(session_id: str, db: AsyncSession = Depends(get_db)):
    session_id = validate_uuid(session_id)
    result = await db.execute(
        select(ReviewDecision).where(ReviewDecision.session_id == session_id)
    )
    revs = result.scalars().all()
    return {"reviews": [
        {
            "id": r.id, "pr_id": r.pr_id, "action": r.action,
            "reviewer": r.reviewer, "note": r.note,
            "modified_text": r.modified_text,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in revs
    ]}
