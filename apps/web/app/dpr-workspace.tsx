"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

type AccessContext = { permissions: string[]; project_permissions: Record<string, string[]> };
type Project = { id: string; number: string; name: string };
type Report = {
  id: string; project_id: string; report_date: string; shift_code: string; status: string; revision: number;
  weather_condition: string | null; temperature_low: string | null; temperature_high: string | null;
  temperature_unit: string | null; notes: string | null; submitted_at: string | null; approved_at: string | null;
};
type WBS = { id: string; code: string; name: string; status: string };
type BOQ = { id: string; number: string; title: string; status: string };
type BOQItem = { id: string; item_code: string; description: string; wbs_code_id: string | null; unit_code: string };
type BOQDetail = BOQ & { items: BOQItem[] };
type WorkProgress = {
  id?: string; wbs_code_id: string | null; boq_item_id: string | null; description: string; location: string | null;
  quantity: string | null; unit_code: string | null; progress_percent: string | null; remarks: string | null;
};
type ReportPayload = { report_id: string; payload: Record<string, any> };

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

function csrfToken() {
  if (typeof document === "undefined") return null;
  const item = document.cookie.split(";").map((v) => v.trim()).find((v) => v.startsWith("construction_os_csrf="));
  return item ? decodeURIComponent(item.split("=").slice(1).join("=")) : null;
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const method = (init?.method || "GET").toUpperCase();
  const headers = new Headers(init?.headers);
  if (init?.body) headers.set("Content-Type", "application/json");
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    const token = csrfToken(); if (token) headers.set("X-CSRF-Token", token);
  }
  const response = await fetch(`${API_BASE}${path}`, { ...init, headers, credentials: "include", cache: "no-store" });
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try { const body = await response.json() as { detail?: unknown }; if (body.detail) message = String(body.detail); } catch {}
    throw new Error(message);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

function localDateValue() {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}

function Status({ value }: { value: string }) {
  return <span className={`status-pill status-${value.replaceAll("_", "-")}`}>{value.replaceAll("_", " ")}</span>;
}

function ReadOnlyTable({ title, rows, preferred }: { title: string; rows: any[]; preferred?: string[] }) {
  if (!rows?.length) return <section className="workspace-card"><h3>{title}</h3><p className="muted">No records from the authoritative source for this DPR.</p></section>;
  const keys = preferred?.filter((k) => rows.some((r) => r?.[k] !== undefined)) || Object.keys(rows[0]).filter((k) => !["id", "source_id", "source_revision"].includes(k));
  return <section className="workspace-card"><h3>{title}</h3><div className="table-wrap"><table><thead><tr>{keys.map((k) => <th key={k}>{k.replaceAll("_", " ")}</th>)}</tr></thead><tbody>{rows.map((row, i) => <tr key={String(row.id || row.source_id || i)}>{keys.map((k) => <td key={k}>{row[k] == null ? "—" : typeof row[k] === "object" ? JSON.stringify(row[k]) : String(row[k])}</td>)}</tr>)}</tbody></table></div></section>;
}

export default function DPRWorkspace({ initialProjectId, initialReportId }: { initialProjectId?: string; initialReportId?: string }) {
  const [context, setContext] = useState<AccessContext | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState(initialProjectId || "");
  const [reports, setReports] = useState<Report[]>([]);
  const [report, setReport] = useState<Report | null>(null);
  const [payload, setPayload] = useState<Record<string, any> | null>(null);
  const [wbs, setWbs] = useState<WBS[]>([]);
  const [boqs, setBoqs] = useState<BOQ[]>([]);
  const [boqItems, setBoqItems] = useState<BOQItem[]>([]);
  const [progress, setProgress] = useState<WorkProgress[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [createDate, setCreateDate] = useState(localDateValue());
  const [createShift, setCreateShift] = useState("day");

  const can = useCallback((permission: string, pid?: string) => {
    if (!context) return false;
    if (context.permissions.includes(permission)) return true;
    return pid ? (context.project_permissions[pid] || []).includes(permission) : false;
  }, [context]);

  const visibleProjects = useMemo(() => projects.filter((p) => can("field.daily_report.view", p.id)), [projects, can]);

  const loadProject = useCallback(async (pid: string) => {
    const [reportRows, wbsRows, boqRows] = await Promise.all([
      api<Report[]>(`/projects/${pid}/daily-reports`),
      api<WBS[]>(`/projects/${pid}/commercial/wbs`).catch(() => [] as WBS[]),
      api<BOQ[]>(`/projects/${pid}/commercial/boqs`).catch(() => [] as BOQ[]),
    ]);
    setReports(reportRows); setWbs(wbsRows.filter((x) => x.status === "active")); setBoqs(boqRows.filter((x) => x.status === "approved"));
  }, []);

  const openReport = useCallback(async (pid: string, rid: string) => {
    const [detail, reportPayload, workRows] = await Promise.all([
      api<Report>(`/projects/${pid}/daily-reports/${rid}`),
      api<ReportPayload>(`/projects/${pid}/daily-reports/${rid}/report-payload`),
      api<WorkProgress[]>(`/projects/${pid}/daily-reports/${rid}/work-progress`),
    ]);
    setReport(detail); setPayload(reportPayload.payload); setProgress(workRows);
  }, []);

  useEffect(() => {
    (async () => {
      setLoading(true); setError("");
      try {
        const [ctx, ps] = await Promise.all([api<AccessContext>("/session/context"), api<Project[]>("/projects")]);
        setContext(ctx); setProjects(ps);
        const visible = ps.filter((p) => ctx.permissions.includes("field.daily_report.view") || (ctx.project_permissions[p.id] || []).includes("field.daily_report.view"));
        const pid = initialProjectId && visible.some((p) => p.id === initialProjectId) ? initialProjectId : visible[0]?.id || "";
        setProjectId(pid);
        if (pid) {
          await loadProject(pid);
          if (initialReportId) await openReport(pid, initialReportId);
        }
      } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
      finally { setLoading(false); }
    })();
  }, [initialProjectId, initialReportId, loadProject, openReport]);

  async function createReport(e: FormEvent) {
    e.preventDefault(); if (!projectId) return;
    setBusy(true); setError("");
    try {
      const created = await api<Report>(`/projects/${projectId}/daily-reports`, { method: "POST", body: JSON.stringify({ report_date: createDate, shift_code: createShift }) });
      await loadProject(projectId); await openReport(projectId, created.id);
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); }
  }

  async function saveHeader() {
    if (!report) return; setBusy(true); setError("");
    try {
      const updated = await api<Report>(`/projects/${projectId}/daily-reports/${report.id}`, {
        method: "PATCH", body: JSON.stringify({
          expected_revision: report.revision,
          weather_condition: report.weather_condition,
          temperature_low: report.temperature_low || null,
          temperature_high: report.temperature_high || null,
          temperature_unit: report.temperature_unit || null,
          notes: report.notes,
        }),
      });
      setReport(updated); await openReport(projectId, report.id); await loadProject(projectId);
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); }
  }

  function addProgress() {
    setProgress((rows) => [...rows, { wbs_code_id: wbs[0]?.id || null, boq_item_id: null, description: "", location: null, quantity: null, unit_code: null, progress_percent: null, remarks: null }]);
  }

  async function loadBoq(boqId: string) {
    if (!boqId) { setBoqItems([]); return; }
    try { const detail = await api<BOQDetail>(`/projects/${projectId}/commercial/boqs/${boqId}`); setBoqItems(detail.items || []); } catch { setBoqItems([]); }
  }

  async function saveProgress() {
    if (!report) return; setBusy(true); setError("");
    try {
      await api(`/projects/${projectId}/daily-reports/${report.id}/work-progress`, {
        method: "PUT", body: JSON.stringify({ expected_revision: report.revision, rows: progress.map(({ id, ...row }) => ({ ...row, source_type: "manual", source_id: null, source_revision: null })) }),
      });
      await openReport(projectId, report.id); await loadProject(projectId);
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); }
  }

  async function lifecycle(action: "submit" | "approve" | "reject" | "reopen") {
    if (!report) return; setBusy(true); setError("");
    try {
      const body: Record<string, unknown> = { expected_revision: report.revision };
      if (action === "reject") body.reason = window.prompt("Reason for rejection") || "Returned for correction";
      const updated = await api<Report>(`/projects/${projectId}/daily-reports/${report.id}/${action}`, { method: "POST", body: JSON.stringify(body) });
      setReport(updated); await openReport(projectId, report.id); await loadProject(projectId);
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); }
  }

  async function render(format: string) {
    if (!report) return; setBusy(true); setError("");
    try {
      const token = csrfToken();
      const response = await fetch(`${API_BASE}/projects/${projectId}/daily-reports/${report.id}/render`, {
        method: "POST", credentials: "include", headers: { "Content-Type": "application/json", ...(token ? { "X-CSRF-Token": token } : {}) },
        body: JSON.stringify({ output_format: format, persist_history: report.status === "approved" }),
      });
      if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || `${response.status} ${response.statusText}`);
      const blob = await response.blob(); const url = URL.createObjectURL(blob);
      if (format === "html") { window.open(url, "_blank", "noopener,noreferrer"); }
      else { const a = document.createElement("a"); a.href = url; a.download = `${String(payload?.report?.number || "DPR")}.${format}`; a.click(); }
      setTimeout(() => URL.revokeObjectURL(url), 30_000);
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); }
  }

  if (loading) return <main className="workspace-shell"><p>Loading DPR workspace…</p></main>;
  return <main className="workspace-shell">
    <header className="workspace-header"><div><p className="eyebrow">Field Operations · India Release</p><h1>Daily Progress Report</h1><p>Site truth first. The report layout never changes the underlying construction data.</p></div><a className="secondary-button" href="/field/dpr-templates">DPR templates</a></header>
    {error && <div className="error-banner">{error}</div>}
    <section className="workspace-card"><div className="form-grid"><label>Project<select value={projectId} onChange={async (e) => { const pid = e.target.value; setProjectId(pid); setReport(null); setPayload(null); await loadProject(pid); }}><option value="">Select project</option>{visibleProjects.map((p) => <option value={p.id} key={p.id}>{p.number} · {p.name}</option>)}</select></label>{projectId && can("field.daily_report.create", projectId) && <form onSubmit={createReport} className="inline-form"><label>Date<input type="date" value={createDate} onChange={(e) => setCreateDate(e.target.value)} /></label><label>Shift<select value={createShift} onChange={(e) => setCreateShift(e.target.value)}><option value="day">Day</option><option value="night">Night</option></select></label><button disabled={busy}>Create DPR</button></form>}</div></section>
    {projectId && <div className="workspace-grid"><aside className="workspace-card"><h2>DPRs</h2>{reports.length === 0 ? <p className="muted">No DPRs yet.</p> : reports.map((r) => <button key={r.id} className={`list-row ${report?.id === r.id ? "selected" : ""}`} onClick={() => openReport(projectId, r.id)}><span>{r.report_date} · {r.shift_code}</span><Status value={r.status} /></button>)}</aside>
    <section className="workspace-main">{!report ? <div className="workspace-card"><h2>Select or create a DPR</h2><p className="muted">Approved attendance, receipts, material consumption, equipment usage and safety records will be reused automatically.</p></div> : <>
      <section className="workspace-card"><div className="section-heading"><div><h2>{payload?.report?.number || `${report.report_date} DPR`}</h2><Status value={report.status} /></div><div className="button-row">{report.status === "draft" && can("field.daily_report.submit", projectId) && <button onClick={() => lifecycle("submit")} disabled={busy}>Submit</button>}{["submitted","in_review"].includes(report.status) && can("field.daily_report.approve", projectId) && <><button onClick={() => lifecycle("approve")} disabled={busy}>Approve</button><button className="secondary-button" onClick={() => lifecycle("reject")} disabled={busy}>Reject</button></>}{report.status === "rejected" && can("field.daily_report.update", projectId) && <button onClick={() => lifecycle("reopen")} disabled={busy}>Reopen</button>}</div></div>
      <div className="form-grid"><label>Weather<input disabled={report.status !== "draft"} value={report.weather_condition || ""} onChange={(e) => setReport({ ...report, weather_condition: e.target.value })} /></label><label>Low °<input disabled={report.status !== "draft"} value={report.temperature_low || ""} onChange={(e) => setReport({ ...report, temperature_low: e.target.value })} /></label><label>High °<input disabled={report.status !== "draft"} value={report.temperature_high || ""} onChange={(e) => setReport({ ...report, temperature_high: e.target.value })} /></label><label>Unit<select disabled={report.status !== "draft"} value={report.temperature_unit || "C"} onChange={(e) => setReport({ ...report, temperature_unit: e.target.value })}><option>C</option><option>F</option></select></label><label className="wide">Notes<textarea disabled={report.status !== "draft"} value={report.notes || ""} onChange={(e) => setReport({ ...report, notes: e.target.value })} /></label></div>{report.status === "draft" && <button onClick={saveHeader} disabled={busy}>Save DPR details</button>}</section>
      <section className="workspace-card"><div className="section-heading"><h3>Work progress</h3>{report.status === "draft" && <button className="secondary-button" onClick={addProgress}>Add work</button>}</div>{boqs.length > 0 && <label>Load BOQ items for selection<select onChange={(e) => loadBoq(e.target.value)} defaultValue=""><option value="">Optional</option>{boqs.map((b) => <option key={b.id} value={b.id}>{b.number} · {b.title}</option>)}</select></label>}<div className="stack">{progress.map((row, index) => <div className="nested-card" key={row.id || index}><div className="form-grid"><label>WBS<select disabled={report.status !== "draft"} value={row.wbs_code_id || ""} onChange={(e) => setProgress((rs) => rs.map((x,i) => i === index ? { ...x, wbs_code_id: e.target.value || null } : x))}><option value="">Select</option>{wbs.map((x) => <option key={x.id} value={x.id}>{x.code} · {x.name}</option>)}</select></label><label>BOQ item<select disabled={report.status !== "draft"} value={row.boq_item_id || ""} onChange={(e) => { const item = boqItems.find((x) => x.id === e.target.value); setProgress((rs) => rs.map((x,i) => i === index ? { ...x, boq_item_id: e.target.value || null, wbs_code_id: item?.wbs_code_id || x.wbs_code_id, unit_code: item?.unit_code || x.unit_code } : x)); }}><option value="">Optional</option>{boqItems.map((x) => <option key={x.id} value={x.id}>{x.item_code} · {x.description}</option>)}</select></label><label className="wide">Description<input disabled={report.status !== "draft"} value={row.description} onChange={(e) => setProgress((rs) => rs.map((x,i) => i === index ? { ...x, description: e.target.value } : x))} /></label><label>Quantity<input disabled={report.status !== "draft"} type="number" step="0.0001" value={row.quantity || ""} onChange={(e) => setProgress((rs) => rs.map((x,i) => i === index ? { ...x, quantity: e.target.value || null } : x))} /></label><label>Unit<input disabled={report.status !== "draft"} value={row.unit_code || ""} onChange={(e) => setProgress((rs) => rs.map((x,i) => i === index ? { ...x, unit_code: e.target.value || null } : x))} /></label><label>Progress %<input disabled={report.status !== "draft"} type="number" min="0" max="100" step="0.01" value={row.progress_percent || ""} onChange={(e) => setProgress((rs) => rs.map((x,i) => i === index ? { ...x, progress_percent: e.target.value || null } : x))} /></label><label>Location<input disabled={report.status !== "draft"} value={row.location || ""} onChange={(e) => setProgress((rs) => rs.map((x,i) => i === index ? { ...x, location: e.target.value || null } : x))} /></label></div>{report.status === "draft" && <button className="danger-link" onClick={() => setProgress((rs) => rs.filter((_,i) => i !== index))}>Remove</button>}</div>)}</div>{report.status === "draft" && <button onClick={saveProgress} disabled={busy}>Save work progress</button>}</section>
      {payload && <><ReadOnlyTable title="Workforce / approved attendance" rows={payload.workforce || []} preferred={["employer","trade","crew","wbs_code","worker_count","present_count","absent_count","regular_hours","overtime_hours"]} /><ReadOnlyTable title="Materials received" rows={payload.materials_received || []} preferred={["grn_number","supplier","material","accepted_quantity","unit_code","wbs_code","challan_number"]} /><ReadOnlyTable title="Materials consumed" rows={payload.materials_consumed || []} preferred={["material","quantity","unit_code","wbs_code","boq_item_code","location"]} /><ReadOnlyTable title="Equipment usage" rows={payload.equipment || []} preferred={["asset_number","equipment","operating_hours","wbs_code","boq_item_code","location"]} /><ReadOnlyTable title="Delays / blockers" rows={payload.delays || []} /><ReadOnlyTable title="Safety / quality" rows={[...(payload.safety || []), ...(payload.quality || [])]} /></>}
      <section className="workspace-card"><h3>Preview / export</h3><p className="muted">All formats use the same normalized DPR payload and effective published template.</p><div className="button-row">{["html","pdf","xlsx","docx","csv","json"].map((f) => <button className={f === "pdf" ? "" : "secondary-button"} key={f} disabled={busy || !can("field.dpr.render", projectId)} onClick={() => render(f)}>{f === "html" ? "Print view" : f.toUpperCase()}</button>)}</div></section>
    </>}</section></div>}
  </main>;
}
