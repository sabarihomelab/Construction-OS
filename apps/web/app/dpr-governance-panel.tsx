"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

type GenerationStatus = {
  report_id: string;
  source_revision: number;
  report_status: string;
  generation_state: string;
  output_format: string;
  job_id: string | null;
  job_status: string | null;
  failure_code: string | null;
  render_id: string | null;
  filename: string | null;
  issued_at: string | null;
  download_path: string | null;
};

type LifecycleEvent = {
  id: string;
  event_type: string;
  report_revision: number;
  actor_user_id: string | null;
  details: Record<string, unknown>;
  created_at: string;
};

type RenderRecord = {
  id: string;
  source_revision: number;
  template_version_id: string;
  output_format: string;
  generation_trigger: string;
  content_sha256: string;
  output_filename: string;
  output_file_asset_id: string | null;
  output_file_version: number | null;
  issued_at: string | null;
  created_at: string;
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

async function api<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
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
  return response.json() as Promise<T>;
}

function apiUrl(path: string) {
  if (path.startsWith("/api/v1/")) return `${API_BASE}${path.slice("/api/v1".length)}`;
  if (path.startsWith("/")) return `${API_BASE}${path}`;
  return `${API_BASE}/${path}`;
}

function human(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function Status({ value }: { value: string }) {
  return <span className={`status-pill status-${value.replaceAll("_", "-")}`}>{human(value)}</span>;
}

function when(value: string | null) {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

export default function DPRGovernancePanel({
  projectId,
  reportId,
}: {
  projectId: string;
  reportId: string;
}) {
  const [generation, setGeneration] = useState<GenerationStatus | null>(null);
  const [history, setHistory] = useState<LifecycleEvent[]>([]);
  const [renders, setRenders] = useState<RenderRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!projectId || !reportId) return;
    try {
      const [generationRow, historyRows, renderRows] = await Promise.all([
        api<GenerationStatus>(`/projects/${projectId}/daily-reports/${reportId}/report-generation`),
        api<LifecycleEvent[]>(`/projects/${projectId}/daily-reports/${reportId}/history`),
        api<RenderRecord[]>(`/projects/${projectId}/daily-reports/${reportId}/render-history`),
      ]);
      setGeneration(generationRow);
      setHistory(historyRows);
      setRenders(renderRows);
      setError("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setLoading(false);
    }
  }, [projectId, reportId]);

  useEffect(() => {
    void load();
  }, [load]);

  const shouldPoll = useMemo(() => {
    if (!generation || generation.report_status !== "approved") return false;
    return !["issued", "failed"].includes(generation.generation_state);
  }, [generation]);

  useEffect(() => {
    if (!shouldPoll) return;
    const timer = window.setInterval(() => void load(), 2500);
    return () => window.clearInterval(timer);
  }, [load, shouldPoll]);

  async function download(path: string, filename: string) {
    setError("");
    try {
      const response = await fetch(apiUrl(path), { credentials: "include", cache: "no-store" });
      if (!response.ok) {
        let message = `${response.status} ${response.statusText}`;
        try {
          const body = await response.json() as { detail?: unknown };
          if (body.detail) message = String(body.detail);
        } catch {}
        throw new Error(message);
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 30_000);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    }
  }

  if (loading) {
    return <section className="workspace-card"><p>Loading DPR governance records…</p></section>;
  }

  return <div className="stack">
    {error && <div className="error-banner"><span>{error}</span></div>}

    <section className="workspace-card">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Official issuance</p>
          <h2>Approved DPR file</h2>
        </div>
        <button className="secondary-button" onClick={() => void load()}>Refresh</button>
      </div>
      {!generation ? <p className="muted">Generation status is unavailable.</p> : <>
        <div className="button-row">
          <Status value={generation.report_status} />
          <Status value={generation.generation_state} />
          <span className="status-pill">Revision {generation.source_revision}</span>
          <span className="status-pill">{generation.output_format.toUpperCase()}</span>
        </div>
        {shouldPoll && <p className="muted">The approved DPR is being issued in the background. This status refreshes automatically.</p>}
        {generation.generation_state === "failed" && <p className="muted">Generation failed{generation.failure_code ? ` (${generation.failure_code})` : ""}. Refresh after the operational issue is corrected.</p>}
        {generation.generation_state === "issued" && generation.download_path && generation.filename && <div className="button-row">
          <button onClick={() => void download(generation.download_path!, generation.filename!)}>Download official {generation.output_format.toUpperCase()}</button>
          <span className="muted">Issued {when(generation.issued_at)}</span>
        </div>}
      </>}
    </section>

    <section className="workspace-card">
      <div className="section-heading"><div><p className="eyebrow">Immutable evidence</p><h3>Issued render history</h3></div><span className="status-pill">{renders.length}</span></div>
      {renders.length === 0 ? <p className="muted">No stored issued renders yet.</p> : <div className="stack">{renders.map((row) => <div className="nested-card" key={row.id}>
        <div className="section-heading">
          <div><strong>{row.output_filename}</strong><p className="muted">Revision {row.source_revision} · {human(row.generation_trigger)} · template {row.template_version_id.slice(0, 8)}</p></div>
          <Status value={row.output_format} />
        </div>
        <div className="button-row">
          <span className="muted">{row.issued_at ? `Issued ${when(row.issued_at)}` : `Rendered ${when(row.created_at)}`}</span>
          {row.output_file_asset_id && row.output_file_version && <button className="secondary-button" onClick={() => void download(`/projects/${projectId}/daily-reports/${reportId}/render-history/${row.id}/download`, row.output_filename)}>Download exact file</button>}
        </div>
      </div>)}</div>}
    </section>

    <section className="workspace-card">
      <div className="section-heading"><div><p className="eyebrow">Audit trail</p><h3>DPR lifecycle history</h3></div><span className="status-pill">{history.length}</span></div>
      {history.length === 0 ? <p className="muted">No lifecycle events are recorded yet.</p> : <div className="stack">{[...history].reverse().map((event) => <div className="nested-card" key={event.id}>
        <div className="section-heading"><div><strong>{human(event.event_type)}</strong><p className="muted">Revision {event.report_revision} · {when(event.created_at)}</p></div></div>
        {Object.keys(event.details || {}).length > 0 && <p className="muted">{Object.entries(event.details).map(([key, value]) => `${human(key)}: ${typeof value === "object" ? JSON.stringify(value) : String(value)}`).join(" · ")}</p>}
      </div>)}</div>}
    </section>
  </div>;
}
