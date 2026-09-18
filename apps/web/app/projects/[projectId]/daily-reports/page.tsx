import DPRWorkspace from "../../../dpr-workspace";

export default async function ProjectDPRPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  return <DPRWorkspace initialProjectId={projectId} />;
}
