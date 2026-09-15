"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

type AccessContext = { permissions: string[] };
type Permission = {
  key: string;
  module: string;
  resource: string;
  action: string;
  description: string;
  risk: "low" | "medium" | "high" | "critical";
};
type RoleScope = "company" | "project" | "both";
type Role = {
  id: string;
  organization_id: string | null;
  key: string;
  name: string;
  description: string | null;
  assignment_scope: RoleScope;
  is_template: boolean;
  is_protected: boolean;
  is_active: boolean;
  version: number;
};
type RoleTemplate = {
  key: string;
  name: string;
  description: string;
  scope_hint: string;
  membership_kind_hint: "internal" | "external" | "service";
  permission_keys: string[];
};
type RolePermissionSet = {
  expected_version: number | null;
  permission_keys: string[];
};
type AssignedRole = {
  id: string;
  key: string;
  name: string;
  assignment_scope: RoleScope;
  is_template: boolean;
  is_protected: boolean;
};
type PartyReference = {
  id: string;
  code: string;
  name: string;
  party_type: string;
};
type Membership = {
  id: string;
  user_id: string;
  primary_email: string;
  display_name: string;
  kind: "internal" | "external" | "service";
  status: "invited" | "active" | "suspended" | "ended";
  role_ids: string[];
  roles: AssignedRole[];
  represented_party_id: string | null;
  represented_party_name: string | null;
  represented_party_type: string | null;
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

function roleKey(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .replace(/-+/g, "-");
}

function riskLabel(value: Permission["risk"]): string {
  return value === "critical" ? "Critical" : value === "high" ? "High" : value === "medium" ? "Medium" : "Low";
}

function scopeLabel(value: RoleScope): string {
  if (value === "company") return "Company";
  if (value === "project") return "Project";
  return "Company + project";
}

export default function AccessManagementWorkspace() {
  const [context, setContext] = useState<AccessContext | null>(null);
  const [roles, setRoles] = useState<Role[]>([]);
  const [templates, setTemplates] = useState<RoleTemplate[]>([]);
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [memberships, setMemberships] = useState<Membership[]>([]);
  const [partyReferences, setPartyReferences] = useState<PartyReference[]>([]);
  const [selectedRoleId, setSelectedRoleId] = useState("");
  const [rolePermissionDraft, setRolePermissionDraft] = useState<Set<string>>(new Set());
  const [rolePermissionVersion, setRolePermissionVersion] = useState<number | null>(null);
  const [selectedMembershipId, setSelectedMembershipId] = useState("");
  const [memberRoleDraft, setMemberRoleDraft] = useState<Set<string>>(new Set());
  const [partyDraft, setPartyDraft] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const canManage = context?.permissions.includes("security.role.manage") ?? false;
  const selectedRole = roles.find((role) => role.id === selectedRoleId) || null;
  const selectedMembership = memberships.find((membership) => membership.id === selectedMembershipId) || null;
  const companyAssignableRoles = roles.filter(
    (role) => role.is_active && (role.assignment_scope === "company" || role.assignment_scope === "both"),
  );

  const groupedPermissions = useMemo(() => {
    const groups = new Map<string, Permission[]>();
    for (const permission of permissions) {
      const current = groups.get(permission.module) || [];
      current.push(permission);
      groups.set(permission.module, current);
    }
    return [...groups.entries()].sort(([left], [right]) => left.localeCompare(right));
  }, [permissions]);

  const load = async () => {
    setError("");
    try {
      const [nextContext, nextRoles, nextTemplates, nextPermissions, nextMemberships, nextParties] = await Promise.all([
        api<AccessContext>("/session/context"),
        api<Role[]>("/security/roles"),
        api<RoleTemplate[]>("/security/role-templates"),
        api<Permission[]>("/security/permissions"),
        api<Membership[]>("/security/memberships"),
        api<PartyReference[]>("/security/party-references"),
      ]);
      setContext(nextContext);
      setRoles(nextRoles);
      setTemplates(nextTemplates);
      setPermissions(nextPermissions);
      setMemberships(nextMemberships);
      setPartyReferences(nextParties);
      if (selectedRoleId && !nextRoles.some((role) => role.id === selectedRoleId)) {
        setSelectedRoleId("");
        setRolePermissionDraft(new Set());
        setRolePermissionVersion(null);
      }
      if (selectedMembershipId && !nextMemberships.some((membership) => membership.id === selectedMembershipId)) {
        setSelectedMembershipId("");
        setMemberRoleDraft(new Set());
        setPartyDraft("");
      }
    } catch (requestError) {
      setError((requestError as Error).message);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const openRole = async (role: Role) => {
    setSelectedRoleId(role.id);
    setError("");
    try {
      const response = await api<RolePermissionSet>(`/security/roles/${role.id}/permissions`);
      setRolePermissionDraft(new Set(response.permission_keys));
      setRolePermissionVersion(response.expected_version);
    } catch (requestError) {
      setError((requestError as Error).message);
    }
  };

  const openMembership = (membership: Membership) => {
    setSelectedMembershipId(membership.id);
    setMemberRoleDraft(new Set(membership.role_ids));
    setPartyDraft(membership.represented_party_id || "");
  };

  const installDefaults = async () => {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const installed = await api<Role[]>("/security/roles/install-defaults", { method: "POST" });
      setMessage(installed.length === 0 ? "All India default roles are already installed." : `Installed ${installed.length} default role${installed.length === 1 ? "" : "s"}.`);
      await load();
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const createRole = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const name = String(form.get("name") || "").trim();
    const key = roleKey(String(form.get("key") || name));
    const description = String(form.get("description") || "").trim() || null;
    const templateKey = String(form.get("template") || "");
    const assignmentScope = String(form.get("assignment_scope") || "project") as RoleScope;
    if (!name || !key) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      if (templateKey) {
        await api<Role>(`/security/roles/from-template/${encodeURIComponent(templateKey)}`, {
          method: "POST",
          body: JSON.stringify({ key, name }),
        });
      } else {
        await api<Role>("/security/roles", {
          method: "POST",
          body: JSON.stringify({ key, name, description, assignment_scope: assignmentScope, permission_keys: [] }),
        });
      }
      event.currentTarget.reset();
      setMessage("Role created. Select it below to configure permissions.");
      await load();
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const saveRolePermissions = async () => {
    if (!selectedRole || rolePermissionVersion === null) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const updated = await api<Role>(`/security/roles/${selectedRole.id}/permissions`, {
        method: "PUT",
        body: JSON.stringify({ expected_version: rolePermissionVersion, permission_keys: [...rolePermissionDraft] }),
      });
      setRolePermissionVersion(updated.version);
      setMessage(`Permissions saved for ${updated.name}.`);
      await load();
      await openRole(updated);
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const addPerson = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const roleId = String(form.get("role_id") || "");
    const representedPartyId = String(form.get("represented_party_id") || "");
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await api<Membership>("/security/memberships", {
        method: "POST",
        body: JSON.stringify({
          primary_email: form.get("primary_email"),
          display_name: form.get("display_name"),
          kind: form.get("kind"),
          status: form.get("status"),
          role_ids: roleId ? [roleId] : [],
          represented_party_id: representedPartyId || null,
        }),
      });
      event.currentTarget.reset();
      setMessage("Person added to the company. Project access can be assigned separately per project.");
      await load();
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const saveMembershipRoles = async () => {
    if (!selectedMembership) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await api<Membership>(`/security/memberships/${selectedMembership.id}/roles`, {
        method: "PUT",
        body: JSON.stringify({ role_ids: [...memberRoleDraft] }),
      });
      setMessage(`Roles updated for ${selectedMembership.display_name}.`);
      await load();
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const savePartyAffiliation = async () => {
    if (!selectedMembership || selectedMembership.kind !== "external") return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const updated = await api<Membership>(`/security/memberships/${selectedMembership.id}/party-affiliation`, {
        method: "PUT",
        body: JSON.stringify({ party_id: partyDraft || null }),
      });
      setPartyDraft(updated.represented_party_id || "");
      setMessage(updated.represented_party_name ? `${updated.display_name} now represents ${updated.represented_party_name}.` : `Party affiliation cleared for ${updated.display_name}.`);
      await load();
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const setMembershipStatus = async (membership: Membership, statusValue: Membership["status"]) => {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const updated = await api<Membership>(`/security/memberships/${membership.id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status: statusValue }),
      });
      setMessage(`${updated.display_name} is now ${updated.status}.`);
      await load();
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
            <h1>People, Roles & Permissions</h1>
            <p>India-first company and project access. Workers remain separate from application users.</p>
          </div>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
            <a href="/admin/project-access">Project access</a>
            <a href="/admin/company">Company settings</a>
          </div>
        </div>

        {error && <div className="error-banner"><strong>Action not completed</strong><span>{error}</span></div>}
        {message && <div className="workflow-card"><strong>{message}</strong></div>}

        <section className="workflow-card">
          <div><p className="eyebrow">DEFAULTS</p><h2>Indian construction role templates</h2><p>Install safe starting roles, then clone or customize them for the company.</p></div>
          <div className="flow-line">
            {templates.map((template) => (
              <div className="flow-step" key={template.key}>
                <strong>{template.name}</strong>
                <small>{template.membership_kind_hint} · {template.scope_hint.replaceAll("_", " ")} · {template.permission_keys.length} permissions</small>
              </div>
            ))}
          </div>
          {canManage && <button disabled={busy} onClick={() => void installDefaults()}>Install missing defaults</button>}
        </section>

        <section className="workflow-card">
          <div><p className="eyebrow">ROLES</p><h2>Create custom role</h2><p>Start blank or copy a recommended template. Project is the safest default scope.</p></div>
          {canManage && (
            <form className="quick-form" onSubmit={createRole}>
              <input name="name" placeholder="Role name" required />
              <input name="key" placeholder="Key (optional)" />
              <select name="template" defaultValue=""><option value="">Blank role</option>{templates.map((template) => <option key={template.key} value={template.key}>Copy: {template.name}</option>)}</select>
              <select name="assignment_scope" defaultValue="project"><option value="project">Project only</option><option value="company">Company wide</option><option value="both">Company or project</option></select>
              <input name="description" placeholder="Description (blank role)" />
              <button disabled={busy}>Create role</button>
            </form>
          )}
          <div className="data-table">
            <div className="table-head four-cols"><span>Role</span><span>Scope / type</span><span>Status</span><span>Action</span></div>
            {roles.map((role) => (
              <div className="table-row four-cols" key={role.id}>
                <span><strong>{role.name}</strong><small style={{ display: "block" }}>{role.key}</small></span>
                <span>{scopeLabel(role.assignment_scope)} · {role.is_protected ? "Protected" : role.is_template ? "Default" : "Custom"}</span>
                <span>{role.is_active ? "Active" : "Inactive"}</span>
                <button onClick={() => void openRole(role)}>Permissions</button>
              </div>
            ))}
          </div>
        </section>

        {selectedRole && (
          <section className="workflow-card">
            <div><p className="eyebrow">PERMISSION EDITOR</p><h2>{selectedRole.name}</h2><p>{scopeLabel(selectedRole.assignment_scope)} scope · {selectedRole.is_protected ? "Protected administrator permissions cannot be edited." : "Changes are server-authoritative and audited."}</p></div>
            {groupedPermissions.map(([module, modulePermissions]) => (
              <details key={module} open={["field", "workforce", "commercial", "projects"].includes(module)}>
                <summary><strong>{module.replaceAll("_", " ").toUpperCase()}</strong> · {modulePermissions.filter((permission) => rolePermissionDraft.has(permission.key)).length}/{modulePermissions.length}</summary>
                <div style={{ display: "grid", gap: 8, padding: "12px 0" }}>
                  {modulePermissions.map((permission) => (
                    <label key={permission.key} style={{ display: "grid", gridTemplateColumns: "24px 1fr auto", gap: 8, alignItems: "start" }}>
                      <input type="checkbox" disabled={!canManage || selectedRole.is_protected || busy} checked={rolePermissionDraft.has(permission.key)} onChange={(event) => setRolePermissionDraft((current) => { const next = new Set(current); if (event.target.checked) next.add(permission.key); else next.delete(permission.key); return next; })} />
                      <span><strong>{permission.resource.replaceAll("_", " ")} · {permission.action.replaceAll("_", " ")}</strong><small style={{ display: "block" }}>{permission.description}</small></span>
                      <small>{riskLabel(permission.risk)}</small>
                    </label>
                  ))}
                </div>
              </details>
            ))}
            {!selectedRole.is_protected && canManage && <button disabled={busy} onClick={() => void saveRolePermissions()}>Save permissions</button>}
          </section>
        )}

        <section className="workflow-card">
          <div><p className="eyebrow">PEOPLE</p><h2>Company memberships</h2><p>Internal staff and selected external people can have logins. Site labour should normally remain Worker/Crew records, not memberships.</p></div>
          {canManage && (
            <form className="quick-form" onSubmit={addPerson}>
              <input type="email" name="primary_email" placeholder="Email" required />
              <input name="display_name" placeholder="Display name" required />
              <select name="kind" defaultValue="internal"><option value="internal">Internal employee</option><option value="external">External party person</option><option value="service">Service account</option></select>
              <select name="status" defaultValue="invited"><option value="invited">Invited</option><option value="active">Active</option></select>
              <select name="represented_party_id" defaultValue=""><option value="">No represented party</option>{partyReferences.map((party) => <option key={party.id} value={party.id}>{party.name} · {party.party_type}</option>)}</select>
              <select name="role_id" defaultValue=""><option value="">No company role yet</option>{companyAssignableRoles.map((role) => <option key={role.id} value={role.id}>{role.name}</option>)}</select>
              <button disabled={busy}>Add person</button>
            </form>
          )}
          <div className="data-table">
            <div className="table-head four-cols"><span>Person</span><span>Membership / party</span><span>Roles</span><span>Action</span></div>
            {memberships.map((membership) => (
              <div className="table-row four-cols" key={membership.id}>
                <span><strong>{membership.display_name}</strong><small style={{ display: "block" }}>{membership.primary_email}</small></span>
                <span>{membership.kind} · {membership.status}{membership.represented_party_name ? <small style={{ display: "block" }}>Represents: {membership.represented_party_name}</small> : null}</span>
                <span>{membership.roles.length ? membership.roles.map((role) => role.name).join(", ") : "No company role"}</span>
                <button onClick={() => openMembership(membership)}>Manage</button>
              </div>
            ))}
          </div>
        </section>

        {selectedMembership && (
          <section className="workflow-card">
            <div><p className="eyebrow">MEMBERSHIP & ROLE ASSIGNMENT</p><h2>{selectedMembership.display_name}</h2><p>Company roles apply across the company. Project-scoped roles must be assigned through Project Access.</p></div>
            {selectedMembership.kind === "external" && (
              <div className="quick-form" style={{ marginBottom: 12 }}>
                <select value={partyDraft} onChange={(event) => setPartyDraft(event.target.value)} disabled={!canManage || busy}>
                  <option value="">No represented party</option>
                  {partyReferences.map((party) => <option key={party.id} value={party.id}>{party.name} · {party.party_type}</option>)}
                </select>
                {canManage && <button disabled={busy} onClick={() => void savePartyAffiliation()}>Save represented party</button>}
              </div>
            )}
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
              {canManage && selectedMembership.status !== "active" && <button disabled={busy} onClick={() => void setMembershipStatus(selectedMembership, "active")}>Activate</button>}
              {canManage && selectedMembership.status === "active" && <button disabled={busy} onClick={() => void setMembershipStatus(selectedMembership, "suspended")}>Suspend</button>}
              {canManage && selectedMembership.status !== "ended" && <button disabled={busy} onClick={() => void setMembershipStatus(selectedMembership, "ended")}>End membership</button>}
            </div>
            <div style={{ display: "grid", gap: 8 }}>
              {companyAssignableRoles.map((role) => (
                <label key={role.id} style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <input type="checkbox" checked={memberRoleDraft.has(role.id)} disabled={!canManage || busy} onChange={(event) => setMemberRoleDraft((current) => { const next = new Set(current); if (event.target.checked) next.add(role.id); else next.delete(role.id); return next; })} />
                  <span><strong>{role.name}</strong> <small>({scopeLabel(role.assignment_scope)} · {role.is_protected ? "protected" : role.is_template ? "default" : "custom"})</small></span>
                </label>
              ))}
            </div>
            {canManage && <button disabled={busy} onClick={() => void saveMembershipRoles()}>Save company role assignment</button>}
          </section>
        )}
      </section>
    </main>
  );
}
