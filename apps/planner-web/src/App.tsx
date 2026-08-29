import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { api } from "./api";
import type {
  ImportResult,
  Machine,
  MachineDraft,
  Material,
  Order,
  PlanningResponse,
  Reel,
} from "./api";
import { LaneDiagram } from "./LaneDiagram";
import {
  formatDate,
  formatLength,
  formatMoney,
  humanizePolicy,
  humanizeState,
  humanizeStatus,
} from "./format";

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
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = async () => {
    setLoading(true);
    try {
      const [m, r, o, mac] = await Promise.all([
        api.materials(),
        api.reels(),
        api.orders(),
        api.machines(),
      ]);
      setMaterials(m);
      setReels(r);
      setOrders(o);
      setMachines(mac);
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

  return (
    <div style={{ minHeight: "100vh", background: "#f3f4f6", color: "#111827" }}>
      <header
        style={{
          background: "#111827",
          color: "white",
          padding: "14px 24px",
          display: "flex",
          alignItems: "center",
          gap: 16,
        }}
      >
        <div style={{ fontSize: 20, fontWeight: 700 }}>
          🧠 Paper<span style={{ color: "#60a5fa" }}>Brain</span>
        </div>
        <nav style={{ display: "flex", gap: 4, marginLeft: 24, flexWrap: "wrap" }}>
          {NAV.map((item) => (
            <button
              key={item.id}
              onClick={() => setScreen(item.id)}
              title={item.hint}
              style={{
                padding: "8px 14px",
                border: "none",
                borderRadius: 6,
                background: screen === item.id ? "#2563eb" : "transparent",
                color: screen === item.id ? "white" : "#d1d5db",
                cursor: "pointer",
                fontWeight: screen === item.id ? 600 : 400,
              }}
            >
              {item.label}
            </button>
          ))}
        </nav>
      </header>

      {error && (
        <div
          style={{
            background: "#fef2f2",
            color: "#991b1b",
            padding: "10px 24px",
            borderBottom: "1px solid #fecaca",
          }}
        >
          ⚠️ {error}
        </div>
      )}

      <main style={{ maxWidth: 1100, margin: "0 auto", padding: "24px" }}>
        {loading ? (
          <p style={{ color: "#6b7280" }}>Loading…</p>
        ) : (
          <>
            {screen === "dashboard" && (
              <Dashboard
                reels={reels}
                orders={orders}
                materials={materials}
                machines={machines}
                onSeed={async () => {
                  try {
                    await api.seedDemo();
                    await refresh();
                  } catch (e) {
                    setError(e instanceof Error ? e.message : "Could not load demo data");
                  }
                }}
                onGo={setScreen}
              />
            )}
            {screen === "inventory" && (
              <Inventory reels={reels} materials={materials} onChange={refresh} />
            )}
            {screen === "orders" && <Orders orders={orders} materials={materials} />}
            {screen === "import" && <ImportScreen onDone={refresh} />}
            {screen === "machine" && <MachineSetup machines={machines} onChange={refresh} />}
            {screen === "planning" && (
              <Planning
                reels={reels}
                orders={orders}
                machines={machines}
                materials={materials}
                currency={currency}
                onGo={setScreen}
              />
            )}
          </>
        )}
      </main>
    </div>
  );
}

/* ---------- Dashboard ---------- */

function Dashboard({
  reels,
  orders,
  materials,
  machines,
  onSeed,
  onGo,
}: {
  reels: Reel[];
  orders: Order[];
  materials: Material[];
  machines: Machine[];
  onSeed: () => Promise<void>;
  onGo: (screen: Screen) => void;
}) {
  const empty = reels.length === 0 && orders.length === 0;
  const openReels = reels.filter((r) => r.state === "opened").length;
  const needingCheck = reels.filter((r) => r.verification_state === "provisional").length;
  const totalSheets = orders.reduce(
    (sum, order) => sum + order.lines.reduce((s, line) => s + line.quantity_required, 0),
    0,
  );

  return (
    <div>
      {empty && (
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
            PaperBrain plans how to cut paper rolls into customer sheets with the least waste.
            To get started, either load your existing records from a spreadsheet, or explore
            with a small demo dataset.
          </p>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
            <button
              onClick={() => onGo("import")}
              style={{
                padding: "12px 20px",
                borderRadius: 8,
                border: "none",
                background: "#2563eb",
                color: "white",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              Import my records
            </button>
            <button
              onClick={() => void onSeed()}
              style={{
                padding: "12px 20px",
                borderRadius: 8,
                border: "1px solid #d1d5db",
                background: "white",
                cursor: "pointer",
              }}
            >
              Try the demo data
            </button>
          </div>
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 16 }}>
        <Stat label="Paper rolls in stock" value={reels.length} sub={`${openReels} open · ${reels.length - openReels} sealed`} />
        <Stat label="Customer orders" value={orders.length} sub={`${totalSheets.toLocaleString()} sheets requested`} />
        <Stat label="Materials" value={materials.length} sub="paper types tracked" />
        <Stat
          label="Cutting machines"
          value={machines.length}
          sub={machines.map((m) => m.code).join(", ") || "none set up"}
        />
      </div>

      {needingCheck > 0 && (
        <div
          style={{
            marginTop: 20,
            background: "#fffbeb",
            border: "1px solid #fde68a",
            borderRadius: 8,
            padding: "12px 16px",
            color: "#92400e",
          }}
        >
          📋 {needingCheck} roll{needingCheck > 1 ? "s" : ""} still need checking before they can be
          planned. <button onClick={() => onGo("inventory")} style={{ color: "#b45309", background: "none", border: "none", textDecoration: "underline", cursor: "pointer" }}>Review them</button>
        </div>
      )}

      {!empty && machines.length === 0 && (
        <div
          style={{
            marginTop: 12,
            background: "#eff6ff",
            border: "1px solid #bfdbfe",
            borderRadius: 8,
            padding: "12px 16px",
            color: "#1e40af",
          }}
        >
          ⚙️ No cutting machine set up yet — PaperBrain needs to know your sheeter's limits before it
          can plan.{" "}
          <button
            onClick={() => onGo("machine")}
            style={{ color: "#1d4ed8", background: "none", border: "none", textDecoration: "underline", cursor: "pointer" }}
          >
            Set it up
          </button>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, sub }: { label: string; value: number | string; sub?: string }) {
  return (
    <div style={{ background: "white", borderRadius: 12, padding: 20, border: "1px solid #e5e7eb" }}>
      <div style={{ fontSize: 30, fontWeight: 700 }}>{value}</div>
      <div style={{ color: "#6b7280", fontSize: 14 }}>{label}</div>
      {sub && <div style={{ color: "#9ca3af", fontSize: 12, marginTop: 4 }}>{sub}</div>}
    </div>
  );
}

/* ---------- Inventory ---------- */

function Inventory({
  reels,
  materials,
  onChange,
}: {
  reels: Reel[];
  materials: Material[];
  onChange: () => Promise<void>;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const materialById = new Map(materials.map((m) => [m.id, m]));
  const unchecked = reels.filter((r) => r.verification_state === "provisional");

  const verifyAll = async () => {
    setBusy("verify");
    setError(null);
    try {
      for (const reel of unchecked) {
        await api.verifyReel(reel.id);
      }
      await onChange();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not confirm the rolls");
    } finally {
      setBusy(null);
    }
  };

  return (
    <div>
      <h2>Paper Rolls</h2>
      <p style={{ color: "#6b7280" }}>
        Every physical roll you own. "Checked" means the details have been confirmed on the shelf.
      </p>
      {error && <ErrorBanner text={error} />}
      {unchecked.length > 0 && (
        <button
          onClick={() => void verifyAll()}
          disabled={busy === "verify"}
          style={{
            padding: "10px 16px",
            borderRadius: 8,
            border: "none",
            background: "#16a34a",
            color: "white",
            fontWeight: 600,
            cursor: "pointer",
            marginBottom: 16,
          }}
        >
          {busy === "verify"
            ? "Confirming…"
            : `✓ Confirm ${unchecked.length} imported roll${unchecked.length > 1 ? "s" : ""} as checked`}
        </button>
      )}
      {reels.length === 0 ? (
        <EmptyState text="No rolls yet. Use “Import Old Records” to load your stock from a spreadsheet." />
      ) : (
        <Table
          headers={["Roll code", "Material", "Width", "Remaining paper", "Condition", "Status"]}
          rows={reels.map((reel) => [
            <strong key="code">{reel.reel_code}</strong>,
            (() => {
              const m = materialById.get(reel.material_spec_id);
              return m ? `${m.family} ${m.gsm_value ?? "?"} GSM` : "—";
            })(),
            `${reel.nominal_width_mm.toLocaleString()} mm`,
            formatLength(reel.remaining_length_mm),
            humanizeState(reel.state),
            <span
              key="status"
              style={{
                color:
                  reel.verification_state === "verified" ? "#16a34a" : "#b45309",
                fontWeight: reel.verification_state === "verified" ? 600 : 400,
              }}
            >
              {humanizeState(reel.verification_state)}
            </span>,
          ])}
        />
      )}
    </div>
  );
}

/* ---------- Orders ---------- */

function Orders({ orders, materials }: { orders: Order[]; materials: Material[] }) {
  const materialById = new Map(materials.map((m) => [m.id, m]));
  return (
    <div>
      <h2>Customer Orders</h2>
      <p style={{ color: "#6b7280" }}>
        What your customers asked for. Each line is one sheet size, with the paper type they want.
      </p>
      {orders.length === 0 ? (
        <EmptyState text="No orders yet. Import them from a spreadsheet or add them later." />
      ) : (
        orders.map((order) => (
          <div
            key={order.id}
            style={{ background: "white", borderRadius: 10, border: "1px solid #e5e7eb", padding: 16, marginBottom: 12 }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
              <strong style={{ fontSize: 16 }}>{order.external_id}</strong>
              <span style={{ color: "#6b7280" }}>Due {formatDate(order.promised_at)}</span>
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
        ))
      )}
    </div>
  );
}

/* ---------- Import ---------- */

function ImportScreen({ onDone }: { onDone: () => Promise<void> }) {
  const [result, setResult] = useState<ImportResult | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = async (kind: "reels" | "orders", file: File, dryRun: boolean) => {
    setBusy(kind + (dryRun ? "-check" : ""));
    setError(null);
    try {
      const outcome =
        kind === "reels" ? await api.importReels(file, dryRun) : await api.importOrders(file, dryRun);
      setResult(outcome);
      if (!dryRun) await onDone();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Import failed");
    } finally {
      setBusy(null);
    }
  };

  return (
    <div>
      <h2>Import Old Records</h2>
      <p style={{ color: "#6b7280" }}>
        Load your existing spreadsheets so PaperBrain starts from your real data. Save your file as
        CSV (in Excel: File → Save As → CSV). First download the template to see the expected
        columns — or just match them in your own file.
      </p>

      <ImportCard
        title="📄 Paper rolls (inventory)"
        templateUrl="/v1/imports/reels/template"
        templateName="reels-template.csv"
        busy={busy}
        onRun={(file, dryRun) => void run("reels", file, dryRun)}
        explanation={[
          "reel_code — your roll's ID or barcode, must be unique",
          "material + gsm — e.g. SBS, 250. Matched against materials already in the system; new ones are created automatically",
          "width + width_unit — e.g. 1250, mm (inches are converted)",
          "length_mm — how much paper is left on the roll",
          "status — 'open' if the roll is already partly used, empty if sealed",
          "cost_per_kg + currency — e.g. 1.25, USD. Used to price the waste in every plan",
        ]}
      />

      <ImportCard
        title="📋 Customer orders"
        templateUrl="/v1/imports/orders/template"
        templateName="orders-template.csv"
        busy={busy}
        onRun={(file, dryRun) => void run("orders", file, dryRun)}
        explanation={[
          "order_number — several lines can share one order number",
          "sheet_width_mm × sheet_length_mm — the finished sheet customers want",
          "quantity — number of sheets; a 2% overrun allowance is applied automatically",
          "due_date — e.g. 2026-09-15",
          "rotation_allowed — 'yes' if the sheet may be turned 90°",
        ]}
      />

      {error && <ErrorBanner text={error} />}
      {result && <ImportResultView result={result} />}
    </div>
  );
}

function ImportCard({
  title,
  templateUrl,
  templateName,
  explanation,
  busy,
  onRun,
}: {
  title: string;
  templateUrl: string;
  templateName: string;
  explanation: string[];
  busy: string | null;
  onRun: (file: File, dryRun: boolean) => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  return (
    <div style={{ background: "white", borderRadius: 12, border: "1px solid #e5e7eb", padding: 20, marginBottom: 16 }}>
      <h3 style={{ marginTop: 0 }}>{title}</h3>
      <ul style={{ color: "#6b7280", fontSize: 13, margin: "8px 0 16px", paddingLeft: 20 }}>
        {explanation.map((line) => (
          <li key={line} style={{ marginBottom: 2 }}>
            {line}
          </li>
        ))}
      </ul>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
        <input
          type="file"
          accept=".csv,text/csv"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          style={{ fontSize: 14 }}
        />
        <a
          href={templateUrl}
          download={templateName}
          style={{ color: "#2563eb", fontSize: 14 }}
        >
          ⬇ Download template
        </a>
        <button
          disabled={!file || busy !== null}
          onClick={() => file && onRun(file, true)}
          style={{
            padding: "10px 16px",
            borderRadius: 8,
            border: "1px solid #d1d5db",
            background: "white",
            cursor: !file || busy !== null ? "default" : "pointer",
            opacity: !file || busy !== null ? 0.5 : 1,
          }}
        >
          Check first
        </button>
        <button
          disabled={!file || busy !== null}
          onClick={() => file && onRun(file, false)}
          style={{
            padding: "10px 16px",
            borderRadius: 8,
            border: "none",
            background: "#2563eb",
            color: "white",
            fontWeight: 600,
            cursor: !file || busy !== null ? "default" : "pointer",
            opacity: !file || busy !== null ? 0.5 : 1,
          }}
        >
          Import
        </button>
      </div>
    </div>
  );
}

function ImportResultView({ result }: { result: ImportResult }) {
  const errors = result.issues.filter((i) => i.severity === "error");
  const warnings = result.issues.filter((i) => i.severity === "warning");
  const created =
    result.dry_run
      ? result.kind === "reels"
        ? `${result.row_count - errors.length} roll(s) would be imported`
        : `${result.created_orders} order(s) would be imported`
      : result.kind === "reels"
        ? `✅ Imported ${result.created_reels} roll(s)` + (result.created_materials ? `, created ${result.created_materials} new material(s)` : "")
        : `✅ Imported ${result.created_orders} order(s) with ${result.created_order_lines} sheet line(s)`;

  return (
    <div style={{ background: "white", borderRadius: 12, border: "1px solid #e5e7eb", padding: 20 }}>
      <h3 style={{ marginTop: 0 }}>
        {result.dry_run ? "Dry-run result (nothing saved)" : "Import result"}
      </h3>
      <p style={{ fontWeight: 600 }}>{created}</p>
      {result.materials_to_create.length > 0 && (
        <p style={{ color: "#6b7280" }}>
          New materials that will be created: {result.materials_to_create.join(", ")}
        </p>
      )}
      {result.skipped_rows > 0 && (
        <p style={{ color: "#b45309" }}>{result.skipped_rows} row(s) skipped:</p>
      )}
      {errors.length > 0 && (
        <div style={{ marginTop: 8 }}>
          {errors.map((issue, index) => (
            <div key={index} style={{ padding: "4px 0", color: "#991b1b", fontSize: 14 }}>
              ❌ Row {issue.row}: {issue.message}
              {issue.field && <span style={{ color: "#9ca3af" }}> (column: {issue.field})</span>}
            </div>
          ))}
        </div>
      )}
      {warnings.length > 0 && (
        <div style={{ marginTop: 8 }}>
          {warnings.map((issue, index) => (
            <div key={index} style={{ padding: "4px 0", color: "#92400e", fontSize: 14 }}>
              ⚠️ Row {issue.row}: {issue.message}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ---------- Machine setup ---------- */

const MACHINE_FIELDS: { key: keyof MachineDraft; label: string; hint: string }[] = [
  {
    key: "min_web_width_mm",
    label: "Narrowest roll the machine accepts (mm)",
    hint: "Rolls thinner than this cannot be loaded",
  },
  {
    key: "max_web_width_mm",
    label: "Widest roll the machine accepts (mm)",
    hint: "Usually the machine's rated web width",
  },
  {
    key: "min_crosscut_length_mm",
    label: "Shortest sheet it can cut (mm)",
    hint: "The cut-to-length limit, measured along the roll",
  },
  {
    key: "max_crosscut_length_mm",
    label: "Longest sheet it can cut (mm)",
    hint: "The longest sheet length the machine will deliver",
  },
  {
    key: "min_lane_width_mm",
    label: "Narrowest strip it can slit (mm)",
    hint: "Thinner strips tear or wander on the machine",
  },
  {
    key: "max_lanes",
    label: "Most strips side-by-side",
    hint: "How many sheets across the roll you can run at once",
  },
  {
    key: "inter_lane_kerf_mm",
    label: "Paper lost per slitting knife (mm)",
    hint: "The width the blade eats between two strips — often 0 to 3",
  },
  {
    key: "min_left_trim_mm",
    label: "Left edge trim (mm)",
    hint: "Unusable paper trimmed off the left edge of every roll",
  },
  {
    key: "min_right_trim_mm",
    label: "Right edge trim (mm)",
    hint: "Unusable paper trimmed off the right edge of every roll",
  },
  {
    key: "setup_loss_mm",
    label: "Paper wasted setting up a job (mm)",
    hint: "Run-up waste each time you change the layout",
  },
];

const DEFAULT_MACHINE: MachineDraft = {
  code: "SHEETER-01",
  min_web_width_mm: 600,
  max_web_width_mm: 1400,
  min_crosscut_length_mm: 300,
  max_crosscut_length_mm: 1200,
  min_lane_width_mm: 150,
  max_lanes: 6,
  inter_lane_kerf_mm: 2,
  min_left_trim_mm: 8,
  min_right_trim_mm: 8,
  setup_loss_mm: 1500,
};

function MachineSetup({
  machines,
  onChange,
}: {
  machines: Machine[];
  onChange: () => Promise<void>;
}) {
  const [draft, setDraft] = useState<MachineDraft>(DEFAULT_MACHINE);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const set = (key: keyof MachineDraft, raw: string) => {
    setSaved(false);
    setDraft((current) =>
      key === "code"
        ? { ...current, code: raw }
        : { ...current, [key]: raw === "" ? 0 : Number(raw) },
    );
  };

  const problem = validateMachine(draft);

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      await api.createMachine(draft);
      await onChange();
      setSaved(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save the machine");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <h2>My Machine</h2>
      <p style={{ color: "#6b7280" }}>
        PaperBrain only suggests plans your machine can actually run. Fill in what your sheeter can
        do — the numbers below are typical starting values, so change what you know and leave the
        rest.
      </p>

      {machines.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <h3>Machines already set up</h3>
          <Table
            headers={["Machine", "Roll widths it accepts", "Strips side-by-side"]}
            rows={machines.map((machine) => [
              <strong key="code">{machine.code}</strong>,
              `${machine.min_web_width_mm.toLocaleString()} – ${machine.max_web_width_mm.toLocaleString()} mm`,
              machine.max_lanes,
            ])}
          />
        </div>
      )}

      <div style={{ background: "white", borderRadius: 12, border: "1px solid #e5e7eb", padding: 20 }}>
        <h3 style={{ marginTop: 0 }}>Add a machine</h3>
        <label style={{ display: "block", marginBottom: 16 }}>
          <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 4 }}>Machine name</div>
          <div style={{ color: "#9ca3af", fontSize: 12, marginBottom: 4 }}>
            Whatever your team calls it on the floor
          </div>
          <input
            value={draft.code}
            onChange={(e) => set("code", e.target.value)}
            style={{ padding: 10, borderRadius: 8, border: "1px solid #d1d5db", width: 260 }}
          />
        </label>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 16 }}>
          {MACHINE_FIELDS.map((field) => (
            <label key={field.key} style={{ display: "block" }}>
              <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 4 }}>{field.label}</div>
              <div style={{ color: "#9ca3af", fontSize: 12, marginBottom: 4 }}>{field.hint}</div>
              <input
                type="number"
                min={0}
                value={String(draft[field.key])}
                onChange={(e) => set(field.key, e.target.value)}
                style={{ padding: 10, borderRadius: 8, border: "1px solid #d1d5db", width: 160 }}
              />
            </label>
          ))}
        </div>

        {problem && <div style={{ marginTop: 16 }}><ErrorBanner text={problem} /></div>}
        {error && <div style={{ marginTop: 16 }}><ErrorBanner text={error} /></div>}
        {saved && (
          <div style={{ marginTop: 16, color: "#16a34a", fontWeight: 600 }}>
            ✓ Saved. PaperBrain can plan on this machine now.
          </div>
        )}

        <button
          onClick={() => void save()}
          disabled={saving || problem !== null}
          style={{
            marginTop: 16,
            padding: "12px 24px",
            borderRadius: 8,
            border: "none",
            background: saving || problem ? "#93c5fd" : "#2563eb",
            color: "white",
            fontWeight: 600,
            fontSize: 15,
          }}
        >
          {saving ? "Saving…" : "Save machine"}
        </button>
      </div>
    </div>
  );
}

function validateMachine(draft: MachineDraft): string | null {
  if (!draft.code.trim()) return "Give the machine a name.";
  const positive: (keyof MachineDraft)[] = [
    "min_web_width_mm",
    "max_web_width_mm",
    "min_crosscut_length_mm",
    "max_crosscut_length_mm",
    "min_lane_width_mm",
    "max_lanes",
  ];
  for (const key of positive) {
    if (Number(draft[key]) <= 0) {
      const label = MACHINE_FIELDS.find((f) => f.key === key)?.label ?? key;
      return `“${label}” must be greater than zero.`;
    }
  }
  if (draft.min_web_width_mm > draft.max_web_width_mm) {
    return "The narrowest roll cannot be wider than the widest roll.";
  }
  if (draft.min_crosscut_length_mm > draft.max_crosscut_length_mm) {
    return "The shortest sheet cannot be longer than the longest sheet.";
  }
  if (draft.min_lane_width_mm > draft.max_web_width_mm) {
    return "The narrowest strip cannot be wider than the widest roll.";
  }
  return null;
}

/* ---------- Planning ---------- */

function Planning({
  reels,
  orders,
  machines,
  materials,
  currency,
  onGo,
}: {
  reels: Reel[];
  orders: Order[];
  machines: Machine[];
  materials: Material[];
  currency: string;
  onGo: (screen: Screen) => void;
}) {
  const [policy, setPolicy] = useState("normal");
  const [plan, setPlan] = useState<PlanningResponse | null>(null);
  const [solving, setSolving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<Awaited<ReturnType<typeof api.plans>>>([]);

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

  const solve = async () => {
    setSolving(true);
    setError(null);
    try {
      const result = await api.solve(policy, 30);
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
      setPlan(await api.plan(id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not open plan");
    }
  };

  const checkedReels = reels.filter((r) => r.verification_state === "verified").length;
  const ready = checkedReels > 0 && orders.length > 0 && machines.length > 0;
  const materialById = new Map(materials.map((m) => [m.id, m]));

  return (
    <div>
      <h2>Cutting Plans</h2>
      <p style={{ color: "#6b7280" }}>
        PaperBrain picks rolls and cutting layouts so orders are delivered on time with the least
        wasted paper. Every result is physically verified before it is shown.
      </p>

      {!ready && (
        <div style={{ background: "white", borderRadius: 12, border: "1px solid #e5e7eb", padding: 20, marginBottom: 16 }}>
          <h3 style={{ marginTop: 0 }}>Three things needed before planning</h3>
          <Checklist
            items={[
              {
                done: checkedReels > 0,
                text:
                  checkedReels > 0
                    ? `${checkedReels} checked paper roll(s) in stock`
                    : "At least one checked paper roll — import your stock, then confirm the rolls",
                screen: reels.length > 0 ? "inventory" : "import",
                action: reels.length > 0 ? "Confirm rolls" : "Import rolls",
              },
              {
                done: orders.length > 0,
                text: orders.length > 0 ? `${orders.length} customer order(s)` : "At least one customer order",
                screen: "import",
                action: "Import orders",
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
        </div>
      )}

      {ready && (
        <div style={{ background: "white", borderRadius: 12, border: "1px solid #e5e7eb", padding: 20, marginBottom: 16 }}>
          <label style={{ display: "block", marginBottom: 6, fontWeight: 600 }}>
            What matters most right now?
          </label>
          <select
            value={policy}
            onChange={(e) => setPolicy(e.target.value)}
            style={{ padding: 10, borderRadius: 8, border: "1px solid #d1d5db", fontSize: 14, minWidth: 280 }}
          >
            {["normal", "open_stock_cleanup", "yield_campaign", "service_recovery", "cash_preservation"].map(
              (p) => (
                <option key={p} value={p}>
                  {humanizePolicy(p)}
                </option>
              ),
            )}
          </select>
          <div style={{ marginTop: 12 }}>
            <button
              onClick={() => void solve()}
              disabled={solving}
              style={{
                padding: "12px 24px",
                borderRadius: 8,
                border: "none",
                background: solving ? "#93c5fd" : "#2563eb",
                color: "white",
                fontWeight: 600,
                fontSize: 15,
              }}
            >
              {solving ? "Working out the best plan…" : "▶ Create cutting plan"}
            </button>
          </div>
        </div>
      )}

      {error && <ErrorBanner text={error} />}

      {plan && <PlanResult plan={plan} materialById={materialById} currency={currency} />}

      {history.length > 0 && (
        <div style={{ marginTop: 24 }}>
          <h3>Previous plans</h3>
          <Table
            headers={["Created", "Focus", "Result", "Paper wasted (est. cost)", "New rolls opened"]}
            rows={history.map((item) => [
              <button
                key="open"
                onClick={() => void openPlan(item.plan_id)}
                style={{ color: "#2563eb", background: "none", border: "none", cursor: "pointer", padding: 0, font: "inherit", textDecoration: "underline" }}
              >
                {formatDate(item.created_at)}
              </button>,
              humanizePolicy(item.policy_name),
              item.validation_valid === false ? "⚠️ Needs attention" : humanizeStatus(item.status),
              formatMoney(item.material_loss_minor, currency),
              item.fresh_reels_opened,
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
  items: { done: boolean; text: string; screen: Screen; action: string }[];
  onGo: (screen: Screen) => void;
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
          <span style={{ flex: 1, color: item.done ? "#374151" : "#111827" }}>{item.text}</span>
          {!item.done && (
            <button
              onClick={() => onGo(item.screen)}
              style={{
                padding: "6px 12px",
                borderRadius: 6,
                border: "1px solid #d1d5db",
                background: "white",
                fontSize: 13,
              }}
            >
              {item.action}
            </button>
          )}
        </div>
      ))}
    </div>
  );
}

function PlanResult({
  plan,
  materialById,
  currency,
}: {
  plan: PlanningResponse;
  materialById: Map<string, Material>;
  currency: string;
}) {
  const reelById = new Map(plan.reels.map((r) => [r.id, r]));
  const patternById = new Map(plan.patterns.map((p) => [p.id, p]));
  const lineById = new Map(plan.order_lines.map((l) => [l.id, l]));
  const totalLoss = plan.objective.material_loss_minor ?? 0;
  const shortage = plan.objective.service_shortage_sheets ?? 0;
  const gsm = materialsGsm(materialById);

  return (
    <div style={{ background: "white", borderRadius: 12, border: "1px solid #e5e7eb", padding: 20 }}>
      <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
        <h3 style={{ margin: 0 }}>
          {shortage > 0 ? "Plan found, but some sheets cannot be made" : humanizeStatus(plan.status)}
        </h3>
        <span style={{ color: plan.validation_valid ? "#16a34a" : "#b91c1c", fontWeight: 600 }}>
          {plan.validation_valid ? "✓ Physically verified" : "⚠ Validation problems"}
        </span>
      </div>

      {shortage > 0 && (
        <div
          style={{
            background: "#fffbeb",
            border: "1px solid #fde68a",
            borderRadius: 8,
            padding: "12px 16px",
            marginTop: 12,
            color: "#92400e",
          }}
        >
          ⚠️ {shortage.toLocaleString()} sheet{shortage > 1 ? "s" : ""} could not be produced from the
          stock PaperBrain is allowed to use. Usual reasons: rolls still waiting to be checked, not
          enough paper of that type, or sheets wider than any roll you own.
        </div>
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
    </div>
  );
}

function materialsGsm(materialById: Map<string, Material>): string | null {
  for (const material of materialById.values()) {
    if (material.gsm_value) return material.gsm_value;
  }
  return null;
}

/* ---------- shared ---------- */

function EmptyState({ text }: { text: string }) {
  return (
    <div
      style={{
        background: "white",
        border: "1px dashed #d1d5db",
        borderRadius: 12,
        padding: 32,
        textAlign: "center",
        color: "#6b7280",
      }}
    >
      {text}
    </div>
  );
}

function ErrorBanner({ text }: { text: string }) {
  return (
    <div
      style={{
        background: "#fef2f2",
        border: "1px solid #fecaca",
        borderRadius: 8,
        padding: "10px 16px",
        color: "#991b1b",
        marginBottom: 12,
      }}
    >
      ⚠️ {text}
    </div>
  );
}

function Table({ headers, rows }: { headers: string[]; rows: ReactNode[][] }) {
  return (
    <div style={{ overflowX: "auto", background: "white", borderRadius: 12, border: "1px solid #e5e7eb" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
        <thead>
          <tr>
            {headers.map((header) => (
              <th
                key={header}
                style={{
                  textAlign: "left",
                  padding: "12px 16px",
                  borderBottom: "1px solid #e5e7eb",
                  color: "#6b7280",
                  fontWeight: 600,
                  fontSize: 12,
                  textTransform: "uppercase",
                  letterSpacing: 0.03,
                }}
              >
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index}>
              {row.map((cell, cellIndex) => (
                <td key={cellIndex} style={{ padding: "12px 16px", borderBottom: "1px solid #f3f4f6" }}>
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
