"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import styles from "./attendance-workspace.module.css";

type AccessContext = {
  permissions: string[];
  project_permissions: Record<string, string[]>;
};

type Project = { id: string; number: string; name: string };
type WBS = { id: string; code: string; name: string; status: string };
type AttendanceStatus = "draft" | "submitted" | "in_review" | "approved" | "rejected" | "void";
type MarkStatus = "not_marked" | "present" | "absent" | "half_day" | "leave" | "weekly_off";

type AttendanceRegister = {
  id: string;
  project_id: string;
  attendance_date: string;
  shift_code: string;
  status: AttendanceStatus;
  revision: number;
  notes: string | null;
  submitted_at: string | null;
  approved_at: string | null;
  rejected_at: string | null;
};

type AttendanceEntry = {
  id: string;
  assignment_id: string;
  worker_id: string;
  wbs_code_id: string | null;
  trade: string | null;
  mark_status: MarkStatus;
  regular_hours: string | number;
  overtime_hours: string | number;
  location: string | null;
  notes: string | null;
  context_snapshot: Record<string, unknown>;
};

type AttendanceDetail = AttendanceRegister & { entries: AttendanceEntry[] };

type RosterItem = {
  assignment_id: string;
  worker_id: string;
  worker_number: string;
  worker_name: string;
  trade: string | null;
  project_role: string | null;
  default_cost_code: string | null;
};

type SummaryRow = {
  employer_party_id: string | null;
  crew_id: string | null;
  trade: string | null;
  worker_count: number;
  present_count: number;
  absent_count: number;
  regular_hours: string | number;
  overtime_hours: string | number;
};

type DPRSummary = {
  register_id: string;
  project_id: string;
  attendance_date: string;
  shift_code: string;
  rows: SummaryRow[];
};

type HistoryEvent = {
  id: string;
  event_type: string;
  register_revision: number;
  details: Record<string, unknown>;
  created_at: string;
};

type EditableEntry = AttendanceEntry & {
  regular_hours_text: string;
  overtime_hours_text: string;
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
const MARKS: { value: MarkStatus; label: string; short: string }[] = [
  { value: "present", label: "Present", short: "P" },
  { value: "absent", label: "Absent", short: "A" },
  { value: "half_day", label: "Half day", short: "½" },
  { value: "leave", label: "Leave", short: "L" },
  { value: "weekly_off", label: "Weekly off", short: "WO" },
  { value: "not_marked", label: "Not marked", short: "—" },
];

function localDateValue() {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}

function csrfToken() {
  if (typeof document === "undefined") return null;
  const item = document.cookie
    .split(";")
    .map((value) => value.trim())
    .find((value) => value.startsWith("construction_os_csrf="));
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
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    credentials: "include",
    cache: "no-store",
  });
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (body.detail) message = String(body.detail);
    } catch {}
    throw new Error(message);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

function formatHours(value: string | number) {
  const number = Number(value || 0);
  return Number.isInteger(number) ? String(number) : number.toFixed(2).replace(/0+$/, "").replace(/\.$/, "");
}

function humanStatus(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function toEditable(entry: AttendanceEntry): EditableEntry {
  return {
    ...entry,
    regular_hours_text: formatHours(entry.regular_hours),
    overtime_hours_text: formatHours(entry.overtime_hours),
  };
}

export default function AttendanceWorkspace() {
  const [context, setContext] = useState<AccessContext | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [attendanceDate, setAttendanceDate] = useState(localDateValue());
  const [shiftCode, setShiftCode] = useState("day");
  const [registers, setRegisters] = useState<AttendanceRegister[]>([]);
  const [register, setRegister] = useState<AttendanceDetail | null>(null);
  const [roster, setRoster] = useState<RosterItem[]>([]);
  const [entries, setEntries] = useState<EditableEntry[]>([]);
  const [wbs, setWbs] = useState<WBS[]>([]);
  const [summary, setSummary] = useState<DPRSummary | null>(null);
  const [history, setHistory] = useState<HistoryEvent[]>([]);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<MarkStatus | "all">("all");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const can = useCallback(
    (permission: string, pid?: string) => {
      if (!context) return false;
      if (context.permissions.includes(permission)) return true;
      return pid ? (context.project_permissions[pid] || []).includes(permission) : false;
    },
    [context],
  );

  const visibleProjects = useMemo(
    () => projects.filter((project) => can("workforce.attendance.view", project.id)),
    [projects, can],
  );

  const rosterByAssignment = useMemo(
    () => new Map(roster.map((item) => [item.assignment_id, item])),
    [roster],
  );

  const metrics = useMemo(() => {
    const result: Record<MarkStatus, number> = {
      present: 0,
      absent: 0,
      half_day: 0,
      leave: 0,
      weekly_off: 0,
      not_marked: 0,
    };
    entries.forEach((entry) => { result[entry.mark_status] += 1; });
    return result;
  }, [entries]);

  const visibleEntries = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return entries.filter((entry) => {
      const worker = rosterByAssignment.get(entry.assignment_id);
      const snapshotName = String(entry.context_snapshot?.worker_name || "");
      const snapshotNumber = String(entry.context_snapshot?.worker_number || "");
      const haystack = `${worker?.worker_name || snapshotName} ${worker?.worker_number || snapshotNumber} ${entry.trade || ""}`.toLowerCase();
      return (filter === "all" || entry.mark_status === filter) && (!needle || haystack.includes(needle));
    });
  }, [entries, filter, rosterByAssignment, search]);

  const editable = Boolean(register && ["draft", "rejected"].includes(register.status) && can("workforce.attendance.update", projectId));
  const allMarked = entries.length > 0 && entries.every((entry) => entry.mark_status !== "not_marked");

  const loadDay = useCallback(async (pid: string, date: string, shift: string) => {
    if (!pid) {
      setRegisters([]); setRegister(null); setRoster([]); setEntries([]); setSummary(null); setHistory([]); setWbs([]);
      return;
    }
    setError("");
    const [registerRows, rosterRows, wbsRows] = await Promise.all([
      api<AttendanceRegister[]>(`/projects/${pid}/workforce/attendance`),
      api<RosterItem[]>(`/projects/${pid}/workforce/attendance/roster?attendance_date=${encodeURIComponent(date)}`),
      api<WBS[]>(`/projects/${pid}/commercial/wbs`).catch(() => [] as WBS[]),
    ]);
    setRegisters(registerRows);
    setRoster(rosterRows);
    setWbs(wbsRows.filter((row) => row.status === "active"));
    const selected = registerRows.find((row) => row.attendance_date === date && row.shift_code === shift) || null;
    if (!selected) {
      setRegister(null); setEntries([]); setSummary(null); setHistory([]);
      return;
    }
    const [detail, historyRows] = await Promise.all([
      api<AttendanceDetail>(`/projects/${pid}/workforce/attendance/${selected.id}`),
      api<HistoryEvent[]>(`/projects/${pid}/workforce/attendance/${selected.id}/history`).catch(() => [] as HistoryEvent[]),
    ]);
    setRegister(detail);
    setEntries(detail.entries.map(toEditable));
    setHistory(historyRows);
    if (detail.status === "approved") {
      setSummary(await api<DPRSummary>(`/projects/${pid}/workforce/attendance/${detail.id}/dpr-summary`).catch(() => null as DPRSummary | null));
    } else {
      setSummary(null);
    }
  }, []);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const [ctx, projectRows] = await Promise.all([
          api<AccessContext>("/session/context"),
          api<Project[]>("/projects"),
        ]);
        setContext(ctx);
        setProjects(projectRows);
        const first = projectRows.find(
          (project) => ctx.permissions.includes("workforce.attendance.view") || (ctx.project_permissions[project.id] || []).includes("workforce.attendance.view"),
        );
        if (first) {
          setProjectId(first.id);
          await loadDay(first.id, attendanceDate, shiftCode);
        }
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : String(reason));
      } finally {
        setLoading(false);
      }
    })();
  }, [attendanceDate, loadDay, shiftCode]);

  async function refresh(pid = projectId, date = attendanceDate, shift = shiftCode) {
    setBusy(true); setError(""); setMessage("");
    try { await loadDay(pid, date, shift); }
    catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setBusy(false); }
  }

  async function changeContext(pid: string, date: string, shift: string) {
    setProjectId(pid); setAttendanceDate(date); setShiftCode(shift); setSearch(""); setFilter("all");
    setBusy(true); setError(""); setMessage("");
    try { await loadDay(pid, date, shift); }
    catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setBusy(false); }
  }

  async function startAttendance() {
    if (!projectId) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const created = await api<AttendanceDetail>(`/projects/${projectId}/workforce/attendance`, {
        method: "POST",
        body: JSON.stringify({ attendance_date: attendanceDate, shift_code: shiftCode, populate_active_workers: true }),
      });
      setRegister(created);
      setEntries(created.entries.map(toEditable));
      setMessage(`Attendance started with ${created.entries.length} active worker${created.entries.length === 1 ? "" : "s"}.`);
      await loadDay(projectId, attendanceDate, shiftCode);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally { setBusy(false); }
  }

  function updateEntry(assignmentId: string, patch: Partial<EditableEntry>) {
    setEntries((rows) => rows.map((row) => row.assignment_id === assignmentId ? { ...row, ...patch } : row));
  }

  function setMark(assignmentId: string, mark: MarkStatus) {
    const nonWorking = ["not_marked", "absent", "leave", "weekly_off"].includes(mark);
    updateEntry(assignmentId, {
      mark_status: mark,
      ...(nonWorking ? { regular_hours_text: "0", overtime_hours_text: "0" } : {}),
    });
  }

  function markAll(mark: MarkStatus) {
    const nonWorking = ["not_marked", "absent", "leave", "weekly_off"].includes(mark);
    setEntries((rows) => rows.map((row) => ({
      ...row,
      mark_status: mark,
      ...(nonWorking ? { regular_hours_text: "0", overtime_hours_text: "0" } : {}),
    })));
  }

  async function saveEntries() {
    if (!register) return null;
    setBusy(true); setError(""); setMessage("");
    try {
      const updated = await api<AttendanceDetail>(`/projects/${projectId}/workforce/attendance/${register.id}/entries`, {
        method: "PUT",
        body: JSON.stringify({
          expected_revision: register.revision,
          entries: entries.map((entry) => ({
            assignment_id: entry.assignment_id,
            mark_status: entry.mark_status,
            regular_hours: Number(entry.regular_hours_text || 0),
            overtime_hours: Number(entry.overtime_hours_text || 0),
            wbs_code_id: entry.wbs_code_id || null,
            location: entry.location || null,
            notes: entry.notes || null,
          })),
        }),
      });
      setRegister(updated);
      setEntries(updated.entries.map(toEditable));
      setMessage("Attendance saved.");
      return updated;
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
      return null;
    } finally { setBusy(false); }
  }

  async function lifecycle(action: "submit" | "approve" | "reject") {
    if (!register) return;
    let reason: string | null = null;
    if (action === "reject") {
      reason = window.prompt("Reason for rejection")?.trim() || null;
      if (!reason) return;
    }
    setBusy(true); setError(""); setMessage("");
    try {
      await api<AttendanceRegister>(`/projects/${projectId}/workforce/attendance/${register.id}/${action}`, {
        method: "POST",
        body: JSON.stringify({ expected_revision: register.revision, ...(reason ? { reason } : {}) }),
      });
      setMessage(action === "submit" ? "Attendance submitted." : action === "approve" ? "Attendance approved and ready for DPR reuse." : "Attendance returned for correction.");
      await loadDay(projectId, attendanceDate, shiftCode);
    } catch (reasonValue) {
      setError(reasonValue instanceof Error ? reasonValue.message : String(reasonValue));
    } finally { setBusy(false); }
  }

  if (loading) return <main className={styles.shell}><div className={styles.loading}>Loading attendance workspace…</div></main>;

  return (
    <main className={styles.shell}>
      <header className={styles.header}>
        <div>
          <p className={styles.eyebrow}>FIELD OPERATIONS · AUTHORITATIVE WORKFORCE RECORD</p>
          <h1>Attendance</h1>
          <p>Mark the crew once. Approved attendance is the source used by DPR crew summaries.</p>
        </div>
        <div className={styles.headerActions}>
          <Link className={styles.secondaryButton} href="/field">Open DPR</Link>
          <Link className={styles.secondaryButton} href="/">Workspace home</Link>
        </div>
      </header>

      {error && <div className={styles.errorBanner}>{error}</div>}
      {message && <div className={styles.successBanner}>{message}</div>}

      <section className={styles.contextCard}>
        <label>Project
          <select value={projectId} disabled={busy} onChange={(event) => changeContext(event.target.value, attendanceDate, shiftCode)}>
            <option value="">Select project</option>
            {visibleProjects.map((project) => <option key={project.id} value={project.id}>{project.number} · {project.name}</option>)}
          </select>
        </label>
        <label>Date
          <input type="date" value={attendanceDate} disabled={busy} onChange={(event) => changeContext(projectId, event.target.value, shiftCode)} />
        </label>
        <label>Shift
          <select value={shiftCode} disabled={busy} onChange={(event) => changeContext(projectId, attendanceDate, event.target.value)}>
            <option value="day">Day</option>
            <option value="night">Night</option>
          </select>
        </label>
        <button className={styles.secondaryButton} disabled={busy || !projectId} onClick={() => refresh()}>Refresh</button>
      </section>

      {!projectId ? (
        <section className={styles.emptyCard}><h2>No accessible project</h2><p>You need project permission <code>workforce.attendance.view</code> to use this workspace.</p></section>
      ) : !register ? (
        <section className={styles.startCard}>
          <div>
            <p className={styles.eyebrow}>NOT STARTED</p>
            <h2>{attendanceDate} · {humanStatus(shiftCode)} shift</h2>
            <p>{roster.length} active worker{roster.length === 1 ? "" : "s"} are available in the project roster for this date.</p>
          </div>
          {can("workforce.attendance.create", projectId) ? (
            <button disabled={busy} onClick={startAttendance}>Start attendance</button>
          ) : <span className={styles.muted}>Create permission required.</span>}
        </section>
      ) : (
        <>
          <section className={styles.registerBar}>
            <div>
              <span className={`${styles.status} ${styles[`status_${register.status}`] || ""}`}>{humanStatus(register.status)}</span>
              <span>Revision {register.revision}</span>
              <span>{entries.length} workers</span>
            </div>
            <div className={styles.actions}>
              {editable && <button className={styles.secondaryButton} disabled={busy} onClick={saveEntries}>Save</button>}
              {["draft", "rejected"].includes(register.status) && can("workforce.attendance.submit", projectId) && (
                <button disabled={busy || !allMarked} title={!allMarked ? "Mark every worker before submitting" : undefined} onClick={() => lifecycle("submit")}>Submit</button>
              )}
              {register.status === "in_review" && can("workforce.attendance.approve", projectId) && (
                <>
                  <button disabled={busy} onClick={() => lifecycle("approve")}>Approve</button>
                  <button className={styles.dangerButton} disabled={busy} onClick={() => lifecycle("reject")}>Reject</button>
                </>
              )}
            </div>
          </section>

          <section className={styles.metrics}>
            <button className={filter === "all" ? styles.metricActive : ""} onClick={() => setFilter("all")}><strong>{entries.length}</strong><span>Total</span></button>
            <button className={filter === "present" ? styles.metricActive : ""} onClick={() => setFilter("present")}><strong>{metrics.present}</strong><span>Present</span></button>
            <button className={filter === "absent" ? styles.metricActive : ""} onClick={() => setFilter("absent")}><strong>{metrics.absent}</strong><span>Absent</span></button>
            <button className={filter === "half_day" ? styles.metricActive : ""} onClick={() => setFilter("half_day")}><strong>{metrics.half_day}</strong><span>Half day</span></button>
            <button className={filter === "not_marked" ? styles.metricWarn : ""} onClick={() => setFilter("not_marked")}><strong>{metrics.not_marked}</strong><span>Not marked</span></button>
          </section>

          <section className={styles.board}>
            <div className={styles.boardToolbar}>
              <div>
                <h2>Crew register</h2>
                <p>{editable ? "Edit marks, hours, cost code and location, then save." : "This register is read-only at its current workflow status."}</p>
              </div>
              <div className={styles.toolbarControls}>
                <input aria-label="Search crew" placeholder="Search worker, number or trade" value={search} onChange={(event) => setSearch(event.target.value)} />
                {editable && <button className={styles.secondaryButton} onClick={() => markAll("present")}>Mark all present</button>}
              </div>
            </div>

            <div className={styles.tableWrap}>
              <table>
                <thead><tr><th>Worker</th><th>Trade / role</th><th>Status</th><th>Regular</th><th>OT</th><th>WBS / cost code</th><th>Location</th><th>Notes</th></tr></thead>
                <tbody>
                  {visibleEntries.map((entry) => {
                    const worker = rosterByAssignment.get(entry.assignment_id);
                    const workerName = worker?.worker_name || String(entry.context_snapshot?.worker_name || "Worker");
                    const workerNumber = worker?.worker_number || String(entry.context_snapshot?.worker_number || "");
                    const role = worker?.project_role || entry.trade || "—";
                    return (
                      <tr key={entry.assignment_id}>
                        <td><strong>{workerName}</strong><small>{workerNumber}</small></td>
                        <td>{entry.trade || role}</td>
                        <td>
                          <div className={styles.markGroup}>
                            {MARKS.map((mark) => <button key={mark.value} disabled={!editable} title={mark.label} className={entry.mark_status === mark.value ? styles.markActive : ""} onClick={() => setMark(entry.assignment_id, mark.value)}>{mark.short}</button>)}
                          </div>
                        </td>
                        <td><input className={styles.hoursInput} type="number" min="0" max="24" step="0.25" disabled={!editable || ["not_marked", "absent", "leave", "weekly_off"].includes(entry.mark_status)} value={entry.regular_hours_text} onChange={(event) => updateEntry(entry.assignment_id, { regular_hours_text: event.target.value })} /></td>
                        <td><input className={styles.hoursInput} type="number" min="0" max="24" step="0.25" disabled={!editable || ["not_marked", "absent", "leave", "weekly_off"].includes(entry.mark_status)} value={entry.overtime_hours_text} onChange={(event) => updateEntry(entry.assignment_id, { overtime_hours_text: event.target.value })} /></td>
                        <td>
                          <select disabled={!editable} value={entry.wbs_code_id || ""} onChange={(event) => updateEntry(entry.assignment_id, { wbs_code_id: event.target.value || null })}>
                            <option value="">Not assigned</option>
                            {wbs.map((code) => <option key={code.id} value={code.id}>{code.code} · {code.name}</option>)}
                          </select>
                        </td>
                        <td><input disabled={!editable} value={entry.location || ""} onChange={(event) => updateEntry(entry.assignment_id, { location: event.target.value || null })} placeholder="Zone / level" /></td>
                        <td><input disabled={!editable} value={entry.notes || ""} onChange={(event) => updateEntry(entry.assignment_id, { notes: event.target.value || null })} placeholder="Optional" /></td>
                      </tr>
                    );
                  })}
                  {visibleEntries.length === 0 && <tr><td colSpan={8} className={styles.emptyCell}>No workers match this filter.</td></tr>}
                </tbody>
              </table>
            </div>
          </section>

          {register.status === "approved" && (
            <section className={styles.integrationCard}>
              <div><p className={styles.eyebrow}>DPR INTEGRATION</p><h2>Approved crew summary</h2><p>This is the authoritative summary available for Daily Progress Report reuse.</p></div>
              {summary?.rows.length ? (
                <div className={styles.summaryGrid}>
                  {summary.rows.map((row, index) => (
                    <div key={`${row.crew_id || "crew"}-${row.trade || "trade"}-${index}`}>
                      <strong>{row.trade || "Unspecified trade"}</strong>
                      <span>{row.present_count} present · {row.absent_count} absent</span>
                      <small>{formatHours(row.regular_hours)} regular h · {formatHours(row.overtime_hours)} OT h</small>
                    </div>
                  ))}
                </div>
              ) : <p className={styles.muted}>No DPR summary rows were returned.</p>}
              <Link className={styles.secondaryButton} href="/field">Continue to DPR</Link>
            </section>
          )}

          {history.length > 0 && (
            <section className={styles.historyCard}>
              <h2>Activity</h2>
              <div className={styles.historyList}>
                {[...history].reverse().slice(0, 8).map((event) => (
                  <div key={event.id}><span>{humanStatus(event.event_type)}</span><small>Revision {event.register_revision} · {new Date(event.created_at).toLocaleString()}</small></div>
                ))}
              </div>
            </section>
          )}
        </>
      )}

      {registers.length > 0 && (
        <footer className={styles.footerNote}>Project has {registers.length} attendance register{registers.length === 1 ? "" : "s"} recorded. The selected date/shift is shown above.</footer>
      )}
    </main>
  );
}
