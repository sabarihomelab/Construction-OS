"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

type AccessContext = { permissions: string[]; project_permissions: Record<string, string[]> };
type Project = { id: string; number: string; name: string };
type Worker = {
  id: string;
  worker_number: string;
  first_name: string;
  last_name: string;
  preferred_name: string | null;
  email: string | null;
  phone: string | null;
  job_title: string | null;
  trade: string | null;
  classification: string | null;
  hire_date: string | null;
  termination_date: string | null;
  status: string;
  revision: number;
};
type Crew = {
  id: string;
  name: string;
  description: string | null;
  supervisor_worker_id: string | null;
  status: string;
  revision: number;
};
type Party = { id: string; code: string; name: string; status: string };
type Assignment = {
  id: string;
  project_id: string;
  worker_id: string;
  crew_id: string | null;
  employer_party_id: string | null;
  engagement_type: string | null;
  project_role: string | null;
  trade: string | null;
  default_cost_code: string | null;
  start_date: string | null;
  end_date: string | null;
  status: string;
  revision: number;
};
type Rate = {
  id: string;
  assignment_id: string;
  worker_id: string;
  wage_basis: string;
  regular_rate: string;
  overtime_rate: string | null;
  double_time_rate: string | null;
  billing_rate: string | null;
  currency_code: string;
  effective_from: string;
  effective_to: string | null;
  source_reference: string | null;
  revision: number;
};
type Attendance = {
  id: string;
  project_id: string;
  attendance_date: string;
  shift_code: string;
  status: string;
  revision: number;
};
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
};
type TimecardDetail = Timecard & { entries: TimeEntry[] };
type TimecardHistory = {
  id: string;
  event_type: string;
  timecard_revision: number;
  details: Record<string, unknown>;
  created_at: string;
};

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
const ENGAGEMENT_TYPES = [
  "staff",
  "direct_labour",
  "contract_labour",
  "subcontractor_labour",
  "vendor_crew",
  "other",
];
const WAGE_BASES = ["hourly", "daily", "weekly", "monthly", "piece_rate", "contract"];

function csrfToken(): string | null {
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
    throw new ApiError(response.status, message);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

function localDateValue() {
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 10);
}

function startOfWeekValue() {
  const now = new Date();
  const day = now.getDay();
  const delta = day === 0 ? -6 : 1 - day;
  now.setDate(now.getDate() + delta);
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 10);
}

function addDays(value: string, days: number) {
  const date = new Date(`${value}T00:00:00`);
  date.setDate(date.getDate() + days);
  return date.toISOString().slice(0, 10);
}

function blankWeek(weekStart: string): TimeEntry[] {
  return Array.from({ length: 7 }, (_, index) => ({
    work_date: addDays(weekStart, index),
    regular_hours: "0",
    overtime_hours: "0",
    double_time_hours: "0",
    cost_code: null,
    location: null,
    work_description: null,
    source_type: "manual",
    source_id: null,
  }));
}

function Status({ value }: { value: string }) {
  return (
    <span className={`status-pill status-${value.replaceAll("_", "-")}`}>
      {value.replaceAll("_", " ")}
    </span>
  );
}

function money(value: string | number | null, currency = "INR") {
  if (value === null || value === "") return "—";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(Number(value));
}

function workerLabel(worker: Worker | undefined, workerId?: string) {
  return worker
    ? `${worker.worker_number} · ${worker.first_name} ${worker.last_name}`
    : `Worker ${workerId || "—"}`;
}

function hasProjectPermission(context: AccessContext, permission: string, projectId: string) {
  return (
    context.permissions.includes(permission) ||
    (context.project_permissions[projectId] || []).includes(permission)
  );
}

function optionalText(form: FormData, key: string) {
  const value = String(form.get(key) || "").trim();
  return value || null;
}

export default function WorkforceWorkspace({ initialProjectId }: { initialProjectId?: string }) {
  const [context, setContext] = useState<AccessContext | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [crews, setCrews] = useState<Crew[]>([]);
  const [parties, setParties] = useState<Party[]>([]);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [registers, setRegisters] = useState<Attendance[]>([]);
  const [timecards, setTimecards] = useState<Timecard[]>([]);
  const [projectId, setProjectId] = useState(initialProjectId || "");
  const [selectedWorkerId, setSelectedWorkerId] = useState("");
  const [selectedCrewId, setSelectedCrewId] = useState("");
  const [selectedAssignmentId, setSelectedAssignmentId] = useState("");
  const [rates, setRates] = useState<Rate[]>([]);
  const [timecard, setTimecard] = useState<TimecardDetail | null>(null);
  const [timeEntries, setTimeEntries] = useState<TimeEntry[]>([]);
  const [timecardHistory, setTimecardHistory] = useState<TimecardHistory[]>([]);
  const [tab, setTab] = useState("attendance");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const can = useCallback(
    (permission: string, targetProject?: string) => {
      if (!context) return false;
      if (context.permissions.includes(permission)) return true;
      return targetProject
        ? (context.project_permissions[targetProject] || []).includes(permission)
        : false;
    },
    [context],
  );

  const workerById = useMemo(
    () => new Map(workers.map((row) => [row.id, row])),
    [workers],
  );
  const crewById = useMemo(() => new Map(crews.map((row) => [row.id, row])), [crews]);
  const partyById = useMemo(() => new Map(parties.map((row) => [row.id, row])), [parties]);
  const selectedWorker = workerById.get(selectedWorkerId);
  const selectedCrew = crewById.get(selectedCrewId);
  const selectedAssignment = assignments.find((row) => row.id === selectedAssignmentId) || null;

  const accessibleProjects = useMemo(
    () =>
      projects.filter((row) => {
        if (!context) return false;
        return (context.project_permissions[row.id] || []).some((permission) =>
          permission.startsWith("workforce."),
        ) || context.permissions.some((permission) => permission.startsWith("workforce."));
      }),
    [context, projects],
  );

  const assignedWorkerIds = useMemo(
    () => new Set(assignments.filter((row) => row.status === "active").map((row) => row.worker_id)),
    [assignments],
  );
  const assignedWorkers = useMemo(
    () => workers.filter((row) => assignedWorkerIds.has(row.id) && row.status === "active"),
    [assignedWorkerIds, workers],
  );

  const loadOrgData = useCallback(async (ctx: AccessContext) => {
    const [workerRows, crewRows, partyRows] = await Promise.all([
      ctx.permissions.includes("workforce.worker.view")
        ? api<Worker[]>("/workforce/workers")
        : Promise.resolve([] as Worker[]),
      ctx.permissions.includes("workforce.crew.view")
        ? api<Crew[]>("/workforce/crews")
        : Promise.resolve([] as Crew[]),
      ctx.permissions.includes("commercial.party.view")
        ? api<Party[]>("/commercial/parties")
        : Promise.resolve([] as Party[]),
    ]);
    setWorkers(workerRows);
    setCrews(crewRows);
    setParties(partyRows.filter((row) => row.status === "active"));
  }, []);

  const loadProject = useCallback(async (target: string, ctx: AccessContext) => {
    const [assignmentRows, attendanceRows, timecardRows] = await Promise.all([
      hasProjectPermission(ctx, "workforce.assignment.view", target)
        ? api<Assignment[]>(`/projects/${target}/workforce/assignments`)
        : Promise.resolve([] as Assignment[]),
      hasProjectPermission(ctx, "workforce.attendance.view", target)
        ? api<Attendance[]>(`/projects/${target}/workforce/attendance`)
        : Promise.resolve([] as Attendance[]),
      hasProjectPermission(ctx, "workforce.timecard.view", target)
        ? api<Timecard[]>(`/projects/${target}/timecards`)
        : Promise.resolve([] as Timecard[]),
    ]);
    setAssignments(assignmentRows);
    setRegisters(attendanceRows);
    setTimecards(timecardRows);
    setSelectedAssignmentId((current) =>
      current && assignmentRows.some((row) => row.id === current) ? current : "",
    );
    setTimecard((current) =>
      current && timecardRows.some((row) => row.id === current.id) ? current : null,
    );
  }, []);

  const bootstrap = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [ctx, projectRows] = await Promise.all([
        api<AccessContext>("/session/context"),
        api<Project[]>("/projects"),
      ]);
      setContext(ctx);
      setProjects(projectRows);
      await loadOrgData(ctx);
      const visible = projectRows.filter(
        (row) =>
          (ctx.project_permissions[row.id] || []).some((permission) =>
            permission.startsWith("workforce."),
          ) || ctx.permissions.some((permission) => permission.startsWith("workforce.")),
      );
      const selected =
        initialProjectId && visible.some((row) => row.id === initialProjectId)
          ? initialProjectId
          : visible[0]?.id || "";
      setProjectId(selected);
      if (selected) await loadProject(selected, ctx);

      const defaultTab = selected && hasProjectPermission(ctx, "workforce.attendance.view", selected)
        ? "attendance"
        : selected && hasProjectPermission(ctx, "workforce.assignment.view", selected)
          ? "staffing"
          : selected && hasProjectPermission(ctx, "workforce.timecard.view", selected)
            ? "timecards"
            : ctx.permissions.includes("workforce.worker.view") || ctx.permissions.includes("workforce.crew.view")
              ? "workers"
              : "attendance";
      setTab(defaultTab);
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setLoading(false);
    }
  }, [initialProjectId, loadOrgData, loadProject]);

  useEffect(() => {
    void bootstrap();
  }, [bootstrap]);

  const refresh = useCallback(async () => {
    if (!context) return;
    await loadOrgData(context);
    if (projectId) await loadProject(projectId, context);
  }, [context, loadOrgData, loadProject, projectId]);

  const run = async (work: () => Promise<void>) => {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await work();
    } catch (requestError) {
      if (requestError instanceof ApiError && requestError.status === 409) {
        try { await refresh(); } catch {}
        setError(
          "This record changed after you opened it. The latest data has been loaded; review it and try again.",
        );
      } else {
        setError((requestError as Error).message);
      }
    } finally {
      setBusy(false);
    }
  };

  const switchProject = async (nextProjectId: string) => {
    if (!context) return;
    setBusy(true);
    setError("");
    setMessage("");
    setProjectId(nextProjectId);
    setSelectedAssignmentId("");
    setRates([]);
    setTimecard(null);
    setTimeEntries([]);
    setTimecardHistory([]);
    try {
      await loadProject(nextProjectId, context);
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const createWorker = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const element = event.currentTarget;
    await run(async () => {
      await api("/workforce/workers", {
        method: "POST",
        body: JSON.stringify({
          worker_number: form.get("worker_number"),
          first_name: form.get("first_name"),
          last_name: form.get("last_name"),
          preferred_name: optionalText(form, "preferred_name"),
          email: optionalText(form, "email"),
          phone: optionalText(form, "phone"),
          job_title: optionalText(form, "job_title"),
          trade: optionalText(form, "trade"),
          classification: optionalText(form, "classification"),
          hire_date: optionalText(form, "hire_date"),
        }),
      });
      element.reset();
      if (context) await loadOrgData(context);
      setMessage("Worker created.");
    });
  };

  const updateWorker = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedWorker) return;
    const form = new FormData(event.currentTarget);
    await run(async () => {
      await api(`/workforce/workers/${selectedWorker.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          expected_revision: selectedWorker.revision,
          first_name: form.get("first_name"),
          last_name: form.get("last_name"),
          preferred_name: optionalText(form, "preferred_name"),
          email: optionalText(form, "email"),
          phone: optionalText(form, "phone"),
          job_title: optionalText(form, "job_title"),
          trade: optionalText(form, "trade"),
          classification: optionalText(form, "classification"),
          hire_date: optionalText(form, "hire_date"),
          termination_date: optionalText(form, "termination_date"),
          status: form.get("status"),
          reason: "Updated from Workforce workspace",
        }),
      });
      if (context) await loadOrgData(context);
      setMessage("Worker updated.");
    });
  };

  const createCrew = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const element = event.currentTarget;
    await run(async () => {
      await api("/workforce/crews", {
        method: "POST",
        body: JSON.stringify({
          name: form.get("name"),
          description: optionalText(form, "description"),
          supervisor_worker_id: form.get("supervisor_worker_id") || null,
        }),
      });
      element.reset();
      if (context) await loadOrgData(context);
      setMessage("Crew created.");
    });
  };

  const updateCrew = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedCrew) return;
    const form = new FormData(event.currentTarget);
    await run(async () => {
      await api(`/workforce/crews/${selectedCrew.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          expected_revision: selectedCrew.revision,
          name: form.get("name"),
          description: optionalText(form, "description"),
          supervisor_worker_id: form.get("supervisor_worker_id") || null,
          status: form.get("status"),
          reason: "Updated from Workforce workspace",
        }),
      });
      if (context) await loadOrgData(context);
      setMessage("Crew updated.");
    });
  };

  const addCrewMember = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedCrew) return;
    const form = new FormData(event.currentTarget);
    await run(async () => {
      await api(`/workforce/crews/${selectedCrew.id}/memberships`, {
        method: "POST",
        body: JSON.stringify({
          worker_id: form.get("worker_id"),
          role: optionalText(form, "role"),
          effective_from: form.get("effective_from"),
          effective_to: optionalText(form, "effective_to"),
        }),
      });
      setMessage("Crew membership added.");
    });
  };

  const assignWorker = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!projectId || !context) return;
    const form = new FormData(event.currentTarget);
    const element = event.currentTarget;
    await run(async () => {
      await api(`/projects/${projectId}/workforce/assignments`, {
        method: "POST",
        body: JSON.stringify({
          worker_id: form.get("worker_id"),
          crew_id: form.get("crew_id") || null,
          employer_party_id: form.get("employer_party_id") || null,
          engagement_type: form.get("engagement_type") || null,
          project_role: optionalText(form, "project_role"),
          trade: optionalText(form, "trade"),
          default_cost_code: optionalText(form, "default_cost_code"),
          start_date: optionalText(form, "start_date"),
          end_date: optionalText(form, "end_date"),
        }),
      });
      element.reset();
      await loadProject(projectId, context);
      setMessage("Worker assigned to project.");
    });
  };

  const updateAssignment = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedAssignment || !context) return;
    const form = new FormData(event.currentTarget);
    await run(async () => {
      await api(`/projects/${projectId}/workforce/assignments/${selectedAssignment.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          expected_revision: selectedAssignment.revision,
          crew_id: form.get("crew_id") || null,
          employer_party_id: form.get("employer_party_id") || null,
          engagement_type: form.get("engagement_type") || null,
          project_role: optionalText(form, "project_role"),
          trade: optionalText(form, "trade"),
          default_cost_code: optionalText(form, "default_cost_code"),
          start_date: optionalText(form, "start_date"),
          end_date: optionalText(form, "end_date"),
          status: form.get("status"),
          reason: "Updated from Workforce workspace",
        }),
      });
      await loadProject(projectId, context);
      setMessage("Project assignment updated.");
    });
  };

  const openAssignment = async (assignmentId: string) => {
    setSelectedAssignmentId(assignmentId);
    setRates([]);
    if (!can("workforce.rate.view", projectId)) return;
    setBusy(true);
    setError("");
    try {
      setRates(
        await api<Rate[]>(
          `/projects/${projectId}/workforce/assignments/${assignmentId}/rates`,
        ),
      );
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const createRate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedAssignment) return;
    const form = new FormData(event.currentTarget);
    const element = event.currentTarget;
    await run(async () => {
      await api(`/projects/${projectId}/workforce/assignments/${selectedAssignment.id}/rates`, {
        method: "POST",
        body: JSON.stringify({
          wage_basis: form.get("wage_basis"),
          regular_rate: form.get("regular_rate"),
          overtime_rate: optionalText(form, "overtime_rate"),
          double_time_rate: optionalText(form, "double_time_rate"),
          billing_rate: optionalText(form, "billing_rate"),
          currency_code: form.get("currency_code") || "INR",
          effective_from: form.get("effective_from"),
          effective_to: optionalText(form, "effective_to"),
          source_reference: optionalText(form, "source_reference"),
        }),
      });
      element.reset();
      setRates(
        await api<Rate[]>(
          `/projects/${projectId}/workforce/assignments/${selectedAssignment.id}/rates`,
        ),
      );
      setMessage("Worker commercial rate added.");
    });
  };

  const endRate = async (rate: Rate) => {
    const effectiveTo = window.prompt("Rate effective-to date (YYYY-MM-DD)", localDateValue())?.trim();
    if (!effectiveTo || !selectedAssignment) return;
    await run(async () => {
      await api(
        `/projects/${projectId}/workforce/assignments/${selectedAssignment.id}/rates/${rate.id}/end`,
        {
          method: "POST",
          body: JSON.stringify({
            expected_revision: rate.revision,
            effective_to: effectiveTo,
            reason: "Ended from Workforce workspace",
          }),
        },
      );
      setRates(
        await api<Rate[]>(
          `/projects/${projectId}/workforce/assignments/${selectedAssignment.id}/rates`,
        ),
      );
      setMessage("Worker commercial rate ended.");
    });
  };

  const createTimecard = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!context) return;
    const form = new FormData(event.currentTarget);
    await run(async () => {
      const created = await api<Timecard>(`/projects/${projectId}/timecards`, {
        method: "POST",
        body: JSON.stringify({ worker_id: form.get("worker_id"), week_start: form.get("week_start") }),
      });
      await loadProject(projectId, context);
      await openTimecard(created.id);
      setMessage("Timecard created.");
    });
  };

  const openTimecard = async (timecardId: string) => {
    setBusy(true);
    setError("");
    try {
      const [detail, history] = await Promise.all([
        api<TimecardDetail>(`/projects/${projectId}/timecards/${timecardId}`),
        api<TimecardHistory[]>(`/projects/${projectId}/timecards/${timecardId}/history`),
      ]);
      setTimecard(detail);
      setTimeEntries(detail.entries.length ? detail.entries : blankWeek(detail.week_start));
      setTimecardHistory(history);
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const updateTimeEntry = (index: number, patch: Partial<TimeEntry>) => {
    setTimeEntries((rows) =>
      rows.map((row, rowIndex) => (rowIndex === index ? { ...row, ...patch } : row)),
    );
  };

  const saveTimecard = async () => {
    if (!timecard || !context) return;
    await run(async () => {
      const saved = await api<TimecardDetail>(
        `/projects/${projectId}/timecards/${timecard.id}/entries`,
        {
          method: "PUT",
          body: JSON.stringify({
            expected_revision: timecard.revision,
            reason: "Updated from Workforce workspace",
            entries: timeEntries.map((entry) => ({
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
        },
      );
      setTimecard(saved);
      setTimeEntries(saved.entries);
      await loadProject(projectId, context);
      setTimecardHistory(
        await api<TimecardHistory[]>(`/projects/${projectId}/timecards/${timecard.id}/history`),
      );
      setMessage("Timecard entries saved.");
    });
  };

  const timecardAction = async (action: "submit" | "approve" | "reject") => {
    if (!timecard || !context) return;
    let reason: string | null = null;
    if (action === "reject") {
      reason = window.prompt("Reason for rejection")?.trim() || null;
      if (!reason) return;
    }
    await run(async () => {
      await api(`/projects/${projectId}/timecards/${timecard.id}/${action}`, {
        method: "POST",
        body: JSON.stringify({
          expected_revision: timecard.revision,
          reason: reason || `${action} from Workforce workspace`,
        }),
      });
      await loadProject(projectId, context);
      await openTimecard(timecard.id);
      setMessage(
        action === "submit"
          ? "Timecard submitted."
          : action === "approve"
            ? "Timecard approved."
            : "Timecard returned for correction.",
      );
    });
  };

  if (loading) {
    return (
      <main className="boot-screen">
        <div className="boot-mark">COS</div><p>Loading workforce…</p>
      </main>
    );
  }

  return (
    <main className="workspace">
      <section className="page-frame">
        <div className="page-heading">
          <div>
            <p className="eyebrow">MODULE 5</p>
            <h1>Workforce / Contract Labour / Attendance</h1>
            <p>
              Keep Worker identity once, staff projects, govern commercial rates and timecards, and use one authoritative daily attendance editor.
            </p>
          </div>
        </div>

        {error && (
          <div className="error-banner">
            <strong>Action not completed</strong><span>{error}</span>
            <button onClick={() => setError("")} type="button">×</button>
          </div>
        )}
        {message && (
          <div className="success-banner"><strong>Saved</strong><span>{message}</span></div>
        )}

        {accessibleProjects.length === 0 &&
        !context?.permissions.includes("workforce.worker.view") &&
        !context?.permissions.includes("workforce.crew.view") ? (
          <div className="empty-state">
            <strong>No accessible workforce area</strong>
            <p>You need company Worker/Crew access or Workforce permission on a project.</p>
          </div>
        ) : (
          <>
            {accessibleProjects.length > 0 && (
              <section className="workflow-card">
                <div>
                  <p className="eyebrow">PROJECT</p>
                  <h2>{projects.find((row) => row.id === projectId)?.name || "Choose project"}</h2>
                </div>
                <div className="quick-form">
                  <select value={projectId} onChange={(event) => void switchProject(event.target.value)}>
                    {accessibleProjects.map((row) => (
                      <option key={row.id} value={row.id}>{row.number} · {row.name}</option>
                    ))}
                  </select>
                  {can("workforce.attendance.view", projectId) && (
                    <button className={tab === "attendance" ? "" : "secondary"} onClick={() => setTab("attendance")} type="button">Attendance</button>
                  )}
                  {can("workforce.assignment.view", projectId) && (
                    <button className={tab === "staffing" ? "" : "secondary"} onClick={() => setTab("staffing")} type="button">Staffing & rates</button>
                  )}
                  {can("workforce.timecard.view", projectId) && (
                    <button className={tab === "timecards" ? "" : "secondary"} onClick={() => setTab("timecards")} type="button">Timecards</button>
                  )}
                  {(context?.permissions.includes("workforce.worker.view") || context?.permissions.includes("workforce.crew.view")) && (
                    <button className={tab === "workers" ? "" : "secondary"} onClick={() => setTab("workers")} type="button">Workers & crews</button>
                  )}
                </div>
              </section>
            )}

            {tab === "attendance" && can("workforce.attendance.view", projectId) && (
              <div className="split-layout">
                <section>
                  <section className="workflow-card">
                    <div>
                      <p className="eyebrow">DAILY MUSTER</p>
                      <h2>Authoritative attendance workspace</h2>
                      <small>
                        Use the dedicated field editor for roster population, bulk marking, hours, WBS allocation, location, workflow, history and DPR reuse.
                      </small>
                    </div>
                    <Link href="/field/attendance">Open attendance workspace →</Link>
                  </section>
                </section>
                <section>
                  <div className="detail-title">
                    <div><p className="eyebrow">RECENT REGISTERS</p><h3>{registers.length} attendance records</h3></div>
                  </div>
                  {registers.length === 0 ? (
                    <div className="empty-state"><strong>No attendance yet</strong><p>Start the first register in the Attendance workspace.</p></div>
                  ) : (
                    <div className="record-list">
                      {registers.map((row) => (
                        <Link
                          className="list-card"
                          href={`/projects/${projectId}/workforce/attendance/${row.id}`}
                          key={row.id}
                        >
                          <div><strong>{row.attendance_date} · {row.shift_code}</strong><small>Revision {row.revision}</small></div>
                          <Status value={row.status} />
                        </Link>
                      ))}
                    </div>
                  )}
                </section>
              </div>
            )}

            {tab === "staffing" && can("workforce.assignment.view", projectId) && (
              <div className="split-layout">
                <section>
                  {can("workforce.assignment.manage", projectId) && context?.permissions.includes("workforce.worker.view") && (
                    <section className="workflow-card">
                      <div><p className="eyebrow">PROJECT STAFFING</p><h2>Assign Worker</h2></div>
                      <form className="quick-form" onSubmit={assignWorker}>
                        <select name="worker_id" required defaultValue="">
                          <option value="" disabled>Select Worker</option>
                          {workers.filter((row) => row.status === "active").map((row) => (
                            <option key={row.id} value={row.id}>{workerLabel(row)}</option>
                          ))}
                        </select>
                        <select name="crew_id" defaultValue="">
                          <option value="">No crew</option>
                          {crews.filter((row) => row.status === "active").map((row) => (
                            <option key={row.id} value={row.id}>{row.name}</option>
                          ))}
                        </select>
                        {parties.length > 0 && (
                          <select name="employer_party_id" defaultValue="">
                            <option value="">No employer Party</option>
                            {parties.map((row) => <option key={row.id} value={row.id}>{row.code} · {row.name}</option>)}
                          </select>
                        )}
                        <select name="engagement_type" defaultValue="contract_labour">
                          {ENGAGEMENT_TYPES.map((value) => <option key={value} value={value}>{value.replaceAll("_", " ")}</option>)}
                        </select>
                        <input name="project_role" placeholder="Project role" />
                        <input name="trade" placeholder="Trade" />
                        <input name="default_cost_code" placeholder="Legacy default cost code" />
                        <input name="start_date" type="date" />
                        <input name="end_date" type="date" />
                        <button disabled={busy}>Assign</button>
                      </form>
                    </section>
                  )}
                  <div className="detail-title"><div><p className="eyebrow">ASSIGNMENTS</p><h3>{assignments.length} project workers</h3></div></div>
                  <div className="record-list">
                    {assignments.map((row) => (
                      <button
                        key={row.id}
                        className={selectedAssignmentId === row.id ? "list-card selected" : "list-card"}
                        onClick={() => void openAssignment(row.id)}
                        type="button"
                      >
                        <div>
                          <strong>{workerLabel(workerById.get(row.worker_id), row.worker_id)}</strong>
                          <small>
                            {row.trade || row.project_role || "No trade/role"} · {(row.engagement_type || "unspecified").replaceAll("_", " ")}
                          </small>
                        </div>
                        <Status value={row.status} />
                      </button>
                    ))}
                  </div>
                </section>

                <section className="detail-panel">
                  {!selectedAssignment ? (
                    <div className="empty-state"><strong>Select a project Worker</strong><p>Open an assignment to manage project context and sensitive commercial rates.</p></div>
                  ) : (
                    <>
                      <div className="detail-title">
                        <div>
                          <p className="eyebrow">PROJECT ASSIGNMENT</p>
                          <h3>{workerLabel(workerById.get(selectedAssignment.worker_id), selectedAssignment.worker_id)}</h3>
                          <small>Revision {selectedAssignment.revision}</small>
                        </div>
                        <Status value={selectedAssignment.status} />
                      </div>

                      <section className="workflow-card">
                        <div><p className="eyebrow">PROJECT CONTEXT</p><h2>Staffing assignment</h2></div>
                        <form className="quick-form" onSubmit={updateAssignment}>
                          <select name="crew_id" defaultValue={selectedAssignment.crew_id || ""} disabled={!can("workforce.assignment.manage", projectId) || busy}>
                            <option value="">No crew</option>
                            {crews.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
                          </select>
                          {parties.length > 0 && (
                            <select name="employer_party_id" defaultValue={selectedAssignment.employer_party_id || ""} disabled={!can("workforce.assignment.manage", projectId) || busy}>
                              <option value="">No employer Party</option>
                              {parties.map((row) => <option key={row.id} value={row.id}>{row.code} · {row.name}</option>)}
                            </select>
                          )}
                          <select name="engagement_type" defaultValue={selectedAssignment.engagement_type || "other"} disabled={!can("workforce.assignment.manage", projectId) || busy}>
                            {ENGAGEMENT_TYPES.map((value) => <option key={value} value={value}>{value.replaceAll("_", " ")}</option>)}
                          </select>
                          <input name="project_role" defaultValue={selectedAssignment.project_role || ""} placeholder="Project role" disabled={!can("workforce.assignment.manage", projectId) || busy} />
                          <input name="trade" defaultValue={selectedAssignment.trade || ""} placeholder="Trade" disabled={!can("workforce.assignment.manage", projectId) || busy} />
                          <input name="default_cost_code" defaultValue={selectedAssignment.default_cost_code || ""} placeholder="Legacy default cost code" disabled={!can("workforce.assignment.manage", projectId) || busy} />
                          <input name="start_date" type="date" defaultValue={selectedAssignment.start_date || ""} disabled={!can("workforce.assignment.manage", projectId) || busy} />
                          <input name="end_date" type="date" defaultValue={selectedAssignment.end_date || ""} disabled={!can("workforce.assignment.manage", projectId) || busy} />
                          <select name="status" defaultValue={selectedAssignment.status} disabled={!can("workforce.assignment.manage", projectId) || busy}>
                            <option value="active">Active</option><option value="suspended">Suspended</option><option value="ended">Ended</option>
                          </select>
                          {can("workforce.assignment.manage", projectId) && <button disabled={busy}>Save assignment</button>}
                        </form>
                      </section>

                      {can("workforce.rate.view", projectId) && (
                        <section className="workflow-card">
                          <div>
                            <p className="eyebrow">SENSITIVE COMMERCIAL DATA</p>
                            <h2>Effective-dated Worker rates</h2>
                            <small>Rate access is permission-gated and intentionally separate from attendance.</small>
                          </div>
                          {can("workforce.rate.manage", projectId) && (
                            <form className="quick-form" onSubmit={createRate}>
                              <select name="wage_basis" defaultValue="daily">
                                {WAGE_BASES.map((value) => <option key={value} value={value}>{value.replaceAll("_", " ")}</option>)}
                              </select>
                              <input name="regular_rate" type="number" min="0" step="0.01" placeholder="Regular rate" required />
                              <input name="overtime_rate" type="number" min="0" step="0.01" placeholder="OT rate" />
                              <input name="double_time_rate" type="number" min="0" step="0.01" placeholder="Double-time rate" />
                              <input name="billing_rate" type="number" min="0" step="0.01" placeholder="Billing rate" />
                              <input name="currency_code" defaultValue="INR" maxLength={3} placeholder="Currency" />
                              <input name="effective_from" type="date" defaultValue={localDateValue()} required />
                              <input name="effective_to" type="date" />
                              <input name="source_reference" placeholder="Source reference" />
                              <button disabled={busy}>Add rate</button>
                            </form>
                          )}
                          {rates.length === 0 ? (
                            <div className="empty-state"><strong>No rates recorded</strong><p>No rate row is visible for this assignment.</p></div>
                          ) : (
                            <div className="record-list">
                              {rates.map((rate) => (
                                <div className="list-card" key={rate.id}>
                                  <div>
                                    <strong>{rate.wage_basis.replaceAll("_", " ")} · {money(rate.regular_rate, rate.currency_code)}</strong>
                                    <small>
                                      {rate.effective_from} → {rate.effective_to || "open"} · OT {money(rate.overtime_rate, rate.currency_code)} · billing {money(rate.billing_rate, rate.currency_code)}
                                    </small>
                                  </div>
                                  {can("workforce.rate.manage", projectId) && !rate.effective_to && (
                                    <button className="secondary" disabled={busy} onClick={() => void endRate(rate)} type="button">End rate</button>
                                  )}
                                </div>
                              ))}
                            </div>
                          )}
                        </section>
                      )}
                    </>
                  )}
                </section>
              </div>
            )}

            {tab === "timecards" && can("workforce.timecard.view", projectId) && (
              <div className="split-layout">
                <section>
                  {can("workforce.timecard.create", projectId) && (
                    <section className="workflow-card">
                      <div><p className="eyebrow">WEEKLY TIME</p><h2>Create timecard</h2></div>
                      <form className="quick-form" onSubmit={createTimecard}>
                        <select name="worker_id" required defaultValue="">
                          <option value="" disabled>Select assigned Worker</option>
                          {assignedWorkers.map((row) => <option key={row.id} value={row.id}>{workerLabel(row)}</option>)}
                        </select>
                        <input name="week_start" type="date" defaultValue={startOfWeekValue()} required />
                        <button disabled={busy || assignedWorkers.length === 0}>Create timecard</button>
                      </form>
                    </section>
                  )}
                  <div className="detail-title"><div><p className="eyebrow">TIMECARDS</p><h3>{timecards.length} records</h3></div></div>
                  {timecards.length === 0 ? (
                    <div className="empty-state"><strong>No timecards</strong><p>Create the first governed weekly timecard for an assigned Worker.</p></div>
                  ) : (
                    <div className="record-list">
                      {timecards.map((row) => (
                        <button
                          className={timecard?.id === row.id ? "list-card selected" : "list-card"}
                          key={row.id}
                          onClick={() => void openTimecard(row.id)}
                          type="button"
                        >
                          <div><strong>{workerLabel(workerById.get(row.worker_id), row.worker_id)}</strong><small>Week {row.week_start} · revision {row.revision}</small></div>
                          <Status value={row.status} />
                        </button>
                      ))}
                    </div>
                  )}
                </section>

                <section className="detail-panel">
                  {!timecard ? (
                    <div className="empty-state"><strong>Select a timecard</strong><p>Open a week to record hours, cost code, location and work description.</p></div>
                  ) : (
                    <>
                      <div className="detail-title">
                        <div>
                          <p className="eyebrow">WEEK OF {timecard.week_start}</p>
                          <h3>{workerLabel(workerById.get(timecard.worker_id), timecard.worker_id)}</h3>
                          <small>Revision {timecard.revision}</small>
                        </div>
                        <Status value={timecard.status} />
                      </div>

                      <div className="record-list">
                        {timeEntries.map((entry, index) => {
                          const editable = ["draft", "rejected"].includes(timecard.status) && can("workforce.timecard.update", projectId);
                          return (
                            <div className="list-card" key={`${entry.work_date}-${index}`}>
                              <div><strong>{new Date(`${entry.work_date}T00:00:00`).toLocaleDateString("en-IN", { weekday: "short", day: "2-digit", month: "short" })}</strong><small>{entry.work_description || "No work description"}</small></div>
                              <div className="quick-form">
                                <input aria-label="Regular hours" disabled={!editable} type="number" min="0" max="24" step="0.25" value={entry.regular_hours} onChange={(event) => updateTimeEntry(index, { regular_hours: event.target.value })} />
                                <input aria-label="Overtime hours" disabled={!editable} type="number" min="0" max="24" step="0.25" value={entry.overtime_hours} onChange={(event) => updateTimeEntry(index, { overtime_hours: event.target.value })} />
                                <input aria-label="Double-time hours" disabled={!editable} type="number" min="0" max="24" step="0.25" value={entry.double_time_hours} onChange={(event) => updateTimeEntry(index, { double_time_hours: event.target.value })} />
                                <input disabled={!editable} value={entry.cost_code || ""} onChange={(event) => updateTimeEntry(index, { cost_code: event.target.value || null })} placeholder="Cost code" />
                                <input disabled={!editable} value={entry.location || ""} onChange={(event) => updateTimeEntry(index, { location: event.target.value || null })} placeholder="Location" />
                                <input disabled={!editable} value={entry.work_description || ""} onChange={(event) => updateTimeEntry(index, { work_description: event.target.value || null })} placeholder="Work description" />
                              </div>
                            </div>
                          );
                        })}
                      </div>

                      <div className="quick-form">
                        {["draft", "rejected"].includes(timecard.status) && can("workforce.timecard.update", projectId) && (
                          <button className="secondary" disabled={busy} onClick={() => void saveTimecard()} type="button">Save entries</button>
                        )}
                        {["draft", "rejected"].includes(timecard.status) && can("workforce.timecard.submit", projectId) && (
                          <button disabled={busy} onClick={() => void timecardAction("submit")} type="button">Submit timecard</button>
                        )}
                        {timecard.status === "in_review" && can("workforce.timecard.approve", projectId) && (
                          <><button className="secondary" disabled={busy} onClick={() => void timecardAction("reject")} type="button">Reject</button><button disabled={busy} onClick={() => void timecardAction("approve")} type="button">Approve</button></>
                        )}
                      </div>

                      {timecardHistory.length > 0 && (
                        <section className="workflow-card">
                          <div><p className="eyebrow">HISTORY</p><h2>Timecard lifecycle</h2></div>
                          <div className="record-list">
                            {[...timecardHistory].reverse().map((event) => (
                              <div className="list-card" key={event.id}>
                                <div><strong>{event.event_type.replaceAll("_", " ")}</strong><small>Revision {event.timecard_revision} · {new Date(event.created_at).toLocaleString("en-IN")}</small></div>
                              </div>
                            ))}
                          </div>
                        </section>
                      )}
                    </>
                  )}
                </section>
              </div>
            )}

            {tab === "workers" && (
              <div className="split-layout">
                <section>
                  {context?.permissions.includes("workforce.worker.manage") && (
                    <section className="workflow-card">
                      <div><p className="eyebrow">WORKER MASTER</p><h2>Add Worker</h2></div>
                      <form className="quick-form" onSubmit={createWorker}>
                        <input name="worker_number" placeholder="Worker no." required />
                        <input name="first_name" placeholder="First name" required />
                        <input name="last_name" placeholder="Last name" required />
                        <input name="preferred_name" placeholder="Preferred name" />
                        <input name="email" type="email" placeholder="Email" />
                        <input name="phone" placeholder="Phone" />
                        <input name="job_title" placeholder="Job title" />
                        <input name="trade" placeholder="Trade" />
                        <input name="classification" placeholder="Classification" />
                        <input name="hire_date" type="date" />
                        <button disabled={busy}>Add Worker</button>
                      </form>
                    </section>
                  )}
                  <div className="detail-title"><div><p className="eyebrow">WORKERS</p><h3>{workers.length} company workers</h3></div></div>
                  <div className="record-list">
                    {workers.map((row) => (
                      <button className={selectedWorkerId === row.id ? "list-card selected" : "list-card"} key={row.id} onClick={() => setSelectedWorkerId(row.id)} type="button">
                        <div><strong>{workerLabel(row)}</strong><small>{row.trade || row.job_title || "No trade/title"}</small></div><Status value={row.status} />
                      </button>
                    ))}
                  </div>
                  {selectedWorker && (
                    <section className="workflow-card">
                      <div><p className="eyebrow">WORKER DETAIL</p><h2>{workerLabel(selectedWorker)}</h2><small>Revision {selectedWorker.revision}</small></div>
                      <form className="quick-form" onSubmit={updateWorker}>
                        <input name="first_name" defaultValue={selectedWorker.first_name} disabled={!context?.permissions.includes("workforce.worker.manage") || busy} required />
                        <input name="last_name" defaultValue={selectedWorker.last_name} disabled={!context?.permissions.includes("workforce.worker.manage") || busy} required />
                        <input name="preferred_name" defaultValue={selectedWorker.preferred_name || ""} disabled={!context?.permissions.includes("workforce.worker.manage") || busy} placeholder="Preferred name" />
                        <input name="email" type="email" defaultValue={selectedWorker.email || ""} disabled={!context?.permissions.includes("workforce.worker.manage") || busy} placeholder="Email" />
                        <input name="phone" defaultValue={selectedWorker.phone || ""} disabled={!context?.permissions.includes("workforce.worker.manage") || busy} placeholder="Phone" />
                        <input name="job_title" defaultValue={selectedWorker.job_title || ""} disabled={!context?.permissions.includes("workforce.worker.manage") || busy} placeholder="Job title" />
                        <input name="trade" defaultValue={selectedWorker.trade || ""} disabled={!context?.permissions.includes("workforce.worker.manage") || busy} placeholder="Trade" />
                        <input name="classification" defaultValue={selectedWorker.classification || ""} disabled={!context?.permissions.includes("workforce.worker.manage") || busy} placeholder="Classification" />
                        <input name="hire_date" type="date" defaultValue={selectedWorker.hire_date || ""} disabled={!context?.permissions.includes("workforce.worker.manage") || busy} />
                        <input name="termination_date" type="date" defaultValue={selectedWorker.termination_date || ""} disabled={!context?.permissions.includes("workforce.worker.manage") || busy} />
                        <select name="status" defaultValue={selectedWorker.status} disabled={!context?.permissions.includes("workforce.worker.manage") || busy}>
                          <option value="active">Active</option><option value="inactive">Inactive</option><option value="terminated">Terminated</option>
                        </select>
                        {context?.permissions.includes("workforce.worker.manage") && <button disabled={busy}>Save Worker</button>}
                      </form>
                    </section>
                  )}
                </section>

                <section>
                  {context?.permissions.includes("workforce.crew.manage") && (
                    <section className="workflow-card">
                      <div><p className="eyebrow">CREWS</p><h2>Create crew</h2></div>
                      <form className="quick-form" onSubmit={createCrew}>
                        <input name="name" placeholder="Crew name" required />
                        <input name="description" placeholder="Description" />
                        <select name="supervisor_worker_id" defaultValue="">
                          <option value="">No supervisor</option>
                          {workers.filter((row) => row.status === "active").map((row) => <option key={row.id} value={row.id}>{workerLabel(row)}</option>)}
                        </select>
                        <button disabled={busy}>Create crew</button>
                      </form>
                    </section>
                  )}
                  <div className="detail-title"><div><p className="eyebrow">CREWS</p><h3>{crews.length} company crews</h3></div></div>
                  <div className="record-list">
                    {crews.map((row) => (
                      <button className={selectedCrewId === row.id ? "list-card selected" : "list-card"} key={row.id} onClick={() => setSelectedCrewId(row.id)} type="button">
                        <div><strong>{row.name}</strong><small>{row.description || `Revision ${row.revision}`}</small></div><Status value={row.status} />
                      </button>
                    ))}
                  </div>
                  {selectedCrew && (
                    <section className="workflow-card">
                      <div><p className="eyebrow">CREW DETAIL</p><h2>{selectedCrew.name}</h2><small>Revision {selectedCrew.revision}</small></div>
                      <form className="quick-form" onSubmit={updateCrew}>
                        <input name="name" defaultValue={selectedCrew.name} disabled={!context?.permissions.includes("workforce.crew.manage") || busy} required />
                        <input name="description" defaultValue={selectedCrew.description || ""} disabled={!context?.permissions.includes("workforce.crew.manage") || busy} placeholder="Description" />
                        <select name="supervisor_worker_id" defaultValue={selectedCrew.supervisor_worker_id || ""} disabled={!context?.permissions.includes("workforce.crew.manage") || busy}>
                          <option value="">No supervisor</option>
                          {workers.map((row) => <option key={row.id} value={row.id}>{workerLabel(row)}</option>)}
                        </select>
                        <select name="status" defaultValue={selectedCrew.status} disabled={!context?.permissions.includes("workforce.crew.manage") || busy}>
                          <option value="active">Active</option><option value="inactive">Inactive</option>
                        </select>
                        {context?.permissions.includes("workforce.crew.manage") && <button disabled={busy}>Save crew</button>}
                      </form>
                      {context?.permissions.includes("workforce.crew.manage") && (
                        <form className="quick-form" onSubmit={addCrewMember}>
                          <select name="worker_id" required defaultValue="">
                            <option value="" disabled>Add Worker to crew</option>
                            {workers.filter((row) => row.status === "active").map((row) => <option key={row.id} value={row.id}>{workerLabel(row)}</option>)}
                          </select>
                          <input name="role" placeholder="Crew role" />
                          <input name="effective_from" type="date" defaultValue={localDateValue()} required />
                          <input name="effective_to" type="date" />
                          <button disabled={busy}>Add membership</button>
                        </form>
                      )}
                    </section>
                  )}
                </section>
              </div>
            )}
          </>
        )}
      </section>
    </main>
  );
}
