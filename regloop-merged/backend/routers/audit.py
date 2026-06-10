"""FR-7 Audit Memory Router"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.database import (
    get_db, AuditRecord, WorkspaceSession,
    Obligation, PolicyMapping, GapAnalysis,
    PolicyPullRequest, ReviewDecision,
)

router = APIRouter()


@router.get("/{session_id}/trail")
async def get_audit_trail(session_id: str, db: AsyncSession = Depends(get_db)):
    """Return complete end-to-end audit trail for a session."""

    result = await db.execute(select(WorkspaceSession).where(WorkspaceSession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")

    obs      = {o.id: o for o in (await db.execute(select(Obligation).where(Obligation.session_id == session_id))).scalars().all()}
    maps     = {m.obligation_id: m for m in (await db.execute(select(PolicyMapping).where(PolicyMapping.session_id == session_id))).scalars().all()}
    gaps     = {g.obligation_id: g for g in (await db.execute(select(GapAnalysis).where(GapAnalysis.session_id == session_id))).scalars().all()}
    prs_list = (await db.execute(select(PolicyPullRequest).where(PolicyPullRequest.session_id == session_id))).scalars().all()
    prs      = {p.obligation_id: p for p in prs_list}
    revs     = {r.pr_id: r for r in (await db.execute(select(ReviewDecision).where(ReviewDecision.session_id == session_id))).scalars().all()}
    records  = (await db.execute(select(AuditRecord).where(AuditRecord.session_id == session_id).order_by(AuditRecord.created_at))).scalars().all()

    # Build enriched trail entries
    trail = []
    for ob_id, ob in obs.items():
        m   = maps.get(ob_id)
        g   = gaps.get(ob_id)
        pr  = prs.get(ob_id)
        rev = revs.get(pr.id) if pr else None

        trail.append({
            "obligation_id":       ob.id,
            "regulatory_source":   session.regulation_name,
            "obligation":          ob.statement,
            "source_citation":     ob.source,
            "domain":              ob.domain,
            "policy_mapping":      {"policy": m.policy_name, "section": m.policy_section, "confidence": m.confidence} if m else None,
            "gap_analysis":        {"coverage": g.coverage, "risk_level": g.risk_level, "explanation": g.explanation} if g else None,
            "proposed_amendment":  {"pr_id": pr.id, "title": pr.title, "owner": pr.suggested_owner} if pr else None,
            "review_decision":     {"action": rev.action, "reviewer": rev.reviewer, "note": rev.note, "timestamp": rev.created_at.isoformat()} if rev else None,
            "timestamp":           ob.created_at.isoformat() if ob.created_at else None,
        })

    return {
        "session_id": session_id,
        "regulation": session.regulation_name,
        "created_at": session.created_at.isoformat(),
        "total_obligations": len(obs),
        "total_prs": len(prs),
        "total_reviews": len(revs),
        "trail": trail,
        "raw_events": [
            {"event_type": r.event_type, "obligation_id": r.obligation_id,
             "actor": r.actor, "data": r.event_data, "timestamp": r.created_at.isoformat()}
            for r in records
        ],
    }
