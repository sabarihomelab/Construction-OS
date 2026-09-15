"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

type AccessContext = { permissions: string[]; project_permissions: Record<string, string[]> };
type Worker = { id: string; worker_number: string; first_name: string; last_name: string };
type TimeEntry = {
  id?: string;
  work_date: string;
  regular_hours: string | number;
  overtime_hours: string | number;
  double_time_hours: string | number;
  cost_code: string | null;
  location: string | null;
  work_description: string | null;
  source_type: string;
  source_id: string | null;
};
type Timecard = {
  id: string;
  project_id: string;
  worker_id: string;
  week_start: string;
  status: string;
  revision: number;
  submitted_at: string | null;
  approved_at: string | null;
  rejected_at: string | null;
  entries: TimeEntry[];
};
type History = { id: string; event_type: string; timecard_revision: number; details: Record<string, unknown>; created_at: string };

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
    const error = new Error(message) as Error & { status?: number };
    error.status = response.status;
    throw error;
  }
  return response.json() as Promise<T>;
}

function addDays(value: string, days: number) {
  const date = new Date(`${value}T00:00:00`);
  date.setDate(date.getDate() + days);
  return date.toISOString().slice(0, 10);
}

function blankWeek(weekStart: string): TimeEntry[] {
  return Array.from({ length: 7 }, (_, index) => ({
    work_date: addDays(weekStart, index), regular_hours: "0", overtime_hours: "0", double_time_hours: "0",
    cost_code: null, location: null, work_description: null, source_type: "manual", source_id: null,
  }));
}

function Status({ value }: { value: string }) {
  return <span className={`status-pill status-${value.replaceAll("_", "-")}`}>{value.replaceAll("_", " ")}</span>;
}

export default function TimecardDetailWorkspace({ projectId, timecardId }: { projectId: string; timecardId: string }) {
  const [context, setContext] = useState<AccessContext | null>(null);
  const [timecard, setTimecard] = useState<Timecard | null>(null);
  const [entries, setEntries] = useState<TimeEntry[]>([]);
  const [history, setHistory] = useState<History[]>([]);
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const can = useCallback((permission: string) => {
    if (!context) return false;
    return context.permissions.includes(permission) || (context.project_permissions[projectId] || []).includes(permission);
  }, [context, projectId]);

  const load = useCallback(async () => {
    try {
      const ctx = await api<AccessContext>("/session/context");
      const [detail, historyRows, workerRows] = await Promise.all([
        api<Timecard>(`/projects/${projectId}/timecards/${timecardId}`),
        api<History[]>(`/projects/${projectId}/timecards/${timecardId}/history`),
        ctx.permissions.includes("workforce.worker.view") ? api<Worker[]>("/workforce/workers") : Promise.resolve([] as Worker[]),
      ]);
      setContext(ctx);
      setTimecard(detail);
      setEntries(detail.entries.length ? detail.entries : blankWeek(detail.week_start));
      setHistory(historyRows);
      setWorkers(workerRows);
      setError("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setLoading(false);
    }
  }, [projectId, timecardId]);

  useEffect(() => { void load(); }, [load]);

  const worker = useMemo(() => workers.find((row) => row.id === timecard?.worker_id), [workers, timecard]);
  const editable = Boolean(timecard && ["draft", "rejected"].includes(timecard.status) && can("workforce.timecard.update"));

  function patchEntry(index: number, patch: Partial<TimeEntry>) {
    setEntries((rows) => rows.map((row, rowIndex) => rowIndex === index ? { ...row, ...patch } : row));
  }

  async function run(work: () => Promise<void>) {
    setBusy(true); setError(""); setMessage("");
    try { await work(); }
    catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
      await load().catch(() => undefined);
    } finally { setBusy(false); }
  }

  async function saveEntries() {
    if (!timecard || !editable) return;
    await run(async () => {
      await api(`/projects/${projectId}/timecards/${timecard.id}/entries`, {
        method: "PUT",
        body: JSON.stringify({
          expected_revision: timecard.revision,
          reason: "Updated from Timecard detail page",
          entries: entries.map((entry) => ({
            work_date: entry.work_date,
            regular_hours: Number(entry.regular_hours || 0),
            overtime_hours: Number(entry.overtime_hours || 0),
            double_time_hours: Number(entry.double_time_hours || 0),
            cost_code: entry.cost_code || null,
            location: entry.location || null,
            work_description: entry.work_description || null,
            source_type: entry.source_type || "manual",
            source_id: entry.source_id || null,
          })),
        }),
      });
      setMessage("Timecard entries saved.");
      await load();
    });
  }

  async function action(kind: "submit" | "approve" | "reject") {
    if (!timecard) return;
    let reason = `${kind} from Timecard detail page`;
    if (kind === "reject") {
      reason = window.prompt("Reason for rejection")?.trim() || "";
      if (!reason) return;
    }
    await run(async () => {
      await api(`/projects/${projectId}/timecards/${timecard.id}/${kind}`, {
        method: "POST",
        body: JSON.stringify({ expected_revision: timecard.revision, reason }),
      });
      setMessage(kind === "approve" ? "Timecard approved." : kind === "reject" ? "Timecard returned for correction." : "Timecard submitted.");
      await load();
    });
  }

  if (loading) return <main className="workspace-shell"><p>Loading timecard…</p></main>;
  if (!timecard) return <main className="workspace-shell"><div className="error-banner"><span>{error || "Timecard not found"}</span></div><Link href="/workforce">Back to Workforce</Link></main>;

  return <main className="workspace-shell">
    <header className="workspace-header">
      <div><p className="eyebrow">Workforce · Timecard</p><h1>{worker ? `${worker.first_name} ${worker.last_name}` : `Worker ${timecard.worker_id.slice(0, 8)}`}</h1><p>Week of {timecard.week_start} · revision {timecard.revision}</p></div>
      <div className="button-row"><Status value={timecard.status} /><Link className="secondary-button" href="/workforce">Back to Workforce</Link></div>
    </header>
    {error && <div className="error-banner"><span>{error}</span></div>}
    {message && <section className="workspace-card"><p>{message}</p></section>}

    <section className="workspace-card">
      <div className="section-heading"><h2>Weekly entries</h2><span className="status-pill">{entries.length} days</span></div>
      <div className="table-wrap"><table><thead><tr><th>Date</th><th>Regular</th><th>OT</th><th>Double</th><th>Cost code</th><th>Location</th><th>Work description</th></tr></thead><tbody>{entries.map((entry, index) => <tr key={entry.id || entry.work_date}>
        <td>{entry.work_date}</td>
        <td><input disabled={!editable || busy} type="number" min="0" max="24" step="0.25" value={entry.regular_hours} onChange={(event) => patchEntry(index, { regular_hours: event.target.value })} /></td>
        <td><input disabled={!editable || busy} type="number" min="0" max="24" step="0.25" value={entry.overtime_hours} onChange={(event) => patchEntry(index, { overtime_hours: event.target.value })} /></td>
        <td><input disabled={!editable || busy} type="number" min="0" max="24" step="0.25" value={entry.double_time_hours} onChange={(event) => patchEntry(index, { double_time_hours: event.target.value })} /></td>
        <td><input disabled={!editable || busy} value={entry.cost_code || ""} onChange={(event) => patchEntry(index, { cost_code: event.target.value || null })} /></td>
        <td><input disabled={!editable || busy} value={entry.location || ""} onChange={(event) => patchEntry(index, { location: event.target.value || null })} /></td>
        <td><input disabled={!editable || busy} value={entry.work_description || ""} onChange={(event) => patchEntry(index, { work_description: event.target.value || null })} /></td>
      </tr>)}</tbody></table></div>
      <div className="button-row">
        {editable && <button disabled={busy} onClick={() => void saveEntries()}>Save entries</button>}
        {["draft", "rejected"].includes(timecard.status) && can("workforce.timecard.submit") && <button disabled={busy} onClick={() => void action("submit")}>Submit</button>}
        {["submitted", "in_review"].includes(timecard.status) && can("workforce.timecard.approve") && <><button disabled={busy} onClick={() => void action("approve")}>Approve</button><button className="secondary-button" disabled={busy} onClick={() => void action("reject")}>Reject</button></>}
      </div>
    </section>

    <section className="workspace-card">
      <div className="section-heading"><h3>Lifecycle history</h3><span className="status-pill">{history.length}</span></div>
      {history.length === 0 ? <p className="muted">No history events.</p> : <div className="stack">{[...history].reverse().map((event) => <div className="nested-card" key={event.id}><strong>{event.event_type.replaceAll("_", " ")}</strong><p className="muted">Revision {event.timecard_revision} · {new Date(event.created_at).toLocaleString()}</p>{Object.keys(event.details || {}).length > 0 && <p className="muted">{Object.entries(event.details).map(([key, value]) => `${key.replaceAll("_", " ")}: ${typeof value === "object" ? JSON.stringify(value) : String(value)}`).join(" · ")}</p>}</div>)}</div>}
    </section>
  </main>;
}
