import EstimatingWorkspace from "../../../../../estimating-workspace";

export default async function EstimateDetailPage({ params }: { params: Promise<{ projectId: string; estimateId: string }> }) {
  const { projectId, estimateId } = await params;
  return <EstimatingWorkspace initialProjectId={projectId} initialEstimateId={estimateId} />;
}
