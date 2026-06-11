"""
RegLoop AI — FastAPI Backend
Merged: uploaded version's router architecture + our Gemini engine + Codespaces CORS
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
from dotenv import load_dotenv

from db.database import init_db
from routers import upload, obligations, mappings, gaps, pullrequests, reviews, audit, export

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="RegLoop AI API",
    description="Closed-Loop Regulatory Execution Engine — Powered by Gemini 2.0 Flash",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

# CORS — Codespaces generates dynamic *.app.github.dev preview URLs that change
# on every new codespace.  For local dev and CI we default to permissive CORS;
# set ALLOWED_ORIGINS in production to restrict to your actual domain.
_raw_origins = os.getenv("ALLOWED_ORIGINS", "*")
_allow_all   = _raw_origins == "*"
_origins     = ["*"] if _allow_all else [o.strip() for o in _raw_origins.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=not _allow_all,   # credentials require explicit origins
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
)


app.include_router(upload.router,       prefix="/api/upload",       tags=["Upload"])
app.include_router(obligations.router,  prefix="/api/obligations",  tags=["Obligations"])
app.include_router(mappings.router,     prefix="/api/mappings",     tags=["Mappings"])
app.include_router(gaps.router,         prefix="/api/gaps",         tags=["Gaps"])
app.include_router(pullrequests.router, prefix="/api/pullrequests", tags=["Pull Requests"])
app.include_router(reviews.router,      prefix="/api/reviews",      tags=["Reviews"])
app.include_router(audit.router,        prefix="/api/audit",        tags=["Audit"])
app.include_router(export.router,       prefix="/api/export",       tags=["Export"])


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "RegLoop AI", "version": "1.0.0", "ai": "Gemini 2.0 Flash"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
