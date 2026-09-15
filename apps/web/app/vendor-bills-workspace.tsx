"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import styles from "./vendor-bills.module.css";

type AccessContext = {
  organization_id: string;
  membership_id: string;
  permissions: string[];
  project_permissions: Record<string, string[]>;
};

type Project = { id: string; number: string; name: string; status: string };
type Party = { id: string; code: string; name: string; status: string };
type PurchaseOrder = {
  id: string;
  number: string;
  supplier_party_id: string;
  status: string;
  currency_code: string;
  subtotal: string;
  tax_total: string;
  total: string;
};
type PurchaseOrderLine = {
  id: string;
  line_number: number;
  material_id: string | null;
  wbs_code_id: string | null;
  description: string;
  unit_code: string;
  quantity: string;
  unit_price: string;
  taxable_value: string;
  hsn_sac: string | null;
  tax_code: string | null;
  tax_rate: string | null;
  tax_amount: string;
  line_total: string;
};
type GoodsReceipt = {
  id: string;
  purchase_order_id: string;
  number: string;
  status: string;
  received_at: string;
};
type GoodsReceiptLine = {
  id: string;
  goods_receipt_id: string;
  purchase_order_line_id: string;
  received_quantity: string;
  accepted_quantity: string;
  rejected_quantity: string;
  unit_code: string;
};
type ReceiptMatch = {
  id: string;
  goods_receipt_line_id: string;
  matched_quantity: string;
};
type VendorBillLine = {
  id: string;
  line_number: number;
  purchase_order_line_id: string;
  material_id: string | null;
  wbs_code_id: string | null;
  boq_item_id: string | null;
  description: string;
  unit_code: string;
  quantity: string;
  unit_price: string;
  po_unit_price_snapshot: string;
  taxable_value: string;
  hsn_sac: string | null;
  tax_code: string | null;
  tax_rate: string | null;
  tax_amount: string;
  line_total: string;
  matched_quantity: string;
  quantity_variance: string;
  price_variance_amount: string;
  match_status: string;
  receipt_matches: ReceiptMatch[];
};
type VendorBill = {
  id: string;
  project_id: string;
  bill_number: string;
  supplier_party_id: string;
  purchase_order_id: string;
  supplier_invoice_number: string;
  invoice_date: string;
  due_date: string | null;
  currency_code: string;
  subtotal: string;
  tax_amount: string;
  total_amount: string;
  status: string;
  match_status: string;
  revision: number;
  variance_override_by_membership_id: string | null;
  variance_override_reason: string | null;
  notes: string | null;
  lines: VendorBillLine[];
};

type Props = { projectId: string; initialVendorBillId?: string };

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

function csrfToken(): string | null {
  if (typeof document === "undefined") return null;
  const entry = document.cookie
    .split(";")
    .map((value) => value.trim())
    .find((value) => value.startsWith("construction_os_csrf="));
  return entry ? decodeURIComponent(entry.split("=").slice(1).join("=")) : null;
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const method = (init?.method || "GET").toUpperCase();
  const headers = new Headers(init?.headers);
  if (init?.body) headers.set("Content-Type", "application/json");
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    const token = csrfToken();
    if (token) headers.set("X-CSRF-Token", token);
  }
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    credentials: "include",
    cache: "no-store",
  });
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      if (body?.detail) message = String(body.detail);
    } catch {}
    throw new Error(message);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

function money(value: string, currency = "INR") {
  const amount = Number(value);
  if (!Number.isFinite(amount)) return "—";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(amount);
}

function dateLabel(value: string | null) {
  if (!value) return "—";
  const parsed = new Date(`${value}T00:00:00`);
  return Number.isNaN(parsed.valueOf())
    ? value
    : new Intl.DateTimeFormat("en-IN", { dateStyle: "medium" }).format(parsed);
}

function Status({ value }: { value: string }) {
  return (
    <span className={styles.status} data-status={value}>
      {value.replaceAll("_", " ")}
    </span>
  );
}

export default function VendorBillsWorkspace({ projectId, initialVendorBillId }: Props) {
  const [context, setContext] = useState<AccessContext | null>(null);
  const [project, setProject] = useState<Project | null>(null);
  const [parties, setParties] = useState<Party[]>([]);
  const [purchaseOrders, setPurchaseOrders] = useState<PurchaseOrder[]>([]);
  const [bills, setBills] = useState<VendorBill[]>([]);
  const [selectedId, setSelectedId] = useState(initialVendorBillId || "");
  const [poLines, setPoLines] = useState<PurchaseOrderLine[]>([]);
  const [receiptLines, setReceiptLines] = useState<GoodsReceiptLine[]>([]);
  const [receiptNumbers, setReceiptNumbers] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [transitionReason, setTransitionReason] = useState("");
  const [overrideVariance, setOverrideVariance] = useState(false);

  const permissions = useMemo(() => {
    if (!context) return new Set<string>();
    return new Set([
      ...context.permissions,
      ...(context.project_permissions[projectId] || []),
    ]);
  }, [context, projectId]);
  const can = useCallback((key: string) => permissions.has(key), [permissions]);
  const selected = bills.find((item) => item.id === selectedId) || null;
  const supplier = parties.find((item) => item.id === selected?.supplier_party_id) || null;
  const selectedPo = purchaseOrders.find((item) => item.id === selected?.purchase_order_id) || null;

  const loadCore = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const access = await api<AccessContext>("/session/context");
      setContext(access);
      const allowed = new Set([
        ...access.permissions,
        ...(access.project_permissions[projectId] || []),
      ]);
      if (!allowed.has("financials.payable.view")) {
        throw new Error("You do not have permission to view vendor bills for this project.");
      }
      const [projects, vendorBills] = await Promise.all([
        api<Project[]>("/projects"),
        api<VendorBill[]>(`/projects/${projectId}/financials/vendor-bills`),
      ]);
      setProject(projects.find((item) => item.id === projectId) || null);
      setBills(vendorBills);
      setSelectedId((current) => {
        if (current && vendorBills.some((item) => item.id === current)) return current;
        return initialVendorBillId && vendorBills.some((item) => item.id === initialVendorBillId)
          ? initialVendorBillId
          : vendorBills[0]?.id || "";
      });
      if (allowed.has("procurement.purchase_order.view")) {
        setPurchaseOrders(
          await api<PurchaseOrder[]>(`/projects/${projectId}/procurement/purchase-orders`),
        );
      } else {
        setPurchaseOrders([]);
      }
      if (allowed.has("commercial.party.view")) {
        setParties(await api<Party[]>("/commercial/parties"));
      } else {
        setParties([]);
      }
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setLoading(false);
    }
  }, [initialVendorBillId, projectId]);

  const loadPoContext = useCallback(
    async (purchaseOrderId: string) => {
      if (!context || !purchaseOrderId) {
        setPoLines([]);
        setReceiptLines([]);
        return;
      }
      if (!can("procurement.purchase_order.view")) {
        setPoLines([]);
        setReceiptLines([]);
        return;
      }
      const lines = await api<PurchaseOrderLine[]>(
        `/projects/${projectId}/procurement/purchase-orders/${purchaseOrderId}/lines`,
      );
      setPoLines(lines);
      if (!can("procurement.receipt.view")) {
        setReceiptLines([]);
        return;
      }
      const receipts = (
        await api<GoodsReceipt[]>(`/projects/${projectId}/procurement/goods-receipts`)
      ).filter(
        (receipt) =>
          receipt.purchase_order_id === purchaseOrderId && receipt.status === "received",
      );
      const receiptMap: Record<string, string> = {};
      receipts.forEach((receipt) => {
        receiptMap[receipt.id] = receipt.number;
      });
      setReceiptNumbers(receiptMap);
      const nested = await Promise.all(
        receipts.map((receipt) =>
          api<GoodsReceiptLine[]>(
            `/projects/${projectId}/procurement/goods-receipts/${receipt.id}/lines`,
          ),
        ),
      );
      setReceiptLines(nested.flat());
    },
    [can, context, projectId],
  );

  useEffect(() => {
    void loadCore();
  }, [loadCore]);

  useEffect(() => {
    if (!selected?.purchase_order_id) {
      setPoLines([]);
      setReceiptLines([]);
      return;
    }
    void loadPoContext(selected.purchase_order_id).catch((requestError: Error) =>
      setError(requestError.message),
    );
  }, [loadPoContext, selected?.purchase_order_id]);

  const mutate = async (work: () => Promise<unknown>, selectResult = false) => {
    setBusy(true);
    setError("");
    try {
      const result = await work();
      if (selectResult && result && typeof result === "object" && "id" in result) {
        setSelectedId(String((result as { id: unknown }).id));
      }
      await loadCore();
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const submitJson = <T,>(path: string, payload: unknown, method = "POST") =>
    api<T>(path, { method, body: JSON.stringify(payload) });

  const partyLabel = (id: string) => {
    const party = parties.find((item) => item.id === id);
    return party ? `${party.code} · ${party.name}` : `Supplier ${id.slice(0, 8)}`;
  };

  const availableOrders = purchaseOrders.filter((item) =>
    ["issued", "part_received", "closed"].includes(item.status),
  );

  const addLine = (event: FormEvent<HTMLFormElement>, line: PurchaseOrderLine) => {
    event.preventDefault();
    if (!selected) return;
    const form = new FormData(event.currentTarget);
    const matches = receiptLines
      .filter((receipt) => receipt.purchase_order_line_id === line.id)
      .map((receipt) => ({
        goods_receipt_line_id: receipt.id,
        matched_quantity: String(form.get(`receipt_${receipt.id}`) || "0"),
      }))
      .filter((match) => Number(match.matched_quantity) > 0);
    void mutate(() =>
      submitJson<VendorBill>(
        `/projects/${projectId}/financials/vendor-bills/${selected.id}/lines`,
        {
          purchase_order_line_id: line.id,
          quantity: form.get("quantity"),
          unit_price: form.get("unit_price"),
          hsn_sac: form.get("hsn_sac") || null,
          tax_code: form.get("tax_code") || null,
          tax_rate: form.get("tax_rate") || null,
          tax_amount: form.get("tax_amount") || "0",
          receipt_matches: matches,
        },
      ),
    );
  };

  if (loading) {
    return (
      <main className={styles.page}>
        <section className={styles.stateCard}>Loading vendor bills…</section>
      </main>
    );
  }

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <div>
          <a className={styles.back} href="/">← Construction OS</a>
          <p className={styles.eyebrow}>FINANCIAL CONTROLS · INDIA</p>
          <h1>Vendor Bills & Payables</h1>
          <p className={styles.subheading}>
            {project ? `${project.number} · ${project.name}` : "Project access unavailable"}
          </p>
        </div>
        <button className={styles.secondaryButton} disabled={busy} onClick={() => void loadCore()}>
          Refresh
        </button>
      </header>

      {error && (
        <div className={styles.error} role="alert">
          <strong>Action not completed</strong>
          <span>{error}</span>
          <button onClick={() => setError("")}>×</button>
        </div>
      )}

      <section className={styles.explainer}>
        <strong>Three-way control without duplicate project cost</strong>
        <span>PO = commitment · GRN = physical receipt · Vendor bill = payable</span>
        <small>Material actual cost remains driven by posted material consumption.</small>
      </section>

      <div className={styles.layout}>
        <aside className={styles.listPanel}>
          <div className={styles.panelHeading}>
            <div><span>Vendor bills</span><strong>{bills.length}</strong></div>
          </div>

          {can("financials.payable.create") && (
            <form
              className={styles.createForm}
              onSubmit={(event) => {
                event.preventDefault();
                const form = new FormData(event.currentTarget);
                void mutate(
                  () =>
                    submitJson<VendorBill>(`/projects/${projectId}/financials/vendor-bills`, {
                      purchase_order_id: form.get("purchase_order_id"),
                      supplier_invoice_number: form.get("supplier_invoice_number"),
                      invoice_date: form.get("invoice_date"),
                      due_date: form.get("due_date") || null,
                      notes: form.get("notes") || null,
                    }),
                  true,
                );
              }}
            >
              <strong>New supplier invoice</strong>
              {can("procurement.purchase_order.view") ? (
                <>
                  <select name="purchase_order_id" required defaultValue="">
                    <option value="" disabled>Select issued PO</option>
                    {availableOrders.map((order) => (
                      <option key={order.id} value={order.id}>
                        {order.number} · {partyLabel(order.supplier_party_id)} · {money(order.total, order.currency_code)}
                      </option>
                    ))}
                  </select>
                  {availableOrders.length === 0 && (
                    <small>No issued or received purchase order is available for billing.</small>
                  )}
                </>
              ) : (
                <small>Purchase Order view permission is required to create a vendor bill.</small>
              )}
              <input name="supplier_invoice_number" placeholder="Supplier invoice no." required />
              <label>Invoice date<input name="invoice_date" type="date" required /></label>
              <label>Due date<input name="due_date" type="date" /></label>
              <textarea name="notes" placeholder="Optional invoice note" rows={2} />
              <button disabled={busy || !can("procurement.purchase_order.view")}>Create draft</button>
            </form>
          )}

          <div className={styles.billList}>
            {bills.length === 0 ? (
              <div className={styles.empty}>
                <strong>No vendor bills yet</strong>
                <span>Create the first bill from an issued purchase order.</span>
              </div>
            ) : (
              bills.map((bill) => (
                <button
                  key={bill.id}
                  className={bill.id === selectedId ? styles.billItemActive : styles.billItem}
                  onClick={() => setSelectedId(bill.id)}
                >
                  <span><strong>{bill.bill_number}</strong><Status value={bill.status} /></span>
                  <b>{money(bill.total_amount, bill.currency_code)}</b>
                  <small>{bill.supplier_invoice_number} · {dateLabel(bill.invoice_date)}</small>
                  <Status value={bill.match_status} />
                </button>
              ))
            )}
          </div>
        </aside>

        <section className={styles.detailPanel}>
          {!selected ? (
            <div className={styles.emptyDetail}>
              <strong>Select a vendor bill</strong>
              <span>The invoice, PO/GRN match, approvals and amounts will appear here.</span>
            </div>
          ) : (
            <>
              <div className={styles.detailHeader}>
                <div>
                  <span className={styles.eyebrow}>SUPPLIER INVOICE</span>
                  <h2>{selected.bill_number}</h2>
                  <p>{supplier ? `${supplier.code} · ${supplier.name}` : partyLabel(selected.supplier_party_id)}</p>
                </div>
                <div className={styles.headerStatuses}>
                  <Status value={selected.status} />
                  <Status value={selected.match_status} />
                </div>
              </div>

              <div className={styles.metrics}>
                <article><span>Invoice total</span><strong>{money(selected.total_amount, selected.currency_code)}</strong></article>
                <article><span>Tax snapshot</span><strong>{money(selected.tax_amount, selected.currency_code)}</strong></article>
                <article><span>PO</span><strong>{selectedPo?.number || selected.purchase_order_id.slice(0, 8)}</strong></article>
                <article><span>Due</span><strong>{dateLabel(selected.due_date)}</strong></article>
              </div>

              {selected.variance_override_reason && (
                <div className={styles.warning}>
                  <strong>Variance override recorded</strong>
                  <span>{selected.variance_override_reason}</span>
                </div>
              )}

              <section className={styles.section}>
                <div className={styles.sectionHeading}>
                  <div><h3>Invoice lines</h3><p>PO facts and GRN allocations are preserved against every supplier invoice line.</p></div>
                </div>
                {selected.lines.length === 0 ? (
                  <div className={styles.empty}><strong>No invoice lines</strong><span>Add the supplier invoice quantities below before submitting.</span></div>
                ) : (
                  <div className={styles.lines}>
                    {selected.lines.map((line) => (
                      <article className={styles.lineCard} key={line.id}>
                        <div className={styles.lineTop}>
                          <div><small>Line {line.line_number}</small><strong>{line.description}</strong><span>{line.quantity} {line.unit_code} × {money(line.unit_price, selected.currency_code)}</span></div>
                          <div><b>{money(line.line_total, selected.currency_code)}</b><Status value={line.match_status} /></div>
                        </div>
                        <div className={styles.matchFacts}>
                          <span>GRN matched <b>{line.matched_quantity} {line.unit_code}</b></span>
                          <span>Qty variance <b>{line.quantity_variance}</b></span>
                          <span>Price variance <b>{money(line.price_variance_amount, selected.currency_code)}</b></span>
                        </div>
                        {line.receipt_matches.length > 0 && (
                          <small className={styles.receiptSummary}>
                            {line.receipt_matches.map((match) => `${match.matched_quantity} from ${match.goods_receipt_line_id.slice(0, 8)}`).join(" · ")}
                          </small>
                        )}
                        {selected.status === "draft" && can("financials.payable.manage") && (
                          <button
                            className={styles.linkButton}
                            disabled={busy}
                            onClick={() =>
                              void mutate(() =>
                                api(
                                  `/projects/${projectId}/financials/vendor-bills/${selected.id}/lines/${line.id}`,
                                  { method: "DELETE" },
                                ),
                              )
                            }
                          >
                            Remove draft line
                          </button>
                        )}
                      </article>
                    ))}
                  </div>
                )}
              </section>

              {selected.status === "draft" && can("financials.payable.manage") && (
                <section className={styles.section}>
                  <div className={styles.sectionHeading}>
                    <div><h3>Add PO line</h3><p>For materials, allocate only accepted quantities from received GRNs. Service PO lines do not require a GRN.</p></div>
                  </div>
                  {!can("procurement.purchase_order.view") ? (
                    <div className={styles.warning}>Purchase Order view permission is required to reconcile invoice lines.</div>
                  ) : (
                    <div className={styles.lineForms}>
                      {poLines
                        .filter((line) => !selected.lines.some((item) => item.purchase_order_line_id === line.id))
                        .map((line) => {
                          const eligibleReceipts = receiptLines.filter(
                            (receipt) => receipt.purchase_order_line_id === line.id && Number(receipt.accepted_quantity) > 0,
                          );
                          return (
                            <form className={styles.lineForm} key={line.id} onSubmit={(event) => addLine(event, line)}>
                              <div className={styles.lineFormTitle}>
                                <div><small>PO line {line.line_number}</small><strong>{line.description}</strong><span>{line.quantity} {line.unit_code} ordered · PO rate {money(line.unit_price, selected.currency_code)}</span></div>
                                {line.material_id ? <span className={styles.tag}>Material</span> : <span className={styles.tag}>Service</span>}
                              </div>
                              <div className={styles.formGrid}>
                                <label>Invoice quantity<input name="quantity" type="number" min="0.0001" step="0.0001" defaultValue={line.quantity} required /></label>
                                <label>Invoice unit price<input name="unit_price" type="number" min="0" step="0.0001" defaultValue={line.unit_price} required /></label>
                                <label>HSN/SAC<input name="hsn_sac" defaultValue={line.hsn_sac || ""} /></label>
                                <label>Tax code<input name="tax_code" defaultValue={line.tax_code || ""} /></label>
                                <label>Tax rate %<input name="tax_rate" type="number" min="0" step="0.0001" defaultValue={line.tax_rate || ""} /></label>
                                <label>Tax amount<input name="tax_amount" type="number" min="0" step="0.01" defaultValue={line.tax_amount || "0"} /></label>
                              </div>
                              {line.material_id && (
                                <div className={styles.receiptBlock}>
                                  <strong>Allocate accepted GRN quantity</strong>
                                  {!can("procurement.receipt.view") ? (
                                    <small>Goods Receipt view permission is required for material invoice matching.</small>
                                  ) : eligibleReceipts.length === 0 ? (
                                    <small>No accepted GRN quantity is available for this PO line.</small>
                                  ) : (
                                    eligibleReceipts.map((receipt) => (
                                      <label key={receipt.id}>
                                        <span>{receiptNumbers[receipt.goods_receipt_id] || "GRN"} · accepted {receipt.accepted_quantity} {receipt.unit_code}</span>
                                        <input name={`receipt_${receipt.id}`} type="number" min="0" step="0.0001" placeholder="Match qty" />
                                      </label>
                                    ))
                                  )}
                                </div>
                              )}
                              <button disabled={busy || Boolean(line.material_id && !can("procurement.receipt.view"))}>Add invoice line</button>
                            </form>
                          );
                        })}
                      {poLines.length > 0 && poLines.every((line) => selected.lines.some((item) => item.purchase_order_line_id === line.id)) && (
                        <div className={styles.empty}>All purchase-order lines are already represented on this draft bill.</div>
                      )}
                    </div>
                  )}
                </section>
              )}

              <section className={styles.actions}>
                <div>
                  <strong>Controlled action</strong>
                  <small>High-risk approval and variance override actions always require server confirmation and audit.</small>
                </div>
                <textarea value={transitionReason} onChange={(event) => setTransitionReason(event.target.value)} rows={2} placeholder="Reason / review note" />
                {selected.status === "draft" && selected.match_status !== "matched" && can("financials.payable.override") && (
                  <label className={styles.overrideCheck}>
                    <input type="checkbox" checked={overrideVariance} onChange={(event) => setOverrideVariance(event.target.checked)} />
                    Submit with variance override
                  </label>
                )}
                <div className={styles.actionButtons}>
                  {selected.status === "draft" && can("financials.payable.submit") && (
                    <button
                      disabled={busy || selected.lines.length === 0 || (selected.match_status !== "matched" && !overrideVariance)}
                      onClick={() =>
                        void mutate(() =>
                          submitJson<VendorBill>(
                            `/projects/${projectId}/financials/vendor-bills/${selected.id}/submit`,
                            {
                              expected_revision: selected.revision,
                              allow_variance_override: overrideVariance,
                              reason: transitionReason || null,
                            },
                          ),
                        )
                      }
                    >
                      Submit for approval
                    </button>
                  )}
                  {selected.status === "submitted" && can("financials.payable.approve") && (
                    <>
                      <button
                        disabled={busy}
                        onClick={() =>
                          void mutate(() =>
                            submitJson<VendorBill>(
                              `/projects/${projectId}/financials/vendor-bills/${selected.id}/approve`,
                              { expected_revision: selected.revision, reason: transitionReason || null },
                            ),
                          )
                        }
                      >
                        Approve payable
                      </button>
                      <button
                        className={styles.dangerButton}
                        disabled={busy || !transitionReason.trim()}
                        onClick={() =>
                          void mutate(() =>
                            submitJson<VendorBill>(
                              `/projects/${projectId}/financials/vendor-bills/${selected.id}/reject`,
                              { expected_revision: selected.revision, reason: transitionReason },
                            ),
                          )
                        }
                      >
                        Reject
                      </button>
                    </>
                  )}
                </div>
              </section>
            </>
          )}
        </section>
      </div>
    </main>
  );
}
