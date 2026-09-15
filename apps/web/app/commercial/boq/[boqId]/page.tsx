import BOQWorkspace from "../../../boq-workspace";

export default async function BOQDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ boqId: string }>;
  searchParams: Promise<{ project?: string }>;
}) {
  const { boqId } = await params;
  const { project } = await searchParams;
  return <BOQWorkspace initialProjectId={project} initialBoqId={boqId} />;
}
