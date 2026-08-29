import { useEffect, useState } from "react";
import type {
  ExecuteResult,
  Machine,
  ManualPlanRun,
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
import { Button, ErrorBanner, Field, Notice, Panel, Stat, StatusChip, Table, inputStyle } from "./ui";

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
              item.policy_name === "manual" ? "Recorded by hand" : humanizePolicy(item.policy_name),
              item.validation_valid === false ? "⚠️ Needs attention" : humanizeStatus(item.status),
              item.material_loss_minor ? formatMoney(item.material_loss_minor, currency) : "—",
              item.fresh_reels_opened,
              item.executed ? <StatusChip key="e" text="Done ✓" tone="green" /> : "—",
            ])}
          />
        </div>
      )}

      <div style={{ marginTop: 32 }}>
        <RecordManualCuts
          reels={reels}
          orders={openOrders}
          machines={machines}
          onDone={async () => {
            await onChanged();
            await loadHistory();
          }}
        />
      </div>
    </div>
  );
}

interface ManualLaneDraft {
  order_line_id: string;
  start_mm: string;
}

function RecordManualCuts({
  reels,
  orders,
  machines,
  onDone,
}: {
  reels: Reel[];
  orders: Order[];
  machines: Machine[];
  onDone: () => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [runs, setRuns] = useState<ManualRunDraft[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ExecuteResult | null>(null);

  const openLines = orders.flatMap((o) =>
    o.lines.map((line) => ({ order: o.external_id, ...line })),
  );

  const start = () => {
    setOpen(true);
    setRuns([
      {
        reel_id: reels[0]?.id ?? "",
        machine_id: machines[0]?.id ?? "",
        crosscut_length_mm: "",
        crosscut_count: "",
        left_trim_mm: "0",
        right_trim_mm: "0",
        lanes: [],
      },
    ]);
    setResult(null);
  };

  const problem = runs.length === 0 || machines.length === 0
    ? machines.length === 0 ? "Add your machine first (under “My Machine”)." : null
    : runs.some((run) => {
        const length = Number(run.crosscut_length_mm);
        const count = Number(run.crosscut_count);
        if (!run.reel_id) return true;
        if (!Number.isFinite(length) || length <= 0) return true;
        if (!Number.isFinite(count) || count <= 0) return true;
        if (run.lanes.length === 0) return true;
        return run.lanes.some((lane) => {
          const startMm = Number(lane.start_mm);
          const line = openLines.find((l) => l.id === lane.order_line_id);
          return (
            !lane.order_line_id ||
            !Number.isFinite(startMm) ||
            startMm < 0 ||
            !line
          );
        });
      })
      ? "Every step needs a roll, the machine, a sheet length, the number of cuts, and at least one strip with its starting position."
      : null;

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      const payload: ManualPlanRun[] = runs.map((run) => ({
        reel_id: run.reel_id,
        machine_id: run.machine_id,
        crosscut_length_mm: Math.round(Number(run.crosscut_length_mm)),
        crosscut_count: Math.round(Number(run.crosscut_count)),
        left_trim_mm: Math.round(Number(run.left_trim_mm) || 0),
        right_trim_mm: Math.round(Number(run.right_trim_mm) || 0),
        lanes: run.lanes.map((lane) => {
          const line = openLines.find((l) => l.id === lane.order_line_id)!;
          return {
            order_line_id: lane.order_line_id,
            start_mm: Math.round(Number(lane.start_mm)),
            width_mm: line.sheet_width_mm,
          };
        }),
      }));
      const outcome = await api.manualExecute(payload);
      setResult(outcome);
      setRuns([]);
      await onDone();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not record the cuts");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Panel title="Already cut it by hand?">
      <p style={{ color: "#6b7280", marginTop: 0 }}>
        If the operator ran the machine without a PaperBrain plan, record what actually happened:
        which roll, which strips across the width, how many cross-cuts. PaperBrain deducts the
        paper, updates the orders, and the leftover stays in stock.
      </p>
      {!open ? (
        <Button onClick={start}>✍️ Record what I actually cut</Button>
      ) : (
        <>
          {error && <ErrorBanner text={error} />}
          {runs.map((run, runIndex) => (
            <div
              key={runIndex}
              style={{
                border: "1px solid #e5e7eb",
                borderRadius: 10,
                padding: 16,
                marginBottom: 12,
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
                <strong>Step {runIndex + 1}</strong>
                {runs.length > 1 && (
                  <Button
                    small
                    kind="danger"
                    onClick={() => setRuns((current) => current.filter((_, i) => i !== runIndex))}
                  >
                    Remove
                  </Button>
                )}
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 12 }}>
                <Field label="Roll used">
                  <select
                    value={run.reel_id}
                    onChange={(e) =>
                      setRuns((current) =>
                        current.map((r, i) => (i === runIndex ? { ...r, reel_id: e.target.value } : r)),
                      )
                    }
                    style={inputStyle}
                  >
                    {reels.map((reel) => (
                      <option key={reel.id} value={reel.id}>
                        {reel.reel_code} ({reel.nominal_width_mm} mm wide,{" "}
                        {humanizeState(reel.state)})
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Machine">
                  <select
                    value={run.machine_id}
                    onChange={(e) =>
                      setRuns((current) =>
                        current.map((r, i) => (i === runIndex ? { ...r, machine_id: e.target.value } : r)),
                      )
                    }
                    style={inputStyle}
                  >
                    {machines.map((machine) => (
                      <option key={machine.id} value={machine.id}>
                        {machine.code}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Sheet length cut (mm)" hint="The length setting on the machine">
                  <input
                    type="number"
                    min={1}
                    value={run.crosscut_length_mm}
                    onChange={(e) =>
                      setRuns((current) =>
                        current.map((r, i) => (i === runIndex ? { ...r, crosscut_length_mm: e.target.value } : r)),
                      )
                    }
                    style={inputStyle}
                    placeholder="e.g. 600"
                  />
                </Field>
                <Field label="Number of cuts" hint="How many sheets came off">
                  <input
                    type="number"
                    min={1}
                    value={run.crosscut_count}
                    onChange={(e) =>
                      setRuns((current) =>
                        current.map((r, i) => (i === runIndex ? { ...r, crosscut_count: e.target.value } : r)),
                      )
                    }
                    style={inputStyle}
                    placeholder="e.g. 500"
                  />
                </Field>
              </div>

              <div style={{ marginTop: 12, fontWeight: 600, fontSize: 14 }}>Strips across the roll width</div>
              <p style={{ color: "#9ca3af", fontSize: 12, margin: "4px 0 8px" }}>
                Say where each strip starts, measuring from the left edge of the roll. Width comes
                from the order sheet size.
              </p>
              {run.lanes.map((lane, laneIndex) => (
                <div
                  key={laneIndex}
                  style={{ display: "grid", gridTemplateColumns: "2fr 1fr auto", gap: 12, marginBottom: 8 }}
                >
                  <Field label={laneIndex === 0 ? "Which order sheet" : undefined}>
                    <select
                      value={lane.order_line_id}
                      onChange={(e) =>
                        setRuns((current) =>
                          current.map((r, i) =>
                            i === runIndex
                              ? {
                                  ...r,
                                  lanes: r.lanes.map((l, j) =>
                                    j === laneIndex ? { ...l, order_line_id: e.target.value } : l,
                                  ),
                                }
                              : r,
                          ),
                        )
                      }
                      style={inputStyle}
                    >
                      <option value="">Choose a sheet…</option>
                      {openLines.map((line) => (
                        <option key={line.id} value={line.id}>
                          {line.order} · {line.sheet_width_mm}×{line.sheet_length_mm} mm
                        </option>
                      ))}
                    </select>
                  </Field>
                  <Field label={laneIndex === 0 ? "Starts at (mm)" : undefined}>
                    <input
                      type="number"
                      min={0}
                      value={lane.start_mm}
                      onChange={(e) =>
                        setRuns((current) =>
                          current.map((r, i) =>
                            i === runIndex
                              ? {
                                  ...r,
                                  lanes: r.lanes.map((l, j) =>
                                    j === laneIndex ? { ...l, start_mm: e.target.value } : l,
                                  ),
                                }
                              : r,
                          ),
                        )
                      }
                      style={inputStyle}
                      placeholder="e.g. 10"
                    />
                  </Field>
                  <Button
                    small
                    kind="danger"
                    onClick={() =>
                      setRuns((current) =>
                        current.map((r, i) =>
                          i === runIndex
                            ? { ...r, lanes: r.lanes.filter((_, j) => j !== laneIndex) }
                            : r,
                        ),
                      )
                    }
                  >
                    ✕
                  </Button>
                </div>
              ))}
              <Button
                small
                onClick={() =>
                  setRuns((current) =>
                    current.map((r, i) =>
                      i === runIndex ? { ...r, lanes: [...r.lanes, { order_line_id: "", start_mm: "" }] } : r,
                    ),
                  )
                }
              >
                + Add a strip
              </Button>
            </div>
          ))}
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
            <Button
              onClick={() =>
                setRuns((current) => [
                  ...current,
                  {
                    reel_id: reels[0]?.id ?? "",
                    machine_id: machines[0]?.id ?? "",
                    crosscut_length_mm: "",
                    crosscut_count: "",
                    left_trim_mm: "0",
                    right_trim_mm: "0",
                    lanes: [],
                  },
                ])
              }
            >
              + Another roll
            </Button>
            <Button kind="primary" onClick={() => void save()} disabled={saving || problem !== null}>
              {saving ? "Recording…" : "Record these cuts"}
            </Button>
            <Button onClick={() => setOpen(false)}>Close</Button>
          </div>
          {problem && <p style={{ color: "#b45309", fontSize: 13, marginTop: 8 }}>{problem}</p>}
        </>
      )}
      {result && (
        <Notice kind="blue">
          <strong>Recorded ✓</strong> — {result.produced_sheets.toLocaleString()} sheets produced.
          {result.orders.length > 0 &&
            ` Order(s) ${result.orders.filter((o) => o.completed).map((o) => o.external_id).join(", ") || "none"} fulfilled.`}
          {result.runs.length > 0 &&
            ` Paper used: ${result.runs
              .map((r) => `${r.reel_code} −${formatLength(r.consumed_length_mm)}`)
              .join(" · ")}.`}
        </Notice>
      )}
    </Panel>
  );
}

interface ManualRunDraft {
  reel_id: string;
  machine_id: string;
  crosscut_length_mm: string;
  crosscut_count: string;
  left_trim_mm: string;
  right_trim_mm: string;
  lanes: ManualLaneDraft[];
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
