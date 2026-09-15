import WorkerDetailWorkspace from "../../../worker-detail-workspace";

export default async function WorkerDetailPage({ params }: { params: Promise<{ workerId: string }> }) {
  const { workerId } = await params;
  return <WorkerDetailWorkspace workerId={workerId} />;
}
