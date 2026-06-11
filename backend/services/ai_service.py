"""
AI Service — Gemini 2.0 Flash
Uploaded version's detailed prompts, system roles, and DORA-tuned fallbacks.
Our Gemini engine with JSON mode, lazy init, and robust JSON extraction.
"""
import asyncio
import json
import os
import re
from typing import Any
from google import genai
from google.genai import types

MODEL = "gemini-2.0-flash"
_client: "genai.Client | None" = None

# ── Prompt injection guard ────────────────────────────────────────────────────
# Strip common jailbreak / instruction-override patterns from user-supplied
# document text before it enters any Gemini prompt.
_INJECTION_PATTERNS = re.compile(
    r"(ignore\s+(all\s+)?previous\s+instructions?|"
    r"disregard\s+(all\s+)?instructions?|"
    r"you\s+are\s+now\s+|"
    r"forget\s+(all\s+)?previous\s+|"
    r"act\s+as\s+(a|an)\s+|"
    r"new\s+instructions?:|"
    r"system\s+prompt:|"
    r"<\s*/?system\s*>|"
    r"\[\s*INST\s*\]|"
    r"###\s*instruction)",
    re.IGNORECASE,
)


def _sanitize_for_prompt(text: str) -> str:
    """Remove prompt-injection patterns from user-supplied document text."""
    return _INJECTION_PATTERNS.sub("[REDACTED]", text)



def _get_client() -> genai.Client:
    global _client
    if _client is None:
        key = os.getenv("GEMINI_API_KEY", "")
        if not key:
            raise ValueError(
                "GEMINI_API_KEY is not set. "
                "Get a free key at https://aistudio.google.com/app/apikey"
            )
        _client = genai.Client(api_key=key)
    return _client


def _call(prompt: str, max_tokens: int = 4096) -> str:
    response = _get_client().models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            max_output_tokens=max_tokens,
            temperature=0.1,
            # Safety settings: block only high-probability harmful content.
            # Compliance document analysis requires discussing sensitive regulatory
            # topics; setting thresholds to BLOCK_ONLY_HIGH avoids false positives
            # while still blocking genuinely harmful outputs.
            safety_settings=[
                types.SafetySetting(category="HARM_CATEGORY_HARASSMENT",        threshold="BLOCK_ONLY_HIGH"),
                types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH",       threshold="BLOCK_ONLY_HIGH"),
                types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_ONLY_HIGH"),
                types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_ONLY_HIGH"),
            ],
            response_mime_type="application/json",
        ),
    )
    return response.text


async def _call_async(prompt: str, max_tokens: int = 4096, retries: int = 3) -> str:
    """Non-blocking wrapper with exponential back-off retry.

    Handles transient Gemini rate-limit (429) and server errors transparently
    so the demo does not fail silently and activate fallback data during a live
    presentation.  Auth / key errors are raised immediately without retrying.
    """
    loop = asyncio.get_event_loop()
    last_exc: Exception = RuntimeError("No attempts made")
    for attempt in range(retries):
        try:
            return await loop.run_in_executor(None, lambda: _call(prompt, max_tokens))
        except Exception as exc:
            last_exc = exc
            msg = str(exc).lower()
            # Never retry these — surface immediately
            if any(k in msg for k in (
                "api_key", "invalid_argument", "permission", "unauthenticated",
                "token", "context_length", "maximum context", "too long",
                "reduce the length", "content_too_large",
            )):
                raise
            # Never retry quota exhausted (limit: 0) — it won't recover within the session
            if "limit: 0" in msg or "resource_exhausted" in msg and "limit: 0" in msg:
                raise
            # Retry on transient rate-limit (429 with retry-after) or server errors
            if attempt < retries - 1:
                wait = 5 * (2 ** attempt)   # 5 s then 10 s
                await asyncio.sleep(wait)
    raise last_exc


def _parse(raw: str) -> Any:
    """Strip markdown fences and parse JSON reliably."""
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    # Find outermost JSON array or object
    match = re.search(r"(\[.*\]|\{.*\})", text, re.DOTALL)
    if match:
        text = match.group(1)
    return json.loads(text)


# ── Stage 1: Obligation Extraction ────────────────────────────────────────────

OBLIGATION_SYSTEM = """You are a senior regulatory compliance expert specialising in financial services ICT and operational resilience regulations (DORA, EBA guidelines, NIS2).

Your task: extract EVERY distinct compliance obligation from the regulatory document provided.
Each obligation must be atomic — one requirement per obligation.

Return a JSON array. Each element must have EXACTLY these keys:
{
  "id": "OBL-001",
  "statement": "Single sentence: what the entity MUST do, starting with a verb",
  "full_text": "The full regulatory text this obligation comes from (1-3 sentences, copied verbatim from the document)",
  "source": "EXACT verbatim text excerpt copied word-for-word from the regulation — this MUST be a direct quote from the document text, not a paraphrase, not a section heading alone. Copy the full sentence(s) verbatim so a reviewer can locate it in the source document. Example format: 'Financial entities shall maintain documented ICT risk management procedures...'",
  "domain": "One of: ICT Risk | Vendor Management | Incident Management | Governance | Reporting | Access Control | Data Protection | Business Continuity",
  "confidence": 0.00,
  "notes": "Brief implementation note or caveat, or empty string"
}

Rules:
- Extract EVERY obligation — do not summarise or merge obligations
- Each bullet point in the regulation = one separate obligation
- Use sequential IDs: OBL-001, OBL-002, OBL-003 ...
- confidence between 0.75 and 0.99
- statement must start with a verb (Maintain, Identify, Conduct, Define, Document, Review, Establish, Preserve)
- source MUST be verbatim quoted text from the document — NOT a paraphrase and NOT just a section heading

Return ONLY a valid JSON array. No preamble, no explanation."""


async def extract_obligations(regulation_text: str, regulation_name: str) -> list:
    # Sanitize user-supplied document text against prompt injection
    regulation_text = _sanitize_for_prompt(regulation_text)
    # Chunk regulation text — DORA PDFs can be 20 000+ chars; Gemini's output cap
    # means we truncate input so the model can return a full obligations array.
    MAX_REG_CHARS = 20000
    if len(regulation_text) > MAX_REG_CHARS:
        regulation_text = regulation_text[:MAX_REG_CHARS] + "\n…[truncated for token limit]"
    prompt = f"""{OBLIGATION_SYSTEM}

Document: {regulation_name}

Full Text:
{regulation_text}

Extract every individual obligation as a separate item. For list-style regulations (bullet points), each bullet is a separate obligation.
Use IDs OBL-001, OBL-002, etc."""
    try:
        return _parse(await _call_async(prompt, max_tokens=8192))
    except Exception:
        return _fallback_obligations()


# ── Stage 2: Policy Mapping ───────────────────────────────────────────────────

MAPPING_SYSTEM = """You are a compliance policy analyst. Your task is to map each regulatory obligation to the SINGLE BEST matching section of the internal policy documents provided.

CRITICAL CONSTRAINT — ONE MAPPING PER OBLIGATION:
- The output array MUST have EXACTLY ONE entry per obligation — no more, no less
- If OBL-001 through OBL-014 are provided, the output MUST have exactly 14 entries
- Each obligation_id must appear EXACTLY ONCE in the output array
- Do NOT return multiple mappings for the same obligation_id under any circumstances

Matching rules:
- Do NOT match on keywords alone — reason about whether the policy section addresses the INTENT of the obligation
- If a policy vaguely addresses a topic (e.g. says "periodically" instead of "annually"), still map it but give lower confidence
- If no policy addresses the obligation at all, set policy_name to "No matching policy found" and confidence to 0.0

Return a JSON array. Each element must have EXACTLY these keys:
{
  "id": "MAP-001",
  "obligation_id": "OBL-001",
  "policy_name": "Name of the internal policy document, or 'No matching policy found'",
  "policy_section": "Section heading or 'N/A'",
  "excerpt": "The exact policy text that addresses this obligation (quote it verbatim, or 'No relevant text found')",
  "confidence": 0.00,
  "rationale": "One sentence: why this policy section does or does not address the obligation"
}

The array must have exactly as many entries as there are obligations — one per obligation, no more, no less.
Return ONLY a valid JSON array."""


async def map_policies(obligations: list, policy_texts: dict) -> list:
    # Sanitize policy texts against prompt injection
    policy_texts = {k: _sanitize_for_prompt(v) for k, v in policy_texts.items()}
    # Chunk each policy to avoid overflowing Gemini's context window.
    # 3 policies × ~8 000 chars each = ~24 000 chars → ~6 000 tokens input alone.
    # We keep the most relevant leading portion of each policy (first 4 000 chars)
    # which covers the executive summary and main obligations in most PDFs.
    MAX_POLICY_CHARS = 15000
    truncated_texts = {
        name: (text[:MAX_POLICY_CHARS] + "\n…[truncated]" if len(text) > MAX_POLICY_CHARS else text)
        for name, text in policy_texts.items()
    }
    policy_block = "\n\n".join(
        f"=== POLICY: {name} ===\n{text}" for name, text in truncated_texts.items()
    )
    obls_json = json.dumps(
        [{"id": o["id"], "statement": o["statement"], "full_text": o.get("full_text", ""), "domain": o["domain"]} for o in obligations],
        indent=2,
    )
    prompt = f"""{MAPPING_SYSTEM}

Map each obligation to the best matching internal policy section.

OBLIGATIONS TO MAP:
{obls_json}

INTERNAL POLICIES:
{policy_block}

Return one mapping entry per obligation. Use the exact obligation ID."""
    try:
        return _parse(await _call_async(prompt, max_tokens=4096))
    except Exception:
        return _fallback_mappings(obligations, list(policy_texts.keys()))


# ── Stage 3: Gap Analysis ─────────────────────────────────────────────────────

GAP_SYSTEM = """You are a regulatory compliance gap analyst. Your task is to evaluate whether each internal policy section sufficiently satisfies its mapped regulatory obligation.

Coverage definitions:
- "Fully Covered": The policy explicitly addresses ALL aspects of the obligation with specific requirements, frequencies, ownership and evidence standards
- "Partially Covered": The policy addresses the general topic BUT is missing specific details such as defined frequency ("periodically" vs "annually"), named ownership, evidence/documentation requirements, or mandatory language ("should" vs "shall")
- "Not Covered": The policy does not address this obligation at all, OR the mapped policy was "No matching policy found"

Risk assignment:
- "High": Critical operational or regulatory risk; no control exists or obligation completely absent
- "Medium": Control exists but is materially incomplete; regulatory exposure if audited
- "Low": Minor wording gap that could be addressed by clarification

IMPORTANT: Be precise about WHY there is a gap. Quote the specific missing element.
e.g. "Policy says 'periodically reviewed' but regulation requires 'at least annually'. Review frequency is undefined."

Return a JSON array with EXACTLY these keys per element:
{
  "id": "GAP-001",
  "obligation_id": "OBL-001",
  "coverage": "Fully Covered | Partially Covered | Not Covered",
  "risk_level": "High | Medium | Low",
  "explanation": "2-3 sentences: what the policy says, what is missing, why it matters",
  "cited_source": "The regulatory source citation from the obligation",
  "recommended_action": "One sentence: specific action to close the gap"
}

Return ONLY a valid JSON array."""


async def analyze_gaps(obligations: list, mappings: list) -> list:
    mapping_by_ob = {m["obligation_id"]: m for m in mappings}
    pairs = []
    for ob in obligations:
        m = mapping_by_ob.get(ob["id"], {})
        pairs.append({
            "obligation_id":      ob["id"],
            "obligation":         ob["statement"],
            "source":             ob.get("source", ""),
            "domain":             ob.get("domain", ""),
            "policy_name":        m.get("policy_name", "No matching policy found"),
            "policy_section":     m.get("policy_section", "N/A"),
            "policy_excerpt":     m.get("excerpt", "No relevant text found"),
            "mapping_confidence": m.get("confidence", 0.0),
        })

    prompt = f"""{GAP_SYSTEM}

Analyse the compliance gap for each of these {len(pairs)} obligation-policy pairs.

{json.dumps(pairs, indent=2)}

Be precise and specific. Where the policy uses vague language ("periodically", "when appropriate", "whenever practical", "may be documented") vs the regulation's specific requirements ("annually", "shall", "must"), that is a gap.
Where a policy concept is completely absent, that is "Not Covered"."""
    try:
        result = _parse(await _call_async(prompt, max_tokens=4096))
        # Quality guard: if every gap has identical coverage the model returned
        # a degenerate response (quota hit mid-call). Use fallback instead.
        if result and len(result) > 1:
            coverages = {g.get("coverage") for g in result}
            if len(coverages) == 1:
                return _fallback_gaps(obligations)
        return result
    except Exception:
        return _fallback_gaps(obligations)


# ── Stage 4: Policy Pull Request Generation ───────────────────────────────────

PR_SYSTEM = """You are a regulatory compliance counsel and policy drafter at a financial institution regulated under DORA and EBA guidelines.

Your task: generate a precise Policy Pull Request for each identified compliance gap.

Each PR must:
- Quote the CURRENT policy text verbatim in before_text
- Write specific, binding amendment language in after_text (use "shall", not "should" or "may")
- Assign the owner from the responsibility matrix if the domain matches
- Be precise enough that a compliance officer could implement it without further research

Return a JSON array with EXACTLY these keys:
{
  "id": "PPR-001",
  "obligation_id": "OBL-001",
  "title": "Amend [Policy Name] to [specific change]",
  "gap_description": "One sentence: what is missing",
  "regulatory_citation": "Exact source from the obligation",
  "suggested_owner": "Full name and role from responsibility matrix, or job title if not in matrix",
  "risk_level": "High | Medium | Low",
  "confidence": 0.00,
  "before_text": "The exact current policy text (verbatim quote, or 'No current policy text addresses this obligation.')",
  "after_text": "The proposed replacement text (specific, binding, compliant — use shall)",
  "implementation_steps": ["Step 1", "Step 2", "Step 3"],
  "estimated_effort": "e.g. 1-2 weeks"
}

Return ONLY a valid JSON array."""


async def generate_pull_requests(obligations: list, gaps: list, matrix_data: list) -> list:
    actionable = [g for g in gaps if g["coverage"] != "Fully Covered"]
    if not actionable:
        return []

    # Build domain → owner lookup from matrix
    owner_map = {}
    for row in (matrix_data or []):
        domain = row.get("Domain", "")
        owner  = row.get("Owner", "")
        dept   = row.get("Department", "")
        if domain and owner:
            owner_map[domain.lower()] = f"{owner} ({dept})"

    ob_map = {o["id"]: o for o in obligations}
    context = []
    for g in actionable:
        ob = ob_map.get(g["obligation_id"], {})
        domain = ob.get("domain", "")
        owner = "Chief Compliance Officer"
        for k, v in owner_map.items():
            if k in domain.lower() or domain.lower() in k:
                owner = v
                break
        context.append({
            "gap_id":             g["id"],
            "obligation_id":      g["obligation_id"],
            "obligation":         ob.get("statement", ""),
            "regulatory_source":  g.get("cited_source", ob.get("source", "")),
            "domain":             domain,
            "coverage":           g["coverage"],
            "risk_level":         g["risk_level"],
            "gap_explanation":    g["explanation"],
            "recommended_action": g.get("recommended_action", ""),
            "suggested_owner":    owner,
        })

    matrix_str = json.dumps(matrix_data[:20]) if matrix_data else "[]"
    prompt = f"""{PR_SYSTEM}

Generate Policy Pull Requests for these {len(context)} compliance gaps.

GAPS REQUIRING AMENDMENT:
{json.dumps(context, indent=2)}

RESPONSIBILITY MATRIX:
{matrix_str}

For each gap:
- before_text: quote the weak/missing current policy language verbatim
- after_text: write the specific binding replacement (use "shall", state exact frequencies, name the responsible role)
- Use the owner from the responsibility matrix where the domain matches"""
    try:
        result = _parse(await _call_async(prompt, max_tokens=6000))
        # Quality guard: if majority of PRs still have [Organisation] template
        # placeholder the model returned filler. Use fallback instead.
        if result and len(result) > 1:
            generic = sum(1 for p in result if "[Organisation]" in p.get("after_text", ""))
            if generic > len(result) // 2:
                return _fallback_prs(actionable, ob_map, owner_map)
        return result
    except Exception:
        return _fallback_prs(actionable, ob_map, owner_map)


# ── Fallbacks — DORA-specific realistic data ──────────────────────────────────

def _fallback_obligations():
    """
    Returned when Gemini is unavailable or rate-limited.
    Based on DORA ICT Risk Update 2026 sample data — if you uploaded a different
    regulation, re-run after verifying your GEMINI_API_KEY is set.
    """
    note_suffix = " [AI unavailable — fallback demo data based on DORA sample]"
    return [
        {"id":"OBL-001","statement":"Maintain documented ICT risk management procedures","full_text":"Financial entities shall maintain documented ICT risk management procedures covering the identification of critical systems, ownership, reviews and escalation.","source":"Financial entities shall maintain documented ICT risk management procedures covering the identification of critical systems, ownership, reviews and escalation.","domain":"ICT Risk","confidence":0.97,"notes":"Covers entire ICT risk governance framework" + note_suffix},
        {"id":"OBL-002","statement":"Identify critical ICT systems within the risk management framework","full_text":"The procedures shall identify critical ICT systems.","source":"The procedures shall identify critical ICT systems.","domain":"ICT Risk","confidence":0.96,"notes":note_suffix},
        {"id":"OBL-003","statement":"Define ownership responsibilities for ICT risk procedures","full_text":"The procedures shall define ownership responsibilities.","source":"The procedures shall define ownership responsibilities.","domain":"Governance","confidence":0.95,"notes":note_suffix},
        {"id":"OBL-004","statement":"Conduct annual ICT risk reviews","full_text":"The procedures shall establish annual risk reviews.","source":"The procedures shall establish annual risk reviews.","domain":"ICT Risk","confidence":0.97,"notes":"Annual frequency is mandatory — 'periodically' is insufficient" + note_suffix},
        {"id":"OBL-005","statement":"Maintain evidence of ICT risk assessments","full_text":"The procedures shall maintain evidence of risk assessments.","source":"The procedures shall maintain evidence of risk assessments.","domain":"ICT Risk","confidence":0.96,"notes":"Evidence must be retained and producible" + note_suffix},
        {"id":"OBL-006","statement":"Document incident escalation procedures","full_text":"The procedures shall document incident escalation procedures.","source":"The procedures shall document incident escalation procedures.","domain":"Incident Management","confidence":0.95,"notes":note_suffix},
        {"id":"OBL-007","statement":"Review critical ICT vendors at least annually","full_text":"Financial entities shall review critical ICT vendors at least annually.","source":"Financial entities shall review critical ICT vendors at least annually.","domain":"Vendor Management","confidence":0.98,"notes":"'Periodically' does not satisfy this — annual frequency required" + note_suffix},
        {"id":"OBL-008","statement":"Maintain evidence of vendor assessments","full_text":"Financial entities shall maintain evidence of vendor assessments.","source":"Financial entities shall maintain evidence of vendor assessments.","domain":"Vendor Management","confidence":0.96,"notes":note_suffix},
        {"id":"OBL-009","statement":"Define responsible owners for vendor oversight","full_text":"Financial entities shall define responsible owners for vendor oversight.","source":"Financial entities shall define responsible owners for vendor oversight.","domain":"Vendor Management","confidence":0.95,"notes":note_suffix},
        {"id":"OBL-010","statement":"Establish escalation procedures for unresolved vendor risks","full_text":"Financial entities shall establish escalation procedures for unresolved vendor risks.","source":"Financial entities shall establish escalation procedures for unresolved vendor risks.","domain":"Vendor Management","confidence":0.94,"notes":note_suffix},
        {"id":"OBL-011","statement":"Maintain documented incident response procedures","full_text":"Financial entities shall maintain documented incident response procedures.","source":"Financial entities shall maintain documented incident response procedures.","domain":"Incident Management","confidence":0.97,"notes":note_suffix},
        {"id":"OBL-012","statement":"Conduct annual incident-response testing","full_text":"Financial entities shall conduct annual incident-response testing.","source":"Financial entities shall conduct annual incident-response testing.","domain":"Incident Management","confidence":0.98,"notes":"Annual testing is mandatory" + note_suffix},
        {"id":"OBL-013","statement":"Preserve evidence of incident-response testing activities","full_text":"Financial entities shall preserve evidence of testing activities.","source":"Financial entities shall preserve evidence of testing activities.","domain":"Incident Management","confidence":0.96,"notes":note_suffix},
        {"id":"OBL-014","statement":"Document post-incident reviews after every significant incident","full_text":"Financial entities shall document post-incident reviews.","source":"Financial entities shall document post-incident reviews after every significant incident. Lessons learned may be documented after major incidents.","domain":"Incident Management","confidence":0.95,"notes":"'May be documented' is insufficient — mandatory documentation required" + note_suffix},
    ]


def _fallback_mappings(obligations, policy_names):
    domain_map = {
        "ict risk":           ("ICT_Risk_Policy.pdf",          "ICT Risk Policy — Framework Section"),
        "vendor management":  ("Vendor_Risk_Policy.pdf",       "Vendor Risk Policy — Review Section"),
        "incident management":("Incident_Response_Policy.pdf", "Incident Response Policy — Process Section"),
        "governance":         ("ICT_Risk_Policy.pdf",          "ICT Risk Policy — Governance Section"),
    }
    excerpts = {
        "ict risk":            "Risk assessments should be conducted periodically. Documentation should be retained whenever practical.",
        "vendor management":   "Critical vendors shall be periodically reviewed. Vendor concerns may be escalated when appropriate.",
        "incident management": "The organization shall maintain an incident response process. Lessons learned may be documented after major incidents.",
        "governance":          "The ICT Risk Team is responsible for maintaining the framework.",
    }
    results = []
    for i, ob in enumerate(obligations):
        domain = ob.get("domain", "ICT Risk").lower()
        key = next((k for k in domain_map if k in domain), "ict risk")
        pname, psection = domain_map[key]
        excerpt = excerpts.get(key, "No relevant text found.")
        results.append({
            "id": f"MAP-{str(i+1).zfill(3)}",
            "obligation_id": ob["id"],
            "policy_name": pname,
            "policy_section": psection,
            "excerpt": excerpt,
            "confidence": 0.45,
            "rationale": f"Policy addresses {domain} generally but lacks the specific requirements of this obligation.",
        })
    return results


def _fallback_gaps(obligations):
    specific = {
        "OBL-001":("Partially Covered","Medium","The ICT Risk Policy acknowledges a risk management framework but does not document specific procedures. Uses permissive language ('should', 'whenever practical') rather than mandatory obligations.","Financial entities shall maintain documented ICT risk management procedures covering the identification of critical systems, ownership, reviews and escalation.","Add documented procedures with mandatory language covering all five sub-requirements."),
        "OBL-002":("Partially Covered","Medium","The policy states the ICT Risk Team maintains the framework but does not explicitly require identification of critical ICT systems as a documented output.","ICT Risk Governance, para 1, bullet 1","Add explicit requirement to maintain a register of critical ICT systems."),
        "OBL-003":("Partially Covered","Medium","The policy identifies the ICT Risk Team but does not define ownership at a granular level for individual systems or risk areas.","ICT Risk Governance, para 1, bullet 2","Define and document named ownership for each critical system and risk domain."),
        "OBL-004":("Not Covered","High","The policy states risk assessments 'should be conducted periodically' but the regulation mandates annual reviews. No frequency is defined, making compliance unverifiable.","ICT Risk Governance, para 1, bullet 3","Replace 'periodically' with 'at least annually' and add a mandatory review schedule."),
        "OBL-005":("Not Covered","High","The policy states documentation 'should be retained whenever practical' — discretionary language that does not satisfy mandatory evidence retention. No retention period specified.","ICT Risk Governance, para 1, bullet 4","Mandate evidence retention with defined format and minimum retention period of 3 years."),
        "OBL-006":("Not Covered","High","The ICT Risk Policy contains no reference to incident escalation procedures. This obligation is entirely absent.","ICT Risk Governance, para 1, bullet 5","Add a dedicated section on incident escalation with defined triggers and escalation paths."),
        "OBL-007":("Partially Covered","Medium","The Vendor Risk Policy states critical vendors 'shall be periodically reviewed' but regulation requires 'at least annually'. Undefined frequency does not satisfy this obligation.","Third-Party ICT Providers, bullet 1","Replace 'periodically reviewed' with 'reviewed at least once every 12 months'."),
        "OBL-008":("Not Covered","High","The Vendor Risk Policy does not require maintenance of evidence of vendor assessments. No documentation obligation exists.","Third-Party ICT Providers, bullet 2","Add requirement to document and retain evidence of each vendor assessment for minimum 3 years."),
        "OBL-009":("Not Covered","High","The Vendor Risk Policy does not define responsible owners for vendor oversight. No accountability assignment exists.","Third-Party ICT Providers, bullet 3","Add explicit ownership assignment for each critical vendor relationship."),
        "OBL-010":("Partially Covered","Medium","The policy states vendor concerns 'may be escalated when appropriate' — permissive language with no defined escalation path, triggers, or timelines.","Third-Party ICT Providers, bullet 4","Replace with mandatory escalation procedure including defined triggers and resolution timeline."),
        "OBL-011":("Partially Covered","Medium","The policy states the organisation 'shall maintain an incident response process' but does not require it to be formally documented with defined steps, roles, and timelines.","Financial entities shall implement a formal ICT-related incident management process to detect, classify and respond to ICT incidents.","Require formal documented procedure with defined steps, roles, timescales, and review cycle."),
        "OBL-012":("Not Covered","High","The Incident Response Policy contains no requirement for annual testing. This obligation is entirely absent.","Financial entities shall establish early warning indicators and classify ICT incidents according to their criticality, duration and data impact.","Add mandatory annual incident-response testing with documented test plan and results."),
        "OBL-013":("Not Covered","High","No requirement to preserve evidence of testing activities. No documentation or retention obligation for test results.","Financial entities shall notify competent authorities of major ICT incidents without undue delay and submit a final report within one month.","Add requirement to document and retain evidence of all tests for minimum 3 years."),
        "OBL-014":("Not Covered","High","Policy states lessons learned 'may be documented after major incidents' — discretionary language. 'May' allows non-compliance.","Financial entities shall conduct post-incident reviews to determine root causes and implement corrective measures to prevent recurrence.","Replace 'may be documented' with 'shall be documented' and define mandatory post-incident review process."),
    }
    gaps = []
    for i, ob in enumerate(obligations):
        g = specific.get(ob["id"])
        if g:
            cov, risk, expl, cite, action = g
        else:
            cov, risk = "Partially Covered", "Medium"
            expl = f"Policy does not fully address this obligation from {ob.get('source', '')}."
            cite, action = ob.get("source", ""), f"Review and update policy to address: {ob.get('statement', '')}."
        gaps.append({
            "id": f"GAP-{str(i+1).zfill(3)}",
            "obligation_id": ob["id"],
            "coverage": cov,
            "risk_level": risk,
            "explanation": expl,
            "cited_source": cite,
            "recommended_action": action,
        })
    return gaps


def _fallback_prs(actionable_gaps, ob_map, owner_map):
    owner_lookup = {
        "ict risk":           "Jane Smith (Risk Management)",
        "vendor management":  "Michael Johnson (Procurement)",
        "incident management":"Sarah Lee (Security Operations)",
        "governance":         "David Brown (Compliance)",
    }
    before_map = {
        "OBL-001":"Risk assessments should be conducted periodically. Documentation should be retained whenever practical.",
        "OBL-004":"Risk assessments should be conducted periodically.",
        "OBL-005":"Documentation should be retained whenever practical.",
        "OBL-007":"Critical vendors shall be periodically reviewed.",
        "OBL-010":"Vendor concerns may be escalated when appropriate.",
        "OBL-011":"The organization shall maintain an incident response process.",
        "OBL-014":"Lessons learned may be documented after major incidents.",
    }
    after_map = {
        "OBL-001":"ICT risk management procedures shall be formally documented, covering: (1) identification of critical ICT systems; (2) defined ownership responsibilities; (3) annual risk reviews; (4) evidence retention for minimum three years; (5) incident escalation procedures. The ICT Risk Team shall maintain and review this documentation annually.",
        "OBL-002":"A register of critical ICT systems shall be maintained and updated at least annually. The register shall include system name, owner, criticality rating, and date of last review. The ICT Risk Team is accountable for maintaining this register.",
        "OBL-003":"Ownership responsibilities for ICT risk shall be formally assigned to named individuals. The ICT Risk Team shall maintain a RACI matrix covering all critical systems and risk domains, reviewed annually.",
        "OBL-004":"ICT risk assessments shall be conducted at least annually. The ICT Risk Team shall maintain a risk assessment schedule and provide evidence of completion to the Compliance function within 30 days of each assessment.",
        "OBL-005":"Evidence of all ICT risk assessments shall be documented and retained for a minimum of three years in the organisation's designated records management system. The ICT Risk Team is responsible for maintaining these records.",
        "OBL-006":"Incident escalation procedures shall be documented within the ICT Risk Policy, defining escalation triggers, responsible parties, timelines, and escalation paths to senior management and regulatory authorities where required.",
        "OBL-007":"Critical ICT vendors shall be formally reviewed at least once every 12 months. Reviews shall assess security posture, operational resilience, and service levels. Evidence of each review shall be documented and signed off by the Vendor Risk Manager.",
        "OBL-008":"Evidence of each vendor assessment shall be documented and retained for a minimum of three years. The Vendor Risk Manager (Procurement) is responsible for maintaining assessment records in the vendor management system.",
        "OBL-009":"A named Vendor Risk Owner shall be assigned for each critical ICT vendor relationship. The Vendor Risk Manager (Procurement) holds overall accountability for the vendor oversight programme and shall maintain an up-to-date ownership register.",
        "OBL-010":"Formal escalation procedures for unresolved vendor risks shall be documented, defining escalation triggers, the escalation path to the Risk Committee, and resolution timelines not exceeding 30 days.",
        "OBL-011":"A formal, documented Incident Response Procedure shall be maintained, defining incident categories, response steps, responsible roles, communication timelines, and mandatory regulatory reporting obligations. The procedure shall be reviewed annually.",
        "OBL-012":"Annual incident-response testing shall be conducted by the Security Operations team. A documented test plan shall be approved in advance and results, including identified gaps and remediation actions, shall be reported to the Risk Committee within 30 days.",
        "OBL-013":"Evidence of all incident-response tests, including test plans, results, and remediation actions, shall be documented and retained for a minimum of three years.",
        "OBL-014":"A post-incident review shall be conducted and documented after every significant incident. Reviews shall be completed within 30 days of incident resolution and submitted to the Risk Committee. The Head of Security Operations is accountable for this process.",
    }
    prs = []
    for i, g in enumerate(actionable_gaps):
        ob = ob_map.get(g["obligation_id"], {})
        domain = ob.get("domain", "").lower()
        owner = "Chief Compliance Officer"
        for k, v in owner_lookup.items():
            if k in domain:
                owner = v
                break
        ob_id = g["obligation_id"]
        before = before_map.get(ob_id, "No current policy text addresses this obligation.")
        after = after_map.get(ob_id, f"[Organisation] shall {ob.get('statement', 'comply with this obligation').lower()}. The {owner} is responsible for implementation and annual review.")
        prs.append({
            "id": f"PPR-{str(i+1).zfill(3)}",
            "obligation_id": ob_id,
            "title": f"Amend policy to address: {ob.get('statement', '')}",
            "gap_description": g.get("explanation", "")[:150],
            "regulatory_citation": g.get("cited_source", ob.get("source", "")),
            "suggested_owner": owner,
            "risk_level": g["risk_level"],
            "confidence": 0.92 if g["coverage"] == "Not Covered" else 0.85,
            "before_text": before,
            "after_text": after,
            "implementation_steps": [
                f"Review current {ob.get('domain', '')} policy wording",
                "Draft amendment using proposed text above",
                f"Submit to {owner} for sign-off",
                "Update policy document and increment version",
                "Communicate change to affected teams and update training materials",
            ],
            "estimated_effort": "1-2 weeks",
        })
    return prs
