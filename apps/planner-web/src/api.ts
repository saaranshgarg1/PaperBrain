const BASE = "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(BASE + path, {
    ...init,
    headers:
      init?.body instanceof FormData
        ? init?.headers
        : { "Content-Type": "application/json", ...init?.headers },
  });
  const text = await response.text();
  const body = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const message = body?.message || body?.detail || `Request failed (${response.status})`;
    throw new Error(message);
  }
  return body as T;
}

export interface Material {
  id: string;
  family: string;
  grade: string;
  gsm_value: string | null;
  cost_minor_per_kg: number;
  currency: string;
}

export interface Reel {
  id: string;
  reel_code: string;
  material_spec_id: string;
  nominal_width_mm: number;
  remaining_length_mm: number;
  state: string;
  verification_state: string;
  location_id: string;
  length_confidence: string;
}

export interface OrderLine {
  id: string;
  order_id: string;
  sheet_width_mm: number;
  sheet_length_mm: number;
  quantity_required: number;
  quantity_min: number;
  quantity_max: number;
  material_spec_id: string;
  due_at: string;
}

export interface Order {
  id: string;
  external_id: string;
  customer_id: string;
  status: string;
  promised_at: string;
  lines: OrderLine[];
}

export interface Machine {
  id: string;
  code: string;
  min_web_width_mm: number;
  max_web_width_mm: number;
  max_lanes: number;
}

export interface MachineDraft {
  code: string;
  min_web_width_mm: number;
  max_web_width_mm: number;
  min_crosscut_length_mm: number;
  max_crosscut_length_mm: number;
  min_lane_width_mm: number;
  max_lanes: number;
  inter_lane_kerf_mm: number;
  min_left_trim_mm: number;
  min_right_trim_mm: number;
  setup_loss_mm: number;
}

export interface PlanLane {
  order_line_id: string;
  start_mm: number;
  width_mm: number;
  position: number;
}

export interface PlanPattern {
  id: string;
  machine_id: string;
  crosscut_length_mm: number;
  lanes: PlanLane[];
  left_trim_mm: number;
  right_trim_mm: number;
  kerf_total_mm: number;
  usable_width_mm: number;
}

export interface PlanRun {
  id: string;
  reel_id: string;
  machine_id: string;
  pattern_id: string;
  crosscut_count: number;
  consumed_length_mm: number;
  outputs: { order_line_id: string; quantity: number }[];
  sequence: number;
}

export interface PlanningResponse {
  plan_id: string;
  status: string;
  policy_name: string;
  objective: Record<string, number>;
  solver: { name?: string; wall_seconds?: number };
  runs: PlanRun[];
  patterns: PlanPattern[];
  order_lines: {
    id: string;
    sheet_width_mm: number;
    sheet_length_mm: number;
    quantity_required: number;
  }[];
  reels: { id: string; reel_code: string; nominal_width_mm: number; state: string }[];
  validation_valid: boolean;
  violations: { code: string; message: string }[];
  created_at: string | null;
}

export interface ImportResult {
  kind: string;
  dry_run: boolean;
  created_reels: number;
  created_materials: number;
  created_orders: number;
  created_order_lines: number;
  skipped_rows: number;
  materials_to_create: string[];
  row_count: number;
  issues: {
    row: number;
    code: string;
    message: string;
    severity: string;
    field: string | null;
  }[];
}

export const api = {
  materials: () => request<Material[]>("/v1/materials"),
  reels: () => request<Reel[]>("/v1/reels"),
  verifyReel: (id: string) =>
    request<Reel>(`/v1/reels/${id}/verify`, { method: "POST", body: "{}" }),
  orders: () => request<Order[]>("/v1/orders"),
  machines: () => request<Machine[]>("/v1/machines"),
  createMachine: (draft: MachineDraft) =>
    request<Machine>("/v1/machines", { method: "POST", body: JSON.stringify(draft) }),
  plans: () =>
    request<
      {
        plan_id: string;
        created_at: string | null;
        status: string;
        policy_name: string;
        run_count: number;
        validation_valid: boolean | null;
        material_loss_minor: number;
        fresh_reels_opened: number;
        service_shortage_sheets: number;
      }[]
    >("/v1/planning/plans"),
  plan: (id: string) => request<PlanningResponse>(`/v1/planning/plans/${id}`),
  solve: (policy: string, timeLimit: number) =>
    request<PlanningResponse>("/v1/planning/runs", {
      method: "POST",
      body: JSON.stringify({
        policy_profile: policy,
        time_limit_seconds: timeLimit,
        seed: 42,
        mode: "full",
      }),
    }),
  seedDemo: () => request<{ code: string }>("/v1/demo/seed", { method: "POST", body: "{}" }),
  importReels: (file: File, dryRun: boolean) => {
    const form = new FormData();
    form.append("file", file);
    form.append("dry_run", String(dryRun));
    return request<ImportResult>("/v1/imports/reels", { method: "POST", body: form });
  },
  importOrders: (file: File, dryRun: boolean) => {
    const form = new FormData();
    form.append("file", file);
    form.append("dry_run", String(dryRun));
    return request<ImportResult>("/v1/imports/orders", { method: "POST", body: form });
  },
};
