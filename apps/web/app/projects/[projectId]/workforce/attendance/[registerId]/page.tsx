import AttendanceWorkspace from "../../../../../attendance-workspace";

export default async function AttendancePage({
  params,
}: {
  params: Promise<{ projectId: string; registerId: string }>;
}) {
  const { projectId, registerId } = await params;
  return <AttendanceWorkspace initialProjectId={projectId} initialRegisterId={registerId} />;
}
