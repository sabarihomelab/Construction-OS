import AttendanceWorkspace from "../../../attendance-workspace";

export default async function WorkforceAttendanceDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ registerId: string }>;
  searchParams: Promise<{ project?: string }>;
}) {
  const { registerId } = await params;
  const { project } = await searchParams;
  return <AttendanceWorkspace initialProjectId={project} initialRegisterId={registerId} />;
}
