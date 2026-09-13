"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

type RoleScope = "company" | "project" | "both";
type Role = {
  id: string;
  key: string;
  name: string;
  assignment_scope: RoleScope;
  is_active: boolean;
};
type CompanyMembership = {
  id: string;
  display_name: string;
  primary_email: string;
  kind: "internal" | "external" | "service";
  status: "invited" | "active" | "suspended" | "ended";
};
type Project = {
  id: string;
  number: string;
  name: string;
  status: string;
};
type ProjectAccessRole = {
  id: string;
  key: string;
  name: string;
  assignment_scope: RoleScope;
  is_template: boolean;
  is_protected: boolean;
};
type ProjectAccessMember = {
  id: string;
  organization_membership_id: string;
  user_id: string;
  display_name: string;
  primary_email: string;
  membership_kind: "internal" | "external" | "service";
  status: "active" | "suspended" | "ended";
  title: string | null;
  role_ids: string[];
  roles: ProjectAccessRole[];
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
  return response.json() as Promise<T>;
}

export default function ProjectAccessWorkspace() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [memberships, setMemberships] = useState<CompanyMembership[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [projectId, setProjectId] = useState("");
  const [access, setAccess] = useState<ProjectAccessMember[]>([]);
  const [selectedMemberId, setSelectedMemberId] = useState("");
  const [roleDraft, setRoleDraft] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const projectRoles = useMemo(
    () => roles.filter((role) => role.is_active && (role.assignment_scope === "project" || role.assignment_scope === "both")),
    [roles],
  );
  const activeCompanyMembers = memberships.filter((membership) => membership.status === "active");
  const selectedMember = access.find((member) => member.id === selectedMemberId) || null;

  const loadBase = async () => {
    try {
      setError("");
      const [nextProjects, nextMemberships, nextRoles] = await Promise.all([
        api<Project[]>("/projects"),
        api<CompanyMembership[]>("/security/memberships"),
        api<Role[]>("/security/roles"),
      ]);
      setProjects(nextProjects);
      setMemberships(nextMemberships);
      setRoles(nextRoles);
      if (!projectId && nextProjects.length > 0) setProjectId(nextProjects[0].id);
    } catch (requestError) {
      setError((requestError as Error).message);
    }
  };

  const loadAccess = async (nextProjectId: string) => {
    if (!nextProjectId) {
      setAccess([]);
      return;
    }
    try {
      setError("");
      const rows = await api<ProjectAccessMember[]>(`/projects/${nextProjectId}/access`);
      setAccess(rows);
      setSelectedMemberId("");
      setRoleDraft(new Set());
    } catch (requestError) {
      setError((requestError as Error).message);
    }
  };

  useEffect(() => {
    void loadBase();
  }, []);

  useEffect(() => {
    if (projectId) void loadAccess(projectId);
  }, [projectId]);

  const addMember = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!projectId) return;
    const form = new FormData(event.currentTarget);
    const membershipId = String(form.get("membership_id") || "");
    if (!membershipId) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await api(`/projects/${projectId}/memberships`, {
        method: "POST",
        body: JSON.stringify({
          organization_membership_id: membershipId,
          title: String(form.get("title") || "").trim() || null,
        }),
      });
      event.currentTarget.reset();
      setMessage("Project membership added. Assign one or more project roles below.");
      await loadAccess(projectId);
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const openMember = (member: ProjectAccessMember) => {
    setSelectedMemberId(member.id);
    setRoleDraft(new Set(member.role_ids));
    setError("");
    setMessage("");
  };

  const saveRoles = async () => {
    if (!projectId || !selectedMember) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const updated = await api<ProjectAccessMember>(
        `/projects/${projectId}/memberships/${selectedMember.id}/roles`,
        { method: "PUT", body: JSON.stringify({ role_ids: [...roleDraft] }) },
      );
      setMessage(`Project roles updated for ${updated.display_name}.`);
      await loadAccess(projectId);
      setSelectedMemberId(updated.id);
      setRoleDraft(new Set(updated.role_ids));
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const setStatus = async (member: ProjectAccessMember, status: ProjectAccessMember["status"]) => {
    if (!projectId) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await api(`/projects/${projectId}/memberships/${member.id}`, {
        method: "PATCH",
        body: JSON.stringify({ status, reason: null }),
      });
      setMessage(`${member.display_name}'s project access is now ${status}.`);
      await loadAccess(projectId);
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="workspace">
      <section className="page-frame">
        <div className="page-heading">
          <div>
            <p className="eyebrow">ADMINISTRATION</p>
            <h1>Project Access</h1>
            <p>Assign active company members to projects and give them project-scoped roles.</p>
          </div>
          <a href="/admin/access">People & roles</a>
        </div>

        {error && <div className="error-banner"><strong>Action not completed</strong><span>{error}</span></div>}
        {message && <div className="workflow-card"><strong>{message}</strong></div>}

        <section className="workflow-card">
          <div><p className="eyebrow">PROJECT</p><h2>Select project</h2></div>
          <select value={projectId} onChange={(event) => setProjectId(event.target.value)} disabled={busy}>
            <option value="">Choose project</option>
            {projects.map((project) => <option key={project.id} value={project.id}>{project.number} · {project.name}</option>)}
          </select>
        </section>

        {projectId && (
          <section className="workflow-card">
            <div><p className="eyebrow">TEAM</p><h2>Add company member</h2><p>Only active company memberships can be added to a project.</p></div>
            <form className="quick-form" onSubmit={addMember}>
              <select name="membership_id" defaultValue="" required disabled={busy}>
                <option value="">Choose person</option>
                {activeCompanyMembers.map((membership) => (
                  <option key={membership.id} value={membership.id}>{membership.display_name} · {membership.primary_email}</option>
                ))}
              </select>
              <input name="title" placeholder="Project title (optional)" disabled={busy} />
              <button disabled={busy}>Add to project</button>
            </form>

            <div className="data-table">
              <div className="table-head four-cols"><span>Person</span><span>Project status</span><span>Project roles</span><span>Action</span></div>
              {access.map((member) => (
                <div className="table-row four-cols" key={member.id}>
                  <span><strong>{member.display_name}</strong><small style={{ display: "block" }}>{member.primary_email}{member.title ? ` · ${member.title}` : ""}</small></span>
                  <span>{member.status}</span>
                  <span>{member.roles.length ? member.roles.map((role) => role.name).join(", ") : "No project role"}</span>
                  <button disabled={busy} onClick={() => openMember(member)}>Manage</button>
                </div>
              ))}
            </div>
          </section>
        )}

        {selectedMember && (
          <section className="workflow-card">
            <div><p className="eyebrow">PROJECT ROLE ASSIGNMENT</p><h2>{selectedMember.display_name}</h2><p>Only Project or Company + project roles are available here.</p></div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
              {selectedMember.status !== "active" && <button disabled={busy} onClick={() => void setStatus(selectedMember, "active")}>Activate project access</button>}
              {selectedMember.status === "active" && <button disabled={busy} onClick={() => void setStatus(selectedMember, "suspended")}>Suspend project access</button>}
              {selectedMember.status !== "ended" && <button disabled={busy} onClick={() => void setStatus(selectedMember, "ended")}>End project access</button>}
            </div>
            <div style={{ display: "grid", gap: 8 }}>
              {projectRoles.map((role) => (
                <label key={role.id} style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <input
                    type="checkbox"
                    checked={roleDraft.has(role.id)}
                    disabled={busy}
                    onChange={(event) => {
                      setRoleDraft((current) => {
                        const next = new Set(current);
                        if (event.target.checked) next.add(role.id); else next.delete(role.id);
                        return next;
                      });
                    }}
                  />
                  <span><strong>{role.name}</strong> <small>({role.assignment_scope})</small></span>
                </label>
              ))}
            </div>
            <button disabled={busy} onClick={() => void saveRoles()}>Save project roles</button>
          </section>
        )}
      </section>
    </main>
  );
}
