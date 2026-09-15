"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useWebSession } from "./web-session-gate";

type Project = { id: string; number: string; name: string };
type ProviderCollection = { key: string; fields: string[] };
type ProviderContract = {
  key: string;
  version: number;
  scalar_paths: string[];
  collections: ProviderCollection[];
  dynamic_prefixes: string[];
};
type Template = {
  id: string;
  project_id: string | null;
  name: string;
  description: string | null;
  active: boolean;
  is_default: boolean;
  current_version: number;
  updated_at: string;
};
type TemplateVersion = {
  id: string;
  template_id: string;
  version: number;
  status: string;
  source_kind: string;
  provider_contract_version: number;
  published_at: string | null;
  created_at: string;
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
    try {
      const body = await response.json() as { detail?: unknown };
      if (body.detail) message = String(body.detail);
    } catch {}
    throw new Error(message);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

function titleCase(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function standardLayout(contract: ProviderContract) {
  const preferredScalars = [
    "company.name",
    "project.number",
    "project.name",
    "project.client_name",
    "report.number",
    "report.date",
    "report.shift",
    "report.weather_condition",
    "report.temperature_low",
    "report.temperature_high",
    "report.temperature_unit",
    "report.notes",
    "approvals.prepared_by",
    "approvals.approved_by",
  ].filter((path) => contract.scalar_paths.includes(path));

  const blocks: Record<string, unknown>[] = [];
  let row = 0;
  if (preferredScalars.length) {
    blocks.push({
      id: "dpr-overview",
      kind: "field_group",
      order: row,
      row,
      width_percent: 100,
      title: "Daily Progress Report",
      scalar_fields: preferredScalars,
    });
    row += 1;
  }

  for (const collection of contract.collections) {
    blocks.push({
      id: `dpr-${collection.key.replaceAll("_", "-")}`,
      kind: "table",
      order: row,
      row,
      width_percent: 100,
      title: titleCase(collection.key),
      data_key: collection.key,
      hide_when_empty: true,
      repeat_table_header: true,
      avoid_row_split: true,
      table_columns: collection.fields.map((field, index) => ({
        key: field,
        label: titleCase(field),
        order: index,
        visible: true,
        align: "left",
      })),
    });
    row += 1;
  }

  return {
    schema_version: 1,
    report_title: "Daily Progress Report",
    page: {
      size: "a4",
      orientation: "portrait",
      margin_top_mm: 12,
      margin_right_mm: 12,
      margin_bottom_mm: 12,
      margin_left_mm: 12,
    },
    header_footer: {
      header_left: "{{company.name}}",
      header_right: "{{project.number}}",
      footer_left: "Daily Progress Report",
      show_page_number: true,
      show_generated_timestamp: true,
    },
    blocks,
  };
}

function Status({ value }: { value: string }) {
  return <span className={`status-pill status-${value.replaceAll("_", "-")}`}>{value.replaceAll("_", " ")}</span>;
}

export default function DPRTemplateWorkspace() {
  const { context } = useWebSession();
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [contract, setContract] = useState<ProviderContract | null>(null);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState("");
  const [versions, setVersions] = useState<TemplateVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [name, setName] = useState("Standard DPR");
  const [description, setDescription] = useState("India-first Daily Progress Report template");
  const [companyWide, setCompanyWide] = useState(false);
  const [isDefault, setIsDefault] = useState(false);

  const can = useCallback((permission: string, pid?: string) => {
    if (context.permissions.includes(permission)) return true;
    return pid ? (context.project_permissions[pid] || []).includes(permission) : false;
  }, [context]);

  const visibleProjects = useMemo(
    () => projects.filter((project) => can("field.dpr.template.view", project.id)),
    [projects, can],
  );

  const selectedTemplate = useMemo(
    () => templates.find((template) => template.id === selectedTemplateId) || null,
    [templates, selectedTemplateId],
  );

  const loadVersions = useCallback(async (pid: string, templateId: string) => {
    if (!pid || !templateId) {
      setVersions([]);
      return;
    }
    setVersions(await api<TemplateVersion[]>(`/projects/${pid}/dpr-templates/${templateId}/versions`));
  }, []);

  const loadProject = useCallback(async (pid: string, preferredTemplateId?: string) => {
    if (!pid) {
      setContract(null);
      setTemplates([]);
      setSelectedTemplateId("");
      setVersions([]);
      return;
    }
    const [providerContract, rows] = await Promise.all([
      api<ProviderContract>(`/projects/${pid}/dpr-templates/contract`),
      api<Template[]>(`/projects/${pid}/dpr-templates`),
    ]);
    setContract(providerContract);
    setTemplates(rows);
    const nextId = preferredTemplateId && rows.some((row) => row.id === preferredTemplateId)
      ? preferredTemplateId
      : rows[0]?.id || "";
    setSelectedTemplateId(nextId);
    await loadVersions(pid, nextId);
  }, [loadVersions]);

  useEffect(() => {
    (async () => {
      setLoading(true);
      setError("");
      try {
        const rows = await api<Project[]>("/projects");
        setProjects(rows);
        const first = rows.find((project) => can("field.dpr.template.view", project.id));
        const pid = first?.id || "";
        setProjectId(pid);
        await loadProject(pid);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setLoading(false);
      }
    })();
  }, [can, loadProject]);

  async function createTemplate(event: FormEvent) {
    event.preventDefault();
    if (!projectId || !name.trim()) return;
    setBusy(true);
    setError("");
    try {
      const created = await api<Template>(`/projects/${projectId}/dpr-templates`, {
        method: "POST",
        body: JSON.stringify({
          name: name.trim(),
          description: description.trim() || null,
          company_wide: companyWide,
          is_default: isDefault,
        }),
      });
      await loadProject(projectId, created.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function createVersion() {
    if (!projectId || !selectedTemplate || !contract) return;
    setBusy(true);
    setError("");
    try {
      await api<TemplateVersion>(`/projects/${projectId}/dpr-templates/${selectedTemplate.id}/versions`, {
        method: "POST",
        body: JSON.stringify({ source_kind: "designer", layout: standardLayout(contract) }),
      });
      await loadProject(projectId, selectedTemplate.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function publishVersion(version: TemplateVersion) {
    if (!projectId || !selectedTemplate) return;
    setBusy(true);
    setError("");
    try {
      await api<TemplateVersion>(
        `/projects/${projectId}/dpr-templates/${selectedTemplate.id}/versions/${version.id}/publish`,
        { method: "POST", body: JSON.stringify({ reason: "Published from DPR template workspace" }) },
      );
      await loadProject(projectId, selectedTemplate.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <main className="workspace-shell"><p>Loading DPR templates…</p></main>;

  const canManageProject = Boolean(projectId && can("field.dpr.template.manage", projectId));
  const canManageCompany = context.permissions.includes("field.dpr.template.manage");
  const canManageSelected = selectedTemplate?.project_id == null ? canManageCompany : canManageProject;

  return <main className="workspace-shell">
    <header className="workspace-header">
      <div>
        <p className="eyebrow">Field Operations · Reporting</p>
        <h1>DPR templates</h1>
        <p>Control presentation without changing the authoritative DPR, BOQ, attendance or project records.</p>
      </div>
      <Link className="secondary-button" href="/field">Back to DPR</Link>
    </header>

    {error && <div className="error-banner"><span>{error}</span></div>}

    <section className="workspace-card">
      <div className="form-grid">
        <label>Project
          <select value={projectId} onChange={async (event) => {
            const pid = event.target.value;
            setProjectId(pid);
            setError("");
            try { await loadProject(pid); } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
          }}>
            <option value="">Select project</option>
            {visibleProjects.map((project) => <option value={project.id} key={project.id}>{project.number} · {project.name}</option>)}
          </select>
        </label>
        {contract && <div className="nested-card"><strong>DPR data contract v{contract.version}</strong><p className="muted">{contract.scalar_paths.length} scalar fields · {contract.collections.length} governed collections</p></div>}
      </div>
    </section>

    {!projectId ? <section className="workspace-card"><h2>No DPR project access</h2><p className="muted">You need DPR template view permission on a project before templates can be opened.</p></section> : <div className="workspace-grid">
      <aside className="workspace-card">
        <div className="section-heading"><h2>Templates</h2><span className="status-pill">{templates.length}</span></div>
        {templates.length === 0 ? <p className="muted">No templates are configured for this project.</p> : templates.map((template) =>
          <button key={template.id} className={`list-row ${selectedTemplateId === template.id ? "selected" : ""}`} onClick={async () => {
            setSelectedTemplateId(template.id);
            setError("");
            try { await loadVersions(projectId, template.id); } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
          }}>
            <span>{template.name}<small>{template.project_id ? "Project" : "Company"}{template.is_default ? " · Default" : ""}</small></span>
            <Status value={template.active ? "active" : "inactive"} />
          </button>)}
      </aside>

      <section className="workspace-main">
        {(canManageProject || canManageCompany) && <section className="workspace-card">
          <h2>Create template</h2>
          <form onSubmit={createTemplate} className="form-grid">
            <label>Name<input value={name} onChange={(event) => setName(event.target.value)} required /></label>
            <label className="wide">Description<input value={description} onChange={(event) => setDescription(event.target.value)} /></label>
            <label><input type="checkbox" checked={isDefault} onChange={(event) => setIsDefault(event.target.checked)} /> Default template</label>
            {canManageCompany && <label><input type="checkbox" checked={companyWide} onChange={(event) => setCompanyWide(event.target.checked)} /> Company-wide</label>}
            <div><button disabled={busy || (companyWide ? !canManageCompany : !canManageProject)}>Create template</button></div>
          </form>
        </section>}

        {!selectedTemplate ? <section className="workspace-card"><h2>Select or create a template</h2><p className="muted">A template owns presentation only; field and commercial records remain the source of truth.</p></section> : <>
          <section className="workspace-card">
            <div className="section-heading">
              <div><p className="eyebrow">{selectedTemplate.project_id ? "Project template" : "Company template"}</p><h2>{selectedTemplate.name}</h2></div>
              {canManageSelected && <button onClick={createVersion} disabled={busy || !contract}>Create standard version</button>}
            </div>
            <p className="muted">{selectedTemplate.description || "No description"}</p>
            <div className="button-row"><Status value={selectedTemplate.active ? "active" : "inactive"} />{selectedTemplate.is_default && <span className="status-pill status-approved">default</span>}<span className="status-pill">current v{selectedTemplate.current_version}</span></div>
          </section>

          <section className="workspace-card">
            <div className="section-heading"><h3>Versions</h3><span className="status-pill">{versions.length}</span></div>
            {versions.length === 0 ? <p className="muted">No versions yet. Create the first contract-driven version to make this template publishable.</p> : <div className="stack">{versions.map((version) => <div className="nested-card" key={version.id}>
              <div className="section-heading"><div><strong>Version {version.version}</strong><p className="muted">Contract v{version.provider_contract_version} · {version.source_kind}</p></div><Status value={version.status} /></div>
              <div className="button-row"><span className="muted">{version.published_at ? `Published ${new Date(version.published_at).toLocaleString()}` : `Created ${new Date(version.created_at).toLocaleString()}`}</span>{version.status !== "published" && canManageSelected && <button onClick={() => publishVersion(version)} disabled={busy}>Publish</button>}</div>
            </div>)}</div>}
          </section>

          {contract && <section className="workspace-card">
            <h3>Authoritative template fields</h3>
            <p className="muted">New standard versions are generated only from this backend contract, so template columns stay aligned with the DPR payload.</p>
            <div className="stack">{contract.collections.map((collection) => <div className="nested-card" key={collection.key}><strong>{titleCase(collection.key)}</strong><p className="muted">{collection.fields.join(" · ")}</p></div>)}</div>
          </section>}
        </>}
      </section>
    </div>}
  </main>;
}
