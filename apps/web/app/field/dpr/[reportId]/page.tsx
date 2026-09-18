import DPRFieldExtensions from "../../../dpr-field-extensions";
import DPRGovernancePanel from "../../../dpr-governance-panel";
import DPRReportOwnedSections from "../../../dpr-report-owned-sections";
import DPRVoidControl from "../../../dpr-void-control";
import DPRWorkspace from "../../../dpr-workspace";

export default async function DPRDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ reportId: string }>;
  searchParams: Promise<{ project?: string }>;
}) {
  const { reportId } = await params;
  const { project } = await searchParams;
  return <>
    <DPRWorkspace initialProjectId={project} initialReportId={reportId} />
    {project && <main className="workspace-shell">
      <DPRReportOwnedSections projectId={project} reportId={reportId} />
      <DPRFieldExtensions projectId={project} reportId={reportId} />
      <DPRGovernancePanel projectId={project} reportId={reportId} />
      <DPRVoidControl projectId={project} reportId={reportId} />
    </main>}
  </>;
}
