import EstimatingWorkspace from "../../../estimating-workspace";

export default async function BudgetDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ budgetId: string }>;
  searchParams: Promise<{ project?: string }>;
}) {
  const { budgetId } = await params;
  const { project } = await searchParams;
  return <EstimatingWorkspace initialProjectId={project} initialBudgetId={budgetId} />;
}
