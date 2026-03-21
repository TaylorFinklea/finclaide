# Finclaide Roadmap

Finclaide is evolving into a polished private household finance OS. The product stays dashboard-first, keeps YNAB as the source of truth for actuals, keeps the spreadsheet as the source of truth for baseline planning, and uses AI as a strong assistant rather than an autonomous operator.

## Product Direction

- Primary users: the operator plus the household.
- Distribution: private tool, not a public SaaS.
- Core surfaces: web dashboard first, MCP second, read-first iOS companion later.
- Product priorities: trustworthy data flow first, better decisions second, breadth later.
- Planning source: spreadsheet remains canonical, but import should become automatic through Google Sheets sync.

## Phase 1: Trusted Core Data Flow

Goal: make import, sync, and reconcile dependable every week.

- Harden workbook parsing against real layout variants while keeping deterministic validation.
- Improve operation state visibility so failures are explicit and actionable.
- Expand regression coverage around importer edge cases, stale data, and reconciliation failures.
- Make freshness and provenance visible in the dashboard and API responses.

Exit criteria:

- Import, sync, and reconcile failures are diagnosable from the app without reading code.
- Real-world workbook variants are covered by deterministic tests.
- Core weekly workflow is stable enough to trust as an operating tool.

## Phase 2: Continuous Planning Ingestion

Goal: remove manual spreadsheet download and refresh friction.

- Add automatic Google Sheets import while preserving workbook-compatible parsing semantics.
- Add scheduled import, sync, and reconcile jobs with operation history.
- Surface freshness, last-run outcome, and stale-data warnings in the UI and API.
- Keep explicit provenance for every plan snapshot and actuals sync.

Exit criteria:

- The operator no longer needs to manually download the planning sheet for normal use.
- The app can tell whether plan data or YNAB actuals are stale at a glance.

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
