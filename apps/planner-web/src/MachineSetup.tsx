import { useState } from "react";
import type { Machine, MachineDraft } from "./api";
import { api } from "./api";
import { Button, ErrorBanner, Field, Panel, Table, inputStyle } from "./ui";

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

export function MachineSetup({
  machines,
  onChange,
}: {
  machines: Machine[];
  onChange: () => Promise<void>;
}) {
  const [draft, setDraft] = useState<MachineDraft>(DEFAULT_MACHINE);
  const [showForm, setShowForm] = useState(machines.length === 0);
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
      setShowForm(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save the machine");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <h2>My Machines</h2>
      <p style={{ color: "#6b7280" }}>
        PaperBrain only suggests plans your machines can actually run. Add every sheeter or
        cutter you use — the numbers below are typical starting values, so change what you know
        and leave the rest.
      </p>

      {machines.length > 0 && (
        <div style={{ marginBottom: 16 }}>
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

      {!showForm && (
        <Button kind="primary" onClick={() => setShowForm(true)}>
          + Add another machine
        </Button>
      )}

      {showForm && (
        <Panel title="Add a machine" actions={<Button small onClick={() => setShowForm(false)}>Close</Button>}>
          {error && <ErrorBanner text={error} />}
          <Field label="Machine name" hint="Whatever your team calls it on the floor">
            <input
              value={draft.code}
              onChange={(e) => set("code", e.target.value)}
              style={{ ...inputStyle, width: 260 }}
            />
          </Field>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 16, marginTop: 16 }}>
            {MACHINE_FIELDS.map((field) => (
              <Field key={field.key} label={field.label} hint={field.hint}>
                <input
                  type="number"
                  min={0}
                  value={String(draft[field.key])}
                  onChange={(e) => set(field.key, e.target.value)}
                  style={{ ...inputStyle, width: 160 }}
                />
              </Field>
            ))}
          </div>
          {problem && <p style={{ color: "#b45309", fontSize: 13, marginTop: 16 }}>{problem}</p>}
          <div style={{ display: "flex", gap: 12, marginTop: 16 }}>
            <Button kind="primary" onClick={() => void save()} disabled={saving || problem !== null}>
              {saving ? "Saving…" : "Save machine"}
            </Button>
            {machines.length > 0 && <Button onClick={() => setShowForm(false)}>Cancel</Button>}
          </div>
          {saved && (
            <div style={{ marginTop: 16, color: "#16a34a", fontWeight: 600 }}>
              ✓ Saved. PaperBrain can plan on this machine now.
            </div>
          )}
        </Panel>
      )}
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
