import TimecardDetailWorkspace from "../../../../timecard-detail-workspace";

export default async function TimecardDetailPage({
  params,
}: {
  params: Promise<{ projectId: string; timecardId: string }>;
}) {
  const { projectId, timecardId } = await params;
  return <TimecardDetailWorkspace projectId={projectId} timecardId={timecardId} />;
}
