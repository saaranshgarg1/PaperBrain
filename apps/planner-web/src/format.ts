export function formatMoney(minor: number, currency = "USD"): string {
  const value = minor / 100;
  return value.toLocaleString(undefined, {
    style: "currency",
    currency,
    maximumFractionDigits: value >= 100 ? 0 : 2,
  });
}

export function formatLength(mm: number): string {
  if (mm >= 1000) return `${(mm / 1000).toLocaleString(undefined, { maximumFractionDigits: 1 })} m`;
  return `${mm} mm`;
}

/** Area of paper in square metres, from a width × length in millimetres. */
export function formatArea(mm2: number): string {
  const m2 = mm2 / 1_000_000;
  if (m2 >= 10_000) return `${Math.round(m2).toLocaleString()} m²`;
  return `${m2.toLocaleString(undefined, { maximumFractionDigits: 1 })} m²`;
}

export function formatKg(mm2: number, gsm: number): string {
  const kg = (mm2 * gsm) / 1_000_000_000;
  return `${kg.toLocaleString(undefined, { maximumFractionDigits: 1 })} kg`;
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  return date.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function daysUntil(iso: string | null | undefined): number | null {
  if (!iso) return null;
  const ms = new Date(iso).getTime() - Date.now();
  return Math.ceil(ms / 86_400_000);
}

export function humanizeState(state: string): string {
  const map: Record<string, string> = {
    unopened: "New (sealed)",
    opened: "Open (in use)",
    reserved: "Reserved",
    exhausted: "Used up",
    quarantined: "On hold",
    provisional: "Needs checking",
    verified: "Checked ✓",
  };
  return map[state] ?? state;
}

export function humanizePolicy(policy: string): string {
  const map: Record<string, string> = {
    normal: "Balanced (recommended)",
    open_stock_cleanup: "Use up open reels first",
    yield_campaign: "Minimize paper waste",
    service_recovery: "Prioritize on-time delivery",
    cash_preservation: "Avoid opening new reels",
  };
  return map[policy] ?? policy;
}

export function humanizeStatus(status: string): string {
  const map: Record<string, string> = {
    optimal: "Best possible plan found",
    feasible: "Working plan found",
    timeout_feasible: "Good plan found (time limit hit)",
    infeasible: "No feasible plan — check inventory",
  };
  return map[status] ?? status;
}

export function humanizeOrderStatus(status: string): string {
  const map: Record<string, string> = {
    draft: "Draft",
    confirmed: "Open",
    validation_required: "Needs checking",
    released: "Released",
    running: "Being cut",
    complete: "Fulfilled ✓",
    cancelled: "Cancelled",
  };
  return map[status] ?? status;
}
