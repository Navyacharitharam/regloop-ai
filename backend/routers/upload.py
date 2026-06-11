"""
FR-1 Upload Workspace Router
Handles file uploads, validation, session creation
"""
import uuid
import re
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json

from db.database import get_db, WorkspaceSession, AuditRecord
from services.document_service import extract_pdf_text, parse_csv

router = APIRouter()

ALLOWED_PDF_TYPES  = {"application/pdf", "application/octet-stream"}
ALLOWED_CSV_TYPES  = {"text/csv", "application/csv", "text/plain", "application/octet-stream"}
MAX_FILE_SIZE_MB   = 20
MAX_FILE_BYTES     = MAX_FILE_SIZE_MB * 1024 * 1024
PDF_MAGIC_BYTES    = b"%PDF"   # Every valid PDF starts with %PDF

# Keep these in sync with ai_service.py
MAX_REG_CHARS = 20000
MAX_POL_CHARS = 15000

_SAFE_FILENAME = re.compile(r"[^\w\s\-.]")  # strip anything outside word chars, space, dash, dot


def _sanitize_filename(name: str) -> str:
    """Remove path separators and special chars from uploaded filenames."""
    name = name.replace("/", "").replace("\\", "").replace("..", "")
    name = _SAFE_FILENAME.sub("", name)
    return name[:120] or "unnamed"


def _validate_pdf_magic(data: bytes, filename: str) -> None:
    """Reject files that claim to be PDFs but lack the PDF magic bytes."""
    if not data.startswith(PDF_MAGIC_BYTES):
        raise HTTPException(400, f"'{filename}' does not appear to be a valid PDF file")


@router.post("/session")
async def create_session(
    regulation: UploadFile = File(...),
    policies: list[UploadFile] = File(...),
    matrix: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new analysis session by uploading:
    - 1 regulatory PDF
    - 1-3 internal policy PDFs
    - 1 responsibility matrix CSV
    """
    # ── Validate file counts ──
    if len(policies) > 3:
        raise HTTPException(400, "Maximum 3 policy documents allowed")
    if len(policies) < 1:
        raise HTTPException(400, "At least 1 policy document required")

    # ── Validate regulation PDF ──
    reg_bytes = await regulation.read()
    if len(reg_bytes) > MAX_FILE_BYTES:
        raise HTTPException(400, f"Regulation file exceeds {MAX_FILE_SIZE_MB}MB limit")
    _validate_pdf_magic(reg_bytes, regulation.filename or "regulation")
    safe_reg_name = _sanitize_filename(regulation.filename or "regulation.pdf")

    # ── Extract regulation text ──
    reg_text = await extract_pdf_text(reg_bytes, safe_reg_name)

    # ── Extract policy texts ──
    policy_names = []
    policy_texts = {}
    for p in policies:
        p_bytes = await p.read()
        if len(p_bytes) > MAX_FILE_BYTES:
            raise HTTPException(400, f"Policy file '{p.filename}' exceeds {MAX_FILE_SIZE_MB}MB limit")
        _validate_pdf_magic(p_bytes, p.filename or "policy")
        safe_name = _sanitize_filename(p.filename or "policy.pdf")
        text = await extract_pdf_text(p_bytes, safe_name)
        policy_names.append(safe_name)
        policy_texts[safe_name] = text

    # ── Parse CSV matrix ──
    csv_bytes = await matrix.read()
    safe_matrix_name = _sanitize_filename(matrix.filename or "matrix.csv")
    try:
        matrix_data = parse_csv(csv_bytes)
    except Exception as e:
        raise HTTPException(400, f"Invalid CSV format: {str(e)}")

    # ── Create session ──
    session_id = str(uuid.uuid4())
    session = WorkspaceSession(
        id=session_id,
        regulation_name=safe_reg_name,
        regulation_text=reg_text,
        policy_names=policy_names,
        policy_texts=policy_texts,
        matrix_data=matrix_data,
    )
    db.add(session)

    # ── FR-7: Write session_created audit event so the trail starts at upload ──
    db.add(AuditRecord(
        id=str(uuid.uuid4()),
        session_id=session_id,
        obligation_id=None,
        event_type="session_created",
        event_data={
            "regulation": safe_reg_name,
            "policies": policy_names,
            "matrix": safe_matrix_name,
            "matrix_rows": len(matrix_data),
            "reg_text_length": len(reg_text),
        },
        actor="Compliance Analyst",
    ))

    await db.commit()

    reg_truncated = len(reg_text) > MAX_REG_CHARS
    pol_truncated = [n for n, t in policy_texts.items() if len(t) > MAX_POL_CHARS]

    return {
        "session_id": session_id,
        "regulation": {
            "name": safe_reg_name,
            "text_length": len(reg_text),
            "preview": reg_text[:300] + "…" if len(reg_text) > 300 else reg_text,
            "truncated": reg_truncated,
        },
        "policies": [
            {"name": n, "text_length": len(t), "preview": t[:200] + "…", "truncated": len(t) > MAX_POL_CHARS}
            for n, t in policy_texts.items()
        ],
        "matrix": {
            "name": safe_matrix_name,
            "rows": len(matrix_data),
            "columns": list(matrix_data[0].keys()) if matrix_data else [],
        },
        "status": "ready",
        "message": "Session created. Ready to begin analysis.",
        "warnings": (
            ([f"Regulatory document is large — only the first ~{MAX_REG_CHARS:,} characters will be sent to the AI. Obligations near the end of long documents may be missed."] if reg_truncated else []) +
            ([f"Policy document(s) truncated for AI context: {', '.join(pol_truncated)}"] if pol_truncated else [])
        ),
    }


@router.get("/session/{session_id}")
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """Retrieve session metadata."""
    result = await db.execute(select(WorkspaceSession).where(WorkspaceSession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")
    return {
        "session_id": session.id,
        "created_at": session.created_at.isoformat(),
        "regulation_name": session.regulation_name,
        "policy_names": session.policy_names,
        "matrix_rows": len(session.matrix_data or []),
    }


@router.get("/session/{session_id}/status")
async def get_session_status(session_id: str, db: AsyncSession = Depends(get_db)):
    """Poll-friendly status endpoint — returns session status and counts for each pipeline stage."""
    from db.database import Obligation, PolicyMapping, GapAnalysis, PolicyPullRequest
    from sqlalchemy import func, select as sel

    result = await db.execute(select(WorkspaceSession).where(WorkspaceSession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")

    obl_count = (await db.execute(sel(func.count()).select_from(Obligation).where(Obligation.session_id == session_id))).scalar()
    map_count = (await db.execute(sel(func.count()).select_from(PolicyMapping).where(PolicyMapping.session_id == session_id))).scalar()
    gap_count = (await db.execute(sel(func.count()).select_from(GapAnalysis).where(GapAnalysis.session_id == session_id))).scalar()
    pr_count  = (await db.execute(sel(func.count()).select_from(PolicyPullRequest).where(PolicyPullRequest.session_id == session_id))).scalar()

    return {
        "session_id":     session_id,
        "status":         session.status,
        "obligations":    obl_count,
        "mappings":       map_count,
        "gaps":           gap_count,
        "pull_requests":  pr_count,
    }
