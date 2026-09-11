import WBSWorkspace from "../../../../wbs-workspace";

export default async function ProjectWBSPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  return <WBSWorkspace initialProjectId={projectId} />;
}
