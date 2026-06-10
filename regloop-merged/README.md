# RegLoop AI — Closed-Loop Regulatory Execution MVP

> Transform regulatory change into a structured, human-reviewed compliance package in minutes.

**Stack**: Next.js 14 · FastAPI · SQLite/PostgreSQL · **Gemini 2.0 Flash (free)**

---

## What It Does

```
Regulation PDF → Extract Obligations → Map to Policies → Gap Analysis
→ Policy Pull Requests → Human Review → Audit Trail → Export
```

Every step is AI-assisted. Every decision requires human approval. No policy is ever changed automatically.

---

## Quick Start

### 1. Get a free Gemini API key
https://aistudio.google.com/app/apikey — no credit card required.

### 2. Backend
```bash
cd backend
echo "GEMINI_API_KEY=your_key_here" > .env
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```
Swagger docs: http://localhost:8000/api/docs

### 3. Frontend
```bash
cd frontend
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm install && npm run dev
```
App: http://localhost:3000

---

## Codespaces (recommended — no local install needed)

See **CODESPACES.md** for the full guide. Summary:

1. Push to GitHub
2. Add `GEMINI_API_KEY` secret at github.com/settings/codespaces
3. Create codespace → runs setup automatically
4. Set port 8000 to **Public** in the PORTS tab
5. `bash .devcontainer/start.sh`
6. Open port 3000 in browser

---

## Sample Data (official reviewer inputs)

| File | Upload as |
|------|-----------|
| `sample_data/DORA_ICT_Risk_Update_2026.pdf` | Regulatory Update |
| `sample_data/ICT_Risk_Policy.pdf` | Internal Policy |
| `sample_data/Vendor_Risk_Policy.pdf` | Internal Policy |
| `sample_data/Incident_Response_Policy.pdf` | Internal Policy |
| `sample_data/responsibility_matrix.csv` | Responsibility Matrix |

---

## Architecture

```
Browser (Next.js)
    │ REST API
FastAPI Backend
    ├── /api/upload        — FR-1: Session + file upload
    ├── /api/obligations   — FR-2: Obligation extraction
    ├── /api/mappings      — FR-3: Policy mapping
    ├── /api/gaps          — FR-4: Gap analysis
    ├── /api/pullrequests  — FR-5: PR generation
    ├── /api/reviews       — FR-6: Human review workflow
    ├── /api/audit         — FR-7: Audit trail + traceability
    └── /api/export        — FR-8: JSON + CSV export
    │
    ├── Gemini 2.0 Flash (4 prompts per run)
    │   ├── Obligation extraction  (detailed system prompt + DORA fallback)
    │   ├── Policy mapping         (semantic + rationale field)
    │   ├── Gap analysis           (coverage + risk + recommended action)
    │   └── PR generation          (before/after + implementation steps)
    │
    └── SQLite (dev) / PostgreSQL (prod)
        8 tables: sessions, obligations, mappings, gaps, PRs,
                  review_decisions, audit_records
```

---

## FR Compliance

| FR | Feature | Implementation |
|----|---------|---------------|
| FR-1 | Upload workspace | Single-call session creation: 1 regulation + 1-3 policies + 1 CSV |
| FR-2 | Obligation extraction | OBL-001 IDs, statement, full_text, source, domain, confidence, notes |
| FR-3 | Policy mapping | Semantic via Gemini; excerpt + rationale + confidence bar |
| FR-4 | Gap analysis | Fully/Partially/Not Covered + High/Medium/Low + recommended_action |
| FR-5 | Policy PR generator | before_text, after_text, implementation_steps, estimated_effort |
| FR-6 | Human review | Approve / Reject / Modify / Escalate; reviewer name + notes recorded |
| FR-7 | Audit memory | Per-obligation traceability grid + full chronological event log |
| FR-8 | Export | JSON (nested + audit trail) + CSV (all columns inc. before/after) |

---

## AI Design

**4 sequential Gemini prompts per analysis run:**

| Stage | Purpose | Fallback |
|-------|---------|---------|
| Obligation Extraction | Extract every obligation with OBL-001 IDs, full_text, domain | 14 DORA-specific hardcoded obligations |
| Policy Mapping | Semantic match to policy sections with rationale | Domain-based fallback mappings |
| Gap Analysis | Coverage + risk + recommended action — detects "periodically" vs "annually" | 14 DORA-specific gap descriptions |
| PR Generation | before/after amendment + implementation steps | 14 DORA-specific policy amendments |

**Fallbacks**: if Gemini is unavailable or rate-limited, the system returns realistic DORA-specific data so the demo always works.

---

## License
MIT
