# Phase 2.5a — Native Plan Model + Editor

**Status**: Complete (2026-04-19)
**Owner**: Claude (tier3_owner)
**Commits**: `761d387`, `121089e`, `0159407`
**Approved spec**: `/Users/tfinklea/.claude/plans/delightful-tinkering-boole.md`

## Goal

Move the canonical plan from a Google Sheet into SQLite owned by the React
UI, without rewriting the existing reconcile / summary / analytics
consumers. First of four 2.5 slices; subsequent slices add versioning,
scenarios, and publish-to-Sheets.

## What shipped

### Backend

- New SQLite tables: `plans` (id, plan_year, name, status, source,
  timestamps, source_import_id) and `plan_categories` (id, plan_id, group,
  category, block, planned, annual_target, due_month, notes, timestamps).
- Partial unique index `idx_plans_active_per_year` enforces "only one
  active plan per year" at the DB layer. Archived plans don't conflict.
- `v_latest_planned_categories` rebuilt: now reads from `plan_categories`
  joined to the active `plans` row, exposing the same column set existing
  consumers SELECT (`group_name`, `category_name`, `block`,
  `planned_milliunits`, `annual_target_milliunits`, `due_month`, plus
  audit-only columns as `NULL`). All 71 existing backend tests pass
  unchanged against the new shim.
- `PlanService` (`src/finclaide/plan_service.py`): `get_active_plan`,
  `create_category`, `update_category`, `delete_category`,
  `rename_category`. Editable-fields whitelist on update prevents
  accidental rename through the standard path. Validation for milliunits
  ≥ 0, due_month ∈ [1, 12], block ∈ {monthly, annual, one_time, stipends,
  savings}, non-empty stripped names. Duplicate (plan_id, group_name,
  category_name) caught at the DB layer and re-raised as
  `DataIntegrityError` with a human message.
- `NotFoundError` added to `errors.py`; registered as 404 handler in
  `register_error_handlers`.
- `BudgetImporter.import_budget()` mirrors into the new model inside the
  same transaction. Archives the prior active plan for the year before
  inserting the new active plan + categories.
- `Database.initialize()` calls `_hydrate_plan_from_latest_import_if_empty()`
  on every startup. Idempotent: no-op when `plans` is already populated;
  no-op when no legacy import exists. Safety net for existing
  installations upgrading past Slice 1.

### API

- `GET /api/plan/active?year=YYYY` — returns plan + categories grouped by
  block + per-block totals.
- `POST /api/plan/categories` — create row; requires plan_id in body.
- `PATCH /api/plan/categories/<id>` — update editable fields; supports a
  `rename: {group_name, category_name}` sub-block for explicit renames.
- `DELETE /api/plan/categories/<id>?plan_id=Y` — delete row.
- All four mirrored on `/ui-api/*` (same-origin + `X-Finclaide-UI: 1`
  for writes).
- `require_ui_write_request` loosened to skip the `is_json` check on
  DELETE (no body).

### Editor UI

- New `/planning` route with a "Planning" nav item (Pencil icon) between
  Transactions and Operations.
- Five block tabs (Monthly / Annual / One-time / Stipends / Savings).
  Each tab renders a `DataTable` with click-to-edit. "Add row" creates
  a category in the currently active block.
- `PlanCategorySheet` slide-out for create + edit. Native HTML5
  validation, no `react-hook-form`. Group + category name fields
  disabled in edit mode unless the "Allow renaming" checkbox is
  toggled (deliberate friction — renames break exact-match
  reconciliation).
- Delete uses an inline `Dialog` confirm.
- Mutations wired through TanStack Query with
  `invalidateQueries({queryKey: ['plan']})` and `['summary']` plus
  sonner toasts.
- Non-blocking `aria-live=polite` banner shown when status reports a
  budget import is currently running.

## Notable design decisions made during execution

- **Compatibility shim, not consumer rewrite.** The new `plan_categories`
  is read by the legacy view; `ReconciliationService`,
  `ReportService.summary`, `AnalyticsService` all kept working unchanged.
  See ADR 2026-04-19 in `decisions.md`.
- **DROP VIEW before CREATE VIEW.** Without it, `CREATE VIEW IF NOT
  EXISTS` would silently keep the old definition on existing DBs.
  Regression test `test_initialize_creates_plan_tables_and_view` asserts
  the new view body references `plan_categories` not `planned_categories`.
- **Renames gated behind a checkbox.** Both at the API layer (separate
  `rename_category` method, separate `rename` body block on PATCH) and
  in the UI (disabled inputs + opt-in checkbox). See ADR 2026-04-19.
- **Editor saves don't share `OperationLock`.** Sub-ms writes shouldn't
  block on 30-second syncs. Documented behavior; lost-edit window
  closed structurally in 2.5b. See ADR 2026-04-19.
- **`status` CHECK only allows 'active' | 'archived' for now.** 2.5b will
  rebuild the table to add 'draft' / 'scenario' — SQLite ALTER doesn't
  support modifying CHECK directly. Schema comment flags this.

## Exit criteria

- [x] React `/planning` page is the canonical editing surface for the
      plan. Saves immediately reflect in `ReportService.summary()` via
      the shim (covered by `test_existing_consumers_still_work_after_edits`).
- [x] Importer continues to work as a hydration path, replacing the
      prior active plan for the year.
- [x] All existing backend consumers (reconcile / summary / analytics)
      pass without modification.

## Verification

- Backend: `pytest` — 100/100 pass (29 new across 22 PlanService cases
  + 7 API cases).
- Frontend: `vitest run` — 19/19 pass (7 new for the planning page).
- TypeScript: `tsc --noEmit -p tsconfig.app.json` — clean.
- Manual smoke (deferred to next session): drive the editor end-to-end
  against real Docker.

## Out of scope (deferred to follow-up slices)

- 2.5b: `plan_revisions` table; rebuild `plans` to extend the `status`
  CHECK constraint with 'draft' / 'scenario'; UI for diff and restore.
- 2.5c: What-if scenarios — branchable plans referencing the active.
- 2.5d: Publish-to-Sheets round-trip into the configured Google Sheet.
- Removing the legacy `planned_groups` / `planned_categories` /
  `budget_imports` tables — they remain as audit through at least 2.5b.
- Configurable threshold extraction — Sonnet backlog item.

## Files touched

**Backend (modified):** `src/finclaide/database.py`,
`src/finclaide/budget_sheet.py`, `src/finclaide/errors.py`,
`src/finclaide/api.py`, `src/finclaide/ui_api.py`,
`src/finclaide/services.py`, `src/finclaide/app.py`.

**Backend (new):** `src/finclaide/plan_service.py`.

**Tests (new):** `tests/test_plan_service.py`. Extensions to
`tests/test_api.py`.

**Frontend (modified):** `frontend/src/lib/api.ts`,
`frontend/src/App.tsx`.

**Frontend (new):** `frontend/src/pages/planning-page.tsx`,
`frontend/src/components/plan-category-sheet.tsx`,
`frontend/src/pages/planning-page.test.tsx`.
