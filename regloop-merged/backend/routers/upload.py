"""
FR-1 Upload Workspace Router
Handles file uploads, validation, session creation
"""
import uuid
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json

from db.database import get_db, WorkspaceSession
from services.document_service import extract_pdf_text, parse_csv

router = APIRouter()

ALLOWED_PDF_TYPES  = {"application/pdf", "application/octet-stream"}
ALLOWED_CSV_TYPES  = {"text/csv", "application/csv", "text/plain", "application/octet-stream"}
MAX_FILE_SIZE_MB   = 20
MAX_FILE_BYTES     = MAX_FILE_SIZE_MB * 1024 * 1024


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

    # ── Extract regulation text ──
    reg_text = await extract_pdf_text(reg_bytes, regulation.filename)

    # ── Extract policy texts ──
    policy_names = []
    policy_texts = {}
    for p in policies:
        p_bytes = await p.read()
        if len(p_bytes) > MAX_FILE_BYTES:
            raise HTTPException(400, f"Policy file '{p.filename}' exceeds {MAX_FILE_SIZE_MB}MB limit")
        text = await extract_pdf_text(p_bytes, p.filename)
        policy_names.append(p.filename)
        policy_texts[p.filename] = text

    # ── Parse CSV matrix ──
    csv_bytes = await matrix.read()
    try:
        matrix_data = parse_csv(csv_bytes)
    except Exception as e:
        raise HTTPException(400, f"Invalid CSV format: {str(e)}")

    # ── Create session ──
    session_id = str(uuid.uuid4())
    session = WorkspaceSession(
        id=session_id,
        regulation_name=regulation.filename,
        regulation_text=reg_text,
        policy_names=policy_names,
        policy_texts=policy_texts,
        matrix_data=matrix_data,
    )
    db.add(session)
    await db.commit()

    return {
        "session_id": session_id,
        "regulation": {
            "name": regulation.filename,
            "text_length": len(reg_text),
            "preview": reg_text[:300] + "…" if len(reg_text) > 300 else reg_text,
        },
        "policies": [
            {"name": n, "text_length": len(t), "preview": t[:200] + "…"}
            for n, t in policy_texts.items()
        ],
        "matrix": {
            "name": matrix.filename,
            "rows": len(matrix_data),
            "columns": list(matrix_data[0].keys()) if matrix_data else [],
        },
        "status": "ready",
        "message": "Session created. Ready to begin analysis.",
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
