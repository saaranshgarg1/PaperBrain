import type { ReactNode } from "react";

export function Button({
  children,
  onClick,
  kind = "default",
  disabled,
  small,
}: {
  children: ReactNode;
  onClick?: () => void;
  kind?: "primary" | "default" | "success" | "danger" | "ghost";
  disabled?: boolean;
  small?: boolean;
}) {
  const styles: Record<string, React.CSSProperties> = {
    primary: { background: disabled ? "#93c5fd" : "#2563eb", color: "white", border: "none" },
    success: { background: disabled ? "#86efac" : "#16a34a", color: "white", border: "none" },
    danger: { background: "white", color: "#b91c1c", border: "1px solid #fca5a5" },
    default: { background: "white", color: "#111827", border: "1px solid #d1d5db" },
    ghost: {
      background: "none",
      color: "#2563eb",
      border: "none",
      textDecoration: "underline",
      padding: 0,
    },
  };
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        padding: small ? "4px 10px" : "10px 16px",
        borderRadius: 8,
        cursor: disabled ? "not-allowed" : "pointer",
        fontWeight: kind === "primary" || kind === "success" ? 600 : 400,
        fontSize: small ? 13 : 14,
        opacity: disabled && kind !== "primary" ? 0.55 : 1,
        ...styles[kind],
      }}
    >
      {children}
    </button>
  );
}

export function Stat({ label, value, sub }: { label: string; value: ReactNode; sub?: string }) {
  return (
    <div style={{ background: "white", borderRadius: 12, padding: 20, border: "1px solid #e5e7eb" }}>
      <div style={{ fontSize: 30, fontWeight: 700 }}>{value}</div>
      <div style={{ color: "#6b7280", fontSize: 14 }}>{label}</div>
      {sub && <div style={{ color: "#9ca3af", fontSize: 12, marginTop: 4 }}>{sub}</div>}
    </div>
  );
}

export function EmptyState({ text }: { text: string }) {
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

export function ErrorBanner({ text }: { text: string }) {
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

export function Notice({ children, kind = "amber" }: { children: ReactNode; kind?: "amber" | "blue" }) {
  const colors =
    kind === "amber"
      ? { background: "#fffbeb", border: "#fde68a", color: "#92400e" }
      : { background: "#eff6ff", border: "#bfdbfe", color: "#1e40af" };
  return (
    <div
      style={{
        background: colors.background,
        border: `1px solid ${colors.border}`,
        borderRadius: 8,
        padding: "12px 16px",
        color: colors.color,
        marginBottom: 12,
      }}
    >
      {children}
    </div>
  );
}

export function Table({ headers, rows }: { headers: string[]; rows: ReactNode[][] }) {
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

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label style={{ display: "block" }}>
      <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 4 }}>{label}</div>
      {hint && <div style={{ color: "#9ca3af", fontSize: 12, marginBottom: 4 }}>{hint}</div>}
      {children}
    </label>
  );
}

export const inputStyle: React.CSSProperties = {
  padding: 10,
  borderRadius: 8,
  border: "1px solid #d1d5db",
  fontSize: 14,
  width: "100%",
};

export function Panel({
  title,
  children,
  actions,
}: {
  title?: string;
  children: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div style={{ background: "white", borderRadius: 12, border: "1px solid #e5e7eb", padding: 20, marginBottom: 16 }}>
      {(title || actions) && (
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          {title && <h3 style={{ margin: "0 0 12px" }}>{title}</h3>}
          {actions}
        </div>
      )}
      {children}
    </div>
  );
}

export function StatusChip({ text, tone }: { text: string; tone: "green" | "amber" | "red" | "gray" | "blue" }) {
  const tones: Record<string, { background: string; color: string }> = {
    green: { background: "#f0fdf4", color: "#15803d" },
    amber: { background: "#fffbeb", color: "#b45309" },
    red: { background: "#fef2f2", color: "#b91c1c" },
    gray: { background: "#f3f4f6", color: "#6b7280" },
    blue: { background: "#eff6ff", color: "#1d4ed8" },
  };
  const style = tones[tone];
  return (
    <span
      style={{
        background: style.background,
        color: style.color,
        padding: "2px 10px",
        borderRadius: 999,
        fontSize: 12,
        fontWeight: 600,
        whiteSpace: "nowrap",
      }}
    >
      {text}
    </span>
  );
}
