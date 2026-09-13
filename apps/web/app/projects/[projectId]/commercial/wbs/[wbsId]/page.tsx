import WBSWorkspace from "../../../../../wbs-workspace";

export default async function WBSDetailPage({
  params,
}: {
  params: Promise<{ projectId: string; wbsId: string }>;
}) {
  const { projectId, wbsId } = await params;
  return <WBSWorkspace initialProjectId={projectId} initialWbsId={wbsId} />;
}
