# Finclaide Roadmap

Finclaide is evolving into a polished private household finance OS. The product stays dashboard-first, keeps YNAB as the source of truth for actuals, keeps the spreadsheet as the source of truth for baseline planning, and uses AI as a strong assistant rather than an autonomous operator.

## Product Direction

- Primary users: the operator plus the household.
- Distribution: private tool, not a public SaaS.
- Core surfaces: web dashboard first, MCP second, read-first iOS companion later.
- Product priorities: trustworthy data flow first, better decisions second, breadth later.
- Planning source: spreadsheet remains canonical, but import should become automatic through Google Sheets sync.

## Phase 1: Trusted Core Data Flow (active, rescoped 2026-04-18)

Goal: make import, sync, and reconcile diagnosable from the dashboard alone.
The plumbing exists; the visibility does not.

- Surface failure causes for import, sync, and reconcile in the dashboard
  (no JSON spelunking).
- Add a deterministic `/api/reconcile/preview` that classifies every planned
  category against YNAB (exact-match / missing-in-YNAB / extra-in-YNAB)
  without mutating data and without fuzzy matching.
- Add a plan-staleness UX (header freshness chip + banner when scheduled
  refresh skipped or failed its last cycle).
- Add a run-detail view (`/api/runs/{id}` + `/operations/runs/:id` page) that
  renders the full `details_json` as a structured card.
- Add frontend baseline tests for the transactions page and a header/nav a11y
  smoke test.

Exit criteria:

- A failing import / sync / reconcile is diagnosable from the UI alone.
- A missed scheduled refresh is impossible to overlook.
- Reconcile failures route through the preview view so the user knows which
  categories drifted before re-running.

## Phase 2: Continuous Planning Ingestion (substantially shipped — sweep)

Goal: remove manual spreadsheet download and refresh friction.

Already shipped: Google Sheets import via Drive service account, remote URL
import, scheduled refresh thread with bootstrap-on-start, run history with
status, freshness scoring on `/api/status`.

Remaining sweep:

- Add failure-mode tests for `ScheduledRefreshService` (operation lock skip,
  reconcile-failure recording, bootstrap respects prior success).
- Make scheduled-refresh `last_status` and `next_run_at` more prominent in
  the dashboard.

Exit criteria:

- Scheduled refresh is fully covered by deterministic tests.
- The operator can see the next scheduled run without leaving Operations.

## Phase 2.5: Native Planning Surface (NEW — added 2026-04-18)

Goal: replace the spreadsheet as the canonical planning surface. The React UI
becomes the editing surface; SQLite owns plan state; Google Sheets becomes a
read-only artifact written by the app on demand.

- Introduce a SQLite plan model (`plans`, `plan_categories`, plan-version
  snapshots) and a `PlanService` that abstracts read / write / branch /
  commit / publish. Importer continues to hydrate the new model so the
  spreadsheet stays a valid migration path.
- Editor surfaces in the React UI for every block the workbook supports
  (monthly, annual, one-time, stipends, savings) with first-class fields for
  group, category, planned amount, annual target, due month, and notes.
- What-if scenarios: branch off the active plan, edit, compare projected
  variance vs current actuals, then commit or discard.
- Versioning & rollback: every save produces a snapshot diffable and
  restorable from the UI.
- Publish-to-Sheets export: writes the current plan back into the configured
  Google Sheet using the existing layout, plus an `.xlsx` download path for
  offline sharing.
- One-shot migration that takes the latest workbook import and hydrates the
  new model as the active plan.

Exit criteria:

- The operator never opens Google Sheets to edit the plan.
- A plan change in the UI is reflected in the next reconcile + summary
  without any manual import step.
- Sheet exports remain readable by non-app users (household members,
  accountant) and round-trip back into the importer if needed.

## Phase 3: Decision Engine V1

Goal: make the app better at answering what changed and what needs attention now.

- Deepen plan-vs-actual reporting and overage watch.
- Improve anomaly explanations so unusual spend is easier to understand.
- Make trend reporting more useful for current-month and recent-history decisions.
- Keep recommendations human-readable and grounded in returned data.

Exit criteria:

- Weekly review reliably identifies spending shifts, overages, and outliers.
- The app explains why something is risky, not just that it is risky.

## Phase 4: Cash Flow and Forecasting

Goal: add forward-looking awareness without changing the source-of-truth model.

- Add timing-aware cash flow and monthly pressure forecasts.
- Model upcoming obligations and remaining-month runway.
- Detect unrealistic budgets where the current plan is unlikely to hold.
- Tie forecast risk back to concrete categories and obligations.

Exit criteria:

- The app can answer whether the current month and near-term plan are realistic.
- Forecast views are actionable enough to influence weekly and monthly decisions.

## Phase 5: Goals and Savings Planning

Goal: connect present spending to future household priorities.

- Add sinking-fund and savings-goal visibility.
- Show tradeoffs between current overspend and future goals.
- Expand recommendations to include goal pressure and reallocation suggestions.
- Make annual targets, savings categories, and household priorities visible in one planning view.

Exit criteria:

- The operator can see how overspending affects goals and savings plans.
- Goals and savings become part of the main planning workflow, not separate tracking.

## Phase 6: Operational Review Workflows

Goal: turn the app from a report viewer into a repeatable finance operating system.

- Add guided weekly review and monthly planning flows.
- Add issue queues for stale data, overspending, forecast risk, and reconciliation problems.
- Track recommendation status and review completion.
- Make review output concise enough to share with the household.

Exit criteria:

- Weekly and monthly reviews are structured workflows rather than ad hoc exploration.
- The app produces a clear list of what needs attention and what was resolved.

## Phase 7: Household Visibility and iOS Companion

Goal: expand from single-operator usage to shared household visibility.

- Add read-first household views with simpler summaries and status screens.
- Build iOS around health, alerts, summaries, goals, and review outcomes.
- Keep edit-heavy planning and operations centered in the web dashboard.
- Support lightweight household visibility without introducing public-SaaS complexity.

Exit criteria:

- Household members can understand current status and upcoming issues without using the desktop dashboard.
- Mobile is useful daily without becoming the primary editing surface.

## Phase 8: Human-Led AI Copilot

Goal: make AI an integrated advisor across dashboard, API, and MCP workflows.

- Unify review summaries, recommendations, and explanations into a consistent AI layer.
- Add proactive but non-autonomous check-ins for health, forecast risk, and goals pressure.
- Make MCP workflows reflect the same review and recommendation model as the dashboard.
- Keep all execution user-approved; AI should recommend, explain, and prepare, not silently act.

Exit criteria:

- AI reduces review time and improves decision quality without reducing operator control.
- Dashboard and MCP experiences feel like two surfaces on the same finance operating system.

## Cross-Cutting Requirements

- Do not weaken strict data integrity or exact-match reconciliation.
- Keep APIs machine-friendly and stable.
- Prefer behavior-level tests over manual validation.
- Treat freshness, provenance, and failure visibility as product features, not internal plumbing.
- Avoid public-SaaS concerns such as self-serve onboarding, billing, and multi-tenant auth unless roadmap direction changes.
