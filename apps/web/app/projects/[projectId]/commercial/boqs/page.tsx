import BOQWorkspace from "../../../../boq-workspace";

export default async function ProjectBOQPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  return <BOQWorkspace initialProjectId={projectId} />;
}
