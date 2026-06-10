"""FR-8 Export Router – JSON and CSV"""
import csv
import io
import json
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.database import (
    get_db, WorkspaceSession, Obligation, PolicyMapping,
    GapAnalysis, PolicyPullRequest, ReviewDecision, AuditRecord,
)

router = APIRouter()


async def _build_package(session_id: str, db: AsyncSession) -> dict:
    result = await db.execute(select(WorkspaceSession).where(WorkspaceSession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")

    obs   = (await db.execute(select(Obligation).where(Obligation.session_id == session_id))).scalars().all()
    maps  = (await db.execute(select(PolicyMapping).where(PolicyMapping.session_id == session_id))).scalars().all()
    gaps  = (await db.execute(select(GapAnalysis).where(GapAnalysis.session_id == session_id))).scalars().all()
    prs   = (await db.execute(select(PolicyPullRequest).where(PolicyPullRequest.session_id == session_id))).scalars().all()
    revs  = (await db.execute(select(ReviewDecision).where(ReviewDecision.session_id == session_id))).scalars().all()
    audit = (await db.execute(select(AuditRecord).where(AuditRecord.session_id == session_id).order_by(AuditRecord.created_at))).scalars().all()

    maps_by_ob = {m.obligation_id: m for m in maps}
    gaps_by_ob = {g.obligation_id: g for g in gaps}
    prs_by_ob  = {p.obligation_id: p for p in prs}
    revs_by_pr = {r.pr_id: r for r in revs}

    return {
        "metadata": {
            "exported_at":    datetime.utcnow().isoformat() + "Z",
            "session_id":     session_id,
            "regulation":     session.regulation_name,
            "policies":       session.policy_names,
            "matrix":         session.matrix_data[:5] if session.matrix_data else [],
            "generator":      "RegLoop AI v1.0",
        },
        "summary": {
            "total_obligations":  len(obs),
            "fully_covered":      sum(1 for g in gaps if g.coverage == "Fully Covered"),
            "partially_covered":  sum(1 for g in gaps if g.coverage == "Partially Covered"),
            "not_covered":        sum(1 for g in gaps if g.coverage == "Not Covered"),
            "high_risk_gaps":     sum(1 for g in gaps if g.risk_level == "High"),
            "pull_requests":      len(prs),
            "approved":           sum(1 for r in revs if r.action == "Approved"),
            "rejected":           sum(1 for r in revs if r.action == "Rejected"),
            "pending":            len(prs) - len(revs),
        },
        "obligations": [
            {"id": o.id, "statement": o.statement, "full_text": o.full_text,
             "source": o.source, "domain": o.domain, "confidence": o.confidence}
            for o in obs
        ],
        "policy_mappings": [
            {"obligation_id": m.obligation_id, "policy_name": m.policy_name,
             "policy_section": m.policy_section, "excerpt": m.excerpt, "confidence": m.confidence}
            for m in maps
        ],
        "gap_analysis": [
            {"obligation_id": g.obligation_id, "coverage": g.coverage,
             "risk_level": g.risk_level, "explanation": g.explanation, "cited_source": g.cited_source}
            for g in gaps
        ],
        "policy_pull_requests": [
            {"id": p.id, "obligation_id": p.obligation_id, "title": p.title,
             "gap_description": p.gap_description, "regulatory_citation": p.regulatory_citation,
             "suggested_owner": p.suggested_owner, "risk_level": p.risk_level,
             "confidence": p.confidence, "before_text": p.before_text, "after_text": p.after_text,
             "status": p.status}
            for p in prs
        ],
        "review_decisions": [
            {"pr_id": r.pr_id, "action": r.action, "reviewer": r.reviewer,
             "note": r.note, "timestamp": r.created_at.isoformat()}
            for r in revs
        ],
        "audit_trail": [
            {"event_type": a.event_type, "obligation_id": a.obligation_id,
             "actor": a.actor, "data": a.event_data, "timestamp": a.created_at.isoformat()}
            for a in audit
        ],
    }


@router.get("/{session_id}/json")
async def export_json(session_id: str, db: AsyncSession = Depends(get_db)):
    package = await _build_package(session_id, db)
    content = json.dumps(package, indent=2)
    return StreamingResponse(
        io.BytesIO(content.encode()),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=regloop-{session_id[:8]}.json"},
    )


@router.get("/{session_id}/csv")
async def export_csv(session_id: str, db: AsyncSession = Depends(get_db)):
    package = await _build_package(session_id, db)

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "obligation_id", "obligation_statement", "regulatory_source", "domain", "confidence",
        "policy_name", "policy_section", "mapping_confidence",
        "coverage_status", "risk_level", "gap_explanation",
        "pr_id", "pr_title", "suggested_owner", "pr_confidence",
        "review_action", "reviewer", "review_note", "reviewed_at",
    ])

    maps = {m["obligation_id"]: m for m in package["policy_mappings"]}
    gaps = {g["obligation_id"]: g for g in package["gap_analysis"]}
    prs  = {p["obligation_id"]: p for p in package["policy_pull_requests"]}
    revs = {r["pr_id"]: r for r in package["review_decisions"]}

    for ob in package["obligations"]:
        m  = maps.get(ob["id"], {})
        g  = gaps.get(ob["id"], {})
        pr = prs.get(ob["id"], {})
        rv = revs.get(pr.get("id", ""), {})
        writer.writerow([
            ob["id"], ob["statement"], ob["source"], ob["domain"], ob.get("confidence",""),
            m.get("policy_name",""), m.get("policy_section",""), m.get("confidence",""),
            g.get("coverage",""), g.get("risk_level",""), g.get("explanation",""),
            pr.get("id",""), pr.get("title",""), pr.get("suggested_owner",""), pr.get("confidence",""),
            rv.get("action",""), rv.get("reviewer",""), rv.get("note",""), rv.get("timestamp",""),
        ])

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.read().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=regloop-{session_id[:8]}.csv"},
    )


@router.get("/{session_id}/summary")
async def export_summary(session_id: str, db: AsyncSession = Depends(get_db)):
    package = await _build_package(session_id, db)
    return JSONResponse({"summary": package["summary"], "metadata": package["metadata"]})
