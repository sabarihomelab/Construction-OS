import EstimatingWorkspace from "../../../estimating-workspace";

export default async function EstimateDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ estimateId: string }>;
  searchParams: Promise<{ project?: string }>;
}) {
  const { estimateId } = await params;
  const { project } = await searchParams;
  return <EstimatingWorkspace initialProjectId={project} initialEstimateId={estimateId} />;
}
