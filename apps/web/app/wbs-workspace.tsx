"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

type AccessContext = {
  permissions: string[];
  project_permissions: Record<string, string[]>;
};

type Project = {
  id: string;
  number: string;
  name: string;
  status: string;
};

type WBS = {
  id: string;
  organization_id: string;
  project_id: string;
  parent_id: string | null;
  code: string;
  name: string;
  kind: string;
  status: string;
  description: string | null;
  revision: number;
};

type WBSTreeItem = WBS & {
  depth: number;
  path_codes: string[];
  child_count: number;
};

type WBSPathNode = {
  id: string;
  code: string;
  name: string;
  kind: string;
  status: string;
};

type WBSDetail = WBS & {
  path: WBSPathNode[];
  child_count: number;
  descendant_count: number;
  direct_usage_count: number;
  subtree_usage_count: number;
  usage_areas: string[];
  structure_locked: boolean;
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
const WBS_KINDS = ["group", "trade", "work_package", "cost_code"];

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

export default function WBSWorkspace({
  initialProjectId,
  initialWbsId,
}: {
  initialProjectId?: string;
  initialWbsId?: string;
}) {
  const [context, setContext] = useState<AccessContext | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState(initialProjectId || "");
  const [tree, setTree] = useState<WBSTreeItem[]>([]);
  const [detail, setDetail] = useState<WBSDetail | null>(null);
  const [query, setQuery] = useState("");
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
    () => projects.filter((project) => can("commercial.wbs.view", project.id)),
    [can, projects],
  );

  const filteredTree = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return tree.filter((item) => {
      if (statusFilter !== "all" && item.status !== statusFilter) return false;
      if (!normalized) return true;
      return [item.code, item.name, item.kind, item.description || ""]
        .join(" ")
        .toLowerCase()
        .includes(normalized);
    });
  }, [query, statusFilter, tree]);

  const loadTree = useCallback(async (targetProjectId: string, targetWbsId?: string) => {
    if (!targetProjectId) {
      setTree([]);
      setDetail(null);
      return;
    }
    const rows = await api<WBSTreeItem[]>(`/projects/${targetProjectId}/commercial/wbs/tree`);
    setTree(rows);
    if (targetWbsId) {
      setDetail(
        await api<WBSDetail>(`/projects/${targetProjectId}/commercial/wbs/${targetWbsId}`),
      );
    } else {
      setDetail(null);
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
          nextContext.permissions.includes("commercial.wbs.view") ||
          (nextContext.project_permissions[project.id] || []).includes("commercial.wbs.view"),
      );
      const selected =
        (initialProjectId && accessible.some((project) => project.id === initialProjectId)
          ? initialProjectId
          : accessible[0]?.id) || "";
      setProjectId(selected);
      if (selected) await loadTree(selected, initialWbsId);
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setLoading(false);
    }
  }, [initialProjectId, initialWbsId, loadTree]);

  useEffect(() => {
    void bootstrap();
  }, [bootstrap]);

  const refresh = useCallback(async () => {
    if (!projectId) return;
    await loadTree(projectId, detail?.id || initialWbsId);
  }, [detail?.id, initialWbsId, loadTree, projectId]);

  const mutate = async (work: () => Promise<unknown>) => {
    setBusy(true);
    setError("");
    try {
      await work();
      await refresh();
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const createCode = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!projectId) return;
    const form = new FormData(event.currentTarget);
    const formElement = event.currentTarget;
    await mutate(async () => {
      const created = await api<WBS>(`/projects/${projectId}/commercial/wbs`, {
        method: "POST",
        body: JSON.stringify({
          code: form.get("code"),
          name: form.get("name"),
          kind: form.get("kind"),
          parent_id: form.get("parent_id") || null,
          description: form.get("description") || null,
        }),
      });
      formElement.reset();
      setDetail(
        await api<WBSDetail>(`/projects/${projectId}/commercial/wbs/${created.id}`),
      );
    });
  };

  const updateCode = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!projectId || !detail) return;
    const form = new FormData(event.currentTarget);
    await mutate(async () => {
      await api<WBS>(`/projects/${projectId}/commercial/wbs/${detail.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          expected_revision: detail.revision,
          name: form.get("name"),
          description: form.get("description") || null,
          kind: form.get("kind"),
          parent_id: form.get("parent_id") || null,
          status: form.get("status"),
          reason: "Updated from WBS workspace",
        }),
      });
    });
  };

  const selectProject = async (nextProjectId: string) => {
    setProjectId(nextProjectId);
    setDetail(null);
    setError("");
    try {
      await loadTree(nextProjectId);
    } catch (requestError) {
      setError((requestError as Error).message);
    }
  };

  if (loading) {
    return <main className="boot-screen"><div className="boot-mark">COS</div><p>Loading WBS…</p></main>;
  }

  return (
    <main className="workspace">
      <section className="page-frame">
        <div className="page-heading">
          <div>
            <p className="eyebrow">MODULE 2</p>
            <h1>WBS / Cost Codes</h1>
            <p>Internal project control structure for planning, cost allocation and downstream reporting.</p>
          </div>
        </div>

        {error && (
          <div className="error-banner">
            <strong>Action not completed</strong>
            <span>{error}</span>
            <button onClick={() => setError("")}>×</button>
          </div>
        )}

        {visibleProjects.length === 0 ? (
          <Empty
            title="No accessible project"
            detail="You need WBS view permission on at least one project before using this workspace."
          />
        ) : (
          <>
            <section className="workflow-card">
              <div>
                <p className="eyebrow">PROJECT CONTROL</p>
                <h2>Choose project</h2>
              </div>
              <div className="quick-form">
                <select value={projectId} onChange={(event) => void selectProject(event.target.value)}>
                  {visibleProjects.map((project) => (
                    <option key={project.id} value={project.id}>
                      {project.number} · {project.name}
                    </option>
                  ))}
                </select>
                <input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Search code or name"
                />
                <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
                  <option value="active">Active</option>
                  <option value="inactive">Inactive</option>
                  <option value="all">All</option>
                </select>
                <button className="secondary" onClick={() => void refresh()} disabled={busy}>
                  Refresh
                </button>
              </div>
            </section>

            {projectId && can("commercial.wbs.manage", projectId) && (
              <section className="workflow-card">
                <div>
                  <p className="eyebrow">ADD STRUCTURE</p>
                  <h2>New WBS code</h2>
                  <small>Codes are stable identifiers. Use inactive status instead of deleting history.</small>
                </div>
                <form className="quick-form" onSubmit={createCode}>
                  <input name="code" placeholder="Code e.g. CIV.CONC" maxLength={80} required />
                  <input name="name" placeholder="Name" maxLength={255} required />
                  <select name="kind" defaultValue="cost_code">
                    {WBS_KINDS.map((value) => (
                      <option key={value} value={value}>{value.replaceAll("_", " ")}</option>
                    ))}
                  </select>
                  <select name="parent_id" defaultValue="">
                    <option value="">No parent</option>
                    {tree.filter((item) => item.status === "active").map((item) => (
                      <option key={item.id} value={item.id}>
                        {"— ".repeat(item.depth)}{item.code} · {item.name}
                      </option>
                    ))}
                  </select>
                  <input name="description" placeholder="Description (optional)" />
                  <button disabled={busy}>Add WBS code</button>
                </form>
              </section>
            )}

            <div className="split-layout">
              <section>
                <div className="detail-title">
                  <div>
                    <p className="eyebrow">HIERARCHY</p>
                    <h3>{filteredTree.length} visible codes</h3>
                  </div>
                </div>
                {filteredTree.length === 0 ? (
                  <Empty
                    title="No WBS codes"
                    detail="Start with the project control hierarchy before connecting BOQ and cost records."
                  />
                ) : (
                  <div className="record-list">
                    {filteredTree.map((item) => (
                      <Link
                        href={`/projects/${projectId}/commercial/wbs/${item.id}`}
                        className={detail?.id === item.id ? "list-card selected" : "list-card"}
                        key={item.id}
                        style={{ paddingLeft: `${16 + item.depth * 22}px` }}
                      >
                        <div>
                          <strong>{item.code} · {item.name}</strong>
                          <small>
                            {item.kind.replaceAll("_", " ")}
                            {item.child_count ? ` · ${item.child_count} child${item.child_count === 1 ? "" : "ren"}` : ""}
                          </small>
                        </div>
                        <Status value={item.status} />
                      </Link>
                    ))}
                  </div>
                )}
              </section>

              <section className="detail-panel">
                {!detail ? (
                  <Empty title="Select a WBS code" detail="Open a code to view hierarchy, usage and lifecycle controls." />
                ) : (
                  <>
                    <div className="detail-title">
                      <div>
                        <p className="eyebrow">WBS DETAIL</p>
                        <h3>{detail.code} · {detail.name}</h3>
                        <small>{detail.path.map((item) => item.code).join(" / ")}</small>
                      </div>
                      <Status value={detail.status} />
                    </div>

                    <div className="metric-grid">
                      <article>
                        <span>Direct usage</span>
                        <strong>{detail.direct_usage_count}</strong>
                        <small>Records using this code</small>
                      </article>
                      <article>
                        <span>Subtree usage</span>
                        <strong>{detail.subtree_usage_count}</strong>
                        <small>Includes descendants</small>
                      </article>
                      <article>
                        <span>Children</span>
                        <strong>{detail.child_count}</strong>
                        <small>{detail.descendant_count} total descendants</small>
                      </article>
                      <article>
                        <span>Structure</span>
                        <strong>{detail.structure_locked ? "Locked" : "Editable"}</strong>
                        <small>{detail.structure_locked ? "Historical usage exists" : "No downstream usage yet"}</small>
                      </article>
                    </div>

                    {detail.usage_areas.length > 0 && (
                      <div className="workflow-card">
                        <div>
                          <p className="eyebrow">USED BY</p>
                          <h2>{detail.usage_areas.join(", ")}</h2>
                          <small>Existing references remain valid if this code is later made inactive.</small>
                        </div>
                      </div>
                    )}

                    <form className="quick-form" onSubmit={updateCode}>
                      <input
                        name="name"
                        defaultValue={detail.name}
                        maxLength={255}
                        disabled={!can("commercial.wbs.manage", projectId) || busy}
                        required
                      />
                      <input
                        name="description"
                        defaultValue={detail.description || ""}
                        placeholder="Description"
                        disabled={!can("commercial.wbs.manage", projectId) || busy}
                      />
                      <select
                        name="kind"
                        defaultValue={detail.kind}
                        disabled={!can("commercial.wbs.manage", projectId) || busy || detail.structure_locked}
                      >
                        {WBS_KINDS.map((value) => (
                          <option key={value} value={value}>{value.replaceAll("_", " ")}</option>
                        ))}
                      </select>
                      <select
                        name="parent_id"
                        defaultValue={detail.parent_id || ""}
                        disabled={!can("commercial.wbs.manage", projectId) || busy || detail.structure_locked}
                      >
                        <option value="">No parent</option>
                        {tree
                          .filter((item) => item.id !== detail.id && item.status === "active")
                          .map((item) => (
                            <option key={item.id} value={item.id}>
                              {"— ".repeat(item.depth)}{item.code} · {item.name}
                            </option>
                          ))}
                      </select>
                      <select
                        name="status"
                        defaultValue={detail.status}
                        disabled={!can("commercial.wbs.manage", projectId) || busy}
                      >
                        <option value="active">Active</option>
                        <option value="inactive">Inactive</option>
                      </select>
                      <button disabled={!can("commercial.wbs.manage", projectId) || busy}>Save WBS code</button>
                    </form>

                    {detail.structure_locked && (
                      <p>
                        Parent and type are locked because this WBS subtree is already referenced by project records.
                        Name, description and active/inactive lifecycle remain controlled separately.
                      </p>
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
