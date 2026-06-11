"""FR-8 Export Router – JSON and CSV"""
import csv
import io
import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from utils import validate_uuid
from db.database import (
    get_db, WorkspaceSession, Obligation, PolicyMapping,
    GapAnalysis, PolicyPullRequest, ReviewDecision, AuditRecord,
)

router = APIRouter()


async def _build_package(session_id: str, db: AsyncSession) -> dict:
    session_id = validate_uuid(session_id)
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

    maps_by_ob: dict[str, list] = {}
    for m in maps:
        maps_by_ob.setdefault(m.obligation_id, []).append(m)
    gaps_by_ob = {g.obligation_id: g for g in gaps}
    prs_by_ob  = {p.obligation_id: p for p in prs}
    revs_by_pr = {r.pr_id: r for r in revs}

    return {
        "metadata": {
            "exported_at":    datetime.now(timezone.utc).isoformat(),
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
             "risk_level": g.risk_level, "explanation": g.explanation,
             "cited_source": g.cited_source, "recommended_action": g.recommended_action or ""}
            for g in gaps
        ],
        "policy_pull_requests": [
            {"id": p.id, "obligation_id": p.obligation_id, "title": p.title,
             "gap_description": p.gap_description, "regulatory_citation": p.regulatory_citation,
             "suggested_owner": p.suggested_owner, "risk_level": p.risk_level,
             "confidence": p.confidence, "before_text": p.before_text, "after_text": p.after_text,
             "implementation_steps": p.implementation_steps or [],
             "estimated_effort": p.estimated_effort or "",
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
        "traceability": [
            {
                "obligation_id":     o.id,
                "regulatory_source": session.regulation_name,
                "source_citation":   o.source,
                "domain":            o.domain,
                "responsible_owner": (
                    prs_by_ob[o.id].suggested_owner
                    if o.id in prs_by_ob
                    else next(
                        (f"{r.get('Owner','')} ({r.get('Department','')})"
                         for r in (session.matrix_data or [])
                         if r.get("Domain","").lower() in o.domain.lower()
                         or o.domain.lower() in r.get("Domain","").lower()),
                        ""
                    )
                ),
                "coverage":          gaps_by_ob[o.id].coverage if o.id in gaps_by_ob else "",
                "risk_level":        gaps_by_ob[o.id].risk_level if o.id in gaps_by_ob else "",
                "pr_id":             prs_by_ob[o.id].id if o.id in prs_by_ob else "",
                "review_action":     revs_by_pr[prs_by_ob[o.id].id].action if o.id in prs_by_ob and prs_by_ob[o.id].id in revs_by_pr else "Pending",
            }
            for o in obs
        ],
    }


@router.get("/{session_id}/json")
async def export_json(session_id: str, db: AsyncSession = Depends(get_db)):
    session_id = validate_uuid(session_id)
    package = await _build_package(session_id, db)
    content = json.dumps(package, indent=2)
    return StreamingResponse(
        io.BytesIO(content.encode()),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=regloop-{session_id[:8]}.json"},
    )


@router.get("/{session_id}/csv")
async def export_csv(session_id: str, db: AsyncSession = Depends(get_db)):
    session_id = validate_uuid(session_id)
    package = await _build_package(session_id, db)

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "obligation_id", "obligation_statement", "regulatory_source", "domain", "confidence",
        "responsible_owner",
        "policy_name", "policy_section", "mapping_confidence",
        "coverage_status", "risk_level", "gap_explanation", "recommended_action",
        "pr_id", "pr_title", "before_text", "after_text",
        "suggested_owner", "pr_confidence",
        "implementation_steps", "estimated_effort",
        "review_action", "reviewer", "review_note", "reviewed_at",
    ])

    maps = {}
    for m in package["policy_mappings"]:
        oid = m["obligation_id"]
        if oid not in maps:
            maps[oid] = dict(m)  # copy so we can mutate safely
        else:
            # Merge additional mappings as semicolon-delimited fields
            maps[oid]["policy_name"]    += "; " + m["policy_name"]
            maps[oid]["policy_section"] += "; " + m["policy_section"]
            # Keep the highest confidence value across all mappings for this obligation
            maps[oid]["confidence"] = max(maps[oid]["confidence"], m.get("confidence", 0))
    gaps = {g["obligation_id"]: g for g in package["gap_analysis"]}
    prs  = {p["obligation_id"]: p for p in package["policy_pull_requests"]}
    revs = {r["pr_id"]: r for r in package["review_decisions"]}

    for ob in package["obligations"]:
        m  = maps.get(ob["id"], {})
        g  = gaps.get(ob["id"], {})
        pr = prs.get(ob["id"], {})
        rv = revs.get(pr.get("id", ""), {})
        # Resolve owner: from PR if present, else from traceability block
        trace_owner = next(
            (t["responsible_owner"] for t in package.get("traceability", []) if t["obligation_id"] == ob["id"]),
            pr.get("suggested_owner", ""),
        )
        writer.writerow([
            ob["id"], ob["statement"], ob["source"], ob["domain"], ob.get("confidence",""),
            trace_owner,
            m.get("policy_name",""), m.get("policy_section",""), m.get("confidence",""),
            g.get("coverage",""), g.get("risk_level",""), g.get("explanation",""), g.get("recommended_action",""),
            pr.get("id",""), pr.get("title",""), pr.get("before_text",""), pr.get("after_text",""),
            pr.get("suggested_owner",""), pr.get("confidence",""),
            "|".join(pr.get("implementation_steps") or []), pr.get("estimated_effort",""),
            rv.get("action",""), rv.get("reviewer",""), rv.get("note",""), rv.get("timestamp",""),
        ])

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(b'\xef\xbb\xbf' + output.read().encode('utf-8')),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=regloop-{session_id[:8]}.csv"},
    )


@router.get("/{session_id}/summary")
async def export_summary(session_id: str, db: AsyncSession = Depends(get_db)):
    session_id = validate_uuid(session_id)
    package = await _build_package(session_id, db)
    return JSONResponse({"summary": package["summary"], "metadata": package["metadata"]})
