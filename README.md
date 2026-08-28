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
- SQLAlchemy persistence models and an initial SQL migration;
- unit, property, and optimization test specifications.

The API uses in-memory repositories by default so the domain and optimizer can be exercised before database integration is enabled. Production deployment must use the database-backed ports, transactional event/outbox persistence, authentication, and approval controls described in `plan.md`.

No plan is releasable merely because a solver produced it. `PlanValidator` must independently validate all geometry, material, machine, quantity, length, and inventory constraints against the same immutable planning snapshot.

## Package boundaries

- `domain`: immutable business objects and value types.
- `rules`: deterministic compatibility and feasibility authority.
- `optimization`: pattern generation, objectives, heuristics, and solver adapters.
- `application`: use cases and repository ports.
- `persistence`: database mappings; no business decisions.
- `api`: transport schemas and HTTP routes.

## Important MVP assumptions

- Reel length is finite and stored in millimetres.
- All lanes in one cutting pattern share one cross-cut length.
- Constant left/right edge damage is supported directly.
- Forecast demand, two-stage slitting, piecewise defects, and detailed sequencing are extension points, not silently approximated.
- Only verified, quality-released, available reels may be selected for an executable plan.
