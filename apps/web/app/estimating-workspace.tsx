"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

type AccessContext = { permissions: string[]; project_permissions: Record<string, string[]> };
type Project = { id: string; number: string; name: string };
type BOQ = { id: string; code: string; name: string; currency_code: string; status: string };
type Estimate = {
  id: string; project_id: string; source_boq_id: string | null; code: string; name: string;
  description: string | null; currency_code: string; status: string; revision: number;
  approved_at: string | null;
};
type EstimateItem = {
  id: string; estimate_id: string; wbs_code_id: string | null; boq_item_id: string | null;
  line_number: number; item_code: string; description: string; unit_code: string;
  quantity: string; rate: string; amount: string; revision: number;
};
type EstimateDetail = Estimate & {
  items: EstimateItem[]; item_count: number; total_selling_amount: string; approval_snapshot_count: number;
};
type BudgetLine = { id: string; wbs_code_id: string; category: string; amount: string; notes: string | null };
type Budget = {
  id: string; project_id: string; estimate_id: string | null; code: string; name: string;
  currency_code: string; status: string; revision: number; approved_at: string | null;
};
type BudgetDetail = Budget & { lines: BudgetLine[]; line_count: number; total_amount: string; approval_snapshot_count: number };
type RateComponent = { kind: string; description: string; unit_code: string; quantity: string; unit_rate: string };
type RateAnalysis = {
  version_number: number; base_rate: string; wastage_amount: string; overhead_amount: string;
  cost_rate: string; profit_amount: string; selling_rate: string;
};
type Approval = { id: string; version_number: number; approved_at: string; reason: string | null; snapshot: Record<string, unknown> };

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
const COMPONENT_KINDS = ["material", "labour", "equipment", "subcontract", "overhead", "other"];

function csrfToken(): string | null {
  if (typeof document === "undefined") return null;
  const token = document.cookie.split(";").map((v) => v.trim()).find((v) => v.startsWith("construction_os_csrf="));
  return token ? decodeURIComponent(token.split("=").slice(1).join("=")) : null;
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
    try { const body = (await response.json()) as { detail?: unknown }; if (body.detail) message = String(body.detail); } catch {}
    throw new Error(message);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

function money(value: string | number, currency = "INR") {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency, maximumFractionDigits: 2 }).format(Number(value || 0));
}

function Status({ value }: { value: string }) {
  return <span className={`status-pill status-${value.replaceAll("_", "-")}`}>{value.replaceAll("_", " ")}</span>;
}

function Empty({ title, detail }: { title: string; detail: string }) {
  return <div className="empty-state"><strong>{title}</strong><p>{detail}</p></div>;
}

export default function EstimatingWorkspace({ initialProjectId, initialEstimateId, initialBudgetId }: {
  initialProjectId?: string; initialEstimateId?: string; initialBudgetId?: string;
}) {
  const [context, setContext] = useState<AccessContext | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState(initialProjectId || "");
  const [boqs, setBoqs] = useState<BOQ[]>([]);
  const [estimates, setEstimates] = useState<Estimate[]>([]);
  const [budgets, setBudgets] = useState<Budget[]>([]);
  const [estimate, setEstimate] = useState<EstimateDetail | null>(null);
  const [budget, setBudget] = useState<BudgetDetail | null>(null);
  const [selectedItemId, setSelectedItemId] = useState("");
  const [analysis, setAnalysis] = useState<RateAnalysis | null>(null);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [tab, setTab] = useState(initialBudgetId ? "budgets" : "estimates");
  const [components, setComponents] = useState<RateComponent[]>([
    { kind: "material", description: "", unit_code: "", quantity: "1", unit_rate: "0" },
  ]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const can = useCallback((permission: string, targetProject: string) => {
    if (!context) return false;
    return context.permissions.includes(permission) || (context.project_permissions[targetProject] || []).includes(permission);
  }, [context]);

  const visibleProjects = useMemo(() => projects.filter((row) =>
    can("estimating.estimate.view", row.id) || can("estimating.budget.view", row.id)), [can, projects]);

  const loadProject = useCallback(async (target: string) => {
    const [estimateRows, budgetRows, boqRows] = await Promise.all([
      api<Estimate[]>(`/projects/${target}/estimating/estimates`),
      api<Budget[]>(`/projects/${target}/estimating/budgets`),
      api<BOQ[]>(`/projects/${target}/commercial/boqs`),
    ]);
    setEstimates(estimateRows); setBudgets(budgetRows); setBoqs(boqRows.filter((row) => row.status === "approved"));
  }, []);

  const openEstimate = useCallback(async (targetProject: string, estimateId: string) => {
    const [detail, history] = await Promise.all([
      api<EstimateDetail>(`/projects/${targetProject}/estimating/estimates/${estimateId}`),
      api<Approval[]>(`/projects/${targetProject}/estimating/estimates/${estimateId}/approvals`),
    ]);
    setEstimate(detail); setBudget(null); setApprovals(history); setTab("estimates");
    setSelectedItemId(detail.items[0]?.id || ""); setAnalysis(null);
  }, []);

  const openBudget = useCallback(async (targetProject: string, budgetId: string) => {
    const [detail, history] = await Promise.all([
      api<BudgetDetail>(`/projects/${targetProject}/estimating/budgets/${budgetId}`),
      api<Approval[]>(`/projects/${targetProject}/estimating/budgets/${budgetId}/approvals`),
    ]);
    setBudget(detail); setEstimate(null); setApprovals(history); setTab("budgets");
  }, []);

  const bootstrap = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const [nextContext, projectRows] = await Promise.all([api<AccessContext>("/session/context"), api<Project[]>("/projects")]);
      setContext(nextContext); setProjects(projectRows);
      const accessible = projectRows.filter((row) => nextContext.permissions.includes("estimating.estimate.view") || nextContext.permissions.includes("estimating.budget.view") || (nextContext.project_permissions[row.id] || []).some((p) => p === "estimating.estimate.view" || p === "estimating.budget.view"));
      const selected = initialProjectId && accessible.some((row) => row.id === initialProjectId) ? initialProjectId : accessible[0]?.id || "";
      setProjectId(selected);
      if (selected) {
        await loadProject(selected);
        if (initialEstimateId) await openEstimate(selected, initialEstimateId);
        if (initialBudgetId) await openBudget(selected, initialBudgetId);
      }
    } catch (requestError) { setError((requestError as Error).message); }
    finally { setLoading(false); }
  }, [initialBudgetId, initialEstimateId, initialProjectId, loadProject, openBudget, openEstimate]);

  useEffect(() => { void bootstrap(); }, [bootstrap]);

  const run = async (work: () => Promise<void>) => {
    setBusy(true); setError("");
    try { await work(); if (projectId) await loadProject(projectId); }
    catch (requestError) { setError((requestError as Error).message); }
    finally { setBusy(false); }
  };

  const createEstimate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); const form = new FormData(event.currentTarget); const element = event.currentTarget;
    await run(async () => {
      const source = String(form.get("source_boq_id") || "");
      const sourceBoq = boqs.find((row) => row.id === source);
      const created = await api<Estimate>(`/projects/${projectId}/estimating/estimates`, { method: "POST", body: JSON.stringify({ code: form.get("code"), name: form.get("name"), description: form.get("description") || null, source_boq_id: source || null, currency_code: sourceBoq?.currency_code || "INR" }) });
      element.reset(); await openEstimate(projectId, created.id);
    });
  };

  const copyBOQ = () => estimate && run(async () => {
    await api(`/projects/${projectId}/estimating/estimates/${estimate.id}/copy-boq-items`, { method: "POST", body: JSON.stringify({ expected_revision: estimate.revision }) });
    await openEstimate(projectId, estimate.id);
  });

  const saveAnalysis = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); if (!selectedItemId) return; const form = new FormData(event.currentTarget);
    await run(async () => {
      await api(`/projects/${projectId}/estimating/rate-analyses`, { method: "POST", body: JSON.stringify({ estimate_item_id: selectedItemId, wastage_percent: form.get("wastage_percent"), overhead_percent: form.get("overhead_percent"), profit_percent: form.get("profit_percent"), components }) });
      const current = await api<RateAnalysis>(`/projects/${projectId}/estimating/estimate-items/${selectedItemId}/rate-analysis`);
      setAnalysis(current); if (estimate) await openEstimate(projectId, estimate.id);
    });
  };

  const actionEstimate = (action: "submit" | "approve") => estimate && run(async () => {
    await api(`/projects/${projectId}/estimating/estimates/${estimate.id}/${action}`, { method: "POST", body: JSON.stringify({ expected_revision: estimate.revision, reason: `${action} from estimating workspace` }) });
    await openEstimate(projectId, estimate.id);
  });

  const reviseEstimate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); if (!estimate) return; const form = new FormData(event.currentTarget);
    await run(async () => {
      const revised = await api<Estimate>(`/projects/${projectId}/estimating/estimates/${estimate.id}/revise`, { method: "POST", body: JSON.stringify({ new_code: form.get("new_code"), new_name: form.get("new_name"), reason: form.get("reason") }) });
      await openEstimate(projectId, revised.id);
    });
  };

  const generateBudget = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); if (!estimate) return; const form = new FormData(event.currentTarget);
    await run(async () => {
      const created = await api<Budget>(`/projects/${projectId}/estimating/estimates/${estimate.id}/budget`, { method: "POST", body: JSON.stringify({ code: form.get("code"), name: form.get("name"), currency_code: estimate.currency_code }) });
      await openBudget(projectId, created.id);
    });
  };

  const approveBudget = () => budget && run(async () => {
    await api(`/projects/${projectId}/estimating/budgets/${budget.id}/approve`, { method: "POST", body: JSON.stringify({ expected_revision: budget.revision, reason: "Approved from estimating workspace" }) });
    await openBudget(projectId, budget.id);
  });

  const loadAnalysis = async (itemId: string) => {
    setSelectedItemId(itemId); setAnalysis(null);
    try { setAnalysis(await api<RateAnalysis>(`/projects/${projectId}/estimating/estimate-items/${itemId}/rate-analysis`)); } catch {}
  };

  if (loading) return <main className="boot-screen"><div className="boot-mark">COS</div><p>Loading estimating…</p></main>;

  return <main className="workspace"><section className="page-frame">
    <div className="page-heading"><div><p className="eyebrow">MODULE 4</p><h1>Estimate / Rate Analysis / Budget</h1><p>Build the internal cost from approved scope, price it, approve it, then create the controlled project budget.</p></div></div>
    {error && <div className="error-banner"><strong>Action not completed</strong><span>{error}</span><button onClick={() => setError("")}>×</button></div>}
    {visibleProjects.length === 0 ? <Empty title="No accessible project" detail="You need estimating or budget view permission on a project." /> : <>
      <section className="workflow-card"><div><p className="eyebrow">PROJECT</p><h2>Choose project</h2></div><div className="quick-form"><select value={projectId} onChange={(e) => void run(async () => { setProjectId(e.target.value); setEstimate(null); setBudget(null); await loadProject(e.target.value); })}>{visibleProjects.map((row) => <option key={row.id} value={row.id}>{row.number} · {row.name}</option>)}</select><button className={tab === "estimates" ? "" : "secondary"} onClick={() => setTab("estimates")}>Estimates</button><button className={tab === "budgets" ? "" : "secondary"} onClick={() => setTab("budgets")}>Budgets</button></div></section>

      {tab === "estimates" && <>
        {can("estimating.estimate.manage", projectId) && <section className="workflow-card"><div><p className="eyebrow">NEW ESTIMATE</p><h2>Start from approved BOQ or manual scope</h2></div><form className="quick-form" onSubmit={createEstimate}><input name="code" placeholder="Estimate code" required/><input name="name" placeholder="Estimate name" required/><select name="source_boq_id" defaultValue=""><option value="">No source BOQ</option>{boqs.map((row) => <option key={row.id} value={row.id}>{row.code} · {row.name}</option>)}</select><input name="description" placeholder="Description"/><button disabled={busy}>Create estimate</button></form></section>}
        <div className="split-layout"><section><div className="detail-title"><div><p className="eyebrow">ESTIMATES</p><h3>{estimates.length} records</h3></div></div>{estimates.length === 0 ? <Empty title="No estimates" detail="Create an internal estimate from the approved project scope."/> : <div className="record-list">{estimates.map((row) => <Link key={row.id} href={`/projects/${projectId}/estimating/estimates/${row.id}`} className={estimate?.id === row.id ? "list-card selected" : "list-card"}><div><strong>{row.code} · {row.name}</strong><small>{row.currency_code}{row.source_boq_id ? " · BOQ linked" : " · manual"}</small></div><Status value={row.status}/></Link>)}</div>}</section>
          <section className="detail-panel">{!estimate ? <Empty title="Select an estimate" detail="Open an estimate to build rate analysis, approve it and create the cost budget."/> : <>
            <div className="detail-title"><div><p className="eyebrow">ESTIMATE</p><h3>{estimate.code} · {estimate.name}</h3><small>{estimate.item_count} items · {money(estimate.total_selling_amount, estimate.currency_code)} selling value</small></div><Status value={estimate.status}/></div>
            <div className="metric-grid"><article><span>Lines</span><strong>{estimate.item_count}</strong><small>Scope items</small></article><article><span>Selling value</span><strong>{money(estimate.total_selling_amount, estimate.currency_code)}</strong><small>Includes configured profit</small></article><article><span>Approvals</span><strong>{estimate.approval_snapshot_count}</strong><small>Immutable snapshots</small></article><article><span>Source</span><strong>{estimate.source_boq_id ? "BOQ" : "Manual"}</strong><small>{estimate.currency_code}</small></article></div>
            {estimate.status === "draft" && estimate.source_boq_id && estimate.items.length === 0 && can("estimating.estimate.manage", projectId) && <button onClick={copyBOQ} disabled={busy}>Copy approved BOQ items</button>}
            {estimate.items.length > 0 && <div className="record-list">{estimate.items.map((item) => <button key={item.id} className={selectedItemId === item.id ? "list-card selected" : "list-card"} onClick={() => void loadAnalysis(item.id)}><div><strong>{item.line_number}. {item.item_code}</strong><small>{item.description} · {item.quantity} {item.unit_code}</small></div><span>{money(item.rate, estimate.currency_code)}/unit</span></button>)}</div>}
            {selectedItemId && estimate.status === "draft" && can("estimating.rate_analysis.manage", projectId) && <section className="workflow-card"><div><p className="eyebrow">RATE ANALYSIS</p><h2>Internal cost + pricing</h2>{analysis && <small>Current v{analysis.version_number}: cost {money(analysis.cost_rate, estimate.currency_code)} · selling {money(analysis.selling_rate, estimate.currency_code)}</small>}</div><form onSubmit={saveAnalysis}><div className="quick-form"><input name="wastage_percent" type="number" step="0.0001" min="0" defaultValue="0" placeholder="Wastage %"/><input name="overhead_percent" type="number" step="0.0001" min="0" defaultValue="0" placeholder="Overhead %"/><input name="profit_percent" type="number" step="0.0001" min="0" defaultValue="0" placeholder="Profit %"/></div>{components.map((component, index) => <div className="quick-form" key={index}><select value={component.kind} onChange={(e) => setComponents((rows) => rows.map((row, i) => i === index ? {...row, kind: e.target.value} : row))}>{COMPONENT_KINDS.map((kind) => <option key={kind}>{kind}</option>)}</select><input value={component.description} onChange={(e) => setComponents((rows) => rows.map((row, i) => i === index ? {...row, description: e.target.value} : row))} placeholder="Component description" required/><input value={component.unit_code} onChange={(e) => setComponents((rows) => rows.map((row, i) => i === index ? {...row, unit_code: e.target.value} : row))} placeholder="Unit"/><input type="number" step="0.0001" min="0" value={component.quantity} onChange={(e) => setComponents((rows) => rows.map((row, i) => i === index ? {...row, quantity: e.target.value} : row))}/><input type="number" step="0.01" min="0" value={component.unit_rate} onChange={(e) => setComponents((rows) => rows.map((row, i) => i === index ? {...row, unit_rate: e.target.value} : row))}/></div>)}<div className="quick-form"><button type="button" className="secondary" onClick={() => setComponents((rows) => [...rows, { kind: "labour", description: "", unit_code: "", quantity: "1", unit_rate: "0" }])}>Add component</button><button disabled={busy}>Save rate analysis version</button></div></form></section>}
            <div className="quick-form">{estimate.status === "draft" && can("estimating.estimate.submit", projectId) && <button onClick={() => actionEstimate("submit")} disabled={busy}>Submit estimate</button>}{estimate.status === "submitted" && can("estimating.estimate.approve", projectId) && <button onClick={() => actionEstimate("approve")} disabled={busy}>Approve estimate</button>}</div>
            {estimate.status === "approved" && <>{can("estimating.budget.manage", projectId) && <form className="quick-form" onSubmit={generateBudget}><input name="code" placeholder="Budget code" required/><input name="name" placeholder="Budget name" required/><button disabled={busy}>Create cost budget</button></form>}{can("estimating.estimate.manage", projectId) && <form className="quick-form" onSubmit={reviseEstimate}><input name="new_code" placeholder="New revision code" required/><input name="new_name" placeholder="Revision name" required/><input name="reason" placeholder="Reason for revision" required/><button className="secondary" disabled={busy}>Create revision draft</button></form>}</>}
            {approvals.length > 0 && <section><p className="eyebrow">APPROVAL HISTORY</p>{approvals.map((row) => <div className="list-card" key={row.id}><div><strong>Version {row.version_number}</strong><small>{new Date(row.approved_at).toLocaleString("en-IN")} · {row.reason || "No reason recorded"}</small></div></div>)}</section>}
          </>}</section></div>
      </>}

      {tab === "budgets" && <div className="split-layout"><section><div className="detail-title"><div><p className="eyebrow">BUDGETS</p><h3>{budgets.length} records</h3></div></div>{budgets.length === 0 ? <Empty title="No budgets" detail="Approve an estimate first, then create the cost budget from its immutable cost snapshot."/> : <div className="record-list">{budgets.map((row) => <Link key={row.id} href={`/projects/${projectId}/estimating/budgets/${row.id}`} className={budget?.id === row.id ? "list-card selected" : "list-card"}><div><strong>{row.code} · {row.name}</strong><small>{row.currency_code}</small></div><Status value={row.status}/></Link>)}</div>}</section><section className="detail-panel">{!budget ? <Empty title="Select a budget" detail="Open a budget to review WBS/category cost lines and approve the current baseline."/> : <><div className="detail-title"><div><p className="eyebrow">PROJECT COST BUDGET</p><h3>{budget.code} · {budget.name}</h3><small>{budget.line_count} lines · {money(budget.total_amount, budget.currency_code)}</small></div><Status value={budget.status}/></div><div className="metric-grid"><article><span>Total cost</span><strong>{money(budget.total_amount, budget.currency_code)}</strong><small>Profit excluded</small></article><article><span>Lines</span><strong>{budget.line_count}</strong><small>WBS × category</small></article><article><span>Approvals</span><strong>{budget.approval_snapshot_count}</strong><small>Historical baselines</small></article></div><div className="record-list">{budget.lines.map((line) => <div className="list-card" key={line.id}><div><strong>{line.category.replaceAll("_", " ")}</strong><small>WBS {line.wbs_code_id}</small></div><span>{money(line.amount, budget.currency_code)}</span></div>)}</div>{budget.status === "draft" && can("estimating.budget.approve", projectId) && <button onClick={approveBudget} disabled={busy}>Approve budget baseline</button>}{approvals.length > 0 && <section><p className="eyebrow">APPROVAL HISTORY</p>{approvals.map((row) => <div className="list-card" key={row.id}><div><strong>Version {row.version_number}</strong><small>{new Date(row.approved_at).toLocaleString("en-IN")} · {row.reason || "No reason recorded"}</small></div></div>)}</section>}</>}</section></div>}
    </>}
  </section></main>;
}
