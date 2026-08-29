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
