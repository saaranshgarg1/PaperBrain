import { useState } from "react";
import type { Material, NamedEntity, Reel } from "./api";
import { api } from "./api";
import { formatLength, humanizeState } from "./format";
import { materialLabel } from "./Dashboard";
import { Button, EmptyState, ErrorBanner, Field, Panel, StatusChip, Table, inputStyle } from "./ui";

interface NewReelDraft {
  reel_code: string;
  material_spec_id: string;
  nominal_width_mm: string;
  remaining_length_mm: string;
  state: "unopened" | "opened";
  location: string;
}

const BLANK_REEL: NewReelDraft = {
  reel_code: "",
  material_spec_id: "",
  nominal_width_mm: "",
  remaining_length_mm: "",
  state: "unopened",
  location: "",
};

export function Inventory({
  reels,
  materials,
  locations,
  onChange,
}: {
  reels: Reel[];
  materials: Material[];
  locations: NamedEntity[];
  onChange: () => Promise<void>;
}) {
  const [showAdd, setShowAdd] = useState(false);
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

  const quarantine = async (reel: Reel) => {
    const reason = window.prompt(
      `Why is roll ${reel.reel_code} being taken off the shelf?\n(e.g. "damaged edge", "returned to supplier")`,
    );
    if (reason === null) return;
    setBusy(reel.id);
    setError(null);
    try {
      await api.quarantineReel(reel.id, reason || "No reason given");
      await onChange();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not update the roll");
    } finally {
      setBusy(null);
    }
  };

  const release = async (reel: Reel) => {
    setBusy(reel.id);
    setError(null);
    try {
      await api.releaseReel(reel.id);
      await onChange();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not update the roll");
    } finally {
      setBusy(null);
    }
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
        <h2 style={{ margin: 0 }}>Paper Rolls</h2>
        <Button kind="primary" onClick={() => setShowAdd((v) => !v)}>
          {showAdd ? "Close" : "+ Add a roll"}
        </Button>
      </div>
      <p style={{ color: "#6b7280" }}>
        Every physical roll you own. "Checked" means the details have been confirmed on the shelf —
        only checked rolls can go into a cutting plan.
      </p>

      {error && <ErrorBanner text={error} />}

      {showAdd && (
        <AddRollForm
          materials={materials}
          locations={locations}
          onDone={async () => {
            setShowAdd(false);
            await onChange();
          }}
          onCancel={() => setShowAdd(false)}
        />
      )}

      {unchecked.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <Button kind="success" onClick={() => void verifyAll()} disabled={busy === "verify"}>
            {busy === "verify"
              ? "Confirming…"
              : `✓ Confirm ${unchecked.length} imported roll${unchecked.length > 1 ? "s" : ""} as checked`}
          </Button>
        </div>
      )}

      {reels.length === 0 ? (
        <EmptyState text="No rolls yet. Use “+ Add a roll” above, or import your whole stock from a spreadsheet under “Import Old Records”." />
      ) : (
        <Table
          headers={["Roll code", "Material", "Width", "Remaining paper", "Condition", "Status", ""]}
          rows={reels.map((reel) => {
            const dimmed = reel.state === "exhausted" || reel.state === "quarantined";
            return [
              <strong key="code" style={{ opacity: dimmed ? 0.5 : 1 }}>
                {reel.reel_code}
              </strong>,
              <span key="mat" style={{ opacity: dimmed ? 0.5 : 1 }}>
                {materialLabel(materialById, reel.material_spec_id)}
              </span>,
              `${reel.nominal_width_mm.toLocaleString()} mm`,
              reel.state === "exhausted" ? (
                <StatusChip text="Nothing left" tone="gray" />
              ) : (
                formatLength(reel.remaining_length_mm)
              ),
              humanizeState(reel.state),
              <span key="status">
                {reel.verification_state === "verified" ? (
                  <StatusChip text="Checked ✓" tone="green" />
                ) : (
                  <StatusChip text="Needs checking" tone="amber" />
                )}
              </span>,
              <span key="actions" style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {reel.verification_state === "provisional" && reel.state !== "exhausted" && (
                  <Button small onClick={() => void api.verifyReel(reel.id).then(onChange)} disabled={busy === reel.id}>
                    ✓ Check
                  </Button>
                )}
                {(reel.state === "unopened" || reel.state === "opened") && (
                  <Button small kind="danger" onClick={() => void quarantine(reel)} disabled={busy === reel.id}>
                    Take off shelf
                  </Button>
                )}
                {reel.state === "quarantined" && (
                  <Button small onClick={() => void release(reel)} disabled={busy === reel.id}>
                    Put back
                  </Button>
                )}
              </span>,
            ];
          })}
        />
      )}
    </div>
  );
}

function AddRollForm({
  materials,
  locations,
  onDone,
  onCancel,
}: {
  materials: Material[];
  locations: NamedEntity[];
  onDone: () => Promise<void>;
  onCancel: () => void;
}) {
  const [draft, setDraft] = useState<NewReelDraft>({
    ...BLANK_REEL,
    material_spec_id: materials[0]?.id ?? "",
    location: locations[0]?.name ?? "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const width = Number(draft.nominal_width_mm);
  const length = Number(draft.remaining_length_mm);
  const problem = !draft.reel_code.trim()
    ? "Give the roll a code or name so it can be found on the shelf"
    : !draft.material_spec_id
      ? "Pick the paper type"
      : !Number.isFinite(width) || width <= 0
        ? "Width must be a positive number (millimetres)"
        : !Number.isFinite(length) || length <= 0
          ? "Length must be a positive number (millimetres)"
          : null;

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      let locationId = locations.find((l) => l.name === draft.location.trim())?.id;
      if (!locationId && draft.location.trim()) {
        locationId = (await api.createLocation(draft.location.trim())).id;
      }
      if (!locationId) locationId = (await api.createLocation("Main Store")).id;
      await api.createReel({
        reel_code: draft.reel_code.trim(),
        material_spec_id: draft.material_spec_id,
        nominal_width_mm: Math.round(width),
        remaining_length_mm: Math.round(length),
        location_id: locationId,
        state: draft.state,
      });
      await onDone();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not add the roll");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Panel title="Add a roll by hand">
      {error && <ErrorBanner text={error} />}
      {materials.length === 0 ? (
        <EmptyState text="There are no paper types yet. Import a spreadsheet first (PaperBrain creates types automatically), or add rolls through the import screen." />
      ) : (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 16 }}>
            <Field label="Roll code" hint="ID or barcode — must be unique">
              <input
                value={draft.reel_code}
                onChange={(e) => setDraft({ ...draft, reel_code: e.target.value })}
                style={inputStyle}
                placeholder="e.g. R-0142"
              />
            </Field>
            <Field label="Paper type">
              <select
                value={draft.material_spec_id}
                onChange={(e) => setDraft({ ...draft, material_spec_id: e.target.value })}
                style={inputStyle}
              >
                {materials.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.family} {m.gsm_value ?? "?"} GSM
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Width (mm)" hint="Across the roll">
              <input
                type="number"
                min={1}
                value={draft.nominal_width_mm}
                onChange={(e) => setDraft({ ...draft, nominal_width_mm: e.target.value })}
                style={inputStyle}
                placeholder="e.g. 1250"
              />
            </Field>
            <Field label="Length left (mm)" hint="Along the roll">
              <input
                type="number"
                min={1}
                value={draft.remaining_length_mm}
                onChange={(e) => setDraft({ ...draft, remaining_length_mm: e.target.value })}
                style={inputStyle}
                placeholder="e.g. 1500000"
              />
            </Field>
            <Field label="Where is it?" hint="Shelf or godown name">
              <input
                value={draft.location}
                onChange={(e) => setDraft({ ...draft, location: e.target.value })}
                style={inputStyle}
                placeholder="e.g. Main Store"
              />
            </Field>
            <Field label="Condition">
              <select
                value={draft.state}
                onChange={(e) => setDraft({ ...draft, state: e.target.value as "unopened" | "opened" })}
                style={inputStyle}
              >
                <option value="unopened">New (sealed)</option>
                <option value="opened">Open — partly used</option>
              </select>
            </Field>
          </div>
          <div style={{ display: "flex", gap: 12, marginTop: 16 }}>
            <Button kind="primary" onClick={() => void save()} disabled={saving || problem !== null}>
              {saving ? "Adding…" : "Add roll"}
            </Button>
            <Button onClick={onCancel}>Cancel</Button>
          </div>
          {problem && <p style={{ color: "#b45309", fontSize: 13, marginTop: 8 }}>{problem}</p>}
        </>
      )}
    </Panel>
  );
}
