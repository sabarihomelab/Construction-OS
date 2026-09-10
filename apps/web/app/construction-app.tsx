"use client";

import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";

type Feature = { key: string; name: string; route: string | null };
type AccessContext = {
  organization_id: string;
  membership_id: string;
  permissions: string[];
  project_permissions: Record<string, string[]>;
  features: Feature[];
};
type Project = {
  id: string;
  number: string;
  name: string;
  status: string;
  locality: string | null;
  region: string | null;
};
type Party = {
  id: string;
  code: string;
  name: string;
  party_type: string;
  status: string;
  gstin: string | null;
  phone: string | null;
  revision: number;
};
type WBS = {
  id: string;
  parent_id: string | null;
  code: string;
  name: string;
  kind: string;
  status: string;
  revision: number;
};
type BOQ = {
  id: string;
  code: string;
  name: string;
  status: string;
  currency_code: string;
  revision: number;
};
type BOQItem = {
  id: string;
  line_number: number;
  item_code: string;
  description: string;
  unit_code: string;
  quantity: string;
  rate: string;
  amount: string;
  revision: number;
};
type BOQDetail = BOQ & { items: BOQItem[]; total_amount: string };
type Measurement = {
  id: string;
  entry_number: number;
  boq_item_id: string;
  measurement_date: string;
  location: string | null;
  quantity: string;
  unit_code: string;
  status: string;
  revision: number;
};
type RABill = {
  id: string;
  bill_number: string;
  counterparty_id: string;
  period_start: string;
  period_end: string;
  status: string;
  currency_code: string;
  gross_amount: string;
  net_payable: string;
  revision: number;
};
type Dashboard = {
  boq_value: string;
  measured_value: string;
  certified_measurement_value: string;
  submitted_bill_value: string;
  certified_bill_value: string;
  open_measurements: number;
  draft_bills: number;
};
type Health = {
  status: string;
  environment_name: string;
  runtime_modules: string[];
};
type RealtimeBatch = {
  next_cursor: number;
  events: Array<{
    sequence: number;
    event_type: string;
    scope_type: string | null;
    scope_id: string | null;
  }>;
};

type View = "overview" | "parties" | "wbs" | "boq" | "measurements" | "billing" | "assistant";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
const API_ORIGIN = API_BASE.replace(/\/api\/v1\/?$/, "");

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
      const body = await response.json();
      if (body?.detail) message = String(body.detail);
    } catch {}
    const error = new Error(message) as Error & { status?: number };
    error.status = response.status;
    throw error;
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

function money(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "—";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(numeric);
}

function Status({ value }: { value: string }) {
  return <span className={`status-pill status-${value.replaceAll("_", "-")}`}>{value.replaceAll("_", " ")}</span>;
}

function Empty({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="empty-state">
      <strong>{title}</strong>
      <p>{detail}</p>
    </div>
  );
}

export default function ConstructionApp() {
  const [health, setHealth] = useState<Health | null>(null);
  const [context, setContext] = useState<AccessContext | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [view, setView] = useState<View>("overview");
  const [parties, setParties] = useState<Party[]>([]);
  const [wbs, setWbs] = useState<WBS[]>([]);
  const [boqs, setBoqs] = useState<BOQ[]>([]);
  const [selectedBoq, setSelectedBoq] = useState<BOQDetail | null>(null);
  const [measurements, setMeasurements] = useState<Measurement[]>([]);
  const [bills, setBills] = useState<RABill[]>([]);
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [authMissing, setAuthMissing] = useState(false);
  const [lastEvent, setLastEvent] = useState<string>("");
  const eventCursor = useRef(0);

  const project = projects.find((item) => item.id === projectId) || null;
  const projectPermissions = useMemo(() => {
    if (!context) return new Set<string>();
    return new Set([
      ...context.permissions,
      ...(projectId ? context.project_permissions[projectId] || [] : []),
    ]);
  }, [context, projectId]);
  const can = useCallback((permission: string) => projectPermissions.has(permission), [projectPermissions]);

  const loadProjectData = useCallback(async () => {
    if (!projectId || !context) return;
    const tasks: Promise<unknown>[] = [];
    const apply = <T,>(permission: string, path: string, setter: (value: T) => void) => {
      if (!can(permission)) return;
      tasks.push(api<T>(path).then(setter));
    };
    apply<Dashboard>("commercial.boq.view", `/projects/${projectId}/commercial/dashboard`, setDashboard);
    apply<WBS[]>("commercial.wbs.view", `/projects/${projectId}/commercial/wbs`, setWbs);
    apply<BOQ[]>("commercial.boq.view", `/projects/${projectId}/commercial/boqs`, setBoqs);
    apply<Measurement[]>(
      "commercial.measurement.view",
      `/projects/${projectId}/commercial/measurements`,
      setMeasurements,
    );
    apply<RABill[]>("commercial.ra_bill.view", `/projects/${projectId}/commercial/ra-bills`, setBills);
    if (can("commercial.party.view")) {
      tasks.push(api<Party[]>("/commercial/parties").then(setParties));
    }
    await Promise.all(tasks);
  }, [can, context, projectId]);

  const bootstrap = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const healthResponse = await fetch(`${API_ORIGIN}/health/ready`, { cache: "no-store" });
      if (healthResponse.ok) setHealth((await healthResponse.json()) as Health);
      const session = await api<AccessContext>("/session/context");
      setContext(session);
      setAuthMissing(false);
      const projectRows = await api<Project[]>("/projects");
      setProjects(projectRows);
      setProjectId((current) => current || projectRows[0]?.id || "");
      if (session.permissions.includes("commercial.party.view")) {
        setParties(await api<Party[]>("/commercial/parties"));
      }
    } catch (requestError) {
      const typed = requestError as Error & { status?: number };
      if (typed.status === 401) setAuthMissing(true);
      else setError(typed.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void bootstrap();
  }, [bootstrap]);

  useEffect(() => {
    if (!context || !projectId) return;
    void loadProjectData().catch((requestError: Error) => setError(requestError.message));
  }, [context, projectId, loadProjectData]);

  useEffect(() => {
    if (!context) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const poll = async () => {
      try {
        const batch = await api<RealtimeBatch>(`/realtime/events?after=${eventCursor.current}&limit=100`);
        eventCursor.current = batch.next_cursor;
        const relevant = batch.events.filter(
          (event) => !event.scope_id || !projectId || event.scope_id === projectId,
        );
        if (relevant.length > 0) {
          setLastEvent(relevant.at(-1)?.event_type || "updated");
          await loadProjectData();
        }
      } catch {}
      if (!stopped) timer = setTimeout(poll, 3500);
    };
    void poll();
    return () => {
      stopped = true;
      if (timer) clearTimeout(timer);
    };
  }, [context, loadProjectData, projectId]);

  const mutate = async (work: () => Promise<unknown>) => {
    setBusy(true);
    setError("");
    try {
      await work();
      await loadProjectData();
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const openBoq = async (id: string) => {
    if (!projectId) return;
    setError("");
    try {
      setSelectedBoq(await api<BOQDetail>(`/projects/${projectId}/commercial/boqs/${id}`));
    } catch (requestError) {
      setError((requestError as Error).message);
    }
  };

  const submitJson = (path: string, payload: unknown, method = "POST") =>
    api(path, { method, body: JSON.stringify(payload) });

  const formJson = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    return new FormData(event.currentTarget);
  };

  const nav: Array<[View, string, string]> = [
    ["overview", "Overview", "01"],
    ["parties", "Parties", "02"],
    ["wbs", "WBS / Cost Codes", "03"],
    ["boq", "BOQ", "04"],
    ["measurements", "Measurements", "05"],
    ["billing", "RA Billing", "06"],
    ["assistant", "Assistant", "AI"],
  ];

  if (loading) {
    return <main className="boot-screen"><div className="boot-mark">COS</div><p>Loading installation state…</p></main>;
  }

  if (authMissing) {
    return (
      <main className="auth-screen">
        <section className="auth-card">
          <div className="boot-mark">COS</div>
          <p className="eyebrow">SECURE WORKSPACE</p>
          <h1>Construction OS is running.</h1>
          <p>
            The application API is available, but this browser does not have an authenticated company session.
            Connect the configured identity provider or complete the authorized administrator bootstrap before using project data.
          </p>
          {health && <small>{health.environment_name} · {health.runtime_modules.length} runtime modules loaded</small>}
          <button onClick={() => void bootstrap()}>Check session again</button>
        </section>
      </main>
    );
  }

  return (
    <main className="app-shell">
      <aside className="app-sidebar">
        <div className="sidebar-brand"><span>COS</span><div><strong>Construction OS</strong><small>India</small></div></div>
        <nav className="primary-nav" aria-label="Primary">
          {nav.map(([key, label, index]) => (
            <button className={view === key ? "nav-item active" : "nav-item"} key={key} onClick={() => setView(key)}>
              <span>{index}</span>{label}
            </button>
          ))}
        </nav>
        <div className="sidebar-foot">
          <span className={health?.status === "ready" ? "health-dot ready" : "health-dot"} />
          <div><strong>{health?.status === "ready" ? "System ready" : "System status unknown"}</strong><small>{lastEvent ? `Live: ${lastEvent}` : "Realtime connected"}</small></div>
        </div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div className="project-switcher">
            <span>Project</span>
            <select value={projectId} onChange={(event) => { setProjectId(event.target.value); setSelectedBoq(null); }}>
              {projects.map((item) => <option key={item.id} value={item.id}>{item.number} · {item.name}</option>)}
            </select>
          </div>
          <div className="topbar-meta">
            <span>INR</span><span>Asia/Kolkata</span><button className="icon-button" onClick={() => void loadProjectData()}>↻</button>
          </div>
        </header>

        <div className="mobile-tabs">
          {nav.map(([key, label]) => <button className={view === key ? "active" : ""} key={key} onClick={() => setView(key)}>{label}</button>)}
        </div>

        <section className="page-frame">
          {error && <div className="error-banner"><strong>Action not completed</strong><span>{error}</span><button onClick={() => setError("")}>×</button></div>}
          {!project && <Empty title="No accessible project" detail="Create a project or ask an administrator to grant project access." />}

          {project && view === "overview" && (
            <>
              <div className="page-heading">
                <div><p className="eyebrow">PROJECT CONTROL ROOM</p><h1>{project.name}</h1><p>{project.number}{project.locality ? ` · ${project.locality}` : ""}{project.region ? `, ${project.region}` : ""}</p></div>
                <Status value={project.status} />
              </div>
              <div className="metric-grid">
                <article><span>Approved BOQ value</span><strong>{money(dashboard?.boq_value)}</strong><small>Contract baseline</small></article>
                <article><span>Measured work</span><strong>{money(dashboard?.measured_value)}</strong><small>{dashboard?.open_measurements ?? "—"} open measurements</small></article>
                <article><span>Certified work</span><strong>{money(dashboard?.certified_measurement_value)}</strong><small>Measurement certification</small></article>
                <article><span>Certified RA bills</span><strong>{money(dashboard?.certified_bill_value)}</strong><small>{dashboard?.draft_bills ?? "—"} draft bills</small></article>
              </div>
              <div className="workflow-card">
                <div><p className="eyebrow">LIVE COMMERCIAL FLOW</p><h2>From contract quantity to certified bill</h2></div>
                <div className="flow-line">
                  {[["WBS", wbs.length], ["BOQ", boqs.length], ["Measurement", measurements.length], ["RA bill", bills.length]].map(([label, count], index) => (
                    <div className="flow-step" key={String(label)}><span>{index + 1}</span><strong>{label}</strong><small>{count} records</small></div>
                  ))}
                </div>
              </div>
            </>
          )}

          {project && view === "parties" && (
            <DataSection title="Parties & Project Directory" detail="Clients, consultants, subcontractors, suppliers and labour contractors. Company tax identifiers remain data, not hard-coded tax logic.">
              {can("commercial.party.manage") && <form className="quick-form" onSubmit={(event) => { const form = formJson(event); void mutate(async () => { await submitJson("/commercial/parties", { code: form.get("code"), name: form.get("name"), party_type: form.get("party_type"), gstin: form.get("gstin") || null, phone: form.get("phone") || null }); event.currentTarget.reset(); }); }}>
                <input name="code" placeholder="Code" required /><input name="name" placeholder="Party name" required />
                <select name="party_type" defaultValue="subcontractor"><option value="client">Client</option><option value="consultant">Consultant</option><option value="subcontractor">Subcontractor</option><option value="supplier">Supplier</option><option value="labour_contractor">Labour contractor</option><option value="other">Other</option></select>
                <input name="gstin" placeholder="GSTIN (optional)" minLength={15} maxLength={15} /><input name="phone" placeholder="Phone" /><button disabled={busy}>Add party</button>
              </form>}
              {parties.length === 0 ? <Empty title="No parties yet" detail="Add the first real client, supplier, subcontractor or consultant." /> : <div className="data-table"><div className="table-head"><span>Code</span><span>Name</span><span>Type</span><span>GSTIN</span><span>Status</span></div>{parties.map((item) => <div className="table-row" key={item.id}><strong>{item.code}</strong><span>{item.name}</span><span>{item.party_type.replaceAll("_", " ")}</span><span>{item.gstin || "—"}</span><Status value={item.status} /></div>)}</div>}
            </DataSection>
          )}

          {project && view === "wbs" && (
            <DataSection title="WBS & Cost Codes" detail="A project-owned hierarchy used by BOQ, procurement, field quantities and job-cost reporting.">
              {can("commercial.wbs.manage") && <form className="quick-form four" onSubmit={(event) => { const form = formJson(event); void mutate(async () => { await submitJson(`/projects/${projectId}/commercial/wbs`, { code: form.get("code"), name: form.get("name"), kind: form.get("kind"), parent_id: form.get("parent_id") || null }); event.currentTarget.reset(); }); }}>
                <input name="code" placeholder="Code e.g. CIV.CONC" required /><input name="name" placeholder="Name" required /><select name="kind" defaultValue="cost_code"><option value="group">Group</option><option value="trade">Trade</option><option value="work_package">Work package</option><option value="cost_code">Cost code</option></select><select name="parent_id" defaultValue=""><option value="">No parent</option>{wbs.map((item) => <option value={item.id} key={item.id}>{item.code} · {item.name}</option>)}</select><button disabled={busy}>Add WBS code</button>
              </form>}
              {wbs.length === 0 ? <Empty title="No WBS yet" detail="Start with the project control structure before loading the BOQ." /> : <div className="data-table"><div className="table-head four-cols"><span>Code</span><span>Name</span><span>Type</span><span>Status</span></div>{wbs.map((item) => <div className="table-row four-cols" key={item.id}><strong>{item.code}</strong><span>{item.name}</span><span>{item.kind.replaceAll("_", " ")}</span><Status value={item.status} /></div>)}</div>}
            </DataSection>
          )}

          {project && view === "boq" && (
            <DataSection title="Bill of Quantities" detail="Draft BOQs are editable. Approval freezes an immutable commercial snapshot; measurements can only reference approved BOQ items.">
              {can("commercial.boq.manage") && <form className="quick-form four" onSubmit={(event) => { const form = formJson(event); void mutate(async () => { await submitJson(`/projects/${projectId}/commercial/boqs`, { code: form.get("code"), name: form.get("name"), currency_code: "INR" }); event.currentTarget.reset(); }); }}><input name="code" placeholder="BOQ code" required /><input name="name" placeholder="BOQ name" required /><input value="INR" readOnly /><button disabled={busy}>Create BOQ</button></form>}
              <div className="split-layout">
                <div>{boqs.length === 0 ? <Empty title="No BOQ yet" detail="Create the contractual or internal BOQ baseline." /> : boqs.map((item) => <button className={selectedBoq?.id === item.id ? "list-card selected" : "list-card"} key={item.id} onClick={() => void openBoq(item.id)}><div><strong>{item.code} · {item.name}</strong><small>Revision {item.revision}</small></div><Status value={item.status} /></button>)}</div>
                <div className="detail-panel">{selectedBoq ? <><div className="detail-title"><div><p className="eyebrow">BOQ DETAIL</p><h3>{selectedBoq.name}</h3></div><strong>{money(selectedBoq.total_amount)}</strong></div>{selectedBoq.status === "draft" && can("commercial.boq.manage") && <form className="line-form" onSubmit={(event) => { const form = formJson(event); void mutate(async () => { await submitJson(`/projects/${projectId}/commercial/boqs/${selectedBoq.id}/items`, { line_number: Number(form.get("line_number")), item_code: form.get("item_code"), description: form.get("description"), unit_code: form.get("unit_code"), quantity: form.get("quantity"), rate: form.get("rate"), wbs_code_id: form.get("wbs_code_id") || null }); await openBoq(selectedBoq.id); event.currentTarget.reset(); }); }}><input name="line_number" type="number" min="1" placeholder="Line" required /><input name="item_code" placeholder="Item code" required /><input className="wide" name="description" placeholder="Description" required /><select name="wbs_code_id" defaultValue=""><option value="">WBS</option>{wbs.map((item) => <option key={item.id} value={item.id}>{item.code}</option>)}</select><input name="unit_code" placeholder="Unit" required /><input name="quantity" type="number" min="0" step="0.001" placeholder="Qty" required /><input name="rate" type="number" min="0" step="0.01" placeholder="Rate" required /><button disabled={busy}>Add item</button></form>}{selectedBoq.items.length === 0 ? <Empty title="No BOQ items" detail="Add item quantities and rates before approval." /> : <div className="boq-lines">{selectedBoq.items.map((item) => <div className="boq-line" key={item.id}><span>{item.line_number}</span><div><strong>{item.item_code} · {item.description}</strong><small>{item.quantity} {item.unit_code} × {money(item.rate)}</small></div><b>{money(item.amount)}</b></div>)}</div>}{selectedBoq.status === "draft" && can("commercial.boq.approve") && <button className="approve-button" disabled={busy || selectedBoq.items.length === 0} onClick={() => void mutate(async () => { await submitJson(`/projects/${projectId}/commercial/boqs/${selectedBoq.id}/approve`, { expected_revision: selectedBoq.revision, reason: "Approved from project commercial workspace" }); await openBoq(selectedBoq.id); })}>Approve BOQ baseline</button>}</> : <Empty title="Select a BOQ" detail="Open a BOQ to see items, value and approval state." />}</div>
              </div>
            </DataSection>
          )}

          {project && view === "measurements" && (
            <DataSection title="Measurement Book" detail="Site quantities are recorded against approved BOQ items, submitted, then independently certified or rejected.">
              {can("commercial.measurement.create") && <MeasurementForm boqs={boqs} projectId={projectId} busy={busy} onMutate={mutate} submitJson={submitJson} />}
              {measurements.length === 0 ? <Empty title="No measurements yet" detail="Approve a BOQ, then record the first measured quantity." /> : <div className="record-list">{measurements.map((item) => <article className="record-card" key={item.id}><div><span className="record-number">MB #{item.entry_number}</span><strong>{item.quantity} {item.unit_code}</strong><small>{item.measurement_date}{item.location ? ` · ${item.location}` : ""}</small></div><div className="record-actions"><Status value={item.status} />{["draft", "rejected"].includes(item.status) && can("commercial.measurement.submit") && <button disabled={busy} onClick={() => void mutate(() => submitJson(`/projects/${projectId}/commercial/measurements/${item.id}/submit`, { expected_revision: item.revision }))}>Submit</button>}{item.status === "submitted" && can("commercial.measurement.certify") && <><button disabled={busy} onClick={() => void mutate(() => submitJson(`/projects/${projectId}/commercial/measurements/${item.id}/review`, { expected_revision: item.revision, approve: true, reason: "Quantity certified" }))}>Certify</button><button className="secondary" disabled={busy} onClick={() => void mutate(() => submitJson(`/projects/${projectId}/commercial/measurements/${item.id}/review`, { expected_revision: item.revision, approve: false, reason: "Returned for correction" }))}>Reject</button></>}</div></article>)}</div>}
            </DataSection>
          )}

          {project && view === "billing" && (
            <DataSection title="RA Billing" detail="Draft RA bills are assembled only from certified, not-yet-billed measurements. Deductions are explicit values; statutory rates are not invented by the application.">
              {can("commercial.ra_bill.create") && <form className="quick-form bill-form" onSubmit={(event) => { const form = formJson(event); void mutate(async () => { await submitJson(`/projects/${projectId}/commercial/ra-bills`, { counterparty_id: form.get("counterparty_id"), bill_number: form.get("bill_number"), period_start: form.get("period_start"), period_end: form.get("period_end"), retention_amount: form.get("retention_amount") || "0", statutory_deduction_amount: form.get("statutory_deduction_amount") || "0", other_deduction_amount: form.get("other_deduction_amount") || "0" }); event.currentTarget.reset(); }); }}><select name="counterparty_id" required defaultValue=""><option value="" disabled>Counterparty</option>{parties.filter((item) => item.status === "active").map((item) => <option key={item.id} value={item.id}>{item.code} · {item.name}</option>)}</select><input name="bill_number" placeholder="RA bill no." required /><label>From<input name="period_start" type="date" required /></label><label>To<input name="period_end" type="date" required /></label><input name="retention_amount" type="number" min="0" step="0.01" placeholder="Retention ₹" /><input name="statutory_deduction_amount" type="number" min="0" step="0.01" placeholder="Statutory deduction ₹" /><input name="other_deduction_amount" type="number" min="0" step="0.01" placeholder="Other deduction ₹" /><button disabled={busy}>Create from certified MB</button></form>}
              {bills.length === 0 ? <Empty title="No RA bills yet" detail="Certified measurements in the selected period become the auditable basis of the first RA bill." /> : <div className="record-list">{bills.map((item) => <article className="record-card bill-card" key={item.id}><div><span className="record-number">{item.bill_number}</span><strong>{money(item.net_payable)}</strong><small>Gross {money(item.gross_amount)} · {item.period_start} → {item.period_end}</small></div><div className="record-actions"><Status value={item.status} />{item.status === "draft" && can("commercial.ra_bill.submit") && <button disabled={busy} onClick={() => void mutate(() => submitJson(`/projects/${projectId}/commercial/ra-bills/${item.id}/submit`, { expected_revision: item.revision }))}>Submit</button>}{item.status === "submitted" && can("commercial.ra_bill.certify") && <button disabled={busy} onClick={() => void mutate(() => submitJson(`/projects/${projectId}/commercial/ra-bills/${item.id}/certify`, { expected_revision: item.revision, reason: "RA bill certified" }))}>Certify</button>}{item.status === "certified" && can("commercial.ra_bill.certify") && <button className="secondary" disabled={busy} onClick={() => void mutate(() => submitJson(`/projects/${projectId}/commercial/ra-bills/${item.id}/mark-paid`, { expected_revision: item.revision, reason: "Payment recorded" }))}>Mark paid</button>}</div></article>)}</div>}
            </DataSection>
          )}

          {project && view === "assistant" && <AssistantPanel />}
        </section>
      </section>
    </main>
  );
}

function DataSection({ title, detail, children }: { title: string; detail: string; children: React.ReactNode }) {
  return <><div className="page-heading compact"><div><p className="eyebrow">INDIA PROJECT WORKFLOW</p><h1>{title}</h1><p>{detail}</p></div></div><section className="section-card">{children}</section></>;
}

function MeasurementForm({ boqs, projectId, busy, onMutate, submitJson }: { boqs: BOQ[]; projectId: string; busy: boolean; onMutate: (work: () => Promise<unknown>) => Promise<void>; submitJson: (path: string, payload: unknown, method?: string) => Promise<unknown> }) {
  const [boqId, setBoqId] = useState("");
  const [detail, setDetail] = useState<BOQDetail | null>(null);
  useEffect(() => {
    if (!boqId) { setDetail(null); return; }
    void api<BOQDetail>(`/projects/${projectId}/commercial/boqs/${boqId}`).then(setDetail).catch(() => setDetail(null));
  }, [boqId, projectId]);
  const approved = boqs.filter((item) => item.status === "approved");
  return <form className="quick-form measurement-form" onSubmit={(event) => { event.preventDefault(); const form = new FormData(event.currentTarget); void onMutate(async () => { await submitJson(`/projects/${projectId}/commercial/measurements`, { boq_item_id: form.get("boq_item_id"), measurement_date: form.get("measurement_date"), location: form.get("location") || null, description: form.get("description") || null, quantity: form.get("quantity") }); event.currentTarget.reset(); setBoqId(""); }); }}><select value={boqId} onChange={(event) => setBoqId(event.target.value)} required><option value="">Approved BOQ</option>{approved.map((item) => <option key={item.id} value={item.id}>{item.code} · {item.name}</option>)}</select><select name="boq_item_id" required defaultValue=""><option value="" disabled>BOQ item</option>{detail?.items.map((item) => <option key={item.id} value={item.id}>{item.item_code} · {item.description}</option>)}</select><input name="measurement_date" type="date" required /><input name="quantity" type="number" min="0.001" step="0.001" placeholder="Measured qty" required /><input name="location" placeholder="Location / grid / floor" /><input name="description" placeholder="Measurement note" /><button disabled={busy || !detail}>Record measurement</button></form>;
}

function AssistantPanel() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const ask = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true); setError(""); setAnswer("");
    try {
      const result = await api<{ answer: string }>("/help/assistant/query", { method: "POST", body: JSON.stringify({ question, mode: "help", include_tenant_knowledge: true }) });
      setAnswer(result.answer);
    } catch (requestError) { setError((requestError as Error).message); }
    finally { setBusy(false); }
  };
  return <DataSection title="Construction OS Assistant" detail="Permission-scoped RAG for product help, company knowledge and future upgrade guidance. It cannot approve commercial records or execute migrations."><form className="assistant-form" onSubmit={ask}><textarea value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Ask about this installation, workflow or approved knowledge…" required /><button disabled={busy}>{busy ? "Checking evidence…" : "Ask assistant"}</button></form>{error && <div className="inline-note">{error}</div>}{answer && <div className="assistant-answer">{answer}</div>}</DataSection>;
}
