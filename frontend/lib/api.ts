const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function req<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Request failed");
  }
  return res.json();
}

// ── Types ──────────────────────────────────────────────────────────────────────
export interface Session {
  session_id: string;
  regulation: { name: string; text_length: number; preview: string; truncated?: boolean };
  policies: { name: string; text_length: number; preview: string; truncated?: boolean }[];
  matrix: { name: string; rows: number; columns: string[] };
  status: string;
  message: string;
  warnings?: string[];
}

export interface Obligation {
  id: string; statement: string; full_text: string;
  source: string; domain: string; confidence: number; notes: string;
}

export interface PolicyMapping {
  id: string; obligation_id: string; policy_name: string;
  policy_section: string; excerpt: string; confidence: number; rationale: string;
}

export interface GapAnalysis {
  id: string; obligation_id: string; coverage: string;
  risk_level: string; explanation: string; cited_source: string;
  recommended_action: string;
}

export interface PolicyPR {
  id: string; obligation_id: string; title: string;
  gap_description: string; regulatory_citation: string;
  suggested_owner: string; risk_level: string; confidence: number;
  before_text: string; after_text: string;
  implementation_steps: string[]; estimated_effort: string;
  status: string;
}

export interface ReviewDecision {
  id: string; pr_id: string; action: string;
  reviewer: string; note: string; modified_text: string; created_at: string;
}

export interface AuditTrailEntry {
  obligation_id: string; regulatory_source: string; obligation: string;
  source_citation: string; domain: string; responsible_owner: string;
  policy_mapping: { policy: string; section: string; confidence: number } | null;
  gap_analysis: { coverage: string; risk_level: string; explanation: string } | null;
  proposed_amendment: { pr_id: string; title: string; owner: string } | null;
  review_decision: { action: string; reviewer: string; note: string; timestamp: string } | null;
  timestamp: string;
}

export interface AuditTrail {
  session_id: string; regulation: string; created_at: string;
  total_obligations: number; total_prs: number; total_reviews: number;
  trail: AuditTrailEntry[];
  raw_events: { event_type: string; obligation_id: string; actor: string; data: Record<string, unknown>; timestamp: string }[];
}

export interface ExportSummary {
  total_obligations: number; fully_covered: number; partially_covered: number;
  not_covered: number; high_risk_gaps: number; pull_requests: number;
  approved: number; rejected: number; pending: number;
}

// ── API calls ──────────────────────────────────────────────────────────────────
export const api = {
  // FR-1: Upload
  createSession: async (regulation: File, policies: File[], matrix: File): Promise<Session> => {
    const form = new FormData();
    form.append("regulation", regulation);
    policies.forEach(p => form.append("policies", p));
    form.append("matrix", matrix);
    const res = await fetch(`${BASE}/api/upload/session`, { method: "POST", body: form });
    if (!res.ok) { const e = await res.json(); throw new Error(e.detail || "Upload failed"); }
    return res.json();
  },
  getSession: (sid: string) => req<{ session_id: string; regulation_name: string; policy_names: string[]; created_at: string; matrix_rows: number }>(`/api/upload/session/${sid}`),
  getSessionStatus: (sid: string) => req<{ session_id: string; status: string; obligations: number; mappings: number; gaps: number; pull_requests: number }>(`/api/upload/session/${sid}/status`),

  // FR-2: Obligations
  extractObligations: (sid: string) => req<{ extracted: number; obligations: Obligation[] }>(`/api/obligations/${sid}/extract`, { method: "POST" }),
  listObligations: (sid: string) => req<{ obligations: Obligation[] }>(`/api/obligations/${sid}`),

  // FR-3: Policy Mapping
  mapPolicies: (sid: string) => req<{ mapped: number; mappings: PolicyMapping[] }>(`/api/mappings/${sid}/map`, { method: "POST" }),
  listMappings: (sid: string) => req<{ mappings: PolicyMapping[] }>(`/api/mappings/${sid}`),

  // FR-4: Gap Analysis
  analyzeGaps: (sid: string) => req<{ analyzed: number; gaps: GapAnalysis[] }>(`/api/gaps/${sid}/analyze`, { method: "POST" }),
  listGaps: (sid: string) => req<{ gaps: GapAnalysis[] }>(`/api/gaps/${sid}`),

  // FR-5: Pull Requests
  generatePRs: (sid: string) => req<{ generated: number; pull_requests: PolicyPR[] }>(`/api/pullrequests/${sid}/generate`, { method: "POST" }),
  listPRs: (sid: string) => req<{ pull_requests: PolicyPR[] }>(`/api/pullrequests/${sid}`),

  // FR-6: Review
  submitReview: (sid: string, prId: string, action: string, reviewer: string, note?: string, modifiedText?: string) =>
    req(`/api/reviews/${sid}/pr/${prId}`, {
      method: "POST",
      body: JSON.stringify({ action, reviewer, note: note || "", modified_text: modifiedText || "" }),
    }),
  listReviews: (sid: string) => req<{ reviews: ReviewDecision[] }>(`/api/reviews/${sid}`),

  // FR-7: Audit
  getAuditTrail: (sid: string) => req<AuditTrail>(`/api/audit/${sid}/trail`),

  // FR-8: Export
  exportJsonUrl: (sid: string) => `${BASE}/api/export/${sid}/json`,
  exportCsvUrl:  (sid: string) => `${BASE}/api/export/${sid}/csv`,
  exportSummary: (sid: string) => req<{ summary: ExportSummary }>(`/api/export/${sid}/summary`),
};
