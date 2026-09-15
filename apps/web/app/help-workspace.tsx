"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useWebSession } from "./web-session-gate";

type HelpTopic = {
  key: string;
  title: string;
  eyebrow: string;
  href: string;
  summary: string;
  workflow: string;
  permission: string;
  feature?: string;
  organizationOnly?: boolean;
  terms: string[];
};

const topics: HelpTopic[] = [
  {
    key: "dpr",
    title: "Daily Progress Reports",
    eyebrow: "FIELD",
    href: "/field",
    summary: "Capture the site day against authoritative project records, then submit and approve a governed DPR.",
    workflow: "Create draft → update work/weather/notes → reuse attendance, materials and equipment → submit → approve → issued PDF.",
    permission: "field.daily_report.view",
    feature: "field",
    terms: ["dpr", "daily report", "site report", "progress", "pdf", "approval"],
  },
  {
    key: "dpr-templates",
    title: "DPR Templates",
    eyebrow: "FIELD ADMIN",
    href: "/field/dpr-templates",
    summary: "Manage versioned DPR layouts using only fields supplied by the reporting provider contract.",
    workflow: "Create template → create contract-valid version → review → publish → future issued DPRs pin that version.",
    permission: "field.dpr.template.view",
    feature: "field.dpr_templates",
    terms: ["template", "layout", "report", "branding", "publish", "dpr"],
  },
  {
    key: "attendance",
    title: "Attendance",
    eyebrow: "WORKFORCE",
    href: "/field/attendance",
    summary: "Supervisor-driven daily attendance for assigned workers and crews, reused by DPR after approval.",
    workflow: "Open register → mark attendance/hours → review → approve → DPR reads the approved summary.",
    permission: "workforce.attendance.view",
    feature: "workforce.attendance",
    terms: ["attendance", "labour", "worker", "crew", "hours", "dpr"],
  },
  {
    key: "workforce",
    title: "Workforce & Time",
    eyebrow: "WORKFORCE",
    href: "/workforce",
    summary: "Maintain workers separately from application users, along with crews, project assignments, rates and time records.",
    workflow: "Create worker → assign to project/crew → capture attendance or time → submit/approve governed time records.",
    permission: "workforce.worker.view",
    feature: "workforce",
    terms: ["worker", "crew", "labour", "timecard", "assignment", "rate"],
  },
  {
    key: "parties",
    title: "Party Directory",
    eyebrow: "MASTER DATA",
    href: "/commercial/parties",
    summary: "Use one shared business-partner master for clients, consultants, suppliers, vendors and subcontractors.",
    workflow: "Create party → assign business roles/details → reuse the same party across later commercial and procurement workflows.",
    permission: "commercial.party.view",
    feature: "commercial.parties",
    terms: ["party", "client", "vendor", "supplier", "subcontractor", "gstin"],
  },
  {
    key: "wbs",
    title: "WBS & Cost Codes",
    eyebrow: "PROJECT CONTROL",
    href: "/commercial/wbs",
    summary: "Build the internal project control hierarchy used to classify BOQ, field progress and future job-cost transactions.",
    workflow: "Create hierarchy → review codes → use stable WBS IDs from BOQ and field records; WBS remains separate from contractual BOQ.",
    permission: "commercial.wbs.view",
    feature: "commercial.wbs",
    terms: ["wbs", "cost code", "hierarchy", "project control", "work breakdown"],
  },
  {
    key: "boq",
    title: "Bill of Quantities",
    eyebrow: "COMMERCIAL",
    href: "/commercial/boq",
    summary: "Create contractual quantity/rate items and approve a controlled baseline without mixing BOQ with internal WBS.",
    workflow: "Create BOQ → add quantity/rate lines → map WBS where needed → validate → approve immutable baseline.",
    permission: "commercial.boq.view",
    feature: "commercial.boq",
    terms: ["boq", "quantity", "rate", "amount", "baseline", "excel"],
  },
  {
    key: "estimating",
    title: "Estimating, Rate Analysis & Budget",
    eyebrow: "PRE-CONSTRUCTION",
    href: "/estimating",
    summary: "Build estimates and rate-analysis inputs, then create controlled project budget baselines and revisions.",
    workflow: "Estimate → rate analysis/resources → review → budget baseline → controlled budget revisions; historical approved values stay intact.",
    permission: "estimating.module.view",
    feature: "estimating",
    terms: ["estimate", "rate analysis", "budget", "resource", "baseline", "revision"],
  },
  {
    key: "access",
    title: "Roles & Access",
    eyebrow: "ADMIN",
    href: "/admin/access",
    summary: "Control company roles and permission sets. The server remains authoritative even when unavailable actions are hidden in the UI.",
    workflow: "Review roles → assign capabilities → assign membership roles → verify effective company/project access.",
    permission: "security.role.view",
    organizationOnly: true,
    terms: ["role", "permission", "access", "security", "membership"],
  },
  {
    key: "project-access",
    title: "Project Access",
    eyebrow: "ADMIN",
    href: "/admin/project-access",
    summary: "Assign company members to projects with project-scoped roles instead of widening company-level privileges.",
    workflow: "Choose project → add membership → assign project role → verify effective project capabilities.",
    permission: "security.role.view",
    organizationOnly: true,
    terms: ["project access", "membership", "role", "permission"],
  },
  {
    key: "company",
    title: "Company Settings",
    eyebrow: "ADMIN",
    href: "/admin/company",
    summary: "Maintain company identity and permitted configuration defaults used by released product surfaces.",
    workflow: "Review identity/defaults → change authorized settings → save versioned configuration → downstream pages read effective values.",
    permission: "admin.settings.view",
    feature: "admin.company",
    organizationOnly: true,
    terms: ["company", "settings", "configuration", "defaults"],
  },
  {
    key: "operations",
    title: "Operations Center",
    eyebrow: "ADMIN",
    href: "/admin/operations",
    summary: "Review tenant-scoped service health, operational events and background processing without exposing infrastructure secrets.",
    workflow: "Check overall status → review component health → inspect open events → review background-job failures where permitted.",
    permission: "admin.operations.view",
    feature: "admin.operations",
    organizationOnly: true,
    terms: ["operations", "health", "jobs", "failures", "admin", "system"],
  },
];

export default function HelpWorkspace() {
  const { hasFeature, hasPermission, hasPermissionAnywhere } = useWebSession();
  const [query, setQuery] = useState("");
  const canViewHelp = hasPermission("help.content.view");

  const visibleTopics = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return topics.filter((topic) => {
      const permitted = topic.organizationOnly ? hasPermission(topic.permission) : hasPermissionAnywhere(topic.permission);
      if (!permitted) return false;
      if (topic.feature && !hasFeature(topic.feature) && !permitted) return false;
      if (!normalized) return true;
      const haystack = [topic.title, topic.eyebrow, topic.summary, topic.workflow, ...topic.terms].join(" ").toLowerCase();
      return haystack.includes(normalized);
    });
  }, [hasFeature, hasPermission, hasPermissionAnywhere, query]);

  if (!canViewHelp) {
    return <main className="page-frame"><section className="empty-state"><strong>Help is not available to this membership.</strong><p>The help.content.view capability is required to view product guidance.</p><Link href="/">Return to workspace</Link></section></main>;
  }

  return <main className="page-frame">
    <div className="page-heading">
      <div><p className="eyebrow">CONSTRUCTION OS · INDIA</p><h1>Help & workflow guidance</h1><p>Deterministic guidance for the product surfaces released in this build. Planned modules and the AI Assistant stay hidden until their release state changes.</p></div>
      <Link className="secondary-button" href="/">Workspace</Link>
    </div>

    <section className="section-card">
      <div className="page-heading compact"><div><p className="eyebrow">FIND HELP</p><h1>What are you trying to do?</h1></div></div>
      <label style={{ display: "grid", gap: 7, maxWidth: 720 }}><span className="eyebrow">SEARCH RELEASED WORKFLOWS</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Try: BOQ, attendance, DPR, worker, budget, role…" style={{ minHeight: 46, border: "1px solid #d7ddd3", borderRadius: 10, padding: "0 12px", background: "#fff" }} /></label>
    </section>

    <section className="section-card">
      <div className="page-heading compact"><div><p className="eyebrow">AVAILABLE TO YOU</p><h1>Released workflows</h1><p>Topics are filtered by your current company and project permissions.</p></div><strong>{visibleTopics.length}</strong></div>
      {visibleTopics.length === 0 ? <div className="empty-state"><strong>No matching help topic</strong><p>Try a broader term, or ask an administrator if you need access to another released workflow.</p></div> : <div className="record-list">{visibleTopics.map((topic) => <article className="record-card" key={topic.key} style={{ alignItems: "flex-start" }}>
        <div><span className="record-number">{topic.eyebrow}</span><strong>{topic.title}</strong><small>{topic.summary}</small><small><b>Workflow:</b> {topic.workflow}</small></div><div className="record-actions"><Link className="secondary-button" href={topic.href}>Open</Link></div>
      </article>)}</div>}
    </section>

    <section className="section-card">
      <div className="page-heading compact"><div><p className="eyebrow">CORE INDIA-FIRST RULES</p><h1>How the released foundation fits together</h1></div></div>
      <div className="record-list">
        <article className="record-card"><div><strong>Party → WBS → BOQ → Estimate/Budget → Workforce/Attendance → DPR</strong><small>Records reuse stable IDs and authoritative sources instead of creating disconnected copies.</small></div></article>
        <article className="record-card"><div><strong>WBS and BOQ are different</strong><small>WBS controls internal project/cost structure. BOQ represents contractual quantity and rate structure.</small></div></article>
        <article className="record-card"><div><strong>Worker is not User</strong><small>Labour records can exist without application accounts; supervisors can capture attendance on behalf of site crews.</small></div></article>
        <article className="record-card"><div><strong>Approved history is preserved</strong><small>Governed baselines, submitted/approved DPRs and issued reports are not silently rewritten. Revisions and lifecycle history remain explicit.</small></div></article>
      </div>
    </section>
  </main>;
}
