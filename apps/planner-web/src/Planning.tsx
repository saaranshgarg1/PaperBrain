import { useEffect, useState } from "react";
import type {
  ExecuteResult,
  Machine,
  Material,
  NamedEntity,
  Order,
  PlanningResponse,
  Reel,
} from "./api";
import { api } from "./api";
import { LaneDiagram } from "./LaneDiagram";
import {
  formatDate,
  formatLength,
  formatMoney,
  humanizePolicy,
  humanizeState,
  humanizeStatus,
} from "./format";
import { materialLabel } from "./Dashboard";
import { Button, ErrorBanner, Notice, Panel, Stat, StatusChip, Table } from "./ui";

export function Planning({
  reels,
  orders,
  machines,
  materials,
  customers,
  currency,
  onGo,
  onChanged,
}: {
  reels: Reel[];
  orders: Order[];
  machines: Machine[];
  materials: Material[];
  customers: NamedEntity[];
  currency: string;
  onGo: (screen: "import" | "inventory" | "orders" | "machine") => void;
  onChanged: () => Promise<void>;
}) {
  const [policy, setPolicy] = useState("normal");
  const [plan, setPlan] = useState<PlanningResponse | null>(null);
  const [execution, setExecution] = useState<ExecuteResult | null>(null);
  const [solving, setSolving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<Awaited<ReturnType<typeof api.plans>>>([]);

  const materialById = new Map(materials.map((m) => [m.id, m]));
  const customerById = new Map(customers.map((c) => [c.id, c.name]));
  const openOrders = orders.filter((o) =>
    ["confirmed", "released", "running"].includes(o.status),
  );
  const checkedReels = reels.filter((r) => r.verification_state === "verified").length;
  const [selected, setSelected] = useState<Set<string>>(new Set());

  useEffect(() => {
    // Default: every open order is selected.
    setSelected((current) =>
      current.size === 0 ? new Set(openOrders.map((o) => o.id)) : current,
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orders.length]);

  const loadHistory = async () => {
    try {
      setHistory(await api.plans());
    } catch {
      /* history is best-effort */
    }
  };

  useEffect(() => {
    void loadHistory();
  }, []);

  const toggle = (id: string) =>
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const selectAll = () => setSelected(new Set(openOrders.map((o) => o.id)));
  const selectNone = () => setSelected(new Set());

  const solve = async () => {
    setSolving(true);
    setError(null);
    setExecution(null);
    try {
      const orderIds = [...selected];
      const result = await api.solve(
        policy,
        30,
        selected.size === openOrders.length ? undefined : orderIds,
      );
      setPlan(result);
      await loadHistory();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Planning failed");
    } finally {
      setSolving(false);
    }
  };

  const openPlan = async (id: string) => {
    try {
      setExecution(null);
      setPlan(await api.plan(id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not open plan");
    }
  };

  const execute = async () => {
    if (!plan) return;
    if (
      !window.confirm(
        `Carry out this plan now?\n\nThe paper will be marked as used up from each roll, and ` +
          `the finished orders will be marked as fulfilled. This cannot be undone.`,
      )
    ) {
      return;
    }
    setError(null);
    try {
      const result = await api.executePlan(plan.plan_id);
      setExecution(result);
      await onChanged();
      await loadHistory();
      // Refresh the plan (now marked executed)
      setPlan(await api.plan(plan.plan_id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not carry out the plan");
    }
  };

  const ready = checkedReels > 0 && openOrders.length > 0 && machines.length > 0;

  return (
    <div>
      <h2>Cutting Plans</h2>
      <p style={{ color: "#6b7280" }}>
        PaperBrain picks rolls and cutting layouts so orders are delivered on time with the least
        wasted paper. Choose which orders to include, create the plan, then carry it out on the
        floor — stock and order lists update automatically.
      </p>

      {!ready && (
        <Panel title="Three things needed before planning">
          <Checklist
            items={[
              {
                done: checkedReels > 0,
                text:
                  checkedReels > 0
                    ? `${checkedReels} checked paper roll(s) in stock`
                    : "At least one checked paper roll — add or import stock, then confirm the rolls",
                screen: reels.length > 0 ? "inventory" : "import",
                action: reels.length > 0 ? "Confirm rolls" : "Add rolls",
              },
              {
                done: openOrders.length > 0,
                text:
                  openOrders.length > 0
                    ? `${openOrders.length} open order(s)`
                    : "At least one open order",
                screen: "orders",
                action: "Take an order",
              },
              {
                done: machines.length > 0,
                text: machines.length > 0 ? `${machines.length} machine set up` : "Your cutting machine's limits",
                screen: "machine",
                action: "Set up machine",
              },
            ]}
            onGo={onGo}
          />
        </Panel>
      )}

      {openOrders.length > 0 && (
        <Panel
          title="Which orders should this plan cover?"
          actions={
            <span style={{ display: "flex", gap: 8 }}>
              <Button small onClick={selectAll}>
                Select all
              </Button>
              <Button small onClick={selectNone}>
                Clear
              </Button>
            </span>
          }
        >
          {openOrders.map((order) => {
            const isSelected = selected.has(order.id);
            const sheets = order.lines.reduce((sum, line) => sum + line.quantity_required, 0);
            return (
              <label
                key={order.id}
                style={{
                  display: "flex",
                  gap: 10,
                  alignItems: "center",
                  padding: "8px 0",
                  borderBottom: "1px dashed #f3f4f6",
                  cursor: "pointer",
                  opacity: isSelected ? 1 : 0.55,
                }}
              >
                <input type="checkbox" checked={isSelected} onChange={() => toggle(order.id)} />
                <strong>{order.external_id}</strong>
                <span style={{ color: "#6b7280", flex: 1 }}>
                  {customerById.get(order.customer_id) ?? ""} · {sheets.toLocaleString()} sheets · due{" "}
                  {formatDate(order.promised_at)}
                </span>
                {order.lines.map((line) => (
                  <span key={line.id} style={{ fontSize: 12, color: "#6b7280" }}>
                    {line.sheet_width_mm}×{line.sheet_length_mm} ·{" "}
                    {materialLabel(materialById, line.material_spec_id)}
                  </span>
                ))}
              </label>
            );
          })}
          <p style={{ color: "#6b7280", fontSize: 13, margin: "10px 0 0" }}>
            {selected.size} of {openOrders.length} order(s) selected
            {selected.size === 0 && " — select at least one to plan"}
          </p>
        </Panel>
      )}

      {ready && selected.size > 0 && (
        <Panel>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "end" }}>
            <div style={{ minWidth: 280, flex: 1 }}>
              <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 4 }}>
                What matters most right now?
              </div>
              <select
                value={policy}
                onChange={(e) => setPolicy(e.target.value)}
                style={{ padding: 10, borderRadius: 8, border: "1px solid #d1d5db", fontSize: 14, width: "100%" }}
              >
                {["normal", "open_stock_cleanup", "yield_campaign", "service_recovery", "cash_preservation"].map(
                  (p) => (
                    <option key={p} value={p}>
                      {humanizePolicy(p)}
                    </option>
                  ),
                )}
              </select>
            </div>
            <Button kind="primary" onClick={() => void solve()} disabled={solving}>
              {solving ? "Working out the best plan…" : "▶ Create cutting plan"}
            </Button>
          </div>
        </Panel>
      )}

      {error && <ErrorBanner text={error} />}

      {execution && <ExecutionResult result={execution} currency={currency} />}

      {plan && <PlanResult plan={plan} materialById={materialById} currency={currency} onExecute={() => void execute()} />}

      {history.length > 0 && (
        <div style={{ marginTop: 24 }}>
          <h3>Previous plans</h3>
          <Table
            headers={["Created", "Focus", "Result", "Paper wasted (est. cost)", "New rolls opened", "Carried out"]}
            rows={history.map((item) => [
              <Button key="open" kind="ghost" onClick={() => void openPlan(item.plan_id)}>
                {formatDate(item.created_at)}
              </Button>,
              humanizePolicy(item.policy_name),
              item.validation_valid === false ? "⚠️ Needs attention" : humanizeStatus(item.status),
              formatMoney(item.material_loss_minor, currency),
              item.fresh_reels_opened,
              item.executed ? <StatusChip key="e" text="Done ✓" tone="green" /> : "—",
            ])}
          />
        </div>
      )}
    </div>
  );
}

function Checklist({
  items,
  onGo,
}: {
  items: { done: boolean; text: string; screen: "import" | "inventory" | "orders" | "machine"; action: string }[];
  onGo: (screen: "import" | "inventory" | "orders" | "machine") => void;
}) {
  return (
    <div>
      {items.map((item) => (
        <div
          key={item.text}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            padding: "8px 0",
            borderBottom: "1px dashed #f3f4f6",
          }}
        >
          <span style={{ fontSize: 18 }}>{item.done ? "✅" : "⬜"}</span>
          <span style={{ flex: 1, color: item.done ? "#374151" : "#111827" }}>
            {item.text}
          </span>
          {!item.done && (
            <Button small onClick={() => onGo(item.screen)}>
              {item.action}
            </Button>
          )}
        </div>
      ))}
    </div>
  );
}

function ExecutionResult({ result, currency }: { result: ExecuteResult; currency: string }) {
  return (
    <Notice kind="blue">
      <strong>Plan carried out ✓</strong>
      <div style={{ marginTop: 6 }}>
        Produced {result.produced_sheets.toLocaleString()} sheets.
        {result.orders.length > 0 && (
          <>
            {" "}
            {result.orders.filter((o) => o.completed).length > 0 &&
              `Order${result.orders.filter((o) => o.completed).length === 1 ? "" : "s"} ${result.orders
                .filter((o) => o.completed)
                .map((o) => o.external_id)
                .join(", ")} marked fulfilled.`}
            {result.orders.some((o) => !o.completed) && (
              <>
                {" "}
                Partly-produced order(s) remain open:{" "}
                {result.orders
                  .filter((o) => !o.completed)
                  .map((o) => o.external_id)
                  .join(", ")}
                .
              </>
            )}
          </>
        )}
      </div>
      <div style={{ marginTop: 6, fontSize: 13 }}>
        Paper used:{" "}
        {result.runs
          .map((r) => `${r.reel_code} −${formatLength(r.consumed_length_mm)}`)
          .join(" · ")}
        {result.runs.some((r) => r.reel_state === "exhausted") && " (roll used up)"}
        {result.runs.some((r) => r.reel_state === "opened") &&
          " — leftovers stay in stock under Paper Rolls"}
      </div>
      <div style={{ marginTop: 4, fontSize: 12, opacity: 0.8 }}>
        All amounts in {currency}. Rolls that still have paper left are shown as "Open (in use)".
      </div>
    </Notice>
  );
}

export function PlanResult({
  plan,
  materialById,
  currency,
  onExecute,
}: {
  plan: PlanningResponse;
  materialById: Map<string, Material>;
  currency: string;
  onExecute?: () => void;
}) {
  const reelById = new Map(plan.reels.map((r) => [r.id, r]));
  const patternById = new Map(plan.patterns.map((p) => [p.id, p]));
  const lineById = new Map(plan.order_lines.map((l) => [l.id, l]));
  const totalLoss = plan.objective.material_loss_minor ?? 0;
  const shortage = plan.objective.service_shortage_sheets ?? 0;
  const gsm = [...materialById.values()].find((m) => m.gsm_value)?.gsm_value ?? null;

  return (
    <Panel>
      <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
        <h3 style={{ margin: 0 }}>
          {shortage > 0 ? "Plan found, but some sheets cannot be made" : humanizeStatus(plan.status)}
        </h3>
        <span style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {plan.executed ? (
            <StatusChip text="Carried out ✓" tone="green" />
          ) : (
            plan.validation_valid && (
              <span style={{ color: "#16a34a", fontWeight: 600 }}>✓ Physically verified</span>
            )
          )}
          {!plan.executed && onExecute && plan.validation_valid && plan.runs.length > 0 && (
            <Button kind="success" onClick={onExecute}>
              ✅ Carry out this plan
            </Button>
          )}
        </span>
      </div>

      {shortage > 0 && (
        <Notice>
          ⚠️ {shortage.toLocaleString()} sheet{shortage > 1 ? "s" : ""} could not be produced from the
          stock PaperBrain is allowed to use. Usual reasons: rolls still waiting to be checked, not
          enough paper of that type, or sheets wider than any roll you own.
        </Notice>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 12, margin: "16px 0" }}>
        <Stat label="Runs on the machine" value={plan.runs.length} />
        <Stat label="New rolls opened" value={plan.objective.fresh_reels_opened ?? 0} />
        <Stat label="Short sheets (missing)" value={shortage} />
        <Stat label="Estimated paper waste" value={formatMoney(totalLoss, currency)} />
      </div>

      {plan.violations.length > 0 && (
        <div style={{ background: "#fef2f2", borderRadius: 8, padding: 12, marginBottom: 12, color: "#991b1b" }}>
          {plan.violations.map((v, i) => (
            <div key={i}>❌ {v.message}</div>
          ))}
        </div>
      )}

      <h4>How to run it</h4>
      {plan.runs
        .slice()
        .sort((a, b) => a.sequence - b.sequence)
        .map((run) => {
          const reel = reelById.get(run.reel_id);
          const pattern = patternById.get(run.pattern_id);
          return (
            <div key={run.id} style={{ marginBottom: 20 }}>
              <div style={{ marginBottom: 6, fontSize: 14 }}>
                <strong>Step {run.sequence + 1}:</strong> roll{" "}
                <strong>{reel?.reel_code ?? "?"}</strong> ({reel ? humanizeState(reel.state) : ""},{" "}
                {reel?.nominal_width_mm.toLocaleString()} mm wide) — cut{" "}
                {run.crosscut_count.toLocaleString()} times, using{" "}
                {formatLength(run.consumed_length_mm)} of paper
              </div>
              {pattern && (
                <LaneDiagram
                  pattern={pattern}
                  crosscutCount={run.crosscut_count}
                  orderLines={plan.order_lines}
                />
              )}
              <div style={{ marginTop: 6, fontSize: 14, color: "#374151" }}>
                Produces:{" "}
                {run.outputs.map((output, index) => {
                  const line = lineById.get(output.order_line_id);
                  return (
                    <span key={output.order_line_id}>
                      {index > 0 && " · "}
                      <strong>{output.quantity.toLocaleString()}</strong> sheets of{" "}
                      {line ? `${line.sheet_width_mm}×${line.sheet_length_mm} mm` : "?"}
                    </span>
                  );
                })}
              </div>
            </div>
          );
        })}

      <div style={{ fontSize: 12, color: "#9ca3af", marginTop: 12 }}>
        Waste estimate uses your material costs{gsm ? ` (${gsm} GSM paper)` : ""}. Solver:{" "}
        {plan.solver.name ?? "?"} · {plan.solver.wall_seconds ?? "?"}s.
      </div>
    </Panel>
  );
}
