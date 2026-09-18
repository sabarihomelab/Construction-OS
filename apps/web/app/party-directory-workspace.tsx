"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

type AccessContext = {
  permissions: string[];
  project_permissions: Record<string, string[]>;
};
type Project = { id: string; number: string; name: string };
type Party = {
  id: string;
  code: string;
  name: string;
  legal_name: string | null;
  party_type: string;
  status: string;
  gstin: string | null;
  pan: string | null;
  email: string | null;
  phone: string | null;
  address_line_1: string | null;
  address_line_2: string | null;
  locality: string | null;
  state_name: string | null;
  state_code: string | null;
  postal_code: string | null;
  payment_terms_days: number | null;
  notes: string | null;
  revision: number;
};
type Assignment = {
  id: string;
  project_id: string;
  party_id: string;
  role: string;
  active: boolean;
  updated_at: string;
};

class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
const PARTY_TYPES = [
  "client",
  "consultant",
  "subcontractor",
  "supplier",
  "labour_contractor",
  "other",
];
const PROJECT_ROLES = [
  "client",
  "pmc",
  "consultant",
  "subcontractor",
  "supplier",
  "labour_contractor",
  "other",
];

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
    throw new ApiError(response.status, message);
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

function textValue(form: FormData, name: string): string | null {
  const value = String(form.get(name) || "").trim();
  return value || null;
}

export default function PartyDirectoryWorkspace({ partyId }: { partyId?: string }) {
  const [context, setContext] = useState<AccessContext | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [parties, setParties] = useState<Party[]>([]);
  const [party, setParty] = useState<Party | null>(null);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [query, setQuery] = useState("");
  const [partyType, setPartyType] = useState("all");
  const [partyStatus, setPartyStatus] = useState("all");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const canOrg = useCallback(
    (permission: string) => context?.permissions.includes(permission) ?? false,
    [context],
  );
  const canProject = useCallback(
    (permission: string, projectId: string) => {
      if (!context) return false;
      return (
        context.permissions.includes(permission) ||
        (context.project_permissions[projectId] || []).includes(permission)
      );
    },
    [context],
  );

  const load = useCallback(async () => {
    setError("");
    try {
      const nextContext = await api<AccessContext>("/session/context");
      setContext(nextContext);
      const projectRows = await api<Project[]>("/projects");
      setProjects(projectRows);
      if (partyId) {
        const currentParty = await api<Party>(`/commercial/parties/${partyId}`);
        setParty(currentParty);
        const visibleProjects = projectRows.filter(
          (project) =>
            nextContext.permissions.includes("commercial.party.view") ||
            (nextContext.project_permissions[project.id] || []).includes(
              "commercial.party.view",
            ),
        );
        const assignmentGroups = await Promise.all(
          visibleProjects.map((project) =>
            api<Assignment[]>(
              `/projects/${project.id}/commercial/party-assignments?party_id=${partyId}&include_inactive=true`,
            ),
          ),
        );
        setAssignments(assignmentGroups.flat());
      } else {
        setParties(await api<Party[]>("/commercial/parties"));
      }
    } catch (requestError) {
      setError((requestError as Error).message);
    }
  }, [partyId]);

  useEffect(() => {
    void load();
  }, [load]);

  const assignmentByProject = useMemo(() => {
    const grouped = new Map<string, Assignment[]>();
    assignments.forEach((assignment) => {
      grouped.set(assignment.project_id, [
        ...(grouped.get(assignment.project_id) || []),
        assignment,
      ]);
    });
    return grouped;
  }, [assignments]);

  const filteredParties = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return parties.filter((item) => {
      const matchesQuery =
        !normalizedQuery ||
        [
          item.code,
          item.name,
          item.legal_name,
          item.gstin,
          item.pan,
          item.email,
          item.phone,
          item.locality,
          item.state_name,
        ]
          .filter(Boolean)
          .some((value) => String(value).toLowerCase().includes(normalizedQuery));
      const matchesType = partyType === "all" || item.party_type === partyType;
      const matchesStatus = partyStatus === "all" || item.status === partyStatus;
      return matchesQuery && matchesType && matchesStatus;
    });
  }, [parties, partyStatus, partyType, query]);

  const createParty = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const element = event.currentTarget;
    const form = new FormData(element);
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api<Party>("/commercial/parties", {
        method: "POST",
        body: JSON.stringify({
          code: String(form.get("code") || "").trim(),
          name: String(form.get("name") || "").trim(),
          legal_name: textValue(form, "legal_name"),
          party_type: form.get("party_type"),
          gstin: textValue(form, "gstin"),
          pan: textValue(form, "pan"),
          email: textValue(form, "email"),
          phone: textValue(form, "phone"),
          address_line_1: textValue(form, "address_line_1"),
          address_line_2: textValue(form, "address_line_2"),
          locality: textValue(form, "locality"),
          state_name: textValue(form, "state_name"),
          state_code: textValue(form, "state_code"),
          postal_code: textValue(form, "postal_code"),
          payment_terms_days: form.get("payment_terms_days")
            ? Number(form.get("payment_terms_days"))
            : null,
          notes: textValue(form, "notes"),
        }),
      });
      element.reset();
      setNotice("Party created successfully.");
      await load();
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const updateParty = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!party) return;
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api<Party>(`/commercial/parties/${party.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          expected_revision: party.revision,
          name: String(form.get("name") || "").trim(),
          legal_name: textValue(form, "legal_name"),
          party_type: form.get("party_type"),
          status: form.get("status"),
          gstin: textValue(form, "gstin"),
          pan: textValue(form, "pan"),
          email: textValue(form, "email"),
          phone: textValue(form, "phone"),
          address_line_1: textValue(form, "address_line_1"),
          address_line_2: textValue(form, "address_line_2"),
          locality: textValue(form, "locality"),
          state_name: textValue(form, "state_name"),
          state_code: textValue(form, "state_code"),
          postal_code: textValue(form, "postal_code"),
          payment_terms_days: form.get("payment_terms_days")
            ? Number(form.get("payment_terms_days"))
            : null,
          notes: textValue(form, "notes"),
          reason: "Updated from Party Directory",
        }),
      });
      setNotice("Party details saved.");
      await load();
    } catch (requestError) {
      if (requestError instanceof ApiError && requestError.status === 409) {
        await load();
        setError("This party changed after you opened it. The latest revision has been loaded; review the values and save again.");
      } else {
        setError((requestError as Error).message);
      }
    } finally {
      setBusy(false);
    }
  };

  const assignRole = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!party) return;
    const form = new FormData(event.currentTarget);
    const projectId = String(form.get("project_id") || "");
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api<Assignment>(`/projects/${projectId}/commercial/parties`, {
        method: "POST",
        body: JSON.stringify({ party_id: party.id, role: form.get("role") }),
      });
      setNotice("Project role assigned.");
      await load();
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const setAssignmentActive = async (assignment: Assignment, active: boolean) => {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api<Assignment>(
        `/projects/${assignment.project_id}/commercial/party-assignments/${assignment.id}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            expected_updated_at: assignment.updated_at,
            active,
            reason: active
              ? "Reactivated from Party Directory"
              : "Deactivated from Party Directory",
          }),
        },
      );
      setNotice(active ? "Project role reactivated." : "Project role deactivated.");
      await load();
    } catch (requestError) {
      if (requestError instanceof ApiError && requestError.status === 409) {
        await load();
        setError("This project assignment changed after you opened it. The latest state has been loaded; try the action again if it is still required.");
      } else {
        setError((requestError as Error).message);
      }
    } finally {
      setBusy(false);
    }
  };

  if (!partyId) {
    return (
      <main className="workspace">
        <section className="page-frame">
          <div className="page-heading">
            <div>
              <p className="eyebrow">MODULE 1</p>
              <h1>Party Directory</h1>
              <p>One company-wide business partner master reused across projects and roles.</p>
            </div>
          </div>
          {error && (
            <div className="error-banner">
              <strong>Action not completed</strong><span>{error}</span>
            </div>
          )}
          {notice && (
            <div className="success-banner">
              <strong>Saved</strong><span>{notice}</span>
            </div>
          )}
          <section className="workflow-card">
            <div>
              <p className="eyebrow">FIND A PARTY</p>
              <h2>Directory</h2>
              <small>{filteredParties.length} of {parties.length} parties shown</small>
            </div>
            <div className="quick-form">
              <input
                aria-label="Search parties"
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search code, name, GSTIN, PAN, email, phone or location"
                type="search"
                value={query}
              />
              <select aria-label="Filter by party type" onChange={(event) => setPartyType(event.target.value)} value={partyType}>
                <option value="all">All types</option>
                {PARTY_TYPES.map((value) => (
                  <option key={value} value={value}>{value.replaceAll("_", " ")}</option>
                ))}
              </select>
              <select aria-label="Filter by party status" onChange={(event) => setPartyStatus(event.target.value)} value={partyStatus}>
                <option value="all">All statuses</option>
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
              </select>
            </div>
          </section>
          {canOrg("commercial.party.manage") && (
            <section className="workflow-card">
              <div>
                <p className="eyebrow">NEW PARTY</p>
                <h2>Create business partner</h2>
                <small>Create the reusable company master once, then assign project roles from its detail page.</small>
              </div>
              <form className="quick-form" onSubmit={createParty}>
                <input name="code" placeholder="Code" required />
                <input name="name" placeholder="Party name" required />
                <input name="legal_name" placeholder="Legal name" />
                <select name="party_type" defaultValue="supplier">
                  {PARTY_TYPES.map((value) => (
                    <option key={value} value={value}>{value.replaceAll("_", " ")}</option>
                  ))}
                </select>
                <input name="gstin" placeholder="GSTIN" minLength={15} maxLength={15} />
                <input name="pan" placeholder="PAN" minLength={10} maxLength={10} />
                <input name="email" placeholder="Email" type="email" />
                <input name="phone" placeholder="Phone" />
                <input name="address_line_1" placeholder="Address line 1" />
                <input name="address_line_2" placeholder="Address line 2" />
                <input name="locality" placeholder="City / locality" />
                <input name="state_name" placeholder="State" />
                <input name="state_code" placeholder="State code" minLength={2} maxLength={2} />
                <input name="postal_code" placeholder="PIN code" />
                <input name="payment_terms_days" type="number" min="0" max="3650" placeholder="Payment terms days" />
                <input name="notes" placeholder="Notes" />
                <button disabled={busy}>{busy ? "Saving…" : "Add party"}</button>
              </form>
            </section>
          )}
          {parties.length === 0 ? (
            <div className="empty-state">
              <strong>No parties yet</strong>
              <p>Add the first real client, supplier, subcontractor, consultant or labour contractor.</p>
            </div>
          ) : filteredParties.length === 0 ? (
            <div className="empty-state">
              <strong>No matching parties</strong>
              <p>Change the search text or filters to see other business partners.</p>
            </div>
          ) : (
            <div className="data-table">
              <div className="table-head">
                <span>Code</span><span>Name</span><span>Type</span><span>GSTIN</span><span>Status</span>
              </div>
              {filteredParties.map((item) => (
                <div className="table-row" key={item.id}>
                  <strong>{item.code}</strong>
                  <span><Link href={`/commercial/parties/${item.id}`}>{item.name}</Link></span>
                  <span>{item.party_type.replaceAll("_", " ")}</span>
                  <span>{item.gstin || "—"}</span>
                  <Status value={item.status} />
                </div>
              ))}
            </div>
          )}
        </section>
      </main>
    );
  }

  return (
    <main className="workspace">
      <section className="page-frame">
        <div className="page-heading">
          <div>
            <p className="eyebrow">PARTY DETAIL</p>
            <h1>{party?.name || "Party"}</h1>
            <p><Link href="/commercial/parties">← Party Directory</Link></p>
          </div>
          {party && <Status value={party.status} />}
        </div>
        {error && (
          <div className="error-banner">
            <strong>Action not completed</strong><span>{error}</span>
          </div>
        )}
        {notice && (
          <div className="success-banner">
            <strong>Saved</strong><span>{notice}</span>
          </div>
        )}
        {!party ? (
          <div className="empty-state"><strong>Loading party…</strong></div>
        ) : (
          <>
            <section className="workflow-card">
              <div>
                <p className="eyebrow">MASTER DATA</p>
                <h2>{party.code}</h2>
                <small>Revision {party.revision}</small>
              </div>
              <form className="quick-form" onSubmit={updateParty}>
                <input name="name" defaultValue={party.name} disabled={!canOrg("commercial.party.manage") || busy} required />
                <input name="legal_name" defaultValue={party.legal_name || ""} placeholder="Legal name" disabled={!canOrg("commercial.party.manage") || busy} />
                <select name="party_type" defaultValue={party.party_type} disabled={!canOrg("commercial.party.manage") || busy}>
                  {PARTY_TYPES.map((value) => (
                    <option key={value} value={value}>{value.replaceAll("_", " ")}</option>
                  ))}
                </select>
                <select name="status" defaultValue={party.status} disabled={!canOrg("commercial.party.manage") || busy}>
                  <option value="active">Active</option>
                  <option value="inactive">Inactive</option>
                </select>
                <input name="gstin" defaultValue={party.gstin || ""} placeholder="GSTIN" minLength={15} maxLength={15} disabled={!canOrg("commercial.party.manage") || busy} />
                <input name="pan" defaultValue={party.pan || ""} placeholder="PAN" minLength={10} maxLength={10} disabled={!canOrg("commercial.party.manage") || busy} />
                <input name="email" type="email" defaultValue={party.email || ""} placeholder="Email" disabled={!canOrg("commercial.party.manage") || busy} />
                <input name="phone" defaultValue={party.phone || ""} placeholder="Phone" disabled={!canOrg("commercial.party.manage") || busy} />
                <input name="address_line_1" defaultValue={party.address_line_1 || ""} placeholder="Address line 1" disabled={!canOrg("commercial.party.manage") || busy} />
                <input name="address_line_2" defaultValue={party.address_line_2 || ""} placeholder="Address line 2" disabled={!canOrg("commercial.party.manage") || busy} />
                <input name="locality" defaultValue={party.locality || ""} placeholder="City / locality" disabled={!canOrg("commercial.party.manage") || busy} />
                <input name="state_name" defaultValue={party.state_name || ""} placeholder="State" disabled={!canOrg("commercial.party.manage") || busy} />
                <input name="state_code" defaultValue={party.state_code || ""} placeholder="State code" minLength={2} maxLength={2} disabled={!canOrg("commercial.party.manage") || busy} />
                <input name="postal_code" defaultValue={party.postal_code || ""} placeholder="PIN code" disabled={!canOrg("commercial.party.manage") || busy} />
                <input name="payment_terms_days" type="number" min="0" max="3650" defaultValue={party.payment_terms_days ?? ""} placeholder="Payment terms days" disabled={!canOrg("commercial.party.manage") || busy} />
                <input name="notes" defaultValue={party.notes || ""} placeholder="Notes" disabled={!canOrg("commercial.party.manage") || busy} />
                <button disabled={!canOrg("commercial.party.manage") || busy}>{busy ? "Saving…" : "Save party"}</button>
              </form>
            </section>
            <section className="workflow-card">
              <div>
                <p className="eyebrow">PROJECT ROLES</p>
                <h2>Assignments</h2>
                <small>The same Party may hold different roles on different projects.</small>
              </div>
              {projects.some((project) => canProject("commercial.party.manage", project.id)) && (
                <form className="quick-form" onSubmit={assignRole}>
                  <select name="project_id" required>
                    {projects
                      .filter((project) => canProject("commercial.party.manage", project.id))
                      .map((project) => (
                        <option key={project.id} value={project.id}>{project.number} · {project.name}</option>
                      ))}
                  </select>
                  <select name="role" defaultValue="supplier">
                    {PROJECT_ROLES.map((value) => (
                      <option key={value} value={value}>{value.replaceAll("_", " ")}</option>
                    ))}
                  </select>
                  <button disabled={busy || party.status !== "active"}>{busy ? "Saving…" : "Assign role"}</button>
                </form>
              )}
              {assignments.length === 0 ? (
                <div className="empty-state">
                  <strong>No project roles</strong>
                  <p>Assign this Party only where it participates in a project.</p>
                </div>
              ) : (
                <div className="record-list">
                  {projects.map((project) =>
                    (assignmentByProject.get(project.id) || []).map((assignment) => (
                      <article className="record-card" key={assignment.id}>
                        <div>
                          <strong>{project.number} · {project.name}</strong>
                          <small>{assignment.role.replaceAll("_", " ")}</small>
                        </div>
                        <div className="record-actions">
                          <Status value={assignment.active ? "active" : "inactive"} />
                          {canProject("commercial.party.manage", project.id) && (
                            <button
                              className="secondary"
                              disabled={busy}
                              onClick={() => void setAssignmentActive(assignment, !assignment.active)}
                              type="button"
                            >
                              {assignment.active ? "Deactivate" : "Reactivate"}
                            </button>
                          )}
                        </div>
                      </article>
                    )),
                  )}
                </div>
              )}
            </section>
          </>
        )}
      </section>
    </main>
  );
}
