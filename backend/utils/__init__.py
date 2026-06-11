"""
Shared security utilities for RegLoop AI.
"""
import re
from fastapi import HTTPException

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def validate_uuid(value: str, field: str = "session_id") -> str:
    """Raise 400 if *value* is not a valid UUID v4.

    Prevents path-traversal, SQL-wildcard injection, and oversized input from
    reaching the database layer via URL path parameters.
    """
    if not value or not _UUID_RE.match(value.strip()):
        raise HTTPException(status_code=400, detail=f"Invalid {field} format")
    return value.strip()
