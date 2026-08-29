# PaperBrain

PaperBrain is a decision-intelligence system for paper-reel inventory, cutting-pattern optimization, production planning, execution, and reconciliation.

This repository currently implements the first vertical slice described in the workspace-level `plan.md`:

- canonical units and typed domain entities;
- roll identity, state, measurements, segments, and immutable events;
- order, machine, orientation, pattern, plan, and policy models;
- deterministic compatibility, geometry, and plan validation;
- bounded pattern enumeration and conservative dominance filtering;
- an open-reel-aware heuristic and a CP-SAT planning adapter;
- application services and in-memory repositories;
- FastAPI contracts and initial routes;
- **CSV import of legacy records (reels and orders) with dry-run validation**;
- **JSON-file state snapshots — the app restarts exactly where you left off (hotstart)**;
- **a built-in web UI (`apps/planner-web`) for non-technical users**.

The API uses in-memory repositories by default so the domain and optimizer can be exercised before database integration is enabled. Production deployment must use the database-backed ports, transactional event/outbox persistence, authentication, and approval controls described in `plan.md`.

No plan is releasable merely because a solver produced it. `PlanValidator` must independently validate all geometry, material, machine, quantity, length, and inventory constraints against the same immutable planning snapshot.

## Quick start

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/) (Node/pnpm only if you change the UI).

```bash
uv sync --extra dev          # create the venv and install dependencies
cd apps/planner-web
pnpm install && pnpm build   # build the web UI (once; skip if dist/ already exists)
cd ../..
uv run paperbrain-api        # serves API + UI at http://localhost:8000
```

Open **http://localhost:8000** in a browser. The UI is designed for people with business
knowledge only — no API calls needed. The flow it walks you through:

1. **Import Old Records** — upload your existing reel stock and customer orders as CSV.
   "Check first" previews what would happen without saving anything. Import again any
   time: new records are added, duplicates skipped.
2. **Paper Rolls** — every roll, with "+ Add a roll" for hand entry, "✓ Check" to confirm
   imported rolls, "Take off shelf"/"Put back" for damaged or returned rolls.
3. **Customer Orders** — "+ Take an order" for phone orders, "Cancel order" to drop one.
4. **My Machine** — enter what your sheeter can do (widths, lanes, trims, kerf).
5. **Cutting Plans** — tick which orders to include (or select all), pick what matters
   most (least waste, on-time delivery, …), press "Create cutting plan". You get
   step-by-step run instructions with a to-scale diagram of how each roll is slit.
   Then press **"Carry out this plan"**: the paper is marked as used from each roll
   (leftovers stay in stock as "Open"), finished orders are marked fulfilled, and
   the dashboard statistics update immediately.
6. **Home** — live statistics: stock vs open demand per paper type, coverage warnings
   ("SBS 250: 64% — short"), orders coming in per week, waste of the latest plan, and
   a "Needs your attention" list (rolls to check, late orders, missing machine).

Optional demo data (1 machine, 2 reels, 1 order) to explore without importing anything:

```bash
PAPERBRAIN_SEED_DEMO=true uv run paperbrain-api
```

or press "Try the demo data" on the empty home screen (only works while stock is empty).

## Hotstart (restart where you left off)

Every successful change is written atomically to a JSON snapshot (default `data/state.json`).
On startup the snapshot is loaded, so inventory, orders, machines, carried-out plans, and even
the paper already consumed from each roll all survive restarts. Configure or disable via:

| Variable | Default | Meaning |
| --- | --- | --- |
| `PAPERBRAIN_STATE_PATH` | `data/state.json` | Snapshot file; set empty to disable persistence |
| `PAPERBRAIN_UI_DIST_PATH` | `apps/planner-web/dist` | Built SPA served at `/` |
| `PAPERBRAIN_SEED_DEMO` | `false` | Seed demo data on first start |

## API sketch

- `POST /v1/reels`, `POST /v1/orders` — add records by hand (what the UI forms use)
- `POST /v1/reels/{id}/verify | quarantine | release` — roll lifecycle
- `POST /v1/orders/{id}/cancel` — drop an order
- `POST /v1/locations`, `POST /v1/customers` — name-based reference data (created on the fly)
- `POST /v1/planning/runs` — solve; optional `order_ids` to plan only selected orders
- `POST /v1/execution/plans/{id}/execute` — carry out a plan: consumes paper, completes orders
- `GET /v1/imports/reels/template`, `GET /v1/imports/orders/template` — CSV templates

## CSV import

Download templates from the UI ("Import Old Records") or the API:

- `GET /v1/imports/reels/template` — columns: `reel_code, material, grade, gsm, width,
  width_unit, length_mm, mass_kg, location, status, cost_per_kg, currency`
- `GET /v1/imports/orders/template` — columns: `order_number, customer, material, gsm,
  sheet_width_mm, sheet_length_mm, quantity, due_date, overrun_percent, rotation_allowed`

Notes:

- `POST /v1/imports/reels|orders` with form field `dry_run=true` validates and reports every
  row issue (error/warning) without saving.
- Widths accept `mm` or `inch` (`width_unit` column; inches are converted).
- Reel `status`: `open`/`opened`/`in use` → partly-used roll; empty or `new`/`sealed` → sealed roll.
- Importing a reel whose material (family + GSM) doesn't exist creates that material automatically.
  Orders referencing a material that doesn't exist are rejected with a row-level message.
- Imported reels start as "needs checking" and must be confirmed (UI one-click, or
  `POST /v1/reels/{id}/verify`) before planning may use them.

## Development

```bash
uv run pytest -q                                # backend test suite
cd apps/planner-web && pnpm install && pnpm dev # UI dev server at :5173, proxies /v1 to :8000
```

## Package boundaries

- `domain`: immutable business objects and value types.
- `rules`: deterministic compatibility and feasibility authority.
- `optimization`: pattern generation, objectives, heuristics, and solver adapters.
- `application`: use cases and repository ports.
- `persistence`: file-snapshot store and database mappings; no business decisions.
- `ingestion`: CSV parsing and normalization for legacy-record import.
- `api`: transport schemas and HTTP routes.

## Important MVP assumptions

- Reel length is finite and stored in millimetres.
- All lanes in one cutting pattern share one cross-cut length.
- Constant left/right edge damage is supported directly.
- Forecast demand, two-stage slitting, piecewise defects, and detailed sequencing are extension points, not silently approximated.
- Only verified, quality-released, available reels may be selected for an executable plan.
