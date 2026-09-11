import DPRWorkspace from "../../../../dpr-workspace";

export default async function ProjectDPRDetailPage({ params }: { params: Promise<{ projectId: string; reportId: string }> }) {
  const { projectId, reportId } = await params;
  return <DPRWorkspace initialProjectId={projectId} initialReportId={reportId} />;
}
