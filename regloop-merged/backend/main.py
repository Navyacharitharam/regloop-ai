"""
RegLoop AI — FastAPI Backend
Merged: uploaded version's router architecture + our Gemini engine + Codespaces CORS
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from dotenv import load_dotenv

from db.database import init_db
from routers import upload, obligations, mappings, gaps, pullrequests, reviews, audit, export

load_dotenv()

app = FastAPI(
    title="RegLoop AI API",
    description="Closed-Loop Regulatory Execution Engine — Powered by Gemini 2.0 Flash",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# CORS — allow all origins so Codespaces *.app.github.dev URLs work
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,   # must be False when allow_origins=["*"]
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await init_db()


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
