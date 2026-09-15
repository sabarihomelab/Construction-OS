import DPRFieldExtensions from "../../../../dpr-field-extensions";
import DPRGovernancePanel from "../../../../dpr-governance-panel";
import DPRVoidControl from "../../../../dpr-void-control";
import DPRWorkspace from "../../../../dpr-workspace";

export default async function ProjectDPRDetailPage({
  params,
}: {
  params: Promise<{ projectId: string; reportId: string }>;
}) {
  const { projectId, reportId } = await params;
  return <>
    <DPRWorkspace initialProjectId={projectId} initialReportId={reportId} />
    <main className="workspace-shell">
      <DPRFieldExtensions projectId={projectId} reportId={reportId} />
      <DPRGovernancePanel projectId={projectId} reportId={reportId} />
      <DPRVoidControl projectId={projectId} reportId={reportId} />
    </main>
  </>;
}
