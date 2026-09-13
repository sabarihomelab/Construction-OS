import Link from "next/link";
import styles from "./workspace-home.module.css";

type Workspace = {
  eyebrow: string;
  title: string;
  detail: string;
  href: string;
  code: string;
  meta: string;
  tone?: "lime" | "blue" | "sand" | "rose";
};

const primaryWorkspaces: Workspace[] = [
  {
    eyebrow: "FIELD",
    title: "Daily field operations",
    detail: "Run DPR capture and the field-first workflows that connect site activity to project controls.",
    href: "/field",
    code: "01",
    meta: "DPR workspace",
    tone: "lime",
  },
  {
    eyebrow: "PRE-CONSTRUCTION",
    title: "Estimating",
    detail: "Build estimates, cost structures and pricing inputs before work moves into commercial control.",
    href: "/estimating",
    code: "02",
    meta: "Estimating workspace",
    tone: "blue",
  },
  {
    eyebrow: "COMMERCIAL",
    title: "Commercial control room",
    detail: "Manage WBS, BOQ, measurements and RA billing from one project commercial workspace.",
    href: "/commercial/control-room",
    code: "03",
    meta: "Project controls",
    tone: "sand",
  },
];

const focusedWorkspaces: Workspace[] = [
  {
    eyebrow: "FIELD",
    title: "Attendance",
    detail: "Mark project crews, working hours and cost codes once, then reuse approved attendance in DPR.",
    href: "/field/attendance",
    code: "04",
    meta: "Authoritative workforce record",
  },
  {
    eyebrow: "COMMERCIAL",
    title: "BOQ",
    detail: "Open the focused BOQ workspace for quantity and rate management.",
    href: "/commercial/boq",
    code: "05",
    meta: "Focused workspace",
  },
  {
    eyebrow: "MASTER DATA",
    title: "Parties",
    detail: "Maintain clients, consultants, suppliers and subcontractors.",
    href: "/commercial/parties",
    code: "06",
    meta: "Company directory",
  },
  {
    eyebrow: "MASTER DATA",
    title: "WBS & cost codes",
    detail: "Maintain the project work breakdown and cost-code hierarchy.",
    href: "/commercial/wbs",
    code: "07",
    meta: "Project structure",
  },
];

const adminWorkspaces: Workspace[] = [
  {
    eyebrow: "ADMIN",
    title: "Access management",
    detail: "Manage organization roles, permissions and user access.",
    href: "/admin/access",
    code: "08",
    meta: "Security administration",
  },
  {
    eyebrow: "ADMIN",
    title: "Project access",
    detail: "Control project memberships and project-scoped permissions.",
    href: "/admin/project-access",
    code: "09",
    meta: "Project security",
  },
  {
    eyebrow: "ADMIN",
    title: "Company settings",
    detail: "Configure company-level identity and product settings.",
    href: "/admin/company",
    code: "10",
    meta: "Configuration",
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
  return (
    <main className={styles.shell}>
      <aside className={styles.sidebar}>
        <Link className={styles.brand} href="/" aria-label="Construction OS home">
          <span className={styles.brandMark}>COS</span>
          <span>
            <strong>Construction OS</strong>
            <small>Web workspace</small>
          </span>
        </Link>

        <div className={styles.sideSection}>
          <p>WORKSPACE</p>
          <a className={`${styles.sideItem} ${styles.active}`} href="#workspaces"><span>01</span>Home</a>
          <a className={styles.sideItem} href="#modules"><span>02</span>Modules</a>
          <a className={styles.sideItem} href="#admin"><span>03</span>Administration</a>
        </div>

        <div className={styles.sidebarFoot}>
          <span className={styles.healthDot} />
          <span>
            <strong>Platform foundation</strong>
            <small>Unified web entry point</small>
          </span>
        </div>
      </aside>

      <section className={styles.workspace} id="workspaces">
        <header className={styles.topbar}>
          <div>
            <span className={styles.topbarLabel}>Construction OS</span>
            <strong>Project delivery workspace</strong>
          </div>
          <div className={styles.topbarMeta}>
            <span>India</span>
            <span>INR</span>
            <span>Asia/Kolkata</span>
          </div>
        </header>

        <div className={styles.page}>
          <section className={styles.hero}>
            <div>
              <p className={styles.eyebrow}>WEB PRODUCT FOUNDATION</p>
              <h1>One place to run the project.</h1>
              <p className={styles.heroCopy}>
                Start in the field, estimate the work, control commercial quantities and manage access without jumping between disconnected tools.
              </p>
            </div>
            <div className={styles.heroAside}>
              <span>Current build</span>
              <strong>Web workspace</strong>
              <small>Existing product workflows are preserved and connected here as the full web product grows.</small>
            </div>
          </section>

          <section className={styles.section}>
            <div className={styles.sectionHeading}>
              <div>
                <p className={styles.eyebrow}>START WORK</p>
                <h2>Core workspaces</h2>
              </div>
              <p>Open the major product areas already implemented on the platform branch.</p>
            </div>
            <div className={styles.primaryGrid}>
              {primaryWorkspaces.map((workspace) => (
                <WorkspaceCard featured key={workspace.href} workspace={workspace} />
              ))}
            </div>
          </section>

          <section className={styles.section} id="modules">
            <div className={styles.sectionHeading}>
              <div>
                <p className={styles.eyebrow}>MODULES</p>
                <h2>Focused work areas</h2>
              </div>
              <p>Use focused screens for site and control tasks without opening a full workspace.</p>
            </div>
            <div className={styles.secondaryGrid}>
              {focusedWorkspaces.map((workspace) => (
                <WorkspaceCard key={workspace.href} workspace={workspace} />
              ))}
            </div>
          </section>

          <section className={styles.section} id="admin">
            <div className={styles.sectionHeading}>
              <div>
                <p className={styles.eyebrow}>ADMINISTRATION</p>
                <h2>Company & access</h2>
              </div>
              <p>Keep security and configuration separate from day-to-day project work.</p>
            </div>
            <div className={styles.secondaryGrid}>
              {adminWorkspaces.map((workspace) => (
                <WorkspaceCard key={workspace.href} workspace={workspace} />
              ))}
            </div>
          </section>
        </div>
      </section>
    </main>
  );
}
