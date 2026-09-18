"use client";

import { useCallback, useEffect, useState } from "react";

type AccessContext = { permissions: string[]; project_permissions: Record<string, string[]> };
type Delay = {
  id?: string; category: string | null; description: string; started_at: string | null; ended_at: string | null;
  lost_hours: string | number | null; responsible_party: string | null; schedule_impact: boolean; notes: string | null;
};
type Safety = {
  id?: string; entry_type: string; summary: string; severity: string | null; safety_record_id: string | null; notes: string | null;
};
type ReportDetail = { id: string; status: string; revision: number; delays: Delay[]; safety: Safety[] };

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
    try { const body = await response.json() as { detail?: unknown }; if (body.detail) message = String(body.detail); } catch {}
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

function localDateTime(value: string | null) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

function isoDateTime(value: string) {
  return value ? new Date(value).toISOString() : null;
}

export default function DPRReportOwnedSections({ projectId, reportId }: { projectId: string; reportId: string }) {
  const [context, setContext] = useState<AccessContext | null>(null);
  const [report, setReport] = useState<ReportDetail | null>(null);
  const [delays, setDelays] = useState<Delay[]>([]);
  const [safety, setSafety] = useState<Safety[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const [ctx, detail] = await Promise.all([
        api<AccessContext>("/session/context"),
        api<ReportDetail>(`/projects/${projectId}/daily-reports/${reportId}`),
      ]);
      setContext(ctx);
      setReport(detail);
      setDelays(detail.delays || []);
      setSafety(detail.safety || []);
      setError("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setLoading(false);
    }
  }, [projectId, reportId]);

  useEffect(() => { void load(); }, [load]);

  const editable = Boolean(report?.status === "draft" && context && (
    context.permissions.includes("field.daily_report.update") ||
    (context.project_permissions[projectId] || []).includes("field.daily_report.update")
  ));

  async function save() {
    if (!report || !editable) return;
    setBusy(true); setError("");
    try {
      await api<ReportDetail>(`/projects/${projectId}/daily-reports/${reportId}/sections`, {
        method: "PUT",
        body: JSON.stringify({
          expected_revision: report.revision,
          reason: "Updated report-owned sections from DPR web detail",
          delays: delays.map(({ id, ...row }) => ({
            ...row,
            started_at: row.started_at || null,
            ended_at: row.ended_at || null,
            lost_hours: row.lost_hours === "" ? null : row.lost_hours,
          })),
          safety: safety.map(({ id, ...row }) => ({ ...row, safety_record_id: row.safety_record_id || null })),
        }),
      });
      window.location.reload();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
      await load().catch(() => undefined);
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <section className="workspace-card"><p>Loading DPR observations…</p></section>;

  return <div className="stack">
    {error && <div className="error-banner"><span>{error}</span></div>}
    <section className="workspace-card">
      <div className="section-heading"><div><p className="eyebrow">Report-owned data</p><h2>Delays / blockers</h2></div>{editable && <button className="secondary-button" onClick={() => setDelays((rows) => [...rows, { category: null, description: "", started_at: null, ended_at: null, lost_hours: null, responsible_party: null, schedule_impact: false, notes: null }])}>Add delay</button>}</div>
      {delays.length === 0 ? <p className="muted">No DPR-owned delays recorded.</p> : <div className="stack">{delays.map((row, index) => <div className="nested-card" key={row.id || index}>
        <div className="form-grid">
          <label>Category<input disabled={!editable || busy} value={row.category || ""} onChange={(event) => setDelays((rows) => rows.map((item, i) => i === index ? { ...item, category: event.target.value || null } : item))} /></label>
          <label className="wide">Description<input disabled={!editable || busy} value={row.description} onChange={(event) => setDelays((rows) => rows.map((item, i) => i === index ? { ...item, description: event.target.value } : item))} /></label>
          <label>Started<input type="datetime-local" disabled={!editable || busy} value={localDateTime(row.started_at)} onChange={(event) => setDelays((rows) => rows.map((item, i) => i === index ? { ...item, started_at: isoDateTime(event.target.value) } : item))} /></label>
          <label>Ended<input type="datetime-local" disabled={!editable || busy} value={localDateTime(row.ended_at)} onChange={(event) => setDelays((rows) => rows.map((item, i) => i === index ? { ...item, ended_at: isoDateTime(event.target.value) } : item))} /></label>
          <label>Lost hours<input type="number" min="0" step="0.25" disabled={!editable || busy} value={row.lost_hours ?? ""} onChange={(event) => setDelays((rows) => rows.map((item, i) => i === index ? { ...item, lost_hours: event.target.value || null } : item))} /></label>
          <label>Responsible party<input disabled={!editable || busy} value={row.responsible_party || ""} onChange={(event) => setDelays((rows) => rows.map((item, i) => i === index ? { ...item, responsible_party: event.target.value || null } : item))} /></label>
          <label><input type="checkbox" disabled={!editable || busy} checked={row.schedule_impact} onChange={(event) => setDelays((rows) => rows.map((item, i) => i === index ? { ...item, schedule_impact: event.target.checked } : item))} /> Schedule impact</label>
          <label className="wide">Notes<textarea disabled={!editable || busy} value={row.notes || ""} onChange={(event) => setDelays((rows) => rows.map((item, i) => i === index ? { ...item, notes: event.target.value || null } : item))} /></label>
        </div>
        {editable && <button className="danger-link" disabled={busy} onClick={() => setDelays((rows) => rows.filter((_, i) => i !== index))}>Remove</button>}
      </div>)}</div>}
    </section>

    <section className="workspace-card">
      <div className="section-heading"><div><p className="eyebrow">Supplemental observation</p><h2>Safety observations</h2></div>{editable && <button className="secondary-button" onClick={() => setSafety((rows) => [...rows, { entry_type: "observation", summary: "", severity: null, safety_record_id: null, notes: null }])}>Add observation</button>}</div>
      <p className="muted">Authoritative Safety records for the report date are reused automatically. Add only DPR-specific observations here.</p>
      {safety.length === 0 ? <p className="muted">No manual DPR safety observations.</p> : <div className="stack">{safety.map((row, index) => <div className="nested-card" key={row.id || index}>
        <div className="form-grid">
          <label>Type<input disabled={!editable || busy} value={row.entry_type} onChange={(event) => setSafety((rows) => rows.map((item, i) => i === index ? { ...item, entry_type: event.target.value } : item))} /></label>
          <label>Severity<input disabled={!editable || busy} value={row.severity || ""} onChange={(event) => setSafety((rows) => rows.map((item, i) => i === index ? { ...item, severity: event.target.value || null } : item))} /></label>
          <label className="wide">Summary<input disabled={!editable || busy} value={row.summary} onChange={(event) => setSafety((rows) => rows.map((item, i) => i === index ? { ...item, summary: event.target.value } : item))} /></label>
          <label className="wide">Notes<textarea disabled={!editable || busy} value={row.notes || ""} onChange={(event) => setSafety((rows) => rows.map((item, i) => i === index ? { ...item, notes: event.target.value || null } : item))} /></label>
        </div>
        {editable && <button className="danger-link" disabled={busy} onClick={() => setSafety((rows) => rows.filter((_, i) => i !== index))}>Remove</button>}
      </div>)}</div>}
    </section>

    {editable && <section className="workspace-card"><button disabled={busy || delays.some((row) => !row.description.trim()) || safety.some((row) => !row.entry_type.trim() || !row.summary.trim())} onClick={() => void save()}>{busy ? "Saving…" : "Save delays & safety observations"}</button></section>}
  </div>;
}
