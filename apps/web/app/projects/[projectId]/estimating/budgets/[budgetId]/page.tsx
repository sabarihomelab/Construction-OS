import EstimatingWorkspace from "../../../../../estimating-workspace";

export default async function BudgetDetailPage({ params }: { params: Promise<{ projectId: string; budgetId: string }> }) {
  const { projectId, budgetId } = await params;
  return <EstimatingWorkspace initialProjectId={projectId} initialBudgetId={budgetId} />;
}
