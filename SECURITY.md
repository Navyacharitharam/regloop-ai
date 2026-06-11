# Security Policy

## Supported Versions

This is a prototype submission for the RegLoop AI challenge. Only the latest version is maintained.

## Security Controls

### Input Validation
- All uploaded files validated by magic bytes (`%PDF` prefix check) before processing
- Filenames sanitised — path separators and special characters stripped
- File size limited to 20 MB per file
- Policy document count capped at 1–3 files
- CSV parsing uses `csv.DictReader` (no shell or SQL involvement)
- All `session_id` path parameters validated as UUID v4 before reaching the database

### Prompt Injection Mitigation
- User-supplied document text is scanned for known prompt-injection patterns (e.g. "ignore previous instructions", `[INST]`, `<system>` tags) before being included in any Gemini prompt
- Matched patterns are replaced with `[REDACTED]`

### Secrets Management
- API keys loaded from `.env` via `python-dotenv` — never hardcoded
- `.env` excluded by `.gitignore` at root and backend level
- Codespaces secret injection via GitHub Secrets — key never written in source files
- `GEMINI_API_KEY` accessed as environment variable only

### Dependencies
- `python-multipart>=0.0.20` — patched against CVE-2024-53981 (ReDoS in multipart parser)
- `fastapi==0.115.0` — patched against CVE-2024-24762
- `pydantic==2.9.2` — patched against CVE-2024-3772
- Dependency versions pinned in `requirements.txt`

### CORS
- `allow_origins=["*"]` with `allow_credentials=False` — intentional for Codespaces/demo
- Restrict to specific origins for production deployment

### Docker / IaC
- Both containers run as non-root users (`appuser`)
- `no-new-privileges:true` security option on both services
- Memory limits applied (512 MB backend, 256 MB frontend)
- Services isolated on an internal bridge network
- `HEALTHCHECK` instructions on both Dockerfiles

### AI Output Handling
- Gemini output is parsed as JSON only — never `eval()`'d or executed
- JSON extraction uses regex to find the outermost `[...]` or `{...}` block
- Malformed AI output triggers fallback to hardcoded safe data rather than crashing

## Reporting a Vulnerability

This is a competition prototype. For security issues, open a GitHub issue marked `[SECURITY]`.
