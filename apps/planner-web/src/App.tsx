import { useEffect, useState } from "react";
import type { Machine, Material, NamedEntity, Order, PlanSummary, Reel } from "./api";
import { api } from "./api";
import { Dashboard, computeStats } from "./Dashboard";
import { ImportScreen } from "./ImportScreen";
import { Inventory } from "./Inventory";
import { MachineSetup } from "./MachineSetup";
import { Orders } from "./Orders";
import { Planning } from "./Planning";
import { ErrorBanner } from "./ui";

type Screen = "dashboard" | "inventory" | "orders" | "import" | "machine" | "planning";

const NAV: { id: Screen; label: string; hint: string }[] = [
  { id: "dashboard", label: "Home", hint: "Overview of everything" },
  { id: "inventory", label: "Paper Rolls", hint: "Your reel stock" },
  { id: "orders", label: "Customer Orders", hint: "What customers asked for" },
  { id: "import", label: "Import Old Records", hint: "Load your existing spreadsheets" },
  { id: "machine", label: "My Machine", hint: "Tell PaperBrain what your sheeter can do" },
  { id: "planning", label: "Cutting Plans", hint: "Let PaperBrain do the planning" },
];

export function App() {
  const [screen, setScreen] = useState<Screen>("dashboard");
  const [materials, setMaterials] = useState<Material[]>([]);
  const [reels, setReels] = useState<Reel[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [machines, setMachines] = useState<Machine[]>([]);
  const [locations, setLocations] = useState<NamedEntity[]>([]);
  const [customers, setCustomers] = useState<NamedEntity[]>([]);
  const [plans, setPlans] = useState<PlanSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = async () => {
    setLoading(true);
    try {
      const [m, r, o, mac, loc, cust, planList] = await Promise.all([
        api.materials(),
        api.reels(),
        api.orders(),
        api.machines(),
        api.locations(),
        api.customers(),
        api.plans().catch(() => []),
      ]);
      setMaterials(m);
      setReels(r);
      setOrders(o);
      setMachines(mac);
      setLocations(loc);
      setCustomers(cust);
      setPlans(planList);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not reach the PaperBrain server");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
  }, []);

  const currency = materials[0]?.currency ?? "USD";
  const stats = computeStats(reels, orders, materials, plans);

  return (
    <div style={{ minHeight: "100vh", display: "flex" }}>
      <nav
        style={{
          width: 230,
          flexShrink: 0,
          background: "#111827",
          color: "white",
          padding: "20px 14px",
          display: "flex",
          flexDirection: "column",
          gap: 2,
        }}
      >
        <div style={{ padding: "0 12px 20px", fontWeight: 800, fontSize: 18 }}>
          PaperBrain
          <div style={{ fontSize: 11, fontWeight: 400, color: "#9ca3af" }}>
            Paper planning, made simple
          </div>
        </div>
        {NAV.map((item) => (
          <button
            key={item.id}
            onClick={() => setScreen(item.id)}
            style={{
              textAlign: "left",
              padding: "10px 12px",
              borderRadius: 8,
              border: "none",
              cursor: "pointer",
              fontSize: 14,
              fontWeight: screen === item.id ? 700 : 400,
              background: screen === item.id ? "#1f2937" : "transparent",
              color: screen === item.id ? "white" : "#d1d5db",
            }}
          >
            {item.label}
            <div style={{ fontSize: 11, color: "#6b7280", fontWeight: 400 }}>{item.hint}</div>
          </button>
        ))}
        <div style={{ marginTop: "auto", padding: "0 12px", fontSize: 11, color: "#4b5563" }}>
          Saved automatically — closes and restarts safely.
        </div>
      </nav>

      <main style={{ flex: 1, padding: 24, maxWidth: 1100 }}>
        {loading && <p style={{ color: "#6b7280" }}>Loading…</p>}
        {error && <ErrorBanner text={error} />}

        {screen === "dashboard" && (
          <Dashboard
            reels={reels}
            orders={orders}
            materials={materials}
            machines={machines}
            plans={plans}
            stats={stats}
            onSeed={async () => {
              await api.seedDemo();
              await refresh();
            }}
            onGo={setScreen}
          />
        )}
        {screen === "inventory" && (
          <Inventory reels={reels} materials={materials} locations={locations} onChange={refresh} />
        )}
        {screen === "orders" && (
          <Orders orders={orders} materials={materials} customers={customers} onChange={refresh} />
        )}
        {screen === "import" && <ImportScreen onDone={refresh} />}
        {screen === "machine" && <MachineSetup machines={machines} onChange={refresh} />}
        {screen === "planning" && (
          <Planning
            reels={reels}
            orders={orders}
            machines={machines}
            materials={materials}
            customers={customers}
            currency={currency}
            onGo={setScreen}
            onChanged={refresh}
          />
        )}
      </main>
    </div>
  );
}
