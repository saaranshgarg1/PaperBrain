import { useState } from "react";
import type { Machine, Material, Order, PlanSummary, Reel } from "./api";
import { daysUntil, formatDate, formatArea, formatMoney, humanizeOrderStatus } from "./format";
import { Button, EmptyState, ErrorBanner, Notice, Panel, Stat, StatusChip } from "./ui";

export interface DashboardStats {
  usableStockMm2: number;
  stockByMaterial: Map<string, { area: number; reels: number }>;
  openOrders: Order[];
  openDemandMm2: number;
  dueThisWeek: Order[];
  overdue: Order[];
  coverageByMaterial: Map<string, { stockArea: number; demandArea: number }>;
  ordersPerWeek: number | null;
  wasteLastPlanMinor: number | null;
  plansExecuted: number;
  totalProducedSheets: number;
  needingCheck: number;
}

export function computeStats(
  reels: Reel[],
  orders: Order[],
  materials: Material[],
  plans: PlanSummary[],
): DashboardStats {
  const materialById = new Map(materials.map((m) => [m.id, m]));
  const stockByMaterial = new Map<string, { area: number; reels: number }>();
  let usableStockMm2 = 0;
  for (const reel of reels) {
    const usable =
      reel.state === "unopened" || reel.state === "opened";
    if (!usable) continue;
    const area = reel.nominal_width_mm * reel.remaining_length_mm;
    usableStockMm2 += area;
    const label = materialLabel(materialById, reel.material_spec_id);
    const entry = stockByMaterial.get(label) ?? { area: 0, reels: 0 };
    entry.area += area;
    entry.reels += 1;
    stockByMaterial.set(label, entry);
  }

  const openOrders = orders.filter(
    (o) => o.status === "confirmed" || o.status === "released" || o.status === "running",
  );
  const demandByMaterial = new Map<string, number>();
  let openDemandMm2 = 0;
  for (const order of openOrders) {
    for (const line of order.lines) {
      const area = line.sheet_width_mm * line.sheet_length_mm * line.quantity_required;
      openDemandMm2 += area;
      const label = materialLabel(materialById, line.material_spec_id);
      demandByMaterial.set(label, (demandByMaterial.get(label) ?? 0) + area);
    }
  }

  const coverageByMaterial = new Map<string, { stockArea: number; demandArea: number }>();
  for (const [label, stock] of stockByMaterial) {
    coverageByMaterial.set(label, {
      stockArea: stock.area,
      demandArea: demandByMaterial.get(label) ?? 0,
    });
  }
  for (const [label, demand] of demandByMaterial) {
    if (!coverageByMaterial.has(label)) {
      coverageByMaterial.set(label, { stockArea: 0, demandArea: demand });
    }
  }

  const now = Date.now();
  const dueThisWeek = openOrders.filter((o) => {
    const days = daysUntil(o.promised_at);
    return days !== null && days <= 7;
  });
  const overdue = openOrders.filter((o) => {
    const days = daysUntil(o.promised_at);
    return days !== null && days < 0;
  });

  // Average incoming order rate over the last 8 weeks, if there is history.
  const withDates = orders
    .map((o) => new Date(o.received_at).getTime())
    .filter((t) => !Number.isNaN(t) && now - t < 8 * 7 * 86_400_000);
  const weeks =
    Math.max(
      ...withDates.map((t) => (now - t) / (7 * 86_400_000)),
      withDates.length > 0 ? 1 : 0,
    ) || 0;
  const ordersPerWeek = weeks > 0 ? withDates.length / weeks : null;

  const executedPlans = plans.filter((p) => p.executed);
  const lastPlan = plans[0] ?? null;

  return {
    usableStockMm2,
    stockByMaterial,
    openOrders,
    openDemandMm2,
    dueThisWeek,
    overdue,
    coverageByMaterial,
    ordersPerWeek,
    wasteLastPlanMinor: lastPlan?.material_loss_minor ?? null,
    plansExecuted: executedPlans.length,
    totalProducedSheets: 0,
    needingCheck: reels.filter((r) => r.verification_state === "provisional").length,
  };
}

export function materialLabel(
  materialById: Map<string, Material>,
  materialSpecId: string,
): string {
  const material = materialById.get(materialSpecId);
  return material ? `${material.family} ${material.gsm_value ?? "?"} GSM` : "Unknown material";
}

export function Dashboard({
  reels,
  orders,
  materials,
  machines,
  plans,
  stats,
  onSeed,
  onGo,
}: {
  reels: Reel[];
  orders: Order[];
  materials: Material[];
  machines: Machine[];
  plans: PlanSummary[];
  stats: DashboardStats;
  onSeed: () => Promise<void>;
  onGo: (screen: "import" | "inventory" | "orders" | "machine" | "planning") => void;
}) {
  const empty = reels.length === 0 && orders.length === 0 && machines.length === 0;
  const currency = materials[0]?.currency ?? "USD";
  const attention: { text: string; action: string; screen: "inventory" | "machine" | "orders" }[] = [];
  if (stats.needingCheck > 0) {
    attention.push({
      text: `${stats.needingCheck} roll${stats.needingCheck > 1 ? "s" : ""} imported but not yet checked — they can't be planned until confirmed`,
      action: "Check them",
      screen: "inventory",
    });
  }
  if (machines.length === 0 && reels.length > 0) {
    attention.push({
      text: "No cutting machine set up — needed before planning",
      action: "Set it up",
      screen: "machine",
    });
  }
  if (stats.overdue.length > 0) {
    attention.push({
      text: `${stats.overdue.length} order${stats.overdue.length > 1 ? "s are" : " is"} past the promised date`,
      action: "See orders",
      screen: "orders",
    });
  }
  for (const [label, coverage] of stats.coverageByMaterial) {
    if (coverage.demandArea > 0 && coverage.stockArea < coverage.demandArea) {
      attention.push({
        text: `Open orders need more ${label} than you have in stock (${formatArea(coverage.stockArea)} vs ${formatArea(coverage.demandArea)} needed)`,
        action: "Buy rolls",
        screen: "orders",
      });
    }
  }

  return (
    <div>
      {empty && <FirstRun onGo={onGo} onSeed={onSeed} />}

      {!empty && (
        <>
          <div
            style={{
              display: "flex",
              gap: 8,
              flexWrap: "wrap",
              marginBottom: 16,
            }}
          >
            <Button kind="primary" onClick={() => onGo("import")}>
              + Add rolls or orders
            </Button>
            <Button onClick={() => onGo("planning")}>✂️ Make a cutting plan</Button>
            <Button onClick={() => onGo("inventory")}>See stock</Button>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 16 }}>
            <Stat
              label="Paper in stock (usable)"
              value={formatArea(stats.usableStockMm2)}
              sub={`${reels.filter((r) => r.state === "unopened" || r.state === "opened").length} rolls · ${stats.stockByMaterial.size} materials`}
            />
            <Stat
              label="Open customer demand"
              value={formatArea(stats.openDemandMm2)}
              sub={`${stats.openOrders.length} order${stats.openOrders.length === 1 ? "" : "s"} · ${stats.dueThisWeek.length} due this week`}
            />
            <Stat
              label="Orders coming in"
              value={stats.ordersPerWeek === null ? "—" : `${stats.ordersPerWeek.toFixed(1)}/week`}
              sub={
                stats.ordersPerWeek === null
                  ? "no order history yet"
                  : `${stats.plansExecuted} plan${stats.plansExecuted === 1 ? "" : "s"} carried out so far`
              }
            />
            <Stat
              label="Waste in latest plan"
              value={
                stats.wasteLastPlanMinor === null
                  ? "—"
                  : formatMoney(stats.wasteLastPlanMinor, currency)
              }
              sub={plans.length > 0 ? `of ${formatArea(stats.openDemandMm2)} demanded paper` : "no plans yet"}
            />
          </div>

          {attention.length > 0 && (
            <Panel title="Needs your attention">
              {attention.map((item) => (
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
                  <span>🔔</span>
                  <span style={{ flex: 1 }}>{item.text}</span>
                  <Button small onClick={() => onGo(item.screen)}>
                    {item.action}
                  </Button>
                </div>
              ))}
            </Panel>
          )}

          {stats.coverageByMaterial.size > 0 && (
            <Panel title="Stock vs open orders, by paper type">
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
                <thead>
                  <tr>
                    {["Paper type", "In stock", "Open orders need", "Coverage"].map((header) => (
                      <th
                        key={header}
                        style={{
                          textAlign: "left",
                          padding: "8px 12px",
                          color: "#6b7280",
                          fontWeight: 600,
                          fontSize: 12,
                          textTransform: "uppercase",
                        }}
                      >
                        {header}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {[...stats.coverageByMaterial.entries()].map(([label, coverage]) => {
                    const percent =
                      coverage.demandArea > 0
                        ? Math.round((coverage.stockArea / coverage.demandArea) * 100)
                        : null;
                    return (
                      <tr key={label}>
                        <td style={{ padding: "8px 12px", fontWeight: 600 }}>{label}</td>
                        <td style={{ padding: "8px 12px" }}>{formatArea(coverage.stockArea)}</td>
                        <td style={{ padding: "8px 12px" }}>
                          {coverage.demandArea > 0 ? formatArea(coverage.demandArea) : "—"}
                        </td>
                        <td style={{ padding: "8px 12px" }}>
                          {percent === null ? (
                            <StatusChip text="No open demand" tone="gray" />
                          ) : percent >= 100 ? (
                            <StatusChip text={`${percent}% — plenty`} tone="green" />
                          ) : percent >= 60 ? (
                            <StatusChip text={`${percent}% — tight`} tone="amber" />
                          ) : (
                            <StatusChip text={`${percent}% — short`} tone="red" />
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </Panel>
          )}

          {stats.openOrders.length > 0 && (
            <Panel title="Next up (open orders)">
              {stats.openOrders
                .slice()
                .sort((a, b) => new Date(a.promised_at).getTime() - new Date(b.promised_at).getTime())
                .slice(0, 5)
                .map((order) => {
                  const days = daysUntil(order.promised_at);
                  const sheets = order.lines.reduce((sum, line) => sum + line.quantity_required, 0);
                  return (
                    <div
                      key={order.id}
                      style={{
                        display: "flex",
                        gap: 12,
                        alignItems: "center",
                        flexWrap: "wrap",
                        padding: "8px 0",
                        borderBottom: "1px dashed #f3f4f6",
                      }}
                    >
                      <strong style={{ minWidth: 110 }}>{order.external_id}</strong>
                      <span style={{ color: "#6b7280" }}>
                        {sheets.toLocaleString()} sheets · due {formatDate(order.promised_at)}
                      </span>
                      {days !== null && days < 0 ? (
                        <StatusChip text={`${Math.abs(days)} days late`} tone="red" />
                      ) : days !== null && days <= 3 ? (
                        <StatusChip text={`${days} day${days === 1 ? "" : "s"} left`} tone="amber" />
                      ) : (
                        <StatusChip text={humanizeOrderStatus(order.status)} tone="blue" />
                      )}
                    </div>
                  );
                })}
            </Panel>
          )}
        </>
      )}
    </div>
  );
}

function FirstRun({
  onGo,
  onSeed,
}: {
  onGo: (screen: "import" | "inventory" | "orders" | "machine" | "planning") => void;
  onSeed: () => Promise<void>;
}) {
  const [error, setError] = useState<string | null>(null);
  return (
    <div
      style={{
        background: "white",
        borderRadius: 12,
        padding: 32,
        marginBottom: 24,
        border: "1px solid #e5e7eb",
      }}
    >
      <h2 style={{ marginTop: 0 }}>Welcome to PaperBrain 👋</h2>
      <p style={{ color: "#4b5563" }}>
        PaperBrain plans how to cut paper rolls into customer sheets with the least waste. To get
        started, either load your existing records from a spreadsheet, add a roll by hand, or
        explore with a small demo dataset.
      </p>
      {error && <ErrorBanner text={error} />}
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <Button kind="primary" onClick={() => onGo("import")}>
          Import my records
        </Button>
        <Button onClick={() => onGo("inventory")}>Add a roll by hand</Button>
        <Button
          onClick={() =>
            onSeed().catch((e) => setError(e instanceof Error ? e.message : "Could not load demo"))
          }
        >
          Try the demo data
        </Button>
      </div>
      <Notice kind="blue">
        <span style={{ display: "block", marginTop: 16 }}>
          💡 Everything you add is saved automatically and restored the next time you start the app —
          you never lose your work.
        </span>
      </Notice>
    </div>
  );
}
