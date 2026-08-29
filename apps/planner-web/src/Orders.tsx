import { useState } from "react";
import type { Material, NamedEntity, Order } from "./api";
import { api } from "./api";
import { daysUntil, formatDate, humanizeOrderStatus } from "./format";
import { materialLabel } from "./Dashboard";
import { Button, EmptyState, ErrorBanner, Field, Panel, StatusChip, inputStyle } from "./ui";

interface NewLineDraft {
  material_spec_id: string;
  sheet_width_mm: string;
  sheet_length_mm: string;
  quantity: string;
}

const BLANK_LINE: NewLineDraft = { material_spec_id: "", sheet_width_mm: "", sheet_length_mm: "", quantity: "" };

export function Orders({
  orders,
  materials,
  customers,
  onChange,
}: {
  orders: Order[];
  materials: Material[];
  customers: NamedEntity[];
  onChange: () => Promise<void>;
}) {
  const [showAdd, setShowAdd] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const materialById = new Map(materials.map((m) => [m.id, m]));
  const customerById = new Map(customers.map((c) => [c.id, c.name]));

  const cancel = async (order: Order) => {
    if (!window.confirm(`Cancel order ${order.external_id}? It will no longer be planned.`)) return;
    setBusy(order.id);
    setError(null);
    try {
      await api.cancelOrder(order.id);
      await onChange();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not cancel the order");
    } finally {
      setBusy(null);
    }
  };

  const open = orders.filter((o) => ["confirmed", "released", "running"].includes(o.status));
  const done = orders.filter((o) => o.status === "complete" || o.status === "cancelled");

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
        <h2 style={{ margin: 0 }}>Customer Orders</h2>
        <Button kind="primary" onClick={() => setShowAdd((v) => !v)}>
          {showAdd ? "Close" : "+ Take an order"}
        </Button>
      </div>
      <p style={{ color: "#6b7280" }}>
        What your customers asked for. Each line is one sheet size, with the paper type they want.
        Orders stay here until a cutting plan that finishes them is carried out.
      </p>

      {error && <ErrorBanner text={error} />}

      {showAdd && (
        <AddOrderForm
          materials={materials}
          customers={customers}
          onDone={async () => {
            setShowAdd(false);
            await onChange();
          }}
          onCancel={() => setShowAdd(false)}
        />
      )}

      {orders.length === 0 ? (
        <EmptyState text="No orders yet. Use “+ Take an order” above, or import them from a spreadsheet under “Import Old Records”." />
      ) : (
        <>
          {open.map((order) => (
            <OrderCard
              key={order.id}
              order={order}
              materialById={materialById}
              customerById={customerById}
              onCancel={() => void cancel(order)}
              busy={busy === order.id}
            />
          ))}
          {done.length > 0 && (
            <>
              <h3 style={{ marginTop: 24 }}>Finished & cancelled</h3>
              {done.map((order) => (
                <OrderCard
                  key={order.id}
                  order={order}
                  materialById={materialById}
                  customerById={customerById}
                  onCancel={() => void cancel(order)}
                  busy={busy === order.id}
                />
              ))}
            </>
          )}
        </>
      )}
    </div>
  );
}

function OrderCard({
  order,
  materialById,
  customerById,
  onCancel,
  busy,
}: {
  order: Order;
  materialById: Map<string, Material>;
  customerById: Map<string, string>;
  onCancel: () => void;
  busy: boolean;
}) {
  const finished = order.status === "complete";
  const cancelled = order.status === "cancelled";
  const days = daysUntil(order.promised_at);
  return (
    <div
      style={{
        background: "white",
        borderRadius: 10,
        border: "1px solid #e5e7eb",
        padding: 16,
        marginBottom: 12,
        opacity: finished || cancelled ? 0.6 : 1,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
        <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
          <strong style={{ fontSize: 16 }}>{order.external_id}</strong>
          {customerById.get(order.customer_id) && (
            <span style={{ color: "#6b7280" }}>{customerById.get(order.customer_id)}</span>
          )}
          {finished ? (
            <StatusChip text="Fulfilled ✓" tone="green" />
          ) : cancelled ? (
            <StatusChip text="Cancelled" tone="gray" />
          ) : days !== null && days < 0 ? (
            <StatusChip text={`${Math.abs(days)} days late`} tone="red" />
          ) : days !== null && days <= 3 ? (
            <StatusChip text={`${days} day${days === 1 ? "" : "s"} left`} tone="amber" />
          ) : (
            <StatusChip text={humanizeOrderStatus(order.status)} tone="blue" />
          )}
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span style={{ color: "#6b7280" }}>Due {formatDate(order.promised_at)}</span>
          {!finished && !cancelled && (
            <Button small kind="danger" onClick={onCancel} disabled={busy}>
              Cancel order
            </Button>
          )}
        </div>
      </div>
      <div style={{ marginTop: 8 }}>
        {order.lines.map((line) => {
          const m = materialById.get(line.material_spec_id);
          return (
            <div
              key={line.id}
              style={{
                display: "flex",
                gap: 16,
                flexWrap: "wrap",
                padding: "6px 0",
                borderBottom: "1px dashed #f3f4f6",
                fontSize: 14,
              }}
            >
              <span style={{ minWidth: 160 }}>
                📄 {line.sheet_width_mm} × {line.sheet_length_mm} mm
              </span>
              <span style={{ minWidth: 100 }}>{line.quantity_required.toLocaleString()} sheets</span>
              <span style={{ color: "#6b7280" }}>
                {m ? `${m.family} ${m.gsm_value ?? "?"} GSM` : ""}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function AddOrderForm({
  materials,
  customers,
  onDone,
  onCancel,
}: {
  materials: Material[];
  customers: NamedEntity[];
  onDone: () => Promise<void>;
  onCancel: () => void;
}) {
  const [orderNumber, setOrderNumber] = useState("");
  const [customer, setCustomer] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [lines, setLines] = useState<NewLineDraft[]>([
    { ...BLANK_LINE, material_spec_id: materials[0]?.id ?? "" },
  ]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const addLine = () =>
    setLines((current) => [...current, { ...BLANK_LINE, material_spec_id: materials[0]?.id ?? "" }]);

  const setLine = (index: number, patch: Partial<NewLineDraft>) =>
    setLines((current) => current.map((line, i) => (i === index ? { ...line, ...patch } : line)));

  const problem = !orderNumber.trim()
    ? "Give the order a number"
    : !customer.trim()
      ? "Who ordered it?"
      : !dueDate
        ? "When is it due?"
        : lines.some((line) => {
            const w = Number(line.sheet_width_mm);
            const l = Number(line.sheet_length_mm);
            const q = Number(line.quantity);
            return (
              !line.material_spec_id ||
              !Number.isFinite(w) ||
              w <= 0 ||
              !Number.isFinite(l) ||
              l <= 0 ||
              !Number.isFinite(q) ||
              q <= 0
            );
          })
          ? "Every line needs a paper type, sheet width, sheet length, and quantity (all positive)"
          : null;

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      let customerId = customers.find((c) => c.name === customer.trim())?.id;
      if (!customerId) customerId = (await api.createCustomer(customer.trim())).id;

      const dueAt = new Date(`${dueDate}T23:59:59Z`).toISOString();
      const now = new Date().toISOString();
      await api.createOrder({
        customer_id: customerId,
        external_id: orderNumber.trim(),
        received_at: now,
        promised_at: dueAt,
        lines: lines.map((line) => {
          const quantity = Math.round(Number(line.quantity));
          return {
            sheet_width_mm: Math.round(Number(line.sheet_width_mm)),
            sheet_length_mm: Math.round(Number(line.sheet_length_mm)),
            quantity_required: quantity,
            quantity_min: quantity,
            quantity_max: Math.ceil(quantity * 1.02),
            material_spec_id: line.material_spec_id,
            due_at: dueAt,
            earliest_start_at: now,
            rotation_allowed: false,
          };
        }),
      });
      await onDone();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save the order");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Panel title="Take a new order">
      {error && <ErrorBanner text={error} />}
      {materials.length === 0 ? (
        <EmptyState text="There are no paper types yet — import your stock first (PaperBrain creates paper types automatically from your spreadsheet)." />
      ) : (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 16 }}>
            <Field label="Order number" hint="Your customer's PO number">
              <input
                value={orderNumber}
                onChange={(e) => setOrderNumber(e.target.value)}
                style={inputStyle}
                placeholder="e.g. PO-5533"
              />
            </Field>
            <Field label="Customer">
              <input
                value={customer}
                onChange={(e) => setCustomer(e.target.value)}
                style={inputStyle}
                placeholder="e.g. Sharma Printers"
              />
            </Field>
            <Field label="Due date">
              <input
                type="date"
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
                style={inputStyle}
              />
            </Field>
          </div>

          <h4 style={{ marginBottom: 8 }}>Sheets they want</h4>
          {lines.map((line, index) => (
            <div
              key={index}
              style={{
                display: "grid",
                gridTemplateColumns: "2fr 1fr 1fr 1fr auto",
                gap: 12,
                alignItems: "end",
                marginBottom: 12,
              }}
            >
              <Field label="Paper type">
                <select
                  value={line.material_spec_id}
                  onChange={(e) => setLine(index, { material_spec_id: e.target.value })}
                  style={inputStyle}
                >
                  {materials.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.family} {m.gsm_value ?? "?"} GSM
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Width (mm)">
                <input
                  type="number"
                  min={1}
                  value={line.sheet_width_mm}
                  onChange={(e) => setLine(index, { sheet_width_mm: e.target.value })}
                  style={inputStyle}
                  placeholder="390"
                />
              </Field>
              <Field label="Length (mm)">
                <input
                  type="number"
                  min={1}
                  value={line.sheet_length_mm}
                  onChange={(e) => setLine(index, { sheet_length_mm: e.target.value })}
                  style={inputStyle}
                  placeholder="600"
                />
              </Field>
              <Field label="Sheets">
                <input
                  type="number"
                  min={1}
                  value={line.quantity}
                  onChange={(e) => setLine(index, { quantity: e.target.value })}
                  style={inputStyle}
                  placeholder="900"
                />
              </Field>
              {lines.length > 1 && (
                <Button
                  small
                  kind="danger"
                  onClick={() => setLines((current) => current.filter((_, i) => i !== index))}
                >
                  Remove
                </Button>
              )}
            </div>
          ))}
          <div style={{ display: "flex", gap: 12, marginTop: 8, flexWrap: "wrap" }}>
            <Button onClick={addLine}>+ Another sheet size</Button>
            <Button kind="primary" onClick={() => void save()} disabled={saving || problem !== null}>
              {saving ? "Saving…" : "Save order"}
            </Button>
            <Button onClick={onCancel}>Cancel</Button>
          </div>
          {problem && <p style={{ color: "#b45309", fontSize: 13, marginTop: 8 }}>{problem}</p>}
        </>
      )}
    </Panel>
  );
}
