"use client";

import { useEffect, useState } from "react";

type AccessContext = { permissions: string[]; project_permissions: Record<string, string[]> };
type Report = { id: string; status: string; revision: number };

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

function csrfToken() {
  if (typeof document === "undefined") return null;
  const item = document.cookie.split(";").map((value) => value.trim()).find((value) => value.startsWith("construction_os_csrf="));
  return item ? decodeURIComponent(item.split("=").slice(1).join("=")) : null;
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const method = (init?.method || "GET").toUpperCase();
  const headers = new Headers(init?.headers);
  if (init?.body) headers.set("Content-Type", "application/json");
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    const token = csrfToken();
    if (token) headers.set("X-CSRF-Token", token);
  }
  const response = await fetch(`${API_BASE}${path}`, { ...init, headers, credentials: "include", cache: "no-store" });
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json() as { detail?: unknown };
      if (body.detail) message = String(body.detail);
    } catch {}
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

function canManage(context: AccessContext, projectId: string) {
  return context.permissions.includes("field.daily_report.manage") || (context.project_permissions[projectId] || []).includes("field.daily_report.manage");
}

export default function DPRVoidControl({ projectId, reportId }: { projectId: string; reportId: string }) {
  const [context, setContext] = useState<AccessContext | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    void Promise.all([
      api<AccessContext>("/session/context"),
      api<Report>(`/projects/${projectId}/daily-reports/${reportId}`),
    ]).then(([nextContext, nextReport]) => {
      setContext(nextContext);
      setReport(nextReport);
    }).catch((caught) => setError(caught instanceof Error ? caught.message : String(caught)));
  }, [projectId, reportId]);

  async function voidReport() {
    const currentReport = report;
    if (!currentReport) return;
    const reason = window.prompt("Reason for voiding this DPR")?.trim();
    if (!reason) return;
    if (!window.confirm("Void this DPR? It will remain in history and cannot be treated as an active report.")) return;
    setBusy(true); setError("");
    try {
      await api<Report>(`/projects/${projectId}/daily-reports/${reportId}/void`, {
        method: "POST",
        body: JSON.stringify({ expected_revision: currentReport.revision, reason }),
      });
      window.location.reload();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
      try {
        setReport(await api<Report>(`/projects/${projectId}/daily-reports/${reportId}`));
      } catch {}
    } finally {
      setBusy(false);
    }
  }

  if (!context || !report || !canManage(context, projectId) || report.status === "void") return null;

  return <section className="workspace-card">
    <div className="section-heading">
      <div><p className="eyebrow">Controlled lifecycle</p><h3>Void DPR</h3></div>
      <button className="danger-link" disabled={busy} onClick={() => void voidReport()}>{busy ? "Voiding…" : "Void report"}</button>
    </div>
    <p className="muted">Voiding preserves the DPR and its audit trail; it does not delete historical evidence.</p>
    {error && <div className="error-banner"><span>{error}</span></div>}
  </section>;
}
