import WorkforceWorkspace from "../../../workforce-workspace";

export default async function ProjectWorkforcePage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  return <WorkforceWorkspace initialProjectId={projectId} />;
}
