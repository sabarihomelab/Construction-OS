import WBSWorkspace from "../../../wbs-workspace";

export default async function WBSDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ wbsId: string }>;
  searchParams: Promise<{ project?: string }>;
}) {
  const { wbsId } = await params;
  const { project } = await searchParams;
  return <WBSWorkspace initialProjectId={project} initialWbsId={wbsId} />;
}
