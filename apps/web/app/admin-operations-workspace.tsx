"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useWebSession } from "./web-session-gate";

type HealthRow = {
  category: string;
  component_key: string;
  state: string;
  summary: string;
  metrics: Record<string, unknown>;
  observed_at: string;
  valid_until: string | null;
  stale: boolean;
};

type EventRow = {
  id: string;
  category: string;
  severity: string;
  status: string;
  title: string;
  summary: string;
  occurrence_count: number;
  first_seen_at: string;
  last_seen_at: string;
  resolved_at: string | null;
  resolution_summary: string | null;
};

type JobFailure = {
  id: string;
  job_type: string;
  status: string;
  attempt_count: number;
  max_attempts: number;
  error_code: string | null;
  created_at: string;
  finished_at: string | null;
};

type OperationsSummary = {
  generated_at: string;
  overall_state: string;
  summary: string;
  health: HealthRow[];
  events: EventRow[];
  jobs: {
    counts: Record<string, number>;
    oldest_pending_at: string | null;
    recent_failures: JobFailure[];
  } | null;
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

function time(value: string | null) {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" });
}

function label(value: string) {
  return value.replaceAll("_", " ").replaceAll("-", " ");
}

function Status({ value }: { value: string }) {
  const normalized = value === "healthy" ? "active" : value === "critical" || value === "degraded" ? "rejected" : value;
  return <span className={`status-pill status-${normalized}`}>{label(value)}</span>;
}

export default function AdminOperationsWorkspace() {
  const { hasPermission } = useWebSession();
  const allowed = hasPermission("admin.operations.view");
  const [summary, setSummary] = useState<OperationsSummary | null>(null);
  const [loading, setLoading] = useState(allowed);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!allowed) return;
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE}/admin/operations/summary`, {
        credentials: "include",
        cache: "no-store",
      });
      if (!response.ok) {
        let message = `${response.status} ${response.statusText}`;
        try {
          const body = await response.json() as { detail?: unknown };
          if (body.detail) message = String(body.detail);
        } catch {}
        throw new Error(message);
      }
      setSummary(await response.json() as OperationsSummary);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setLoading(false);
    }
  }, [allowed]);

  useEffect(() => { void load(); }, [load]);

  const openEvents = useMemo(() => summary?.events.filter((item) => item.status === "open") ?? [], [summary]);
  const jobCounts = summary?.jobs?.counts ?? {};
  const pendingJobs = (jobCounts.queued ?? 0) + (jobCounts.running ?? 0) + (jobCounts.retrying ?? 0);

  if (!allowed) {
    return <main className="page-frame"><section className="empty-state"><strong>Operations Center is not available to this membership.</strong><p>Company operational diagnostics require the admin.operations.view capability.</p><Link href="/">Return to workspace</Link></section></main>;
  }

  return <main className="page-frame">
    <div className="page-heading">
      <div>
        <p className="eyebrow">ADMIN · OPERATIONS</p>
        <h1>Operations Center</h1>
        <p>Tenant-scoped health, operational events and background processing. Infrastructure secrets and cross-company data are never exposed here.</p>
      </div>
      <div className="record-actions"><Link className="secondary-button" href="/">Workspace</Link><button onClick={() => void load()} disabled={loading}>{loading ? "Refreshing…" : "Refresh"}</button></div>
    </div>

    {error && <div className="error-banner"><strong>Unable to load operations</strong><span>{error}</span><button onClick={() => setError("")}>×</button></div>}

    {loading && !summary ? <section className="empty-state"><strong>Loading operational state…</strong><p>Reading the latest company-scoped health projections.</p></section> : summary && <>
      <div className="metric-grid">
        <article><span>Overall status</span><strong><Status value={summary.overall_state} /></strong><small>{summary.summary}</small></article>
        <article><span>Monitored components</span><strong>{summary.health.length}</strong><small>{summary.health.filter((item) => item.stale).length} stale snapshot(s)</small></article>
        <article><span>Open events</span><strong>{openEvents.length}</strong><small>{summary.events.length} recent event(s) visible</small></article>
        <article><span>Background work</span><strong>{summary.jobs ? pendingJobs : "—"}</strong><small>{summary.jobs ? `${jobCounts.failed ?? 0} failed job(s)` : "Job diagnostics not permitted"}</small></article>
      </div>

      <section className="section-card">
        <div className="page-heading compact"><div><p className="eyebrow">SERVICE HEALTH</p><h1>Current component state</h1></div><small>Generated {time(summary.generated_at)}</small></div>
        {summary.health.length === 0 ? <div className="empty-state"><strong>No health snapshots yet</strong><p>The page stays truthful until the installation records operational telemetry.</p></div> : <div className="record-list">{summary.health.map((item) => <article className="record-card" key={`${item.category}:${item.component_key}`}>
          <div><span className="record-number">{label(item.category)}</span><strong>{label(item.component_key)}</strong><small>{item.summary} · observed {time(item.observed_at)}{item.stale ? " · stale" : ""}</small></div><Status value={item.stale ? "attention" : item.state} />
        </article>)}</div>}
      </section>

      <section className="section-card">
        <div className="page-heading compact"><div><p className="eyebrow">OPERATIONAL EVENTS</p><h1>Recent attention items</h1></div></div>
        {summary.events.length === 0 ? <div className="empty-state"><strong>No operational incidents recorded</strong><p>New installations do not show manufactured warnings or placeholder incidents.</p></div> : <div className="record-list">{summary.events.map((item) => <article className="record-card" key={item.id}>
          <div><span className="record-number">{label(item.category)} · {item.occurrence_count} occurrence(s)</span><strong>{item.title}</strong><small>{item.summary} · last seen {time(item.last_seen_at)}</small>{item.resolution_summary && <small>Resolution: {item.resolution_summary}</small>}</div><div className="record-actions"><Status value={item.severity} /><Status value={item.status} /></div>
        </article>)}</div>}
      </section>

      {summary.jobs && <section className="section-card">
        <div className="page-heading compact"><div><p className="eyebrow">BACKGROUND PROCESSING</p><h1>Jobs & report generation</h1></div>{summary.jobs.oldest_pending_at && <small>Oldest pending: {time(summary.jobs.oldest_pending_at)}</small>}</div>
        <div className="metric-grid">
          {(["queued", "running", "retrying", "failed"] as const).map((state) => <article key={state}><span>{label(state)}</span><strong>{jobCounts[state] ?? 0}</strong><small>Tenant-scoped background jobs</small></article>)}
        </div>
        <div style={{ marginTop: 18 }}>
          {summary.jobs.recent_failures.length === 0 ? <div className="empty-state"><strong>No recent failed jobs</strong><p>Report generation, imports, file processing and other background work have no recorded failures in this view.</p></div> : <div className="record-list">{summary.jobs.recent_failures.map((item) => <article className="record-card" key={item.id}><div><span className="record-number">{label(item.job_type)}</span><strong>{item.error_code || "Background job failed"}</strong><small>Attempts {item.attempt_count}/{item.max_attempts} · {time(item.finished_at || item.created_at)}</small></div><Status value={item.status} /></article>)}</div>}
        </div>
      </section>}
    </>}
  </main>;
}
