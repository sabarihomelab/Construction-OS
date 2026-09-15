import PartyDirectoryWorkspace from "../../../party-directory-workspace";

export default async function PartyDetailPage({
  params,
}: {
  params: Promise<{ partyId: string }>;
}) {
  const { partyId } = await params;
  return <PartyDirectoryWorkspace partyId={partyId} />;
}
