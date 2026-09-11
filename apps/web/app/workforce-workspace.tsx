"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

type AccessContext = { permissions: string[]; project_permissions: Record<string, string[]> };
type Project = { id: string; number: string; name: string };
type Worker = { id: string; worker_number: string; first_name: string; last_name: string; trade: string | null; status: string; revision: number };
type Crew = { id: string; name: string; status: string; revision: number };
type Assignment = { id: string; project_id: string; worker_id: string; crew_id: string | null; employer_party_id: string | null; engagement_type: string | null; trade: string | null; status: string; revision: number };
type AttendanceEntry = { id: string; assignment_id: string; worker_id: string; crew_id: string | null; employer_party_id: string | null; trade: string | null; mark_status: string; regular_hours: string; overtime_hours: string; wbs_code_id: string | null; location: string | null; notes: string | null; context_snapshot: Record<string, unknown> };
type Attendance = { id: string; project_id: string; attendance_date: string; shift_code: string; status: string; revision: number; submitted_at: string | null; approved_at: string | null; entries?: AttendanceEntry[] };
type SummaryRow = { employer_party_id: string | null; crew_id: string | null; trade: string | null; worker_count: number; present_count: number; absent_count: number; regular_hours: string; overtime_hours: string };
type DPRSummary = { register_id: string; attendance_date: string; shift_code: string; rows: SummaryRow[] };

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
const MARKS = ["present", "absent", "half_day", "leave", "weekly_off"];

function csrfToken(): string | null {
  if (typeof document === "undefined") return null;
  const item = document.cookie.split(";").map((v) => v.trim()).find((v) => v.startsWith("construction_os_csrf="));
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
    try { const body = (await response.json()) as { detail?: unknown }; if (body.detail) message = String(body.detail); } catch {}
    throw new Error(message);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

function Status({ value }: { value: string }) {
  return <span className={`status-pill status-${value.replaceAll("_", "-")}`}>{value.replaceAll("_", " ")}</span>;
}

function workerLabel(worker: Worker | undefined, entry?: AttendanceEntry) {
  if (worker) return `${worker.worker_number} · ${worker.first_name} ${worker.last_name}`;
  const number = String(entry?.context_snapshot.worker_number || "Worker");
  const name = String(entry?.context_snapshot.worker_name || entry?.worker_id || "");
  return `${number} · ${name}`;
}

export default function WorkforceWorkspace({ initialProjectId, initialRegisterId }: { initialProjectId?: string; initialRegisterId?: string }) {
  const [context, setContext] = useState<AccessContext | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [crews, setCrews] = useState<Crew[]>([]);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [registers, setRegisters] = useState<Attendance[]>([]);
  const [projectId, setProjectId] = useState(initialProjectId || "");
  const [attendance, setAttendance] = useState<Attendance | null>(null);
  const [summary, setSummary] = useState<DPRSummary | null>(null);
  const [tab, setTab] = useState("attendance");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const can = useCallback((permission: string, targetProject?: string) => {
    if (!context) return false;
    if (context.permissions.includes(permission)) return true;
    return targetProject ? (context.project_permissions[targetProject] || []).includes(permission) : false;
  }, [context]);

  const workerById = useMemo(() => new Map(workers.map((row) => [row.id, row])), [workers]);
  const accessibleProjects = useMemo(() => projects.filter((row) =>
    can("workforce.assignment.view", row.id) || can("workforce.attendance.view", row.id) || can("workforce.timecard.view", row.id)
  ), [can, projects]);

  const loadProject = useCallback(async (target: string) => {
    const [assignmentRows, attendanceRows] = await Promise.all([
      api<Assignment[]>(`/projects/${target}/workforce/assignments`),
      api<Attendance[]>(`/projects/${target}/workforce/attendance`),
    ]);
    setAssignments(assignmentRows);
    setRegisters(attendanceRows);
  }, []);

  const openAttendance = useCallback(async (targetProject: string, registerId: string) => {
    const detail = await api<Attendance>(`/projects/${targetProject}/workforce/attendance/${registerId}`);
    setAttendance(detail);
    setSummary(null);
    if (detail.status === "approved") {
      try { setSummary(await api<DPRSummary>(`/projects/${targetProject}/workforce/attendance/${registerId}/dpr-summary`)); } catch {}
    }
    setTab("attendance");
  }, []);

  const bootstrap = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const [nextContext, projectRows, workerRows, crewRows] = await Promise.all([
        api<AccessContext>("/session/context"), api<Project[]>("/projects"), api<Worker[]>("/workforce/workers"), api<Crew[]>("/workforce/crews"),
      ]);
      setContext(nextContext); setProjects(projectRows); setWorkers(workerRows); setCrews(crewRows);
      const visible = projectRows.filter((row) => nextContext.permissions.some((p) => p.startsWith("workforce.")) || (nextContext.project_permissions[row.id] || []).some((p) => p.startsWith("workforce.")));
      const selected = initialProjectId && visible.some((row) => row.id === initialProjectId) ? initialProjectId : visible[0]?.id || "";
      setProjectId(selected);
      if (selected) {
        await loadProject(selected);
        if (initialRegisterId) await openAttendance(selected, initialRegisterId);
      }
    } catch (requestError) { setError((requestError as Error).message); }
    finally { setLoading(false); }
  }, [initialProjectId, initialRegisterId, loadProject, openAttendance]);

  useEffect(() => { void bootstrap(); }, [bootstrap]);

  const run = async (work: () => Promise<void>) => {
    setBusy(true); setError("");
    try { await work(); if (projectId) await loadProject(projectId); }
    catch (requestError) { setError((requestError as Error).message); }
    finally { setBusy(false); }
  };

  const createWorker = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); const form = new FormData(event.currentTarget); const element = event.currentTarget;
    await run(async () => {
      await api("/workforce/workers", { method: "POST", body: JSON.stringify({ worker_number: form.get("worker_number"), first_name: form.get("first_name"), last_name: form.get("last_name"), trade: form.get("trade") || null }) });
      setWorkers(await api<Worker[]>("/workforce/workers")); element.reset();
    });
  };

  const createCrew = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); const form = new FormData(event.currentTarget); const element = event.currentTarget;
    await run(async () => {
      await api("/workforce/crews", { method: "POST", body: JSON.stringify({ name: form.get("name"), description: form.get("description") || null }) });
      setCrews(await api<Crew[]>("/workforce/crews")); element.reset();
    });
  };

  const assignWorker = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); if (!projectId) return; const form = new FormData(event.currentTarget); const element = event.currentTarget;
    await run(async () => {
      await api(`/projects/${projectId}/workforce/assignments`, { method: "POST", body: JSON.stringify({ worker_id: form.get("worker_id"), crew_id: form.get("crew_id") || null, engagement_type: form.get("engagement_type") || null, trade: form.get("trade") || null }) });
      element.reset();
    });
  };

  const createAttendance = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); if (!projectId) return; const form = new FormData(event.currentTarget);
    await run(async () => {
      const created = await api<Attendance>(`/projects/${projectId}/workforce/attendance`, { method: "POST", body: JSON.stringify({ attendance_date: form.get("attendance_date"), shift_code: form.get("shift_code") || "day", populate_active_workers: true }) });
      await openAttendance(projectId, created.id);
    });
  };

  const updateMark = (entryId: string, field: "mark_status" | "regular_hours" | "overtime_hours", value: string) => {
    setAttendance((current) => current ? { ...current, entries: (current.entries || []).map((row) => row.id === entryId ? { ...row, [field]: value, ...(field === "mark_status" && ["absent", "leave", "weekly_off"].includes(value) ? { regular_hours: "0", overtime_hours: "0" } : {}) } : row) } : current);
  };

  const markAllPresent = () => setAttendance((current) => current ? { ...current, entries: (current.entries || []).map((row) => ({ ...row, mark_status: "present", regular_hours: row.regular_hours === "0" ? "8" : row.regular_hours })) } : current);

  const saveAttendance = () => attendance && run(async () => {
    const saved = await api<Attendance>(`/projects/${projectId}/workforce/attendance/${attendance.id}/entries`, { method: "PUT", body: JSON.stringify({ expected_revision: attendance.revision, entries: (attendance.entries || []).map((row) => ({ assignment_id: row.assignment_id, mark_status: row.mark_status, regular_hours: row.regular_hours, overtime_hours: row.overtime_hours, wbs_code_id: row.wbs_code_id, location: row.location, notes: row.notes })) }) });
    setAttendance(saved);
  });

  const submitAttendance = () => attendance && run(async () => {
    const saved = await api<Attendance>(`/projects/${projectId}/workforce/attendance/${attendance.id}/submit`, { method: "POST", body: JSON.stringify({ expected_revision: attendance.revision, reason: "Submitted from workforce workspace" }) });
    await openAttendance(projectId, saved.id);
  });

  const reviewAttendance = (approve: boolean) => attendance && run(async () => {
    const saved = await api<Attendance>(`/projects/${projectId}/workforce/attendance/${attendance.id}/${approve ? "approve" : "reject"}`, { method: "POST", body: JSON.stringify({ expected_revision: attendance.revision, reason: approve ? "Approved from workforce workspace" : "Returned for correction" }) });
    await openAttendance(projectId, saved.id);
  });

  if (loading) return <main className="boot-screen"><div className="boot-mark">COS</div><p>Loading workforce…</p></main>;

  return <main className="workspace"><section className="page-frame">
    <div className="page-heading"><div><p className="eyebrow">MODULE 5</p><h1>Workforce / Contract Labour / Attendance</h1><p>Keep Worker identity once, assign people to projects, and finish daily site muster with minimal typing.</p></div></div>
    {error && <div className="error-banner"><strong>Action not completed</strong><span>{error}</span><button onClick={() => setError("")}>×</button></div>}
    {accessibleProjects.length === 0 ? <div className="empty-state"><strong>No accessible project</strong><p>You need Workforce project permissions.</p></div> : <>
      <section className="workflow-card"><div><p className="eyebrow">PROJECT</p><h2>{projects.find((row) => row.id === projectId)?.name || "Choose project"}</h2></div><div className="quick-form"><select value={projectId} onChange={(event) => void run(async () => { setProjectId(event.target.value); setAttendance(null); await loadProject(event.target.value); })}>{accessibleProjects.map((row) => <option key={row.id} value={row.id}>{row.number} · {row.name}</option>)}</select><button className={tab === "attendance" ? "" : "secondary"} onClick={() => setTab("attendance")}>Attendance</button><button className={tab === "staffing" ? "" : "secondary"} onClick={() => setTab("staffing")}>Staffing</button><button className={tab === "workers" ? "" : "secondary"} onClick={() => setTab("workers")}>Workers & Crews</button></div></section>

      {tab === "attendance" && <div className="split-layout"><section>
        {can("workforce.attendance.create", projectId) && <section className="workflow-card"><div><p className="eyebrow">DAILY MUSTER</p><h2>Start attendance</h2></div><form className="quick-form" onSubmit={createAttendance}><input type="date" name="attendance_date" defaultValue={new Date().toISOString().slice(0, 10)} required/><input name="shift_code" defaultValue="day" placeholder="Shift"/><button disabled={busy}>Create & load workers</button></form></section>}
        <div className="detail-title"><div><p className="eyebrow">REGISTERS</p><h3>{registers.length} attendance days</h3></div></div>
        <div className="record-list">{registers.map((row) => <button key={row.id} className={attendance?.id === row.id ? "list-card selected" : "list-card"} onClick={() => void openAttendance(projectId, row.id)}><div><strong>{row.attendance_date} · {row.shift_code}</strong><small>Revision {row.revision}</small></div><Status value={row.status}/></button>)}</div>
      </section><section>
        {!attendance ? <div className="empty-state"><strong>Select an attendance register</strong><p>Create today’s register and all active project workers will be loaded automatically.</p></div> : <>
          <div className="detail-title"><div><p className="eyebrow">{attendance.attendance_date} · {attendance.shift_code}</p><h2>Site attendance</h2></div><Status value={attendance.status}/></div>
          {attendance.status === "draft" || attendance.status === "rejected" ? <div className="quick-form"><button className="secondary" onClick={markAllPresent}>Mark all present</button>{can("workforce.attendance.update", projectId) && <button disabled={busy} onClick={saveAttendance}>Save attendance</button>}{can("workforce.attendance.submit", projectId) && <button disabled={busy} onClick={submitAttendance}>Submit</button>}</div> : null}
          {attendance.status === "in_review" && can("workforce.attendance.approve", projectId) && <div className="quick-form"><button className="secondary" disabled={busy} onClick={() => reviewAttendance(false)}>Reject</button><button disabled={busy} onClick={() => reviewAttendance(true)}>Approve</button></div>}
          <div className="record-list">{(attendance.entries || []).map((entry) => <div key={entry.id} className="list-card"><div><strong>{workerLabel(workerById.get(entry.worker_id), entry)}</strong><small>{entry.trade || "No trade"}{entry.context_snapshot.engagement_type ? ` · ${String(entry.context_snapshot.engagement_type).replaceAll("_", " ")}` : ""}</small></div>{attendance.status === "draft" || attendance.status === "rejected" ? <div className="quick-form"><select value={entry.mark_status} onChange={(event) => updateMark(entry.id, "mark_status", event.target.value)}>{MARKS.map((mark) => <option key={mark} value={mark}>{mark.replaceAll("_", " ")}</option>)}</select><input type="number" min="0" max="24" step="0.5" value={entry.regular_hours} onChange={(event) => updateMark(entry.id, "regular_hours", event.target.value)} aria-label="Regular hours"/><input type="number" min="0" max="24" step="0.5" value={entry.overtime_hours} onChange={(event) => updateMark(entry.id, "overtime_hours", event.target.value)} aria-label="Overtime hours"/></div> : <Status value={entry.mark_status}/>}</div>)}</div>
          {summary && <section className="workflow-card"><div><p className="eyebrow">DPR READY</p><h3>Approved crew summary</h3></div><div className="record-list">{summary.rows.map((row, index) => <div key={`${row.crew_id}-${row.trade}-${index}`} className="list-card"><div><strong>{row.trade || "General labour"}</strong><small>{row.present_count} present · {row.absent_count} absent · {row.regular_hours} regular hrs · {row.overtime_hours} OT hrs</small></div><span>{row.worker_count} workers</span></div>)}</div></section>}
        </>}
      </section></div>}

      {tab === "staffing" && <div className="split-layout"><section>
        {can("workforce.assignment.manage", projectId) && <section className="workflow-card"><div><p className="eyebrow">PROJECT STAFFING</p><h2>Assign Worker</h2></div><form className="quick-form" onSubmit={assignWorker}><select name="worker_id" required defaultValue=""><option value="" disabled>Select Worker</option>{workers.filter((row) => row.status === "active").map((row) => <option key={row.id} value={row.id}>{row.worker_number} · {row.first_name} {row.last_name}</option>)}</select><select name="crew_id" defaultValue=""><option value="">No crew</option>{crews.filter((row) => row.status === "active").map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</select><select name="engagement_type" defaultValue="contract_labour"><option value="staff">Staff</option><option value="direct_labour">Direct labour</option><option value="contract_labour">Contract labour</option><option value="subcontractor_labour">Subcontractor labour</option><option value="vendor_crew">Vendor crew</option></select><input name="trade" placeholder="Trade / role"/><button disabled={busy}>Assign</button></form></section>}
      </section><section><div className="detail-title"><div><p className="eyebrow">ASSIGNMENTS</p><h3>{assignments.length} project workers</h3></div></div><div className="record-list">{assignments.map((row) => <div key={row.id} className="list-card"><div><strong>{workerLabel(workerById.get(row.worker_id))}</strong><small>{row.trade || "No trade"} · {(row.engagement_type || "unspecified").replaceAll("_", " ")}</small></div><Status value={row.status}/></div>)}</div></section></div>}

      {tab === "workers" && <div className="split-layout"><section>{context?.permissions.includes("workforce.worker.manage") && <section className="workflow-card"><div><p className="eyebrow">WORKER MASTER</p><h2>Add Worker</h2></div><form className="quick-form" onSubmit={createWorker}><input name="worker_number" placeholder="Worker no." required/><input name="first_name" placeholder="First name" required/><input name="last_name" placeholder="Last name" required/><input name="trade" placeholder="Trade"/><button disabled={busy}>Add Worker</button></form></section>}<div className="record-list">{workers.map((row) => <div key={row.id} className="list-card"><div><strong>{row.worker_number} · {row.first_name} {row.last_name}</strong><small>{row.trade || "No trade"}</small></div><Status value={row.status}/></div>)}</div></section><section>{context?.permissions.includes("workforce.crew.manage") && <section className="workflow-card"><div><p className="eyebrow">CREWS</p><h2>Create crew</h2></div><form className="quick-form" onSubmit={createCrew}><input name="name" placeholder="Crew name" required/><input name="description" placeholder="Description"/><button disabled={busy}>Create crew</button></form></section>}<div className="record-list">{crews.map((row) => <div key={row.id} className="list-card"><div><strong>{row.name}</strong><small>Revision {row.revision}</small></div><Status value={row.status}/></div>)}</div></section></div>}
    </>}
  </section></main>;
}
