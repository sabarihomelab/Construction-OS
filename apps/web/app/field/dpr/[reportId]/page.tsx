import DPRGovernancePanel from "../../../dpr-governance-panel";
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
    {project && <main className="workspace-shell"><DPRGovernancePanel projectId={project} reportId={reportId} /></main>}
  </>;
}
