"use client";

import { ChangeEvent, useCallback, useEffect, useMemo, useState } from "react";

type AccessContext = { permissions: string[]; project_permissions: Record<string, string[]> };
type Report = { id: string; status: string; revision: number };
type FieldOption = { key: string; label: string };
type FieldDefinition = {
  definition_id: string;
  key: string;
  label: string;
  description: string | null;
  field_type: string;
  required: boolean;
  editable: boolean;
  display_order: number;
  default_value: unknown;
  options: FieldOption[];
};
type DefinitionResponse = { project_id: string; fields: FieldDefinition[] };
type FieldValue = { definition_id: string; value: unknown };
type ValuesResponse = { report_id: string; report_revision: number; values: FieldValue[] };
type Photo = {
  asset_id: string;
  version: number;
  filename: string;
  content_type: string | null;
  size_bytes: number;
  relation_type: string;
  client_photo_id: string | null;
  caption: string | null;
  captured_at: string | null;
  created_at: string;
  report_revision: number;
};
type UploadSession = {
  upload_id: string;
  client_photo_id: string;
  target: { url: string; method: string; headers: Record<string, string>; expires_at: string };
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
  if (init?.body && !(init.body instanceof Blob) && !(init.body instanceof ArrayBuffer)) headers.set("Content-Type", "application/json");
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
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

function can(context: AccessContext | null, permission: string, projectId: string) {
  if (!context) return false;
  return context.permissions.includes(permission) || (context.project_permissions[projectId] || []).includes(permission);
}

function sizeLabel(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function inputDateTime(value: unknown) {
  if (typeof value !== "string" || !value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "";
  const local = new Date(parsed.getTime() - parsed.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

async function sha256(file: File) {
  const digest = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
  return Array.from(new Uint8Array(digest)).map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

export default function DPRFieldExtensions({ projectId, reportId }: { projectId: string; reportId: string }) {
  const [context, setContext] = useState<AccessContext | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [definitions, setDefinitions] = useState<FieldDefinition[]>([]);
  const [values, setValues] = useState<Record<string, unknown>>({});
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [caption, setCaption] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const editable = report?.status === "draft" && can(context, "field.daily_report.update", projectId);
  const canUpload = editable && can(context, "files.file.upload", projectId);

  const load = useCallback(async () => {
    if (!projectId || !reportId) return;
    try {
      const [ctx, reportRow, definitionRows, valueRows, photoRows] = await Promise.all([
        api<AccessContext>("/session/context"),
        api<Report>(`/projects/${projectId}/daily-reports/${reportId}`),
        api<DefinitionResponse>(`/projects/${projectId}/daily-reports/custom-fields/definitions`),
        api<ValuesResponse>(`/projects/${projectId}/daily-reports/${reportId}/custom-fields`),
        api<Photo[]>(`/projects/${projectId}/daily-reports/${reportId}/photos`),
      ]);
      setContext(ctx);
      setReport(reportRow);
      setDefinitions(definitionRows.fields);
      setValues(Object.fromEntries(valueRows.values.map((item) => [item.definition_id, item.value])));
      setPhotos(photoRows);
      setError("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setLoading(false);
    }
  }, [projectId, reportId]);

  useEffect(() => { void load(); }, [load]);

  const visibleDefinitions = useMemo(
    () => [...definitions].sort((a, b) => a.display_order - b.display_order || a.label.localeCompare(b.label)),
    [definitions],
  );

  function setValue(id: string, value: unknown) {
    setValues((current) => ({ ...current, [id]: value }));
  }

  async function saveCustomFields() {
    if (!report || !editable) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const writable = visibleDefinitions.filter((definition) => definition.editable);
      await api<ValuesResponse>(`/projects/${projectId}/daily-reports/${reportId}/custom-fields`, {
        method: "PUT",
        body: JSON.stringify({
          expected_revision: report.revision,
          reason: "Updated from DPR web workspace",
          values: writable.map((definition) => ({ definition_id: definition.definition_id, value: values[definition.definition_id] ?? null })),
        }),
      });
      setMessage("Custom fields saved.");
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
      await load().catch(() => undefined);
    } finally {
      setBusy(false);
    }
  }

  async function uploadPhoto() {
    if (!report || !file || !canUpload) return;
    setBusy(true); setError(""); setMessage("");
    let uploadId = "";
    try {
      const clientPhotoId = crypto.randomUUID();
      const checksum = await sha256(file);
      const session = await api<UploadSession>(`/projects/${projectId}/daily-reports/${reportId}/photos/uploads`, {
        method: "POST",
        body: JSON.stringify({
          expected_revision: report.revision,
          client_photo_id: clientPhotoId,
          original_filename: file.name,
          content_type: file.type || "image/jpeg",
          size_bytes: file.size,
          sha256: checksum,
        }),
      });
      uploadId = session.upload_id;
      const targetUrl = session.target.url.startsWith("/api/v1/")
        ? `${API_BASE}${session.target.url.slice("/api/v1".length)}`
        : session.target.url;
      const headers = new Headers(session.target.headers || {});
      const isLocal = session.target.url.startsWith("/api/v1/") || session.target.url.startsWith("/");
      if (isLocal) {
        const token = csrfToken();
        if (token) headers.set("X-CSRF-Token", token);
      }
      if (!headers.has("Content-Type")) headers.set("Content-Type", file.type || "application/octet-stream");
      const uploadResponse = await fetch(targetUrl, {
        method: session.target.method || "PUT",
        headers,
        body: file,
        credentials: isLocal ? "include" : "omit",
      });
      if (!uploadResponse.ok) throw new Error(`Photo upload failed: ${uploadResponse.status} ${uploadResponse.statusText}`);
      await api<Photo>(`/projects/${projectId}/daily-reports/${reportId}/photos/uploads/${session.upload_id}/finalize`, {
        method: "POST",
        body: JSON.stringify({
          expected_revision: report.revision,
          client_photo_id: clientPhotoId,
          caption: caption.trim() || null,
          captured_at: new Date(file.lastModified || Date.now()).toISOString(),
        }),
      });
      setFile(null); setCaption(""); setMessage("Photo attached to DPR.");
      const input = document.getElementById("dpr-photo-file") as HTMLInputElement | null;
      if (input) input.value = "";
      await load();
    } catch (caught) {
      if (uploadId) {
        await api<void>(`/projects/${projectId}/daily-reports/${reportId}/photos/uploads/${uploadId}`, { method: "DELETE" }).catch(() => undefined);
      }
      setError(caught instanceof Error ? caught.message : String(caught));
      await load().catch(() => undefined);
    } finally {
      setBusy(false);
    }
  }

  async function removePhoto(photo: Photo) {
    if (!report || !editable) return;
    if (!window.confirm(`Remove ${photo.filename} from this DPR?`)) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await api(`/projects/${projectId}/daily-reports/${reportId}/photos/${photo.asset_id}?expected_revision=${report.revision}`, { method: "DELETE" });
      setMessage("Photo removed.");
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
      await load().catch(() => undefined);
    } finally {
      setBusy(false);
    }
  }

  function renderField(definition: FieldDefinition) {
    const value = values[definition.definition_id] ?? definition.default_value ?? null;
    const disabled = !editable || !definition.editable || busy;
    const common = { disabled, required: definition.required };

    if (definition.field_type === "boolean") {
      return <input type="checkbox" checked={Boolean(value)} onChange={(event) => setValue(definition.definition_id, event.target.checked)} {...common} />;
    }
    if (definition.field_type === "long_text") {
      return <textarea value={typeof value === "string" ? value : ""} onChange={(event) => setValue(definition.definition_id, event.target.value || null)} {...common} />;
    }
    if (definition.field_type === "single_select") {
      return <select value={typeof value === "string" ? value : ""} onChange={(event) => setValue(definition.definition_id, event.target.value || null)} {...common}><option value="">Select</option>{definition.options.map((option) => <option key={option.key} value={option.key}>{option.label}</option>)}</select>;
    }
    if (definition.field_type === "multi_select") {
      const selected = Array.isArray(value) ? value.map(String) : [];
      return <select multiple value={selected} onChange={(event: ChangeEvent<HTMLSelectElement>) => setValue(definition.definition_id, Array.from(event.target.selectedOptions).map((option) => option.value))} {...common}>{definition.options.map((option) => <option key={option.key} value={option.key}>{option.label}</option>)}</select>;
    }
    if (definition.field_type === "currency") {
      const current = value && typeof value === "object" ? value as { amount?: unknown; currency?: unknown } : {};
      return <div className="inline-form"><input type="number" step="0.01" value={current.amount == null ? "" : String(current.amount)} onChange={(event) => setValue(definition.definition_id, { amount: event.target.value, currency: String(current.currency || "INR") })} {...common} /><input maxLength={3} value={String(current.currency || "INR")} onChange={(event) => setValue(definition.definition_id, { amount: current.amount ?? "", currency: event.target.value.toUpperCase() })} disabled={disabled} /></div>;
    }
    if (definition.field_type === "measurement") {
      const current = value && typeof value === "object" ? value as { value?: unknown; unit?: unknown } : {};
      return <div className="inline-form"><input type="number" step="any" value={current.value == null ? "" : String(current.value)} onChange={(event) => setValue(definition.definition_id, { value: event.target.value, unit: String(current.unit || "") })} {...common} /><input placeholder="Unit" value={String(current.unit || "")} onChange={(event) => setValue(definition.definition_id, { value: current.value ?? "", unit: event.target.value })} disabled={disabled} /></div>;
    }
    if (["integer", "decimal"].includes(definition.field_type)) {
      return <input type="number" step={definition.field_type === "integer" ? "1" : "any"} value={value == null ? "" : String(value)} onChange={(event) => setValue(definition.definition_id, event.target.value || null)} {...common} />;
    }
    if (definition.field_type === "date") {
      return <input type="date" value={typeof value === "string" ? value : ""} onChange={(event) => setValue(definition.definition_id, event.target.value || null)} {...common} />;
    }
    if (definition.field_type === "datetime") {
      return <input type="datetime-local" value={inputDateTime(value)} onChange={(event) => setValue(definition.definition_id, event.target.value ? new Date(event.target.value).toISOString() : null)} {...common} />;
    }
    const inputType = definition.field_type === "email" ? "email" : definition.field_type === "url" ? "url" : definition.field_type === "phone" ? "tel" : "text";
    return <input type={inputType} value={value == null ? "" : String(value)} onChange={(event) => setValue(definition.definition_id, event.target.value || null)} {...common} />;
  }

  if (loading) return <section className="workspace-card"><p>Loading DPR field extensions…</p></section>;

  return <div className="stack">
    {error && <div className="error-banner"><span>{error}</span></div>}
    {message && <section className="workspace-card"><p>{message}</p></section>}

    <section className="workspace-card">
      <div className="section-heading"><div><p className="eyebrow">Configured data</p><h2>Custom fields</h2></div>{report && <span className="status-pill">Revision {report.revision}</span>}</div>
      {visibleDefinitions.length === 0 ? <p className="muted">No DPR custom fields are configured for this company.</p> : <>
        <div className="form-grid">{visibleDefinitions.map((definition) => <label className={["long_text", "multi_select"].includes(definition.field_type) ? "wide" : ""} key={definition.definition_id}>{definition.label}{definition.required ? " *" : ""}{renderField(definition)}{definition.description && <small className="muted">{definition.description}</small>}</label>)}</div>
        {editable && visibleDefinitions.some((definition) => definition.editable) && <button onClick={() => void saveCustomFields()} disabled={busy}>Save custom fields</button>}
      </>}
    </section>

    <section className="workspace-card">
      <div className="section-heading"><div><p className="eyebrow">File & Media</p><h2>Site photos</h2></div><span className="status-pill">{photos.length}</span></div>
      {canUpload && <div className="form-grid">
        <label className="wide">Image<input id="dpr-photo-file" type="file" accept="image/jpeg,image/png,image/webp,image/heic,image/heif" onChange={(event) => setFile(event.target.files?.[0] || null)} /></label>
        <label className="wide">Caption<input value={caption} onChange={(event) => setCaption(event.target.value)} placeholder="Location, activity or observation" /></label>
        <div><button disabled={busy || !file} onClick={() => void uploadPhoto()}>{busy ? "Working…" : "Attach photo"}</button></div>
      </div>}
      {photos.length === 0 ? <p className="muted">No photos attached to this DPR.</p> : <div className="stack">{photos.map((photo) => <div className="nested-card" key={photo.asset_id}>
        <div className="section-heading"><div><strong>{photo.filename}</strong><p className="muted">{sizeLabel(photo.size_bytes)} · version {photo.version} · {new Date(photo.created_at).toLocaleString()}</p></div>{editable && <button className="danger-link" disabled={busy} onClick={() => void removePhoto(photo)}>Remove</button>}</div>
        <p>{photo.caption || "No caption"}</p>
      </div>)}</div>}
      {report?.status !== "draft" && <p className="muted">Photos are locked after the DPR leaves draft status.</p>}
    </section>
  </div>;
}
