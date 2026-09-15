"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

type AccessContext = { permissions: string[] };
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

export default function WorkerDetailWorkspace({ workerId }: { workerId: string }) {
  const [context, setContext] = useState<AccessContext | null>(null);
  const [worker, setWorker] = useState<Worker | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function load() {
    setError("");
    try {
      const [ctx, workers] = await Promise.all([
        api<AccessContext>("/session/context"),
        api<Worker[]>("/workforce/workers"),
      ]);
      const selected = workers.find((row) => row.id === workerId) || null;
      if (!selected) throw new Error("Worker not found");
      setContext(ctx);
      setWorker(selected);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, [workerId]);

  const editable = Boolean(context?.permissions.includes("workforce.worker.manage"));

  async function save() {
    if (!worker || !editable) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const updated = await api<Worker>(`/workforce/workers/${worker.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          expected_revision: worker.revision,
          worker_number: worker.worker_number,
          first_name: worker.first_name,
          last_name: worker.last_name,
          preferred_name: worker.preferred_name || null,
          email: worker.email || null,
          phone: worker.phone || null,
          job_title: worker.job_title || null,
          trade: worker.trade || null,
          classification: worker.classification || null,
          hire_date: worker.hire_date || null,
          termination_date: worker.termination_date || null,
          status: worker.status,
          reason: "Updated from Worker detail page",
        }),
      });
      setWorker(updated);
      setMessage("Worker saved.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
      await load().catch(() => undefined);
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <main className="workspace-shell"><p>Loading Worker…</p></main>;
  if (!worker) return <main className="workspace-shell"><div className="error-banner"><span>{error || "Worker not found"}</span></div><Link href="/workforce">Back to Workforce</Link></main>;

  const update = (patch: Partial<Worker>) => setWorker((current) => current ? { ...current, ...patch } : current);

  return <main className="workspace-shell">
    <header className="workspace-header">
      <div><p className="eyebrow">Workforce · Worker record</p><h1>{worker.first_name} {worker.last_name}</h1><p>{worker.worker_number} · revision {worker.revision}</p></div>
      <Link className="secondary-button" href="/workforce">Back to Workforce</Link>
    </header>
    {error && <div className="error-banner"><span>{error}</span></div>}
    {message && <section className="workspace-card"><p>{message}</p></section>}
    <section className="workspace-card">
      <div className="section-heading"><h2>Worker identity</h2><span className={`status-pill status-${worker.status}`}>{worker.status}</span></div>
      <div className="form-grid">
        <label>Worker number<input disabled={!editable || busy} value={worker.worker_number} onChange={(event) => update({ worker_number: event.target.value })} /></label>
        <label>First name<input disabled={!editable || busy} value={worker.first_name} onChange={(event) => update({ first_name: event.target.value })} /></label>
        <label>Last name<input disabled={!editable || busy} value={worker.last_name} onChange={(event) => update({ last_name: event.target.value })} /></label>
        <label>Preferred name<input disabled={!editable || busy} value={worker.preferred_name || ""} onChange={(event) => update({ preferred_name: event.target.value || null })} /></label>
        <label>Email<input type="email" disabled={!editable || busy} value={worker.email || ""} onChange={(event) => update({ email: event.target.value || null })} /></label>
        <label>Phone<input type="tel" disabled={!editable || busy} value={worker.phone || ""} onChange={(event) => update({ phone: event.target.value || null })} /></label>
        <label>Job title<input disabled={!editable || busy} value={worker.job_title || ""} onChange={(event) => update({ job_title: event.target.value || null })} /></label>
        <label>Trade<input disabled={!editable || busy} value={worker.trade || ""} onChange={(event) => update({ trade: event.target.value || null })} /></label>
        <label>Classification<input disabled={!editable || busy} value={worker.classification || ""} onChange={(event) => update({ classification: event.target.value || null })} /></label>
        <label>Hire date<input type="date" disabled={!editable || busy} value={worker.hire_date || ""} onChange={(event) => update({ hire_date: event.target.value || null })} /></label>
        <label>Termination date<input type="date" disabled={!editable || busy} value={worker.termination_date || ""} onChange={(event) => update({ termination_date: event.target.value || null })} /></label>
        <label>Status<select disabled={!editable || busy} value={worker.status} onChange={(event) => update({ status: event.target.value })}><option value="active">Active</option><option value="inactive">Inactive</option><option value="terminated">Terminated</option></select></label>
      </div>
      {editable && <button disabled={busy || !worker.worker_number.trim() || !worker.first_name.trim() || !worker.last_name.trim()} onClick={() => void save()}>{busy ? "Saving…" : "Save Worker"}</button>}
    </section>
  </main>;
}
