"use client";

import Link from "next/link";
import { useMemo } from "react";
import { useWebSession } from "./web-session-gate";
import styles from "./workspace-home.module.css";

type Workspace = {
  eyebrow: string;
  title: string;
  detail: string;
  href: string;
  code: string;
  meta: string;
  tone?: "lime" | "blue" | "sand" | "rose";
  featureKeys?: string[];
  permissionKeys?: string[];
  organizationOnly?: boolean;
};

const primaryWorkspaces: Workspace[] = [
  {
    eyebrow: "FIELD",
    title: "Daily field operations",
    detail: "Run DPR capture and connect daily site activity to the project record.",
    href: "/field",
    code: "01",
    meta: "DPR workspace",
    tone: "lime",
    featureKeys: ["field"],
    permissionKeys: ["field.daily_report.view"],
  },
  {
    eyebrow: "PRE-CONSTRUCTION",
    title: "Estimating",
    detail: "Build estimates, rate inputs and budgets before work moves into project controls.",
    href: "/estimating",
    code: "02",
    meta: "Estimating workspace",
    tone: "blue",
    featureKeys: ["estimating"],
    permissionKeys: ["estimating.module.view"],
  },
  {
    eyebrow: "WORKFORCE",
    title: "Workforce & time",
    detail: "Maintain workers, crews, project assignments, rates and governed time records.",
    href: "/workforce",
    code: "03",
    meta: "Labour operations",
    tone: "sand",
    featureKeys: ["workforce"],
    permissionKeys: [
      "workforce.worker.view",
      "workforce.assignment.view",
      "workforce.timecard.view",
      "workforce.attendance.view",
    ],
  },
];

const focusedWorkspaces: Workspace[] = [
  {
    eyebrow: "FIELD",
    title: "Attendance",
    detail: "Mark crews, working hours and cost codes once, then reuse approved attendance in DPR.",
    href: "/field/attendance",
    code: "04",
    meta: "Workforce record",
    featureKeys: ["workforce.attendance"],
    permissionKeys: ["workforce.attendance.view"],
  },
  {
    eyebrow: "COMMERCIAL",
    title: "BOQ",
    detail: "Manage contractual quantities, rates and the approved project baseline.",
    href: "/commercial/boq",
    code: "05",
    meta: "Quantity & rate control",
    featureKeys: ["commercial.boq"],
    permissionKeys: ["commercial.boq.view"],
  },
  {
    eyebrow: "MASTER DATA",
    title: "Parties",
    detail: "Maintain the shared directory for clients, consultants, suppliers and subcontractors.",
    href: "/commercial/parties",
    code: "06",
    meta: "Company directory",
    featureKeys: ["commercial.parties"],
    permissionKeys: ["commercial.party.view"],
  },
  {
    eyebrow: "PROJECT CONTROL",
    title: "WBS & cost codes",
    detail: "Maintain the project work breakdown and cost-control hierarchy.",
    href: "/commercial/wbs",
    code: "07",
    meta: "Project structure",
    featureKeys: ["commercial.wbs"],
    permissionKeys: ["commercial.wbs.view"],
  },
];

const adminWorkspaces: Workspace[] = [
  {
    eyebrow: "ADMIN",
    title: "Access management",
    detail: "Manage company roles, permission sets and membership access.",
    href: "/admin/access",
    code: "08",
    meta: "Security administration",
    permissionKeys: ["security.role.view"],
    organizationOnly: true,
  },
  {
    eyebrow: "ADMIN",
    title: "Project access",
    detail: "Assign company members and project-scoped roles to project teams.",
    href: "/admin/project-access",
    code: "09",
    meta: "Project security",
    permissionKeys: ["security.role.view"],
    organizationOnly: true,
  },
  {
    eyebrow: "ADMIN",
    title: "Company settings",
    detail: "Configure company identity, defaults and product settings.",
    href: "/admin/company",
    code: "10",
    meta: "Configuration",
    featureKeys: ["admin.company"],
    permissionKeys: ["admin.settings.view"],
    organizationOnly: true,
  },
];

function WorkspaceCard({ workspace, featured = false }: { workspace: Workspace; featured?: boolean }) {
  return (
    <Link
      className={`${styles.card} ${featured ? styles.featuredCard : ""} ${
        workspace.tone ? styles[workspace.tone] : ""
      }`}
      href={workspace.href}
    >
      <div className={styles.cardTop}>
        <span className={styles.code}>{workspace.code}</span>
        <span className={styles.openMark} aria-hidden="true">↗</span>
      </div>
      <div className={styles.cardBody}>
        <p className={styles.eyebrow}>{workspace.eyebrow}</p>
        <h2>{workspace.title}</h2>
        <p>{workspace.detail}</p>
      </div>
      <div className={styles.cardFoot}>
        <span className={styles.readyDot} />
        <span>{workspace.meta}</span>
      </div>
    </Link>
  );
}

export default function WorkspaceHome() {
  const { context, hasFeature, hasPermission, hasPermissionAnywhere, logout } = useWebSession();

  const visible = (workspace: Workspace) => {
    if (workspace.featureKeys?.some((key) => hasFeature(key))) return true;
    if (!workspace.permissionKeys?.length) return true;
    return workspace.permissionKeys.some((permission) =>
      workspace.organizationOnly ? hasPermission(permission) : hasPermissionAnywhere(permission),
    );
  };

  const primary = useMemo(
    () => primaryWorkspaces.filter(visible),
    [context.authorization_revision, context.configuration_revision],
  );
  const focused = useMemo(
    () => focusedWorkspaces.filter(visible),
    [context.authorization_revision, context.configuration_revision],
  );
  const admin = useMemo(
    () => adminWorkspaces.filter(visible),
    [context.authorization_revision, context.configuration_revision],
  );
  const allVisible = [...primary, ...focused, ...admin];

  return (
    <main className={styles.shell}>
      <aside className={styles.sidebar}>
        <Link className={styles.brand} href="/" aria-label="Construction OS home">
          <span className={styles.brandMark}>COS</span>
          <span>
            <strong>Construction OS</strong>
            <small>Project workspace</small>
          </span>
        </Link>

        <nav className={styles.navigation} aria-label="Workspace navigation">
          <div className={styles.sideSection}>
            <p>HOME</p>
            <Link className={`${styles.sideItem} ${styles.active}`} href="/"><span>⌂</span>Overview</Link>
          </div>

          {primary.length > 0 && (
            <div className={styles.sideSection}>
              <p>WORKSPACES</p>
              {primary.map((workspace) => (
                <Link className={styles.sideItem} href={workspace.href} key={workspace.href}>
                  <span>{workspace.code}</span>{workspace.title}
                </Link>
              ))}
            </div>
          )}

          {focused.length > 0 && (
            <div className={styles.sideSection}>
              <p>TOOLS</p>
              {focused.map((workspace) => (
                <Link className={styles.sideItem} href={workspace.href} key={workspace.href}>
                  <span>{workspace.code}</span>{workspace.title}
                </Link>
              ))}
            </div>
          )}

          {admin.length > 0 && (
            <div className={styles.sideSection}>
              <p>ADMINISTRATION</p>
              {admin.map((workspace) => (
                <Link className={styles.sideItem} href={workspace.href} key={workspace.href}>
                  <span>{workspace.code}</span>{workspace.title}
                </Link>
              ))}
            </div>
          )}
        </nav>

        <div className={styles.sidebarFoot}>
          <span className={styles.healthDot} />
          <span>
            <strong>Secure workspace</strong>
            <small>{allVisible.length} available {allVisible.length === 1 ? "area" : "areas"}</small>
          </span>
        </div>
      </aside>

      <section className={styles.workspace}>
        <header className={styles.topbar}>
          <div>
            <span className={styles.topbarLabel}>Construction OS</span>
            <strong>Project delivery workspace</strong>
          </div>
          <div className={styles.topbarActions}>
            <span className={styles.accessChip}>{allVisible.length} workspaces</span>
            <button onClick={() => void logout()} type="button">Sign out</button>
          </div>
        </header>

        <div className={styles.page}>
          <section className={styles.hero}>
            <div>
              <p className={styles.eyebrow}>YOUR WORKSPACE</p>
              <h1>Project operations, without the clutter.</h1>
              <p className={styles.heroCopy}>
                Construction OS now builds this web workspace from your company and project access. Modules you cannot use are kept out of the way.
              </p>
            </div>
            <div className={styles.heroAside}>
              <span>Access model</span>
              <strong>Role & project aware</strong>
              <small>Server permissions remain authoritative. Navigation only exposes the work areas available to this membership.</small>
            </div>
          </section>

          {allVisible.length === 0 ? (
            <section className={styles.emptyState}>
              <span>NO ACCESSIBLE WORKSPACES</span>
              <h2>Your account is active, but no project module is available yet.</h2>
              <p>Ask a company administrator to assign the required company or project role. The backend continues to enforce access even when navigation is hidden.</p>
            </section>
          ) : (
            <>
              {primary.length > 0 && (
                <section className={styles.section}>
                  <div className={styles.sectionHeading}>
                    <div>
                      <p className={styles.eyebrow}>START WORK</p>
                      <h2>Core workspaces</h2>
                    </div>
                    <p>Open the main areas available for your current role and project access.</p>
                  </div>
                  <div className={styles.primaryGrid}>
                    {primary.map((workspace) => (
                      <WorkspaceCard featured key={workspace.href} workspace={workspace} />
                    ))}
                  </div>
                </section>
              )}

              {focused.length > 0 && (
                <section className={styles.section}>
                  <div className={styles.sectionHeading}>
                    <div>
                      <p className={styles.eyebrow}>QUICK ACCESS</p>
                      <h2>Focused work areas</h2>
                    </div>
                    <p>Go directly to a task without opening a larger control workspace.</p>
                  </div>
                  <div className={styles.secondaryGrid}>
                    {focused.map((workspace) => (
                      <WorkspaceCard key={workspace.href} workspace={workspace} />
                    ))}
                  </div>
                </section>
              )}

              {admin.length > 0 && (
                <section className={styles.section}>
                  <div className={styles.sectionHeading}>
                    <div>
                      <p className={styles.eyebrow}>ADMINISTRATION</p>
                      <h2>Company & access</h2>
                    </div>
                    <p>Security and configuration appear only for memberships with administrative access.</p>
                  </div>
                  <div className={styles.secondaryGrid}>
                    {admin.map((workspace) => (
                      <WorkspaceCard key={workspace.href} workspace={workspace} />
                    ))}
                  </div>
                </section>
              )}
            </>
          )}
        </div>
      </section>
    </main>
  );
}
