import VendorBillsWorkspace from "../../../../../vendor-bills-workspace";

export default async function VendorBillDetailPage({
  params,
}: {
  params: Promise<{ projectId: string; vendorBillId: string }>;
}) {
  const { projectId, vendorBillId } = await params;
  return <VendorBillsWorkspace projectId={projectId} initialVendorBillId={vendorBillId} />;
}
