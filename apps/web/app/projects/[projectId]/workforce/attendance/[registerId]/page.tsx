import WorkforceWorkspace from "../../../../../workforce-workspace";

export default async function AttendancePage({ params }: { params: Promise<{ projectId: string; registerId: string }> }) {
  const { projectId, registerId } = await params;
  return <WorkforceWorkspace initialProjectId={projectId} initialRegisterId={registerId} />;
}
