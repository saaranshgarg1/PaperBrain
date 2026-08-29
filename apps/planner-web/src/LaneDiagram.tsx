import { colorFor } from "./colors";
import type { PlanPattern } from "./api";
import { formatLength } from "./format";

interface LaneDiagramProps {
  pattern: PlanPattern;
  crosscutCount: number;
  orderLines: { id: string; sheet_width_mm: number; sheet_length_mm: number }[];
}

export function LaneDiagram({ pattern, crosscutCount, orderLines }: LaneDiagramProps) {
  const totalWidth = pattern.usable_width_mm + pattern.left_trim_mm + pattern.right_trim_mm;
  const scale = 100 / totalWidth;
  const lineById = new Map(orderLines.map((line) => [line.id, line]));
  const sortedLanes = [...pattern.lanes].sort((a, b) => a.start_mm - b.start_mm);

  const trimStyle = {
    position: "absolute" as const,
    top: 0,
    bottom: 0,
    background:
      "repeating-linear-gradient(45deg, #f3f4f6, #f3f4f6 4px, #e5e7eb 4px, #e5e7eb 8px)",
  };

  return (
    <div style={{ border: "1px solid #e5e7eb", borderRadius: 8, padding: 12 }}>
      <div style={{ marginBottom: 6, fontSize: 13, color: "#374151" }}>
        Sheet length: <strong>{formatLength(pattern.crosscut_length_mm)}</strong> ·{" "}
        {crosscutCount.toLocaleString()} cuts · edge trim {pattern.left_trim_mm}+{pattern.right_trim_mm} mm
      </div>
      <div
        style={{
          position: "relative",
          height: 44,
          background: "#f9fafb",
          borderRadius: 6,
          overflow: "hidden",
        }}
      >
        {pattern.left_trim_mm > 0 && (
          <div
            title={`Left edge trim: ${pattern.left_trim_mm} mm (waste)`}
            style={{ ...trimStyle, left: 0, width: `${pattern.left_trim_mm * scale}%` }}
          />
        )}
        {sortedLanes.map((lane, index) => {
          const line = lineById.get(lane.order_line_id);
          return (
            <div
              key={index}
              title={`${line ? `${line.sheet_width_mm} × ${line.sheet_length_mm} mm sheet` : "Sheet"} — ${formatLength(lane.width_mm)} wide`}
              style={{
                position: "absolute",
                left: `${(pattern.left_trim_mm + lane.start_mm) * scale}%`,
                width: `${lane.width_mm * scale}%`,
                top: 0,
                bottom: 0,
                background: colorFor(index),
                color: "white",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 11,
                fontWeight: 600,
                overflow: "hidden",
                whiteSpace: "nowrap",
              }}
            >
              {lane.width_mm * scale > 5 ? lane.width_mm : ""}
            </div>
          );
        })}
        {pattern.right_trim_mm > 0 && (
          <div
            title={`Right edge trim: ${pattern.right_trim_mm} mm (waste)`}
            style={{ ...trimStyle, right: 0, width: `${pattern.right_trim_mm * scale}%` }}
          />
        )}
      </div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          fontSize: 11,
          color: "#9ca3af",
          marginTop: 2,
        }}
      >
        <span>0 mm</span>
        <span>{totalWidth.toLocaleString()} mm across the roll</span>
      </div>
    </div>
  );
}
