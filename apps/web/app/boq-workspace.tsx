"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

type AccessContext = {
  permissions: string[];
  project_permissions: Record<string, string[]>;
};

type Project = { id: string; number: string; name: string; status: string };
type WBS = { id: string; code: string; name: string; status: string };
type BOQ = {
  id: string;
  code: string;
  name: string;
  description: string | null;
  currency_code: string;
  status: string;
  revision: number;
  approved_at: string | null;
};
type BOQItem = {
  id: string;
  wbs_code_id: string | null;
  line_number: number;
  item_code: string;
  description: string;
  unit_code: string;
  quantity: string;
  rate: string;
  amount: string;
  hsn_sac: string | null;
  notes: string | null;
  revision: number;
};
type BOQDetail = BOQ & {
  items: BOQItem[];
  total_amount: string;
  item_count: number;
  mapped_item_count: number;
  revision_count: number;
  editable: boolean;
};
type BOQRevision = {
  id: string;
  version_number: number;
  approved_at: string;
  reason: string | null;
};
type ImportRow = {
  row_number: number;
  line_number: number | null;
  item_code: string;
  description: string;
  unit_code: string;
  quantity: string | null;
  rate: string | null;
  amount: string | null;
  wbs_code: string | null;
  errors: string[];
};
type ImportPreview = {
  rows: ImportRow[];
  valid_rows: number;
  invalid_rows: number;
  total_amount: string;
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

function csrfToken(): string | null {
  if (typeof document === "undefined") return null;
  const entry = document.cookie
    .split(";")
    .map((value) => value.trim())
    .find((value) => value.startsWith("construction_os_csrf="));
  return entry ? decodeURIComponent(entry.split("=").slice(1).join("=")) : null;
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

function money(value: string | number | null | undefined, currency = "INR") {
  if (value === null || value === undefined || value === "") return "—";
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "—";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(numeric);
}

function Status({ value }: { value: string }) {
  return (
    <span className={`status-pill status-${value.replaceAll("_", "-")}`}>
      {value.replaceAll("_", " ")}
    </span>
  );
}

function Empty({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="empty-state">
      <strong>{title}</strong>
      <p>{detail}</p>
    </div>
  );
}

export default function BOQWorkspace({
  initialProjectId,
  initialBoqId,
}: {
  initialProjectId?: string;
  initialBoqId?: string;
}) {
  const [context, setContext] = useState<AccessContext | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState(initialProjectId || "");
  const [boqs, setBoqs] = useState<BOQ[]>([]);
  const [wbs, setWbs] = useState<WBS[]>([]);
  const [detail, setDetail] = useState<BOQDetail | null>(null);
  const [revisions, setRevisions] = useState<BOQRevision[]>([]);
  const [editingItemId, setEditingItemId] = useState<string | null>(null);
  const [csvText, setCsvText] = useState("");
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [approvalReason, setApprovalReason] = useState("");
  const [cancelReason, setCancelReason] = useState("");
  const [statusFilter, setStatusFilter] = useState("active");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  const can = useCallback(
    (permission: string, targetProjectId: string) => {
      if (!context) return false;
      return (
        context.permissions.includes(permission) ||
        (context.project_permissions[targetProjectId] || []).includes(permission)
      );
    },
    [context],
  );

  const visibleProjects = useMemo(
    () => projects.filter((project) => can("commercial.boq.view", project.id)),
    [can, projects],
  );

  const filteredBoqs = useMemo(() => {
    if (statusFilter === "all") return boqs;
    if (statusFilter === "active") return boqs.filter((boq) => boq.status !== "cancelled");
    return boqs.filter((boq) => boq.status === statusFilter);
  }, [boqs, statusFilter]);

  const activeWbs = useMemo(() => wbs.filter((item) => item.status === "active"), [wbs]);
  const editingItem = detail?.items.find((item) => item.id === editingItemId) || null;

  const loadProject = useCallback(async (targetProjectId: string, targetBoqId?: string) => {
    if (!targetProjectId) {
      setBoqs([]);
      setWbs([]);
      setDetail(null);
      setRevisions([]);
      return;
    }
    const [boqRows, wbsRows] = await Promise.all([
      api<BOQ[]>(`/projects/${targetProjectId}/commercial/boqs`),
      api<WBS[]>(`/projects/${targetProjectId}/commercial/wbs`),
    ]);
    setBoqs(boqRows);
    setWbs(wbsRows);
    if (targetBoqId) {
      const nextDetail = await api<BOQDetail>(
        `/projects/${targetProjectId}/commercial/boqs/${targetBoqId}`,
      );
      setDetail(nextDetail);
      setRevisions(
        await api<BOQRevision[]>(
          `/projects/${targetProjectId}/commercial/boqs/${targetBoqId}/revisions`,
        ),
      );
    } else {
      setDetail(null);
      setRevisions([]);
    }
  }, []);

  const bootstrap = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const nextContext = await api<AccessContext>("/session/context");
      const projectRows = await api<Project[]>("/projects");
      setContext(nextContext);
      setProjects(projectRows);
      const accessible = projectRows.filter(
        (project) =>
          nextContext.permissions.includes("commercial.boq.view") ||
          (nextContext.project_permissions[project.id] || []).includes("commercial.boq.view"),
      );
      const selected =
        (initialProjectId && accessible.some((project) => project.id === initialProjectId)
          ? initialProjectId
          : accessible[0]?.id) || "";
      setProjectId(selected);
      if (selected) await loadProject(selected, initialBoqId);
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setLoading(false);
    }
  }, [initialBoqId, initialProjectId, loadProject]);

  useEffect(() => {
    void bootstrap();
  }, [bootstrap]);

  const refresh = useCallback(
    async (targetBoqId?: string) => {
      if (!projectId) return;
      await loadProject(projectId, targetBoqId ?? detail?.id ?? initialBoqId);
    },
    [detail?.id, initialBoqId, loadProject, projectId],
  );

  const mutate = async (work: () => Promise<string | void>) => {
    setBusy(true);
    setError("");
    try {
      const target = await work();
      await refresh(target || undefined);
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const createBoq = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!projectId) return;
    const form = new FormData(event.currentTarget);
    const formElement = event.currentTarget;
    await mutate(async () => {
      const created = await api<BOQ>(`/projects/${projectId}/commercial/boqs`, {
        method: "POST",
        body: JSON.stringify({
          code: form.get("code"),
          name: form.get("name"),
          description: form.get("description") || null,
          currency_code: form.get("currency_code") || "INR",
        }),
      });
      formElement.reset();
      return created.id;
    });
  };

  const updateHeader = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!projectId || !detail) return;
    const form = new FormData(event.currentTarget);
    await mutate(async () => {
      await api(`/projects/${projectId}/commercial/boqs/${detail.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          expected_revision: detail.revision,
          name: form.get("name"),
          description: form.get("description") || null,
          currency_code: form.get("currency_code"),
          reason: "Updated from BOQ workspace",
        }),
      });
    });
  };

  const addItem = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!projectId || !detail) return;
    const form = new FormData(event.currentTarget);
    const formElement = event.currentTarget;
    await mutate(async () => {
      await api(`/projects/${projectId}/commercial/boqs/${detail.id}/items`, {
        method: "POST",
        body: JSON.stringify({
          expected_boq_revision: detail.revision,
          line_number: Number(form.get("line_number")),
          item_code: form.get("item_code"),
          description: form.get("description"),
          unit_code: form.get("unit_code"),
          quantity: form.get("quantity"),
          rate: form.get("rate"),
          wbs_code_id: form.get("wbs_code_id") || null,
          hsn_sac: form.get("hsn_sac") || null,
          notes: form.get("notes") || null,
        }),
      });
      formElement.reset();
    });
  };

  const updateItem = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!projectId || !detail || !editingItem) return;
    const form = new FormData(event.currentTarget);
    await mutate(async () => {
      await api(`/projects/${projectId}/commercial/boqs/${detail.id}/items/${editingItem.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          expected_revision: editingItem.revision,
          expected_boq_revision: detail.revision,
          line_number: Number(form.get("line_number")),
          item_code: form.get("item_code"),
          description: form.get("description"),
          unit_code: form.get("unit_code"),
          quantity: form.get("quantity"),
          rate: form.get("rate"),
          wbs_code_id: form.get("wbs_code_id") || null,
          hsn_sac: form.get("hsn_sac") || null,
          notes: form.get("notes") || null,
          reason: "Updated from BOQ workspace",
        }),
      });
      setEditingItemId(null);
    });
  };

  const deleteItem = async (item: BOQItem) => {
    if (!projectId || !detail) return;
    await mutate(async () => {
      await api(`/projects/${projectId}/commercial/boqs/${detail.id}/items/${item.id}`, {
        method: "DELETE",
        body: JSON.stringify({
          expected_revision: item.revision,
          expected_boq_revision: detail.revision,
          reason: "Removed from draft BOQ workspace",
        }),
      });
      if (editingItemId === item.id) setEditingItemId(null);
    });
  };

  const previewCsv = async () => {
    if (!projectId || !detail || !csvText) return;
    setBusy(true);
    setError("");
    try {
      setPreview(
        await api<ImportPreview>(`/projects/${projectId}/commercial/boqs/${detail.id}/import/preview`, {
          method: "POST",
          body: JSON.stringify({ csv_text: csvText }),
        }),
      );
    } catch (requestError) {
      setError((requestError as Error).message);
      setPreview(null);
    } finally {
      setBusy(false);
    }
  };

  const applyCsv = async () => {
    if (!projectId || !detail || !preview || preview.invalid_rows > 0) return;
    await mutate(async () => {
      await api(`/projects/${projectId}/commercial/boqs/${detail.id}/import/apply`, {
        method: "POST",
        body: JSON.stringify({
          expected_revision: detail.revision,
          csv_text: csvText,
          reason: "Controlled CSV import from BOQ workspace",
        }),
      });
      setCsvText("");
      setPreview(null);
    });
  };

  const selectProject = async (nextProjectId: string) => {
    setProjectId(nextProjectId);
    setDetail(null);
    setRevisions([]);
    setPreview(null);
    setCsvText("");
    setError("");
    try {
      await loadProject(nextProjectId);
    } catch (requestError) {
      setError((requestError as Error).message);
    }
  };

  if (loading) {
    return <main className="boot-screen"><div className="boot-mark">COS</div><p>Loading BOQ…</p></main>;
  }

  return (
    <main className="workspace">
      <section className="page-frame">
        <div className="page-heading">
          <div>
            <p className="eyebrow">MODULE 3</p>
            <h1>Bill of Quantities</h1>
            <p>Contract quantity and rate baseline, kept separate from the internal WBS / cost-code structure.</p>
          </div>
        </div>

        {error && (
          <div className="error-banner">
            <strong>Action not completed</strong><span>{error}</span>
            <button onClick={() => setError("")}>×</button>
          </div>
        )}

        {visibleProjects.length === 0 ? (
          <Empty title="No accessible project" detail="You need BOQ view permission on at least one project." />
        ) : (
          <>
            <section className="workflow-card">
              <div><p className="eyebrow">PROJECT</p><h2>Choose BOQ workspace</h2></div>
              <div className="quick-form">
                <select value={projectId} onChange={(event) => void selectProject(event.target.value)}>
                  {visibleProjects.map((project) => (
                    <option key={project.id} value={project.id}>{project.number} · {project.name}</option>
                  ))}
                </select>
                <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
                  <option value="active">Active</option>
                  <option value="draft">Draft</option>
                  <option value="approved">Approved</option>
                  <option value="cancelled">Cancelled</option>
                  <option value="all">All</option>
                </select>
                <button className="secondary" onClick={() => void refresh()} disabled={busy}>Refresh</button>
              </div>
            </section>

            {projectId && can("commercial.boq.manage", projectId) && (
              <section className="workflow-card">
                <div>
                  <p className="eyebrow">NEW BASELINE</p><h2>Create BOQ</h2>
                  <small>The BOQ code remains stable. Approved BOQs are immutable.</small>
                </div>
                <form className="quick-form" onSubmit={createBoq}>
                  <input name="code" placeholder="BOQ code" maxLength={64} required />
                  <input name="name" placeholder="BOQ name" maxLength={255} required />
                  <input name="description" placeholder="Description (optional)" />
                  <input name="currency_code" defaultValue="INR" maxLength={3} required />
                  <button disabled={busy}>Create BOQ</button>
                </form>
              </section>
            )}

            <div className="split-layout">
              <section>
                <div className="detail-title"><div><p className="eyebrow">BOQS</p><h3>{filteredBoqs.length} records</h3></div></div>
                {filteredBoqs.length === 0 ? (
                  <Empty title="No BOQ yet" detail="Create the project contract or internal BOQ baseline." />
                ) : (
                  <div className="record-list">
                    {filteredBoqs.map((boq) => (
                      <button
                        className={detail?.id === boq.id ? "list-card selected" : "list-card"}
                        key={boq.id}
                        onClick={() => void loadProject(projectId, boq.id)}
                      >
                        <div><strong>{boq.code} · {boq.name}</strong><small>Revision {boq.revision} · {boq.currency_code}</small></div>
                        <Status value={boq.status} />
                      </button>
                    ))}
                  </div>
                )}
              </section>

              <section className="detail-panel">
                {!detail ? (
                  <Empty title="Select a BOQ" detail="Open a BOQ to manage items, approvals and controlled import/export." />
                ) : (
                  <>
                    <div className="detail-title">
                      <div><p className="eyebrow">BOQ DETAIL</p><h3>{detail.code} · {detail.name}</h3><small>Revision {detail.revision}</small></div>
                      <Status value={detail.status} />
                    </div>

                    <div className="metric-grid">
                      <article><span>BOQ value</span><strong>{money(detail.total_amount, detail.currency_code)}</strong><small>Current item total</small></article>
                      <article><span>Items</span><strong>{detail.item_count}</strong><small>Authoritative quantity lines</small></article>
                      <article><span>WBS mapped</span><strong>{detail.mapped_item_count}</strong><small>{detail.item_count - detail.mapped_item_count} unmapped</small></article>
                      <article><span>Approved snapshots</span><strong>{detail.revision_count}</strong><small>{detail.editable ? "Draft editable" : "Historical baseline"}</small></article>
                    </div>

                    {detail.editable && can("commercial.boq.manage", projectId) && (
                      <>
                        <section className="workflow-card">
                          <div><p className="eyebrow">HEADER</p><h2>Draft details</h2></div>
                          <form className="quick-form" onSubmit={updateHeader}>
                            <input name="name" defaultValue={detail.name} maxLength={255} required />
                            <input name="description" defaultValue={detail.description || ""} placeholder="Description" />
                            <input name="currency_code" defaultValue={detail.currency_code} maxLength={3} disabled={detail.item_count > 0} required />
                            <button disabled={busy}>Save header</button>
                          </form>
                        </section>

                        <section className="workflow-card">
                          <div><p className="eyebrow">ADD ITEM</p><h2>BOQ quantity line</h2></div>
                          <form className="quick-form" onSubmit={addItem}>
                            <input name="line_number" type="number" min="1" placeholder="Line" required />
                            <input name="item_code" placeholder="Item code" maxLength={80} required />
                            <input name="description" placeholder="Description" required />
                            <input name="unit_code" placeholder="Unit" maxLength={24} required />
                            <input name="quantity" type="number" min="0" step="0.001" placeholder="Quantity" required />
                            <input name="rate" type="number" min="0" step="0.01" placeholder="Rate" required />
                            <select name="wbs_code_id" defaultValue=""><option value="">No WBS mapping</option>{activeWbs.map((item) => <option key={item.id} value={item.id}>{item.code} · {item.name}</option>)}</select>
                            <input name="hsn_sac" placeholder="HSN/SAC (optional)" maxLength={16} />
                            <input name="notes" placeholder="Notes (optional)" />
                            <button disabled={busy}>Add item</button>
                          </form>
                        </section>
                      </>
                    )}

                    {detail.items.length === 0 ? (
                      <Empty title="No BOQ items" detail="Add lines manually or preview a controlled CSV import before approval." />
                    ) : (
                      <div className="record-list">
                        {detail.items.map((item) => (
                          <article className="record-card" key={item.id}>
                            <div>
                              <span className="record-number">Line {item.line_number}</span>
                              <strong>{item.item_code} · {item.description}</strong>
                              <small>{item.quantity} {item.unit_code} × {money(item.rate, detail.currency_code)} · {money(item.amount, detail.currency_code)}</small>
                            </div>
                            {detail.editable && can("commercial.boq.manage", projectId) && (
                              <div className="record-actions">
                                <button className="secondary" onClick={() => setEditingItemId(item.id)}>Edit</button>
                                <button className="secondary" disabled={busy} onClick={() => void deleteItem(item)}>Delete</button>
                              </div>
                            )}
                          </article>
                        ))}
                      </div>
                    )}

                    {editingItem && detail.editable && (
                      <section className="workflow-card">
                        <div><p className="eyebrow">EDIT ITEM</p><h2>{editingItem.item_code}</h2></div>
                        <form className="quick-form" onSubmit={updateItem}>
                          <input name="line_number" type="number" min="1" defaultValue={editingItem.line_number} required />
                          <input name="item_code" defaultValue={editingItem.item_code} maxLength={80} required />
                          <input name="description" defaultValue={editingItem.description} required />
                          <input name="unit_code" defaultValue={editingItem.unit_code} maxLength={24} required />
                          <input name="quantity" type="number" min="0" step="0.001" defaultValue={editingItem.quantity} required />
                          <input name="rate" type="number" min="0" step="0.01" defaultValue={editingItem.rate} required />
                          <select name="wbs_code_id" defaultValue={editingItem.wbs_code_id || ""}><option value="">No WBS mapping</option>{activeWbs.map((item) => <option key={item.id} value={item.id}>{item.code} · {item.name}</option>)}</select>
                          <input name="hsn_sac" defaultValue={editingItem.hsn_sac || ""} placeholder="HSN/SAC" maxLength={16} />
                          <input name="notes" defaultValue={editingItem.notes || ""} placeholder="Notes" />
                          <button disabled={busy}>Save item</button>
                          <button type="button" className="secondary" onClick={() => setEditingItemId(null)}>Close</button>
                        </form>
                      </section>
                    )}

                    {detail.editable && can("commercial.boq.manage", projectId) && (
                      <section className="workflow-card">
                        <div>
                          <p className="eyebrow">CONTROLLED IMPORT</p><h2>CSV / Excel-compatible import</h2>
                          <small>Save the BOQ sheet as CSV. Preview validates every row before one atomic import.</small>
                        </div>
                        <div className="quick-form">
                          <input
                            type="file"
                            accept=".csv,text/csv"
                            onChange={(event) => {
                              const file = event.target.files?.[0];
                              setPreview(null);
                              if (!file) return setCsvText("");
                              void file.text().then(setCsvText).catch((requestError: Error) => setError(requestError.message));
                            }}
                          />
                          <button type="button" className="secondary" onClick={() => window.open(`${API_BASE}/projects/${projectId}/commercial/boqs/template.csv`, "_blank")}>
                            CSV template
                          </button>
                          <button type="button" disabled={busy || !csvText} onClick={() => void previewCsv()}>Preview import</button>
                        </div>
                        {preview && (
                          <>
                            <div className="metric-grid">
                              <article><span>Valid rows</span><strong>{preview.valid_rows}</strong><small>Ready to apply</small></article>
                              <article><span>Invalid rows</span><strong>{preview.invalid_rows}</strong><small>Must be corrected</small></article>
                              <article><span>Import value</span><strong>{money(preview.total_amount, detail.currency_code)}</strong><small>Valid rows only</small></article>
                            </div>
                            <div className="record-list">
                              {preview.rows.slice(0, 50).map((row) => (
                                <article className="record-card" key={`${row.row_number}-${row.item_code}`}>
                                  <div><span className="record-number">CSV row {row.row_number}</span><strong>{row.item_code || "Missing item code"}</strong><small>{row.errors.length ? row.errors.join(" · ") : `${row.quantity} ${row.unit_code} · ${money(row.amount, detail.currency_code)}`}</small></div>
                                  <Status value={row.errors.length ? "invalid" : "ready"} />
                                </article>
                              ))}
                            </div>
                            <button className="approve-button" disabled={busy || preview.invalid_rows > 0 || preview.valid_rows === 0} onClick={() => void applyCsv()}>
                              Apply validated rows
                            </button>
                          </>
                        )}
                      </section>
                    )}

                    <section className="workflow-card">
                      <div><p className="eyebrow">EXPORT</p><h2>Portable BOQ data</h2></div>
                      <div className="quick-form">
                        <button type="button" className="secondary" onClick={() => window.open(`${API_BASE}/projects/${projectId}/commercial/boqs/${detail.id}/export.csv`, "_blank")}>Export current CSV</button>
                        {revisions.map((revision) => (
                          <button type="button" className="secondary" key={revision.id} onClick={() => window.open(`${API_BASE}/projects/${projectId}/commercial/boqs/${detail.id}/revisions/${revision.version_number}/export.csv`, "_blank")}>
                            Approved v{revision.version_number}
                          </button>
                        ))}
                      </div>
                    </section>

                    {detail.editable && (
                      <section className="workflow-card">
                        <div><p className="eyebrow">LIFECYCLE</p><h2>Approve or cancel draft</h2><small>Approval freezes the current BOQ and stores an immutable snapshot.</small></div>
                        <div className="quick-form">
                          {can("commercial.boq.approve", projectId) && (
                            <>
                              <input value={approvalReason} onChange={(event) => setApprovalReason(event.target.value)} placeholder="Approval reason / reference" />
                              <button className="approve-button" disabled={busy || detail.item_count === 0} onClick={() => void mutate(async () => {
                                await api(`/projects/${projectId}/commercial/boqs/${detail.id}/approve`, { method: "POST", body: JSON.stringify({ expected_revision: detail.revision, reason: approvalReason || null }) });
                                setApprovalReason("");
                              })}>Approve BOQ baseline</button>
                            </>
                          )}
                          {can("commercial.boq.manage", projectId) && (
                            <>
                              <input value={cancelReason} onChange={(event) => setCancelReason(event.target.value)} placeholder="Cancellation reason" />
                              <button className="secondary" disabled={busy || !cancelReason.trim()} onClick={() => void mutate(async () => {
                                await api(`/projects/${projectId}/commercial/boqs/${detail.id}/cancel`, { method: "POST", body: JSON.stringify({ expected_revision: detail.revision, reason: cancelReason }) });
                                setCancelReason("");
                              })}>Cancel draft</button>
                            </>
                          )}
                        </div>
                      </section>
                    )}

                    {revisions.length > 0 && (
                      <section className="workflow-card">
                        <div><p className="eyebrow">APPROVAL HISTORY</p><h2>Immutable snapshots</h2></div>
                        <div className="record-list">
                          {revisions.map((revision) => (
                            <article className="record-card" key={revision.id}>
                              <div><span className="record-number">Version {revision.version_number}</span><strong>{new Date(revision.approved_at).toLocaleString("en-IN")}</strong><small>{revision.reason || "No approval reason recorded"}</small></div>
                            </article>
                          ))}
                        </div>
                      </section>
                    )}
                  </>
                )}
              </section>
            </div>
          </>
        )}
      </section>
    </main>
  );
}
