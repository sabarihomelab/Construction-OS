import EstimatingWorkspace from "../../../estimating-workspace";

export default async function ProjectEstimatingPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  return <EstimatingWorkspace initialProjectId={projectId} />;
}
