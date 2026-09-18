import VendorBillsWorkspace from "../../../../vendor-bills-workspace";

export default async function VendorBillsPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  return <VendorBillsWorkspace projectId={projectId} />;
}
