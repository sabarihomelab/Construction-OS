import DPRFieldExtensions from "../../../dpr-field-extensions";
import DPRGovernancePanel from "../../../dpr-governance-panel";
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
      <DPRFieldExtensions projectId={project} reportId={reportId} />
      <DPRGovernancePanel projectId={project} reportId={reportId} />
      <DPRVoidControl projectId={project} reportId={reportId} />
    </main>}
  </>;
}
