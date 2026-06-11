"use client";
import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  api, Obligation, PolicyMapping, GapAnalysis, PolicyPR, ReviewDecision, AuditTrailEntry,
} from "@/lib/api";
import {
  Shield, Upload, FileText, Search, GitPullRequest, Clock, Download,
  CheckCircle, XCircle, AlertTriangle, ArrowLeft, RefreshCw,
  ChevronDown, ChevronUp, Eye, Edit3, ArrowUpCircle, Check, X, Link2,
  Play, Loader2,
} from "lucide-react";

type Tab = "upload" | "obligations" | "mappings" | "gaps" | "review" | "audit" | "export";
type StepStatus = "idle" | "running" | "done" | "error";

interface PipelineState {
  extract: StepStatus; map: StepStatus; gaps: StepStatus; prs: StepStatus;
}

export default function WorkspacePage() {
  const { id: sid } = useParams() as { id: string };
  const router = useRouter();

  const [sessionName, setSessionName] = useState("");
  const [activeTab, setActiveTab] = useState<Tab>(() => {
    // Restore tab from sessionStorage so page reload doesn't reset to upload
    if (typeof window !== "undefined") {
      const saved = sessionStorage.getItem(`regloop_tab_${typeof window !== "undefined" ? window.location.pathname : ""}`);
      if (saved) return saved as Tab;
    }
    return "upload";
  });

  // Persist active tab on every change
  const setActiveTabPersisted = (tab: Tab) => {
    setActiveTab(tab);
    if (typeof window !== "undefined") {
      sessionStorage.setItem(`regloop_tab_${window.location.pathname}`, tab);
    }
  };
  const [error, setError] = useState("");

  // Data
  const [obligations, setObligations] = useState<Obligation[]>([]);
  const [mappings, setMappings] = useState<PolicyMapping[]>([]);
  const [gaps, setGaps] = useState<GapAnalysis[]>([]);
  const [prs, setPRs] = useState<PolicyPR[]>([]);
  const [reviews, setReviews] = useState<ReviewDecision[]>([]);
  const [auditTrail, setAuditTrail] = useState<AuditTrailEntry[]>([]);
  const [auditEvents, setAuditEvents] = useState<{ event_type: string; obligation_id: string; actor: string; data: Record<string, unknown>; timestamp: string }[]>([]);

  // Pipeline step states
  const [pipeline, setPipeline] = useState<PipelineState>({ extract: "idle", map: "idle", gaps: "idle", prs: "idle" });
  const [stepMsg, setStepMsg] = useState("");

  // Upload state
  const [regulation, setRegulation] = useState<File | null>(null);
  const [policies, setPolicies] = useState<File[]>([]);
  const [matrix, setMatrix] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [sessionReady, setSessionReady] = useState(false);
  const [uploadSummary, setUploadSummary] = useState<{ regulation: { name: string; text_length: number; preview: string; truncated?: boolean }; policies: { name: string; text_length: number; truncated?: boolean }[]; matrix: { name: string; rows: number; columns: string[] } } | null>(null);
  const [uploadWarnings, setUploadWarnings] = useState<string[]>([]);
  const [isFallbackData, setIsFallbackData] = useState(false);

  // Review
  const [reviewingPR, setReviewingPR] = useState<PolicyPR | null>(null);
  const [reviewNotes, setReviewNotes] = useState("");
  const [reviewerName, setReviewerName] = useState("Compliance Analyst");
  const [modifiedText, setModifiedText] = useState("");
  const [expandedObl, setExpandedObl] = useState<string | null>(null);

  // Load existing session data on mount
  const loadExisting = useCallback(async () => {
    try {
      // Load session metadata first for the header name
      const meta = await api.getSession(sid).catch(() => null);
      if (meta) {
        setSessionName(meta.regulation_name || "");
        // Session exists in DB — restore upload summary so the pipeline button is visible
        // This covers the post-redirect case (backend UUID ≠ pre-generated frontend UUID)
        setUploadSummary({
          regulation: { name: meta.regulation_name, text_length: 0, preview: "", truncated: false },
          policies: (meta.policy_names || []).map((n: string) => ({ name: n, text_length: 0, truncated: false })),
          matrix: { name: "responsibility_matrix.csv", rows: meta.matrix_rows || 0, columns: [] },
        });
        setSessionReady(true);
      }

      const [oblRes, mapRes, gapRes, prRes, revRes] = await Promise.all([
        api.listObligations(sid).catch(() => ({ obligations: [] })),
        api.listMappings(sid).catch(() => ({ mappings: [] })),
        api.listGaps(sid).catch(() => ({ gaps: [] })),
        api.listPRs(sid).catch(() => ({ pull_requests: [] })),
        api.listReviews(sid).catch(() => ({ reviews: [] })),
      ]);
      setObligations(oblRes.obligations);
      setMappings(mapRes.mappings);
      setGaps(gapRes.gaps);
      setPRs(prRes.pull_requests);
      setReviews(revRes.reviews);

      if (oblRes.obligations.length > 0) {
        setPipeline({ extract: "done", map: mapRes.mappings.length > 0 ? "done" : "idle", gaps: gapRes.gaps.length > 0 ? "done" : "idle", prs: prRes.pull_requests.length > 0 ? "done" : "idle" });
        // Only auto-switch tabs if we don't already have a persisted tab position
        const savedTab = sessionStorage.getItem(`regloop_tab_${window.location.pathname}`);
        if (!savedTab) setActiveTabPersisted("obligations");
      }

      if (prRes.pull_requests.length > 0) {
        const audit = await api.getAuditTrail(sid).catch(() => null);
        if (audit) { setAuditTrail(audit.trail); setAuditEvents(audit.raw_events); if (!meta) setSessionName(audit.regulation); }
      }
    } catch { /* new session — nothing to load */ }
  }, [sid]);

  useEffect(() => { loadExisting(); }, [loadExisting]);

  // ── Upload & create session ────────────────────────────────────────────────
  async function handleCreateSession() {
    if (!regulation || policies.length === 0 || !matrix) return;
    setUploading(true);
    setError("");
    try {
      const sess = await api.createSession(regulation, policies, matrix);
      // The backend generates its own session UUID — we must use it, not the
      // frontend-pre-generated [id] in the URL.  Redirect to the real session ID
      // and persist it in localStorage so the home page can list it.
      const realId = sess.session_id;
      const ids: string[] = JSON.parse(localStorage.getItem("regloop_sessions") || "[]");
      // Remove the stale frontend-generated id and add the real backend id
      const filtered = ids.filter(i => i !== sid && i !== realId);
      localStorage.setItem("regloop_sessions", JSON.stringify([realId, ...filtered]));

      // If the backend returned a different ID, navigate to the correct URL
      if (realId !== sid) {
        // Store state in sessionStorage under the new ID before redirect
        sessionStorage.setItem(`regloop_tab_/workspace/${realId}`, "upload");
        router.replace(`/workspace/${realId}`);
        return; // The new page will mount fresh with the correct sid
      }

      setSessionName(sess.regulation.name);
      setUploadWarnings(sess.warnings || []);
      setUploadSummary({ regulation: sess.regulation, policies: sess.policies, matrix: sess.matrix });
      setSessionReady(true);
      setActiveTabPersisted("upload");
    } catch (e: unknown) { setError((e as Error).message); }
    finally { setUploading(false); }
  }

  // ── Pipeline steps ─────────────────────────────────────────────────────────
  async function runFullPipeline() {
    setError("");

    // Helper: poll /status every 2s while a step is running, updating stepMsg with live counts
    async function pollUntilDone(
      apiCall: Promise<unknown>,
      pollMsg: (s: { obligations: number; mappings: number; gaps: number; pull_requests: number }) => string,
    ) {
      let done = false;
      const timer = setInterval(async () => {
        if (done) return;
        try {
          const s = await api.getSessionStatus(sid);
          setStepMsg(pollMsg(s));
        } catch { /* ignore poll errors */ }
      }, 2000);
      try {
        const result = await apiCall;
        done = true;
        clearInterval(timer);
        return result;
      } catch (e) {
        done = true;
        clearInterval(timer);
        throw e;
      }
    }

    // Step 1 — Extract
    setPipeline(p => ({ ...p, extract: "running" }));
    setStepMsg("Calling Gemini to extract obligations — this takes ~20s…");
    try {
      const r1 = await pollUntilDone(
        api.extractObligations(sid),
        s => `Extracting obligations… ${s.obligations} found so far`,
      ) as { obligations: typeof obligations };
      setObligations(r1.obligations);
      // Detect if AI was unavailable and fallback data was returned
      if (r1.obligations.some((o: {notes?: string}) => o.notes?.includes("fallback demo data"))) {
        setIsFallbackData(true);
      }
      setPipeline(p => ({ ...p, extract: "done" }));
    } catch (e: unknown) {
      setPipeline(p => ({ ...p, extract: "error" }));
      setError(`Extraction failed: ${(e as Error).message}`);
      setStepMsg("");
      return;
    }

    // Step 2 — Map
    setPipeline(p => ({ ...p, map: "running" }));
    setStepMsg("Mapping obligations to policy sections — ~20s…");
    try {
      const r2 = await pollUntilDone(
        api.mapPolicies(sid),
        s => `Mapping policies… ${s.mappings} mappings so far`,
      ) as { mappings: typeof mappings };
      setMappings(r2.mappings);
      setPipeline(p => ({ ...p, map: "done" }));
    } catch (e: unknown) {
      setPipeline(p => ({ ...p, map: "error" }));
      setError(`Mapping failed: ${(e as Error).message}`);
      setStepMsg("");
      return;
    }

    // Step 3 — Gap Analysis
    setPipeline(p => ({ ...p, gaps: "running" }));
    setStepMsg("Analysing compliance gaps — ~15s…");
    try {
      const r3 = await pollUntilDone(
        api.analyzeGaps(sid),
        s => `Analysing gaps… ${s.gaps} gaps identified so far`,
      ) as { gaps: typeof gaps };
      setGaps(r3.gaps);
      setPipeline(p => ({ ...p, gaps: "done" }));
    } catch (e: unknown) {
      setPipeline(p => ({ ...p, gaps: "error" }));
      setError(`Gap analysis failed: ${(e as Error).message}`);
      setStepMsg("");
      return;
    }

    // Step 4 — Generate PRs
    setPipeline(p => ({ ...p, prs: "running" }));
    setStepMsg("Generating policy pull requests — ~20s…");
    try {
      const r4 = await pollUntilDone(
        api.generatePRs(sid),
        s => `Generating pull requests… ${s.pull_requests} created so far`,
      ) as { pull_requests: typeof prs };
      setPRs(r4.pull_requests);
      setPipeline(p => ({ ...p, prs: "done" }));
      // Load audit trail
      const audit = await api.getAuditTrail(sid).catch(() => null);
      if (audit) { setAuditTrail(audit.trail); setAuditEvents(audit.raw_events); }
    } catch (e: unknown) {
      setPipeline(p => ({ ...p, prs: "error" }));
      setError(`PR generation failed: ${(e as Error).message}`);
    }
    setStepMsg("");
    setActiveTabPersisted("obligations");
  }

  const [toast, setToast] = useState<{ msg: string; type: "success" | "error" } | null>(null);
  function showToast(msg: string, type: "success" | "error" = "success") {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3000);
  }

  async function submitReview(action: string) {
    if (!reviewingPR) return;
    try {
      await api.submitReview(sid, reviewingPR.id, action, reviewerName, reviewNotes, action === "Modified" ? modifiedText : undefined);
      const [prRes, revRes] = await Promise.all([api.listPRs(sid), api.listReviews(sid)]);
      setPRs(prRes.pull_requests);
      setReviews(revRes.reviews);
      const audit = await api.getAuditTrail(sid).catch(() => null);
      if (audit) { setAuditTrail(audit.trail); setAuditEvents(audit.raw_events); }
      showToast(`${action} — decision recorded in audit trail`);
    } catch (e: unknown) { setError((e as Error).message); }
    setReviewingPR(null); setReviewNotes(""); setModifiedText("");
  }

  const isRunning = Object.values(pipeline).includes("running");
  const isComplete = pipeline.prs === "done";
  const pendingPRs = prs.filter(p => p.status === "pending").length;
  const reviewMap = Object.fromEntries(reviews.map(r => [r.pr_id, r]));

  const gapMap = Object.fromEntries(gaps.map(g => [g.obligation_id, g]));
  const mapMap: Record<string, PolicyMapping[]> = {};
  mappings.forEach(m => { mapMap[m.obligation_id] = [...(mapMap[m.obligation_id] || []), m]; });
  const prMap: Record<string, PolicyPR> = {};
  prs.forEach(p => { prMap[p.obligation_id] = p; });

  const tabs: { id: Tab; label: string; icon: React.ElementType; count?: number; disabled?: boolean }[] = [
    { id: "upload",      label: "Upload",        icon: Upload },
    { id: "obligations", label: "Obligations",   icon: FileText,       count: obligations.length,  disabled: obligations.length === 0 },
    { id: "mappings",    label: "Policy Mapping",icon: Link2,          count: mappings.length,     disabled: mappings.length === 0 },
    { id: "gaps",        label: "Gap Analysis",  icon: Search,         count: gaps.length,         disabled: gaps.length === 0 },
    { id: "review",      label: "Review PRs",    icon: GitPullRequest, count: pendingPRs,          disabled: prs.length === 0 },
    { id: "audit",       label: "Audit Trail",   icon: Clock,          count: auditEvents.length,  disabled: auditEvents.length === 0 },
    { id: "export",      label: "Export",        icon: Download,                                   disabled: obligations.length === 0 },
  ];

  return (
    <div className="min-h-screen flex flex-col" style={{ background: "var(--navy)" }}>
      {/* Header */}
      <header style={{ background: "var(--navy-mid)", borderBottom: "1px solid rgba(0,180,216,0.15)" }}>
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button onClick={() => router.push("/")} className="flex items-center gap-2 text-sm" style={{ color: "var(--silver)" }}>
              <ArrowLeft size={16} /> Back
            </button>
            <div className="w-px h-5" style={{ background: "rgba(148,163,184,0.2)" }} />
            <Shield size={16} style={{ color: "var(--teal)" }} />
            <span className="font-semibold" style={{ color: "var(--white)" }}>
              {sessionName || `Session ${sid.slice(0, 8)}`}
            </span>
            {isRunning && (
              <div className="flex items-center gap-2 text-xs px-2 py-1 rounded-full" style={{ background: "rgba(245,158,11,0.15)", color: "var(--amber)" }}>
                <Loader2 size={11} className="animate-spin" /> {stepMsg || "Running..."}
              </div>
            )}
            {isComplete && !isRunning && (
              <div className="flex items-center gap-2 text-xs px-2 py-1 rounded-full badge-approved">
                <CheckCircle size={12} /> Complete
              </div>
            )}
          </div>
          <div className="flex items-center gap-3 text-xs" style={{ color: "var(--silver)" }}>
            {obligations.length > 0 && <><span style={{ color: "var(--teal)" }}>{obligations.length} obligations</span><span>·</span></>}
            {gaps.length > 0 && <><span style={{ color: "var(--amber)" }}>{gaps.filter(g => g.coverage !== "Fully Covered").length} gaps</span><span>·</span></>}
            {prs.length > 0 && <span style={{ color: pendingPRs > 0 ? "var(--amber)" : "var(--green)" }}>{prs.length} PRs</span>}
          </div>
        </div>

        {/* Pipeline progress bar */}
        {isRunning && (
          <div style={{ height: 2, background: "rgba(0,180,216,0.1)" }}>
            <div className="animate-pulse" style={{ height: "100%", background: "var(--teal)", width: `${pipeline.extract === "done" ? pipeline.map === "done" ? pipeline.gaps === "done" ? 90 : 65 : 35 : 10}%`, transition: "width 0.5s ease" }} />
          </div>
        )}

        {/* Tabs */}
        <div className="max-w-7xl mx-auto px-6 flex">
          {tabs.map(tab => (
            <button key={tab.id} onClick={() => !tab.disabled && setActiveTabPersisted(tab.id)} disabled={tab.disabled}
              className="flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-all"
              style={{ borderColor: activeTab === tab.id ? "var(--teal)" : "transparent", color: tab.disabled ? "rgba(148,163,184,0.3)" : activeTab === tab.id ? "var(--teal)" : "var(--silver)", cursor: tab.disabled ? "not-allowed" : "pointer" }}>
              <tab.icon size={14} />
              {tab.label}
              {tab.count !== undefined && tab.count > 0 && (
                <span className="px-1.5 py-0.5 rounded-full text-xs font-bold" style={{ background: "rgba(0,180,216,0.2)", color: "var(--teal)" }}>{tab.count}</span>
              )}
            </button>
          ))}
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8 w-full flex-1">
        {error && (
          <div className="mb-4 p-3 rounded-lg flex items-center gap-2 text-sm" style={{ background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)", color: "#ef4444" }}>
            <AlertTriangle size={14} /> {error}
            <button onClick={() => setError("")} className="ml-auto"><X size={14} /></button>
          </div>
        )}
        {toast && (
          <div className="fixed bottom-6 right-6 z-50 px-4 py-3 rounded-xl text-sm font-medium flex items-center gap-2 shadow-lg"
            style={{ background: toast.type === "success" ? "rgba(16,185,129,0.95)" : "rgba(239,68,68,0.95)", color: "#fff", border: "1px solid rgba(255,255,255,0.15)" }}>
            <CheckCircle size={15} /> {toast.msg}
          </div>
        )}

        {activeTab === "upload" && (
          <UploadTab
            regulation={regulation} policies={policies} matrix={matrix}
            sessionReady={sessionReady} uploading={uploading} isRunning={isRunning}
            pipeline={pipeline} uploadSummary={uploadSummary}
            onRegulation={setRegulation} onAddPolicy={f => setPolicies(p => [...p, f])}
            onRemovePolicy={i => setPolicies(p => p.filter((_, j) => j !== i))}
            onMatrix={setMatrix} onCreateSession={handleCreateSession} onRunPipeline={runFullPipeline}
            warnings={uploadWarnings}
            onReset={() => {
              setRegulation(null);
              setPolicies([]);
              setMatrix(null);
              setSessionReady(false);
              setUploadWarnings([]);
              setUploadSummary(null);
              setObligations([]);
              setMappings([]);
              setGaps([]);
              setPRs([]);
              setReviews([]);
              setAuditTrail([]);
              setAuditEvents([]);
              setPipeline({ extract: "idle", map: "idle", gaps: "idle", prs: "idle" });
              setIsFallbackData(false);
            }}
          />
        )}
        {activeTab === "obligations" && (
          <ObligationsTab obligations={obligations} mapMap={mapMap} gapMap={gapMap} prMap={prMap} reviewMap={reviewMap}
            expandedObl={expandedObl} onToggle={id => setExpandedObl(e => e === id ? null : id)}
            isFallback={isFallbackData} />
        )}
        {activeTab === "mappings" && (
          <MappingsTab obligations={obligations} mappings={mappings} />
        )}
        {activeTab === "gaps" && (
          <GapsTab obligations={obligations} gaps={gaps} gapMap={gapMap} />
        )}
        {activeTab === "review" && (
          <ReviewTab prs={prs} obligations={obligations} reviewMap={reviewMap} onReview={setReviewingPR} />
        )}
        {activeTab === "audit" && (
          <AuditTab trail={auditTrail} events={auditEvents} />
        )}
        {activeTab === "export" && (
          <ExportTab sid={sid} obligations={obligations} mappings={mappings} gaps={gaps} prs={prs} reviews={reviews} />
        )}
      </main>

      {reviewingPR && (
        <ReviewModal pr={reviewingPR}
          obligation={obligations.find(o => o.id === reviewingPR.obligation_id)}
          notes={reviewNotes} modifiedText={modifiedText} reviewer={reviewerName}
          existingReview={reviewMap[reviewingPR.id]}
          onNotesChange={setReviewNotes} onModifiedChange={setModifiedText} onReviewerChange={setReviewerName}
          onSubmit={submitReview}
          onReopen={() => {
            // Locally mark the PR as pending so the review buttons reappear
            const reopened = reviewingPR ? { ...reviewingPR, status: "pending" } : null;
            if (reopened) {
              setPRs(prev => prev.map(p => p.id === reopened.id ? reopened : p));
              setReviewingPR(reopened);
            }
            setReviewNotes("");
            setModifiedText("");
          }}
          onClose={() => setReviewingPR(null)} />
      )}
    </div>
  );
}

// ─── Shared components ─────────────────────────────────────────────────────────
function ConfBar({ value }: { value: number }) {
  const pct = Math.round((value || 0) * 100);
  const color = pct >= 85 ? "var(--green)" : pct >= 60 ? "var(--amber)" : "#ef4444";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 rounded-full" style={{ background: "rgba(148,163,184,0.12)" }}>
        <div className="h-full rounded-full" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="text-xs font-mono w-8" style={{ color }}>{pct}%</span>
    </div>
  );
}

function StepBadge({ status, label }: { status: StepStatus; label: string }) {
  const s: Record<StepStatus, { bg: string; color: string; icon: React.ReactNode }> = {
    idle:    { bg: "rgba(148,163,184,0.08)", color: "var(--silver)",   icon: <div className="w-1.5 h-1.5 rounded-full bg-gray-400" /> },
    running: { bg: "rgba(245,158,11,0.12)",  color: "var(--amber)",    icon: <Loader2 size={10} className="animate-spin" /> },
    done:    { bg: "rgba(16,185,129,0.12)",  color: "var(--green)",    icon: <Check size={10} /> },
    error:   { bg: "rgba(239,68,68,0.12)",   color: "#ef4444",         icon: <X size={10} /> },
  };
  const { bg, color, icon } = s[status];
  return (
    <div className="flex items-center gap-1.5 px-2 py-1 rounded text-xs font-medium" style={{ background: bg, color }}>
      {icon} {label}
    </div>
  );
}

function Skeleton() {
  return (
    <div className="grid gap-3">
      {[1, 2, 3].map(i => (
        <div key={i} className="card p-5">
          <div className="h-2.5 rounded mb-3 w-1/3" style={{ background: "rgba(148,163,184,0.1)" }} />
          <div className="h-2.5 rounded mb-2" style={{ background: "rgba(148,163,184,0.07)" }} />
          <div className="h-2.5 rounded w-2/3" style={{ background: "rgba(148,163,184,0.05)" }} />
        </div>
      ))}
    </div>
  );
}

// ─── Upload Tab ────────────────────────────────────────────────────────────────
function UploadTab({ regulation, policies, matrix, sessionReady, uploading, isRunning, pipeline, uploadSummary, onRegulation, onAddPolicy, onRemovePolicy, onMatrix, onCreateSession, onRunPipeline, warnings, onReset }: {
  regulation: File | null; policies: File[]; matrix: File | null;
  sessionReady: boolean; uploading: boolean; isRunning: boolean; pipeline: PipelineState;
  uploadSummary: { regulation: { name: string; text_length: number; preview: string; truncated?: boolean }; policies: { name: string; text_length: number; truncated?: boolean }[]; matrix: { name: string; rows: number; columns: string[] } } | null;
  onRegulation: (f: File) => void; onAddPolicy: (f: File) => void; onRemovePolicy: (i: number) => void;
  onMatrix: (f: File) => void; onCreateSession: () => void; onRunPipeline: () => void;
  warnings?: string[]; onReset?: () => void;
}) {
  const canUpload = !!regulation && policies.length > 0 && !!matrix;
  return (
    <div className="max-w-3xl mx-auto">
      <div className="mb-8">
        <h2 className="text-xl font-bold mb-1" style={{ color: "var(--white)" }}>Upload Documents</h2>
        <p className="text-sm" style={{ color: "var(--silver)" }}>Upload all three document types, then run the full analysis pipeline.</p>
      </div>

      <div className="grid gap-4 mb-6">
        {/* Regulation */}
        <div className="card p-5" style={{ borderColor: regulation ? "rgba(16,185,129,0.3)" : "rgba(0,180,216,0.15)" }}>
          <div className="flex items-center justify-between mb-2">
            <div>
              <span className="font-semibold text-sm" style={{ color: "var(--white)" }}>Regulatory Document</span>
              <span className="ml-2 text-xs px-1.5 py-0.5 rounded" style={{ background: "rgba(239,68,68,0.12)", color: "#ef4444" }}>Required · PDF</span>
            </div>
            {regulation && <CheckCircle size={16} style={{ color: "var(--green)" }} />}
          </div>
          {regulation
            ? <div className="flex items-center gap-2 text-sm p-2 rounded" style={{ background: "rgba(16,185,129,0.05)", border: "1px solid rgba(16,185,129,0.1)" }}>
                <FileText size={13} style={{ color: "var(--teal)" }} />
                <span style={{ color: "var(--white)" }}>{regulation.name}</span>
                <label className="ml-auto flex items-center gap-1 cursor-pointer text-xs px-2 py-0.5 rounded" style={{ color: "var(--teal)", border: "1px solid rgba(0,180,216,0.25)" }}>
                  <input type="file" accept=".pdf" className="hidden" onChange={e => { const f = e.target.files?.[0]; if (f) { onRegulation(f); e.target.value = ""; } }} />
                  Replace
                </label>
                <button onClick={() => onRegulation(null as any)}><X size={12} style={{ color: "var(--silver)" }} /></button>
              </div>
            : <label className="flex items-center gap-2 text-sm px-3 py-2 rounded-lg w-fit cursor-pointer" style={{ border: "1px dashed rgba(0,180,216,0.3)", color: "var(--teal)" }}>
                <input type="file" accept=".pdf" className="hidden" onChange={e => { const f = e.target.files?.[0]; if (f) { onRegulation(f); e.target.value = ""; } }} />
                + Upload PDF
              </label>
          }
        </div>

        {/* Policies */}
        <div className="card p-5" style={{ borderColor: policies.length > 0 ? "rgba(16,185,129,0.3)" : "rgba(0,180,216,0.15)" }}>
          <div className="flex items-center justify-between mb-2">
            <div>
              <span className="font-semibold text-sm" style={{ color: "var(--white)" }}>Internal Policy Documents</span>
              <span className="ml-2 text-xs px-1.5 py-0.5 rounded" style={{ background: "rgba(239,68,68,0.12)", color: "#ef4444" }}>Required · 1–3 PDFs</span>
            </div>
            {policies.length > 0 && <CheckCircle size={16} style={{ color: "var(--green)" }} />}
          </div>
          {policies.map((p, i) => (
            <div key={i} className="flex items-center gap-2 text-sm p-2 rounded mb-2" style={{ background: "rgba(16,185,129,0.05)", border: "1px solid rgba(16,185,129,0.1)" }}>
              <FileText size={13} style={{ color: "var(--teal)" }} />
              <span style={{ color: "var(--white)" }}>{p.name}</span>
              <button onClick={() => onRemovePolicy(i)} className="ml-auto"><X size={12} style={{ color: "var(--silver)" }} /></button>
            </div>
          ))}
          {policies.length < 3 && (
            <label className="flex items-center gap-2 text-sm px-3 py-2 rounded-lg w-fit cursor-pointer" style={{ border: "1px dashed rgba(0,180,216,0.3)", color: "var(--teal)" }}>
              <input type="file" accept=".pdf" className="hidden" onChange={e => { const f = e.target.files?.[0]; if (f) { onAddPolicy(f); e.target.value = ""; } }} />
              + Add Policy PDF
            </label>
          )}
        </div>

        {/* Matrix */}
        <div className="card p-5" style={{ borderColor: matrix ? "rgba(16,185,129,0.3)" : "rgba(0,180,216,0.15)" }}>
          <div className="flex items-center justify-between mb-2">
            <div>
              <span className="font-semibold text-sm" style={{ color: "var(--white)" }}>Responsibility Matrix</span>
              <span className="ml-2 text-xs px-1.5 py-0.5 rounded" style={{ background: "rgba(239,68,68,0.12)", color: "#ef4444" }}>Required · CSV</span>
            </div>
            {matrix && <CheckCircle size={16} style={{ color: "var(--green)" }} />}
          </div>
          {matrix
            ? <div className="flex items-center gap-2 text-sm p-2 rounded" style={{ background: "rgba(16,185,129,0.05)", border: "1px solid rgba(16,185,129,0.1)" }}>
                <FileText size={13} style={{ color: "var(--teal)" }} />
                <span style={{ color: "var(--white)" }}>{matrix.name}</span>
                <label className="ml-auto flex items-center gap-1 cursor-pointer text-xs px-2 py-0.5 rounded" style={{ color: "var(--teal)", border: "1px solid rgba(0,180,216,0.25)" }}>
                  <input type="file" accept=".csv" className="hidden" onChange={e => { const f = e.target.files?.[0]; if (f) { onMatrix(f); e.target.value = ""; } }} />
                  Replace
                </label>
                <button onClick={() => onMatrix(null as any)}><X size={12} style={{ color: "var(--silver)" }} /></button>
              </div>
            : <label className="flex items-center gap-2 text-sm px-3 py-2 rounded-lg w-fit cursor-pointer" style={{ border: "1px dashed rgba(0,180,216,0.3)", color: "var(--teal)" }}>
                <input type="file" accept=".csv" className="hidden" onChange={e => { const f = e.target.files?.[0]; if (f) { onMatrix(f); e.target.value = ""; } }} />
                + Upload CSV
              </label>
          }
        </div>
      </div>

      {/* FR-1: Upload Summary — shown after successful session creation */}
      {uploadSummary && (
        <div className="card p-5 mb-4" style={{ borderColor: "rgba(0,180,216,0.3)" }}>
          <div className="text-xs font-semibold mb-3 uppercase tracking-wider" style={{ color: "var(--teal)" }}>✓ Upload Summary</div>
          <div className="grid gap-2">
            <div className="p-3 rounded" style={{ background: "rgba(0,180,216,0.04)", border: "1px solid rgba(0,180,216,0.08)" }}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-medium" style={{ color: "var(--white)" }}>{uploadSummary.regulation.name}</span>
                <span className="text-xs px-1.5 py-0.5 rounded" style={{ background: "rgba(129,140,248,0.1)", color: "#818cf8" }}>Regulation</span>
              </div>
              <div className="text-xs mb-1" style={{ color: "var(--silver)" }}>{uploadSummary.regulation.text_length.toLocaleString()} characters extracted{uploadSummary.regulation.truncated ? " (truncated)" : ""}</div>
              {uploadSummary.regulation.preview && (
                <div className="text-xs italic p-2 rounded" style={{ background: "rgba(148,163,184,0.04)", color: "rgba(148,163,184,0.7)", borderLeft: "2px solid rgba(0,180,216,0.2)" }}>
                  "{uploadSummary.regulation.preview.slice(0, 200)}"…
                </div>
              )}
            </div>
            {uploadSummary.policies.map((pol, i) => (
              <div key={i} className="p-3 rounded" style={{ background: "rgba(16,185,129,0.03)", border: "1px solid rgba(16,185,129,0.08)" }}>
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium" style={{ color: "var(--white)" }}>{pol.name}</span>
                  <span className="text-xs px-1.5 py-0.5 rounded" style={{ background: "rgba(16,185,129,0.1)", color: "var(--green)" }}>Policy</span>
                </div>
                <div className="text-xs mt-1" style={{ color: "var(--silver)" }}>{pol.text_length.toLocaleString()} characters extracted{pol.truncated ? " (truncated)" : ""}</div>
              </div>
            ))}
            <div className="p-3 rounded" style={{ background: "rgba(245,158,11,0.03)", border: "1px solid rgba(245,158,11,0.08)" }}>
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium" style={{ color: "var(--white)" }}>{uploadSummary.matrix.name}</span>
                <span className="text-xs px-1.5 py-0.5 rounded" style={{ background: "rgba(245,158,11,0.1)", color: "var(--amber)" }}>Matrix</span>
              </div>
              <div className="text-xs mt-1" style={{ color: "var(--silver)" }}>{uploadSummary.matrix.rows} data rows · Columns: {uploadSummary.matrix.columns.join(", ")}</div>
            </div>
          </div>
        </div>
      )}

      {warnings && warnings.length > 0 && (
        <div className="mb-4 p-3 rounded-lg" style={{ background: "rgba(245,158,11,0.08)", border: "1px solid rgba(245,158,11,0.3)" }}>
          <div className="flex items-center gap-2 mb-1">
            <AlertTriangle size={13} style={{ color: "var(--amber)" }} />
            <span className="text-xs font-semibold" style={{ color: "var(--amber)" }}>Document Size Warning</span>
          </div>
          {warnings.map((w, i) => (
            <p key={i} className="text-xs" style={{ color: "rgba(245,158,11,0.8)" }}>{w}</p>
          ))}
        </div>
      )}

      {/* Pipeline status */}
      {sessionReady && (
        <div className="card p-4 mb-4">
          <div className="text-xs font-semibold mb-3 uppercase tracking-wider" style={{ color: "var(--silver)" }}>Analysis Pipeline</div>
          <div className="flex items-center gap-2 flex-wrap">
            <StepBadge status={pipeline.extract} label="1. Extract Obligations" />
            <div style={{ color: "var(--silver)", fontSize: 10 }}>→</div>
            <StepBadge status={pipeline.map} label="2. Map Policies" />
            <div style={{ color: "var(--silver)", fontSize: 10 }}>→</div>
            <StepBadge status={pipeline.gaps} label="3. Gap Analysis" />
            <div style={{ color: "var(--silver)", fontSize: 10 }}>→</div>
            <StepBadge status={pipeline.prs} label="4. Generate PRs" />
          </div>
        </div>
      )}

      {/* Action buttons */}
      {!sessionReady ? (
        <button onClick={onCreateSession} disabled={!canUpload || uploading}
          className="w-full py-3 rounded-xl font-semibold text-sm flex items-center justify-center gap-2"
          style={{ background: canUpload ? "var(--teal)" : "rgba(148,163,184,0.12)", color: canUpload ? "var(--navy)" : "rgba(148,163,184,0.4)", cursor: canUpload ? "pointer" : "not-allowed" }}>
          {uploading ? <><Loader2 size={16} className="animate-spin" /> Uploading...</> : <><Upload size={16} /> Upload & Create Session</>}
        </button>
      ) : (
        <div className="grid gap-2">
          <button onClick={onRunPipeline} disabled={isRunning}
            className="w-full py-3 rounded-xl font-semibold text-sm flex items-center justify-center gap-2"
            style={{ background: isRunning ? "rgba(148,163,184,0.12)" : "var(--teal)", color: isRunning ? "rgba(148,163,184,0.4)" : "var(--navy)", cursor: isRunning ? "not-allowed" : "pointer" }}>
            {isRunning ? <><Loader2 size={16} className="animate-spin" /> Running Pipeline...</> : <><Play size={16} /> Run Full Analysis Pipeline</>}
          </button>
          {onReset && !isRunning && (
            <button onClick={onReset}
              className="w-full py-2 rounded-xl text-sm flex items-center justify-center gap-2"
              style={{ background: "transparent", color: "var(--silver)", border: "1px solid rgba(148,163,184,0.2)", cursor: "pointer" }}>
              <RefreshCw size={13} /> Reset workspace &amp; re-upload different files
            </button>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Obligations Tab ───────────────────────────────────────────────────────────
function ObligationsTab({ obligations, mapMap, gapMap, prMap, reviewMap, expandedObl, onToggle, isFallback }: {
  obligations: Obligation[]; mapMap: Record<string, PolicyMapping[]>; gapMap: Record<string, GapAnalysis>;
  prMap: Record<string, PolicyPR>; reviewMap: Record<string, ReviewDecision>;
  expandedObl: string | null; onToggle: (id: string) => void; isFallback?: boolean;
}) {
  const cvgCls: Record<string, string> = { "Fully Covered": "badge-fully", "Partially Covered": "badge-partial", "Not Covered": "badge-not" };
  const cvgShort: Record<string, string> = { "Fully Covered": "Covered", "Partially Covered": "Partial", "Not Covered": "Not Covered" };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-bold" style={{ color: "var(--white)" }}>Extracted Obligations</h2>
          <p className="text-sm mt-1" style={{ color: "var(--silver)" }}>{obligations.length} obligations · {Object.values(gapMap).filter(g => g.coverage === "Not Covered").length} not covered · {Object.values(gapMap).filter(g => g.coverage === "Partially Covered").length} partial</p>
        </div>
      </div>
      {isFallback && (
        <div className="mb-4 p-3 rounded-lg flex items-start gap-2" style={{ background: "rgba(245,158,11,0.08)", border: "1px solid rgba(245,158,11,0.3)" }}>
          <AlertTriangle size={14} style={{ color: "var(--amber)", flexShrink: 0, marginTop: 1 }} />
          <div>
            <span className="text-xs font-semibold" style={{ color: "var(--amber)" }}>Gemini AI Unavailable — Demo Fallback Data</span>
            <p className="text-xs mt-0.5" style={{ color: "rgba(245,158,11,0.7)" }}>
              The obligations below are pre-loaded DORA sample data because the AI could not be reached. Verify your <code className="font-mono">GEMINI_API_KEY</code> is set, then re-run the pipeline to extract obligations from your actual document.
            </p>
          </div>
        </div>
      )}
      <div className="grid gap-3">
        {/* FR-2: structured obligations table */}
        <div className="card overflow-hidden mb-2">
          <table className="w-full text-sm">
            <thead>
              <tr style={{ borderBottom: "1px solid rgba(0,180,216,0.1)" }}>
                {["ID", "Statement", "Domain", "Source Reference", "Confidence", "Coverage", "Risk"].map(h => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-semibold" style={{ color: "var(--silver)" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {obligations.map(obl => {
                const gap = gapMap[obl.id];
                return (
                  <tr key={obl.id} onClick={() => onToggle(obl.id)} style={{ borderBottom: "1px solid rgba(0,180,216,0.04)", cursor: "pointer" }}
                    onMouseEnter={e => (e.currentTarget.style.background = "rgba(0,180,216,0.03)")}
                    onMouseLeave={e => (e.currentTarget.style.background = "")}>
                    <td className="px-4 py-2 text-xs font-mono" style={{ color: "var(--teal)" }}>{obl.id}</td>
                    <td className="px-4 py-2" style={{ maxWidth: 200 }}><div className="text-xs" style={{ color: "var(--white)" }}>{obl.statement.slice(0, 65)}{obl.statement.length > 65 ? "…" : ""}</div></td>
                    <td className="px-4 py-2"><span className="text-xs px-1.5 py-0.5 rounded" style={{ background: "rgba(129,140,248,0.1)", color: "#818cf8" }}>{obl.domain}</span></td>
                    <td className="px-4 py-2 text-xs font-mono" style={{ color: "var(--silver)", maxWidth: 140 }}>{obl.source?.slice(0, 50)}{obl.source?.length > 50 ? "…" : ""}</td>
                    <td className="px-4 py-2" style={{ width: 90 }}><ConfBar value={obl.confidence} /></td>
                    <td className="px-4 py-2">{gap ? <span className={`text-xs px-2 py-0.5 rounded-full ${cvgCls[gap.coverage]}`}>{cvgShort[gap.coverage]}</span> : <span style={{ color: "rgba(148,163,184,0.3)" }}>—</span>}</td>
                    <td className="px-4 py-2">{gap ? <span className={`text-xs px-2 py-0.5 rounded-full badge-${gap.risk_level.toLowerCase()}`}>{gap.risk_level}</span> : <span style={{ color: "rgba(148,163,184,0.3)" }}>—</span>}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {/* Expandable detail cards below the table */}
        {obligations.map((obl, i) => {
          const gap = gapMap[obl.id];
          const maps = mapMap[obl.id] || [];
          const pr = prMap[obl.id];
          const rev = pr ? reviewMap[pr.id] : null;
          const isExpanded = expandedObl === obl.id;
          return (
            <div key={obl.id} className="card overflow-hidden" style={{ borderColor: gap?.risk_level === "High" && gap?.coverage !== "Fully Covered" ? "rgba(239,68,68,0.2)" : "rgba(0,180,216,0.15)" }}>
              <button className="w-full p-5 text-left flex items-start gap-4" onClick={() => onToggle(obl.id)}>
                <div className="flex-shrink-0 w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold" style={{ background: "rgba(0,180,216,0.1)", color: "var(--teal)" }}>{i + 1}</div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-2">
                    <span className="text-xs font-mono px-1.5 py-0.5 rounded" style={{ background: "rgba(148,163,184,0.08)", color: "var(--silver)" }}>{obl.id}</span>
                    <span className="text-xs px-1.5 py-0.5 rounded" style={{ background: "rgba(129,140,248,0.1)", color: "#818cf8" }}>{obl.domain}</span>
                    {gap && <span className={`text-xs px-2 py-0.5 rounded-full ${cvgCls[gap.coverage]}`}>{cvgShort[gap.coverage]}</span>}
                    {gap && <span className={`text-xs px-2 py-0.5 rounded-full badge-${gap.risk_level.toLowerCase()}`}>{gap.risk_level}</span>}
                    {rev && <span className={`text-xs px-2 py-0.5 rounded-full badge-${rev.action.toLowerCase()}`}>{rev.action}</span>}
                  </div>
                  <p className="text-sm leading-relaxed" style={{ color: "var(--white)" }}>{obl.statement}</p>
                  <div className="flex items-center gap-3 mt-2">
                    <span className="text-xs font-mono" style={{ color: "var(--silver)" }}>{obl.source}</span>
                    <div className="w-32"><ConfBar value={obl.confidence} /></div>
                  </div>
                </div>
                <div style={{ color: "var(--silver)", flexShrink: 0 }}>{isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}</div>
              </button>

              {isExpanded && (
                <div className="px-5 pb-5 border-t" style={{ borderColor: "rgba(0,180,216,0.08)" }}>
                  {obl.full_text && (
                    <div className="mt-4 p-3 rounded text-xs italic" style={{ background: "rgba(129,140,248,0.04)", border: "1px solid rgba(129,140,248,0.1)", color: "#a5b4fc" }}>
                      "{obl.full_text}"
                    </div>
                  )}
                  {maps.length > 0 && (
                    <div className="mt-4">
                      <div className="text-xs font-semibold mb-2 uppercase tracking-wider" style={{ color: "var(--silver)" }}>Policy Mappings</div>
                      {maps.map(m => (
                        <div key={m.id} className="p-3 rounded-lg mb-2" style={{ background: "rgba(0,180,216,0.04)", border: "1px solid rgba(0,180,216,0.08)" }}>
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-xs font-medium" style={{ color: "var(--teal)" }}>{m.policy_section} — {m.policy_name}</span>
                            <div className="w-28"><ConfBar value={m.confidence} /></div>
                          </div>
                          <p className="text-xs italic" style={{ color: "var(--silver)" }}>"{m.excerpt}"</p>
                          {m.rationale && <p className="text-xs mt-1" style={{ color: "rgba(148,163,184,0.6)" }}>{m.rationale}</p>}
                        </div>
                      ))}
                    </div>
                  )}
                  {gap && (
                    <div className="mt-4">
                      <div className="text-xs font-semibold mb-2 uppercase tracking-wider" style={{ color: "var(--silver)" }}>Gap Analysis</div>
                      <div className="p-3 rounded-lg" style={{ background: gap.coverage === "Fully Covered" ? "rgba(16,185,129,0.05)" : "rgba(239,68,68,0.05)", border: `1px solid ${gap.coverage === "Fully Covered" ? "rgba(16,185,129,0.1)" : "rgba(239,68,68,0.1)"}` }}>
                        <p className="text-xs" style={{ color: gap.coverage === "Fully Covered" ? "#6ee7b7" : "#fca5a5" }}>{gap.explanation}</p>
                        {gap.recommended_action && <p className="text-xs mt-2 font-medium" style={{ color: "var(--amber)" }}>→ {gap.recommended_action}</p>}
                      </div>
                    </div>
                  )}
                  {pr && (
                    <div className="mt-4">
                      <div className="text-xs font-semibold mb-2 uppercase tracking-wider" style={{ color: "var(--silver)" }}>Policy Pull Request — {pr.id}</div>
                      <div className="grid grid-cols-2 gap-3">
                        <div className="p-3 rounded" style={{ background: "rgba(239,68,68,0.04)", border: "1px solid rgba(239,68,68,0.1)" }}>
                          <div className="text-xs font-semibold mb-1" style={{ color: "#ef4444" }}>BEFORE</div>
                          <p className="text-xs font-mono" style={{ color: "#fca5a5" }}>{pr.before_text}</p>
                        </div>
                        <div className="p-3 rounded" style={{ background: "rgba(16,185,129,0.04)", border: "1px solid rgba(16,185,129,0.1)" }}>
                          <div className="text-xs font-semibold mb-1" style={{ color: "var(--green)" }}>AFTER</div>
                          <p className="text-xs font-mono" style={{ color: "#6ee7b7" }}>{rev?.modified_text || pr.after_text}</p>
                        </div>
                      </div>
                      {pr.implementation_steps?.length > 0 && (
                        <div className="mt-2">
                          <div className="text-xs font-semibold mb-1 uppercase tracking-wider" style={{ color: "var(--silver)" }}>Implementation Steps</div>
                          <div className="grid gap-1">
                            {pr.implementation_steps.map((step: string, i: number) => (
                              <div key={i} className="flex items-start gap-2 text-xs">
                                <span className="w-4 h-4 rounded flex items-center justify-center flex-shrink-0 font-mono" style={{ background: "rgba(0,180,216,0.1)", color: "var(--teal)", fontSize: 9 }}>{i + 1}</span>
                                <span style={{ color: "var(--silver)" }}>{step}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                      <div className="flex gap-3 mt-2 text-xs" style={{ color: "var(--silver)" }}>
                        <span>Owner: <span style={{ color: "var(--white)" }}>{pr.suggested_owner}</span></span>
                        <span>·</span>
                        <span>Effort: <span style={{ color: "var(--white)" }}>{pr.estimated_effort}</span></span>
                        <span>·</span>
                        <span className={`badge-${pr.status}`}>{pr.status}</span>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Mappings Tab ──────────────────────────────────────────────────────────────
function MappingsTab({ obligations, mappings }: { obligations: Obligation[]; mappings: PolicyMapping[] }) {
  const oblMap = Object.fromEntries(obligations.map(o => [o.id, o]));
  const byPolicy: Record<string, PolicyMapping[]> = {};
  mappings.forEach(m => { byPolicy[m.policy_name] = [...(byPolicy[m.policy_name] || []), m]; });

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-xl font-bold" style={{ color: "var(--white)" }}>Policy Mapping</h2>
        <p className="text-sm mt-1" style={{ color: "var(--silver)" }}>{mappings.length} sections matched across {Object.keys(byPolicy).length} policies</p>
      </div>
      {mappings.length === 0 ? <Skeleton /> : Object.entries(byPolicy).map(([policyName, maps]) => (
        <div key={policyName} className="mb-6">
          <div className="flex items-center gap-2 mb-3">
            <FileText size={14} style={{ color: "var(--teal)" }} />
            <span className="font-semibold text-sm" style={{ color: "var(--white)" }}>{policyName}</span>
            <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: "rgba(0,180,216,0.1)", color: "var(--teal)" }}>{maps.length} matches</span>
          </div>
          <div className="grid gap-2 ml-5">
            {maps.map(m => {
              const obl = oblMap[m.obligation_id];
              return (
                <div key={m.id} className="card p-4">
                  <div className="flex items-start justify-between gap-4 mb-2">
                    <div>
                      <span className="text-xs font-medium" style={{ color: "var(--teal)" }}>{m.policy_section}</span>
                      <span className="text-xs ml-2 font-mono" style={{ color: "var(--silver)" }}>↔ {m.obligation_id}</span>
                      {obl && <p className="text-xs mt-0.5" style={{ color: "var(--silver)" }}>{obl.statement.slice(0, 90)}...</p>}
                    </div>
                    <div className="w-28 flex-shrink-0"><ConfBar value={m.confidence} /></div>
                  </div>
                  <div className="p-2 rounded text-xs italic" style={{ background: "rgba(148,163,184,0.04)", borderLeft: "2px solid rgba(0,180,216,0.3)", color: "var(--silver)" }}>"{m.excerpt}"</div>
                  {m.rationale && <p className="text-xs mt-1" style={{ color: "rgba(148,163,184,0.5)" }}>{m.rationale}</p>}
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── Gaps Tab ──────────────────────────────────────────────────────────────────
function GapsTab({ obligations, gaps, gapMap }: { obligations: Obligation[]; gaps: GapAnalysis[]; gapMap: Record<string, GapAnalysis> }) {
  const cvgCls: Record<string, string> = { "Fully Covered": "badge-fully", "Partially Covered": "badge-partial", "Not Covered": "badge-not" };
  return (
    <div>
      <div className="mb-6">
        <h2 className="text-xl font-bold" style={{ color: "var(--white)" }}>Gap Analysis</h2>
      </div>
      <div className="grid grid-cols-4 gap-4 mb-8">
        {[
          { label: "Not Covered",       value: gaps.filter(g => g.coverage === "Not Covered").length,       color: "#ef4444" },
          { label: "Partially Covered", value: gaps.filter(g => g.coverage === "Partially Covered").length, color: "var(--amber)" },
          { label: "Fully Covered",     value: gaps.filter(g => g.coverage === "Fully Covered").length,     color: "var(--green)" },
          { label: "High Risk",         value: gaps.filter(g => g.risk_level === "High" && g.coverage !== "Fully Covered").length, color: "#a855f7" },
        ].map(c => (
          <div key={c.label} className="card p-4">
            <div className="text-2xl font-bold" style={{ color: c.color }}>{c.value}</div>
            <div className="text-sm mt-1" style={{ color: "var(--white)" }}>{c.label}</div>
          </div>
        ))}
      </div>
      {gaps.length === 0 ? <Skeleton /> : (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr style={{ borderBottom: "1px solid rgba(0,180,216,0.1)" }}>
                {["ID", "Obligation", "Domain", "Coverage", "Risk", "Source Citation", "Gap Explanation", "Action"].map(h => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-semibold" style={{ color: "var(--silver)" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {obligations.map(obl => {
                const gap = gapMap[obl.id];
                if (!gap) return null;
                return (
                  <tr key={obl.id} style={{ borderBottom: "1px solid rgba(0,180,216,0.04)" }}>
                    <td className="px-4 py-3 text-xs font-mono" style={{ color: "var(--teal)" }}>{obl.id}</td>
                    <td className="px-4 py-3" style={{ maxWidth: 200 }}>
                      <div className="text-xs" style={{ color: "var(--white)" }}>{obl.statement.slice(0, 65)}...</div>
                    </td>
                    <td className="px-4 py-3"><span className="text-xs px-1.5 py-0.5 rounded" style={{ background: "rgba(129,140,248,0.1)", color: "#818cf8" }}>{obl.domain}</span></td>
                    <td className="px-4 py-3"><span className={`text-xs px-2 py-0.5 rounded-full ${cvgCls[gap.coverage]}`}>{gap.coverage}</span></td>
                    <td className="px-4 py-3"><span className={`text-xs px-2 py-0.5 rounded-full badge-${gap.risk_level.toLowerCase()}`}>{gap.risk_level}</span></td>
                    <td className="px-4 py-3 text-xs font-mono" style={{ color: "var(--silver)", maxWidth: 160 }}>{(gap.cited_source || obl.source || "").slice(0, 60)}{(gap.cited_source || obl.source || "").length > 60 ? "…" : ""}</td>
                    <td className="px-4 py-3 text-xs" style={{ color: "var(--silver)", maxWidth: 240 }}>{gap.explanation.slice(0, 100)}...</td>
                    <td className="px-4 py-3 text-xs" style={{ color: "var(--amber)", maxWidth: 180 }}>{gap.recommended_action?.slice(0, 70)}...</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ─── Review Tab ────────────────────────────────────────────────────────────────
function ReviewTab({ prs, obligations, reviewMap, onReview }: { prs: PolicyPR[]; obligations: Obligation[]; reviewMap: Record<string, ReviewDecision>; onReview: (pr: PolicyPR) => void }) {
  const oblMap = Object.fromEntries(obligations.map(o => [o.id, o]));
  const pending  = prs.filter(p => p.status === "pending");
  const reviewed = prs.filter(p => p.status !== "pending");
  return (
    <div>
      <div className="mb-6">
        <h2 className="text-xl font-bold" style={{ color: "var(--white)" }}>Policy Pull Requests</h2>
        <p className="text-sm mt-1" style={{ color: "var(--silver)" }}>AI-generated amendments — every decision requires human approval.</p>
      </div>
      {pending.length > 0 && (
        <div className="mb-8">
          <div className="flex items-center gap-2 mb-4"><div className="pulse-dot" /><span className="text-sm font-semibold" style={{ color: "var(--amber)" }}>{pending.length} pending review</span></div>
          <div className="grid gap-3">
            {pending.map(pr => {
              const obl = oblMap[pr.obligation_id];
              return (
                <div key={pr.id} className="card p-5" style={{ borderColor: "rgba(245,158,11,0.25)" }}>
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 flex-wrap mb-2">
                        <span className="text-xs font-mono" style={{ color: "var(--teal)" }}>{pr.id}</span>
                        <span className={`text-xs px-2 py-0.5 rounded-full badge-${pr.risk_level.toLowerCase()}`}>{pr.risk_level}</span>
                        <span className="text-xs px-1.5 py-0.5 rounded-full badge-pending">pending</span>
                      </div>
                      <p className="text-sm font-medium mb-1" style={{ color: "var(--white)" }}>{pr.title}</p>
                      {obl && <p className="text-xs" style={{ color: "var(--silver)" }}>{obl.statement.slice(0, 90)}...</p>}
                      <div className="flex items-center gap-3 mt-2 text-xs" style={{ color: "var(--silver)" }}>
                        <span>Owner: <span style={{ color: "var(--white)" }}>{pr.suggested_owner}</span></span>
                        <span>·</span><span>Effort: {pr.estimated_effort}</span>
                        <span>·</span><div className="w-24"><ConfBar value={pr.confidence} /></div>
                      </div>
                    </div>
                    <button onClick={() => onReview(pr)} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium flex-shrink-0" style={{ background: "rgba(245,158,11,0.15)", color: "var(--amber)", border: "1px solid rgba(245,158,11,0.3)" }}>
                      <Eye size={13} /> Review
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
      {reviewed.length > 0 && (
        <div>
          <div className="text-sm font-semibold mb-3" style={{ color: "var(--silver)" }}>Reviewed ({reviewed.length})</div>
          <div className="grid gap-2">
            {reviewed.map(pr => {
              const rev = reviewMap[pr.id];
              return (
                <div key={pr.id} className="card p-4 flex items-center justify-between">
                  <div>
                    <div className="text-sm" style={{ color: "var(--white)" }}>{pr.title}</div>
                    <div className="text-xs mt-0.5" style={{ color: "var(--silver)" }}>{pr.suggested_owner} · {rev?.created_at ? new Date(rev.created_at).toLocaleString() : ""}</div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`text-xs px-2 py-0.5 rounded-full badge-${pr.status}`}>{pr.status}</span>
                    <button onClick={() => onReview(pr)} style={{ color: "var(--silver)" }}><Eye size={13} /></button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Audit Tab ─────────────────────────────────────────────────────────────────
function AuditTab({ trail, events }: { trail: AuditTrailEntry[]; events: { event_type: string; obligation_id: string; actor: string; data: Record<string, unknown>; timestamp: string }[] }) {
  const evtColor: Record<string, string> = { extracted: "var(--teal)", mapped: "#818cf8", gap_detected: "var(--amber)", pr_created: "var(--green)", reviewed: "#a855f7" };

  const totalObls = trail.length;
  const fullyCovered = trail.filter(t => t.gap_analysis?.coverage === "Fully Covered").length;
  const notCovered = trail.filter(t => t.gap_analysis?.coverage === "Not Covered").length;
  const highRisk = trail.filter(t => t.gap_analysis?.risk_level === "High" && t.gap_analysis?.coverage !== "Fully Covered").length;
  const reviewed = trail.filter(t => t.review_decision !== null).length;
  const coveragePct = totalObls > 0 ? Math.round((fullyCovered / totalObls) * 100) : 0;

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-xl font-bold" style={{ color: "var(--white)" }}>Audit Trail</h2>
        <p className="text-sm mt-1" style={{ color: "var(--silver)" }}>End-to-end traceability: regulatory source → obligation → mapping → gap → PR → decision</p>
      </div>

      {totalObls > 0 && (
        <div className="grid grid-cols-5 gap-3 mb-8">
          {[
            { label: "Total Obligations", value: totalObls,      color: "var(--teal)" },
            { label: "Fully Covered",     value: fullyCovered,   color: "var(--green)" },
            { label: "Not Covered",       value: notCovered,     color: "#ef4444" },
            { label: "High Risk Gaps",    value: highRisk,       color: "#a855f7" },
            { label: "Decisions Recorded",value: reviewed,       color: "var(--amber)" },
          ].map(c => (
            <div key={c.label} className="card p-4 text-center">
              <div className="text-2xl font-bold" style={{ color: c.color }}>{c.value}</div>
              <div className="text-xs mt-1" style={{ color: "var(--silver)" }}>{c.label}</div>
            </div>
          ))}
        </div>
      )}
      {trail.length > 0 && (
        <div className="mb-8">
          <div className="text-xs font-semibold mb-3 uppercase tracking-wider" style={{ color: "var(--silver)" }}>Obligation Traceability ({trail.length})</div>          <div className="grid gap-2">
            {trail.map((t, i) => (
              <div key={t.obligation_id} className="card p-4 text-xs">
                <div className="grid grid-cols-5 gap-3">
                  <div>
                    <div className="font-semibold mb-1" style={{ color: "var(--silver)" }}>SOURCE</div>
                    <div className="font-mono" style={{ color: "var(--teal)" }}>{t.obligation_id}</div>
                    <div className="mt-0.5" style={{ color: "var(--silver)" }}>{t.source_citation}</div>
                  </div>
                  <div>
                    <div className="font-semibold mb-1" style={{ color: "var(--silver)" }}>OBLIGATION</div>
                    <div style={{ color: "var(--white)" }}>{t.obligation.slice(0, 60)}...</div>
                  </div>
                  <div>
                    <div className="font-semibold mb-1" style={{ color: "var(--silver)" }}>POLICY MAPPING</div>
                    {t.policy_mapping ? <><div style={{ color: "var(--teal)" }}>{t.policy_mapping.policy}</div><div style={{ color: "var(--silver)" }}>{t.policy_mapping.section}</div></> : <div style={{ color: "rgba(148,163,184,0.3)" }}>None</div>}
                  </div>
                  <div>
                    <div className="font-semibold mb-1" style={{ color: "var(--silver)" }}>GAP / OWNER</div>
                    {t.gap_analysis
                      ? <>
                          <span className={`badge-${t.gap_analysis.coverage === "Fully Covered" ? "fully" : t.gap_analysis.coverage === "Partially Covered" ? "partial" : "not"}`}>{t.gap_analysis.coverage}</span>
                          {(t.proposed_amendment?.owner || (t as {responsible_owner?: string}).responsible_owner) && <div className="mt-1 text-xs" style={{ color: "var(--white)" }}>{t.proposed_amendment?.owner || (t as {responsible_owner?: string}).responsible_owner}</div>}
                        </>
                      : <div style={{ color: "rgba(148,163,184,0.3)" }}>—</div>}
                  </div>
                  <div>
                    <div className="font-semibold mb-1" style={{ color: "var(--silver)" }}>DECISION</div>
                    {t.review_decision
                      ? <>
                          <span className={`badge-${t.review_decision.action.toLowerCase()}`}>{t.review_decision.action}</span>
                          <div className="mt-1 text-xs" style={{ color: "rgba(148,163,184,0.6)" }}>{t.review_decision.reviewer}</div>
                          <div className="text-xs" style={{ color: "rgba(148,163,184,0.4)" }}>{new Date(t.review_decision.timestamp).toLocaleDateString()}</div>
                        </>
                      : <div style={{ color: "rgba(148,163,184,0.3)" }}>Pending</div>}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
      <div className="text-xs font-semibold mb-3 uppercase tracking-wider" style={{ color: "var(--silver)" }}>Event Log ({events.length})</div>
      <div className="grid gap-1.5">
        {events.map((e, i) => (
          <div key={i} className="card p-3 flex items-center gap-3">
            <span className="text-xs font-mono w-5 text-right flex-shrink-0" style={{ color: "rgba(148,163,184,0.4)" }}>{i + 1}</span>
            <div className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: evtColor[e.event_type] || "var(--silver)" }} />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium" style={{ color: "var(--white)" }}>{e.event_type.replace("_", " ")}</span>
                <span className="text-xs font-mono px-1.5 py-0.5 rounded" style={{ background: "rgba(148,163,184,0.06)", color: "var(--silver)" }}>{e.actor}</span>
                <span className="text-xs font-mono" style={{ color: "rgba(148,163,184,0.4)" }}>{new Date(e.timestamp).toISOString().slice(0, 19).replace("T", " ")}</span>
              </div>
              {e.obligation_id && <div className="text-xs" style={{ color: "var(--silver)" }}>{e.obligation_id}</div>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Export Tab ────────────────────────────────────────────────────────────────
function ExportTab({ sid, obligations, mappings, gaps, prs, reviews }: { sid: string; obligations: Obligation[]; mappings: PolicyMapping[]; gaps: GapAnalysis[]; prs: PolicyPR[]; reviews: ReviewDecision[] }) {
  return (
    <div className="max-w-2xl mx-auto">
      <div className="mb-8">
        <h2 className="text-xl font-bold" style={{ color: "var(--white)" }}>Export Compliance Package</h2>
        <p className="text-sm mt-1" style={{ color: "var(--silver)" }}>Download the full review package for auditors, regulators, and management reporting.</p>
      </div>
      <div className="card p-5 mb-4">
        <div className="font-semibold mb-3" style={{ color: "var(--white)" }}>Package Summary</div>
        <div className="grid grid-cols-2 gap-2 text-sm">
          {[
            { label: "Obligations",      value: obligations.length },
            { label: "Policy Mappings",  value: mappings.length },
            { label: "Gaps (Not Fully Covered)", value: gaps.filter(g => g.coverage !== "Fully Covered").length },
            { label: "High Risk Gaps",   value: gaps.filter(g => g.risk_level === "High").length },
            { label: "Policy PRs",       value: prs.length },
            { label: "Reviews Completed",value: reviews.length },
          ].map(item => (
            <div key={item.label} className="flex justify-between py-1" style={{ borderBottom: "1px solid rgba(148,163,184,0.06)" }}>
              <span style={{ color: "var(--silver)" }}>{item.label}</span>
              <span className="font-semibold" style={{ color: "var(--white)" }}>{item.value}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="grid gap-3">
        {[
          { url: api.exportJsonUrl(sid), fmt: "JSON", desc: "Full nested export: obligations, mappings, gaps, PRs, implementation steps, audit trail" },
          { url: api.exportCsvUrl(sid),  fmt: "CSV",  desc: "Flat spreadsheet: all columns including before/after text, owner, review decisions, timestamps" },
        ].map(item => (
          <a key={item.fmt} href={item.url} download className="card p-5 flex items-center justify-between" style={{ textDecoration: "none", transition: "border-color 0.2s" }}
            onMouseEnter={e => (e.currentTarget.style.borderColor = "rgba(0,180,216,0.4)")}
            onMouseLeave={e => (e.currentTarget.style.borderColor = "rgba(0,180,216,0.15)")}>
            <div>
              <div className="font-semibold text-sm" style={{ color: "var(--white)" }}>{item.fmt} Export</div>
              <div className="text-xs mt-0.5" style={{ color: "var(--silver)" }}>{item.desc}</div>
            </div>
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm" style={{ background: "rgba(0,180,216,0.1)", color: "var(--teal)" }}>
              <Download size={14} /> {item.fmt}
            </div>
          </a>
        ))}
      </div>
    </div>
  );
}

// ─── Review Modal ──────────────────────────────────────────────────────────────
function ReviewModal({ pr, obligation, notes, modifiedText, reviewer, existingReview, onNotesChange, onModifiedChange, onReviewerChange, onSubmit, onClose, onReopen }: {
  pr: PolicyPR; obligation?: Obligation; notes: string; modifiedText: string; reviewer: string;
  existingReview?: ReviewDecision;
  onNotesChange: (v: string) => void; onModifiedChange: (v: string) => void; onReviewerChange: (v: string) => void;
  onSubmit: (action: string) => void; onClose: () => void; onReopen: () => void;
}) {
  const [showModify, setShowModify] = useState(false);
  const isReviewed = pr.status !== "pending";

  return (
    <div className="fixed inset-0 flex items-center justify-center z-50" style={{ background: "rgba(0,0,0,0.75)" }}>
      <div className="w-full max-w-3xl mx-4 rounded-xl overflow-hidden flex flex-col" style={{ background: "var(--navy-mid)", border: "1px solid rgba(0,180,216,0.2)", maxHeight: "90vh" }}>
        <div className="p-5 flex items-center justify-between flex-shrink-0" style={{ borderBottom: "1px solid rgba(0,180,216,0.1)" }}>
          <div className="flex items-center gap-2">
            <GitPullRequest size={16} style={{ color: "var(--teal)" }} />
            <span className="font-semibold" style={{ color: "var(--white)" }}>{pr.id}</span>
            <span className={`text-xs px-2 py-0.5 rounded-full badge-${pr.risk_level.toLowerCase()}`}>{pr.risk_level}</span>
            {isReviewed && <span className={`text-xs px-2 py-0.5 rounded-full badge-${pr.status}`}>{pr.status}</span>}
          </div>
          <button onClick={onClose} style={{ color: "var(--silver)" }}><X size={18} /></button>
        </div>

        <div className="p-5 grid gap-4 overflow-y-auto">
          {obligation && (
            <div className="p-3 rounded-lg text-sm" style={{ background: "rgba(0,180,216,0.05)", border: "1px solid rgba(0,180,216,0.1)", color: "var(--white)" }}>
              <div className="text-xs font-semibold mb-1" style={{ color: "var(--silver)" }}>REGULATORY OBLIGATION</div>
              {obligation.statement}
              <div className="text-xs font-mono mt-1" style={{ color: "var(--teal)" }}>{obligation.source}</div>
            </div>
          )}

          <div>
            <div className="text-xs font-semibold mb-1" style={{ color: "var(--silver)" }}>GAP DESCRIPTION</div>
            <p className="text-sm" style={{ color: "var(--white)" }}>{pr.gap_description}</p>
          </div>

          <div>
            <div className="text-xs font-semibold mb-2" style={{ color: "var(--silver)" }}>BEFORE / AFTER</div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <div className="text-xs font-semibold mb-1 flex items-center gap-1" style={{ color: "#ef4444" }}><XCircle size={10} /> Current</div>
                <div className="p-3 rounded text-xs font-mono" style={{ background: "rgba(239,68,68,0.05)", border: "1px solid rgba(239,68,68,0.12)", color: "#fca5a5", minHeight: 80 }}>{pr.before_text}</div>
              </div>
              <div>
                <div className="text-xs font-semibold mb-1 flex items-center gap-1" style={{ color: "var(--green)" }}><CheckCircle size={10} /> Proposed</div>
                {showModify
                  ? <textarea value={modifiedText || pr.after_text} onChange={e => onModifiedChange(e.target.value)} rows={5} className="w-full p-3 rounded text-xs font-mono resize-none" style={{ background: "rgba(16,185,129,0.05)", border: "1px solid rgba(16,185,129,0.3)", color: "#6ee7b7", outline: "none" }} />
                  : <div className="p-3 rounded text-xs font-mono" style={{ background: "rgba(16,185,129,0.05)", border: "1px solid rgba(16,185,129,0.1)", color: "#6ee7b7", minHeight: 80 }}>{existingReview?.modified_text || pr.after_text}</div>
                }
              </div>
            </div>
          </div>

          {pr.implementation_steps?.length > 0 && (
            <div>
              <div className="text-xs font-semibold mb-2" style={{ color: "var(--silver)" }}>IMPLEMENTATION STEPS</div>
              <div className="grid gap-1">
                {pr.implementation_steps.map((step, i) => (
                  <div key={i} className="flex items-start gap-2 text-xs">
                    <span className="w-4 h-4 rounded flex items-center justify-center flex-shrink-0 font-mono" style={{ background: "rgba(0,180,216,0.1)", color: "var(--teal)", fontSize: 9 }}>{i + 1}</span>
                    <span style={{ color: "var(--silver)" }}>{step}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="grid grid-cols-3 gap-3 text-xs">
            {[
              { label: "CITATION", value: pr.regulatory_citation },
              { label: "OWNER", value: pr.suggested_owner },
              { label: "EFFORT", value: pr.estimated_effort },
            ].map(item => (
              <div key={item.label} className="p-3 rounded" style={{ background: "rgba(148,163,184,0.04)", border: "1px solid rgba(148,163,184,0.08)" }}>
                <div className="font-semibold mb-1" style={{ color: "var(--silver)" }}>{item.label}</div>
                <div style={{ color: "var(--white)" }}>{item.value}</div>
              </div>
            ))}
          </div>

          {!isReviewed && (
            <>
              <div>
                <div className="text-xs font-semibold mb-1" style={{ color: "var(--silver)" }}>REVIEWER NAME</div>
                <input value={reviewer} onChange={e => onReviewerChange(e.target.value)} className="w-full p-2 rounded text-sm" style={{ background: "rgba(148,163,184,0.05)", border: "1px solid rgba(148,163,184,0.15)", color: "var(--white)", outline: "none" }} />
              </div>
              <div>
                <div className="text-xs font-semibold mb-1" style={{ color: "var(--silver)" }}>NOTES (optional)</div>
                <textarea value={notes} onChange={e => onNotesChange(e.target.value)} placeholder="Notes for audit record..." rows={2} className="w-full p-2 rounded text-sm resize-none" style={{ background: "rgba(148,163,184,0.05)", border: "1px solid rgba(148,163,184,0.12)", color: "var(--white)", outline: "none" }} />
              </div>
            </>
          )}

          {isReviewed && existingReview?.note && (
            <div className="p-3 rounded text-sm" style={{ background: "rgba(148,163,184,0.05)", border: "1px solid rgba(148,163,184,0.1)", color: "var(--white)" }}>
              <div className="text-xs font-semibold mb-1" style={{ color: "var(--silver)" }}>REVIEWER NOTE — {existingReview.reviewer}</div>
              {existingReview.note}
            </div>
          )}
        </div>

        {!isReviewed && (
          <div className="p-5 flex items-center gap-2 flex-shrink-0" style={{ borderTop: "1px solid rgba(0,180,216,0.08)" }}>
            <button onClick={() => onSubmit("Approved")} className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium" style={{ background: "rgba(16,185,129,0.15)", color: "var(--green)", border: "1px solid rgba(16,185,129,0.3)" }}><Check size={14} /> Approve</button>
            <button onClick={() => { if (!showModify) { onModifiedChange(pr.after_text); setShowModify(true); } else { if ((modifiedText || pr.after_text).trim() === pr.after_text.trim()) { if (!window.confirm("No changes detected. Submit as Modified anyway?")) return; } onSubmit("Modified"); } }} className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium" style={{ background: "rgba(59,130,246,0.12)", color: "#3b82f6", border: "1px solid rgba(59,130,246,0.3)" }}><Edit3 size={14} /> {showModify ? "Save Modified" : "Modify"}</button>
            <button onClick={() => onSubmit("Escalated")} className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium" style={{ background: "rgba(168,85,247,0.12)", color: "#a855f7", border: "1px solid rgba(168,85,247,0.3)" }}><ArrowUpCircle size={14} /> Escalate</button>
            <button onClick={() => onSubmit("Rejected")} className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium ml-auto" style={{ background: "rgba(239,68,68,0.12)", color: "#ef4444", border: "1px solid rgba(239,68,68,0.3)" }}><X size={14} /> Reject</button>
          </div>
        )}
        {isReviewed && (
          <div className="p-5 flex items-center gap-2 flex-shrink-0" style={{ borderTop: "1px solid rgba(0,180,216,0.08)" }}>
            <div className="flex-1 text-xs" style={{ color: "var(--silver)" }}>
              Decision recorded by <span style={{ color: "var(--white)" }}>{existingReview?.reviewer || "reviewer"}</span>
              {existingReview?.note && <span> · &ldquo;{existingReview.note}&rdquo;</span>}
            </div>
            <button onClick={onReopen} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium" style={{ background: "rgba(245,158,11,0.12)", color: "var(--amber)", border: "1px solid rgba(245,158,11,0.3)" }}>
              <RefreshCw size={12} /> Override / Re-review
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
