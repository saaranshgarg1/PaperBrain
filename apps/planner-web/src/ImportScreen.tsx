import { useState } from "react";
import type { ImportResult } from "./api";
import { api } from "./api";
import { Button, ErrorBanner, Panel } from "./ui";

export function ImportScreen({ onDone }: { onDone: () => Promise<void> }) {
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
        columns — or just match them in your own file. You can import again any time: new rolls and
        orders are added, duplicates are skipped.
      </p>

      <ImportCard
        title="📄 Paper rolls (inventory)"
        templateUrl="/v1/imports/reels/template"
        templateName="reels-template.csv"
        busy={busy}
        onRun={(file, dryRun) => void run("reels", file, dryRun)}
        explanation={[
          "reel_code — your roll's ID or barcode, must be unique",
          "material + gsm — e.g. SBS, 250. Matched against paper types already in the system; new ones are created automatically",
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
    <Panel title={title}>
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
        <a href={templateUrl} download={templateName} style={{ color: "#2563eb", fontSize: 14 }}>
          ⬇ Download template
        </a>
        <Button disabled={!file || busy !== null} onClick={() => file && onRun(file, true)}>
          Check first
        </Button>
        <Button
          kind="primary"
          disabled={!file || busy !== null}
          onClick={() => file && onRun(file, false)}
        >
          Import
        </Button>
      </div>
    </Panel>
  );
}

function ImportResultView({ result }: { result: ImportResult }) {
  const errors = result.issues.filter((i) => i.severity === "error");
  const warnings = result.issues.filter((i) => i.severity === "warning");
  const created = result.dry_run
    ? result.kind === "reels"
      ? `${result.row_count - errors.length} roll(s) would be imported`
      : `${result.created_orders} order(s) would be imported`
    : result.kind === "reels"
      ? `✅ Imported ${result.created_reels} roll(s)` +
        (result.created_materials ? `, created ${result.created_materials} new paper type(s)` : "")
      : `✅ Imported ${result.created_orders} order(s) with ${result.created_order_lines} sheet line(s)`;

  return (
    <Panel title={result.dry_run ? "Dry-run result (nothing saved)" : "Import result"}>
      <p style={{ fontWeight: 600 }}>{created}</p>
      {result.materials_to_create.length > 0 && (
        <p style={{ color: "#6b7280" }}>
          New paper types that will be created: {result.materials_to_create.join(", ")}
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
    </Panel>
  );
}
