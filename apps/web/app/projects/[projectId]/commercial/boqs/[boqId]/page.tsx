import BOQWorkspace from "../../../../../boq-workspace";

export default async function BOQDetailPage({
  params,
}: {
  params: Promise<{ projectId: string; boqId: string }>;
}) {
  const { projectId, boqId } = await params;
  return <BOQWorkspace initialProjectId={projectId} initialBoqId={boqId} />;
}
