const modules = [
  ["Field", "Crews, timesheets, daily reports, safety and equipment"],
  ["Projects", "Tasks, RFIs, submittals, drawings, inspections and documents"],
  ["Financials", "Budgets, costs, commitments, change orders and payroll prep"],
  ["AI", "Voice reporting, project summaries, document extraction and risk signals"],
];

const navigation = ["Overview", "Projects", "Field", "Financials", "Reports", "Support"];

export default function Home() {
  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand">COS</div>
        <nav>
          <strong>Construction OS</strong>
          {navigation.map((item) => <span key={item}>{item}</span>)}
        </nav>
      </aside>

      <section className="content">
        <div className="mobile-bar">
          <div className="mobile-brand"><span>COS</span><strong>Construction OS</strong></div>
          <nav className="mobile-nav" aria-label="Primary navigation">
            {navigation.map((item) => <span key={item}>{item}</span>)}
          </nav>
        </div>

        <header>
          <div>
            <p className="eyebrow">PLATFORM FOUNDATION</p>
            <h1>One operating system for construction.</h1>
            <p className="lede">Run field work, project controls and financial workflows from the same source of truth.</p>
          </div>
          <button>New project</button>
        </header>

        <div className="stats">
          <article><span>Active projects</span><b>0</b></article>
          <article><span>People on site</span><b>0</b></article>
          <article><span>Open RFIs</span><b>0</b></article>
          <article><span>Pending approvals</span><b>0</b></article>
        </div>

        <h2>Platform modules</h2>
        <div className="grid">
          {modules.map(([name, description]) => (
            <article className="card" key={name}>
              <div className="icon">{name.slice(0, 1)}</div>
              <h3>{name}</h3>
              <p>{description}</p>
              <span className="status">Foundation ready</span>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}
