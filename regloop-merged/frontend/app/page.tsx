"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Plus, Shield, FileSearch, CheckCircle, ArrowRight, Trash2, GitPullRequest } from "lucide-react";

interface SessionItem {
  session_id: string;
  regulation_name: string;
  policy_names: string[];
  created_at: string;
}

export default function Home() {
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const router = useRouter();

  useEffect(() => {
    // Load session IDs from localStorage
    const ids: string[] = JSON.parse(localStorage.getItem("regloop_sessions") || "[]");
    Promise.all(ids.map(id => api.getSession(id).catch(() => null)))
      .then(results => setSessions(results.filter(Boolean) as SessionItem[]));
  }, []);

  function newSession() {
    const id = crypto.randomUUID();
    const ids: string[] = JSON.parse(localStorage.getItem("regloop_sessions") || "[]");
    localStorage.setItem("regloop_sessions", JSON.stringify([id, ...ids]));
    router.push(`/workspace/${id}`);
  }

  function removeSession(sid: string) {
    const ids: string[] = JSON.parse(localStorage.getItem("regloop_sessions") || "[]");
    localStorage.setItem("regloop_sessions", JSON.stringify(ids.filter(i => i !== sid)));
    setSessions(s => s.filter(x => x.session_id !== sid));
  }

  return (
    <div className="min-h-screen" style={{ background: "var(--navy)" }}>
      <header style={{ background: "var(--navy-mid)", borderBottom: "1px solid rgba(0,180,216,0.15)" }}>
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: "rgba(0,180,216,0.15)" }}>
              <Shield size={16} style={{ color: "var(--teal)" }} />
            </div>
            <span className="font-bold text-lg tracking-tight" style={{ color: "var(--white)" }}>RegLoop</span>
            <span className="text-xs" style={{ color: "var(--silver)" }}>AI Regulatory Execution · Gemini 2.0 Flash</span>
          </div>
          <button onClick={newSession} className="flex items-center gap-2 px-4 py-2 rounded-lg font-medium text-sm" style={{ background: "var(--teal)", color: "var(--navy)" }}>
            <Plus size={15} /> New Workspace
          </button>
        </div>
      </header>

      <section className="max-w-6xl mx-auto px-6 py-16">
        <div className="text-center mb-12">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium mb-6" style={{ background: "rgba(0,180,216,0.08)", color: "var(--teal)", border: "1px solid rgba(0,180,216,0.2)" }}>
            <div className="pulse-dot" /> AI-Powered Compliance Automation — Free with Gemini
          </div>
          <h1 className="text-5xl font-bold mb-4 tracking-tight" style={{ color: "var(--white)" }}>
            Regulation → review-ready<br /><span style={{ color: "var(--teal)" }}>in minutes, not days</span>
          </h1>
          <p className="text-lg max-w-2xl mx-auto" style={{ color: "var(--silver)" }}>
            Upload a regulation and your internal policies. RegLoop extracts every obligation, finds policy gaps, generates binding policy amendments, and maintains a full audit trail — with humans approving every decision.
          </p>
        </div>

        <div className="grid grid-cols-4 gap-4 mb-16">
          {[
            { icon: FileSearch,    label: "Extract",      sub: "Every obligation from regulation",    color: "var(--teal)" },
            { icon: Shield,        label: "Map",          sub: "Against internal policy documents",   color: "#818cf8" },
            { icon: ArrowRight,    label: "Gap Analysis", sub: "Coverage status + risk rating",       color: "var(--amber)" },
            { icon: GitPullRequest,label: "Pull Requests",sub: "Policy amendments for human review",  color: "var(--green)" },
          ].map((step, i) => (
            <div key={i} className="card p-4 text-center">
              <div className="w-10 h-10 rounded-lg mx-auto mb-3 flex items-center justify-center" style={{ background: `${step.color}18` }}>
                <step.icon size={18} style={{ color: step.color }} />
              </div>
              <div className="font-semibold text-sm" style={{ color: "var(--white)" }}>{step.label}</div>
              <div className="text-xs mt-1" style={{ color: "var(--silver)" }}>{step.sub}</div>
            </div>
          ))}
        </div>

        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-lg" style={{ color: "var(--white)" }}>Workspaces</h2>
          </div>

          {sessions.length === 0 ? (
            <div className="card p-12 text-center">
              <Shield size={40} className="mx-auto mb-4" style={{ color: "rgba(0,180,216,0.25)" }} />
              <p className="font-medium mb-2" style={{ color: "var(--white)" }}>No workspaces yet</p>
              <p className="text-sm mb-6" style={{ color: "var(--silver)" }}>Create one to start a compliance review</p>
              <button onClick={newSession} className="px-6 py-2 rounded-lg font-medium text-sm" style={{ background: "var(--teal)", color: "var(--navy)" }}>
                Create First Workspace
              </button>
            </div>
          ) : (
            <div className="grid gap-3">
              {sessions.map(s => (
                <div key={s.session_id} onClick={() => router.push(`/workspace/${s.session_id}`)}
                  className="card p-5 flex items-center justify-between"
                  style={{ cursor: "pointer", transition: "border-color 0.2s" }}
                  onMouseEnter={e => (e.currentTarget.style.borderColor = "rgba(0,180,216,0.45)")}
                  onMouseLeave={e => (e.currentTarget.style.borderColor = "rgba(0,180,216,0.15)")}>
                  <div className="flex items-center gap-4">
                    <div className="w-9 h-9 rounded-lg flex items-center justify-center" style={{ background: "rgba(0,180,216,0.08)" }}>
                      <FileSearch size={16} style={{ color: "var(--teal)" }} />
                    </div>
                    <div>
                      <div className="font-medium" style={{ color: "var(--white)" }}>{s.regulation_name || `Session ${s.session_id.slice(0, 8)}`}</div>
                      <div className="text-xs mt-0.5" style={{ color: "var(--silver)" }}>
                        {s.policy_names?.length || 0} policies · {new Date(s.created_at).toLocaleString()}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button onClick={e => { e.stopPropagation(); removeSession(s.session_id); }} style={{ color: "var(--silver)", padding: 6 }}>
                      <Trash2 size={13} />
                    </button>
                    <ArrowRight size={15} style={{ color: "var(--silver)" }} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
