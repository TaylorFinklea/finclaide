# Decisions

> Architecture decision records. Append-only — one entry per decision.

## [2026-04-04] Tiered backlog with Codex as tier3_owner

**Context**: Setting up standardized AI handoff docs across repos.
**Decision**: Codex owns Tier 3 (Opus-level) backlog items for this repo. Claude and other agents work Haiku and Sonnet tiers.
**Rationale**: Codex is the primary architect for finclaide. Tier 3 items (tests, API design, complex refactors) need architectural continuity.

## [2026-04-18] Tier 3 owner shifts to Claude

**Context**: Operator brought Claude in to plan and execute the next phase
directly, rather than handing architectural work to Codex.
**Decision**: `tier3_owner` in `.docs/ai/roadmap.md` is now `claude`. Claude
may execute Opus-tier work using the phase-execution protocol; Codex remains
welcome to pick up Haiku/Sonnet items in parallel.
**Rationale**: Continuity of architectural intent matters more than tool
identity. Operator is currently routing planning sessions through Claude, so
Claude must be the one accountable for design decisions and migrations.

## [2026-04-18] Phase 1 rescoped, not restarted

**Context**: Phase 1 ("Trusted Core Data Flow") looked ~80% shipped on
inspection — reconcile, scheduled refresh, run history, freshness scoring all
exist. But weekly-use pain remains around failure visibility and reconcile
diagnosability.
**Decision**: Keep Phase 1 active, but redefine its scope to the concrete
visibility gaps still felt in real use (failure-cause card, reconcile
preview, plan-staleness UX, run-detail view, FE test baseline). Phase 2 is
also largely shipped and shrinks to a sweep task.
**Rationale**: Restarting Phase 1 would imply distrust of the existing
import/sync/reconcile core, which is not warranted. Closing the visibility
gaps is the smaller, higher-leverage move.

## [2026-04-18] In-app planning becomes canonical; Sheets is an artifact

**Context**: The `2026 Budget` sheet is the canonical plan today. Operator
flagged the spreadsheet as a friction point ("we need something better than
a Google Sheet for planning").
**Decision**: Inserts a new Phase 2.5 ("Native Planning Surface") between
Phases 2 and 3. After 2.5 ships, the React UI is the canonical editing
surface for the plan; SQLite owns plan state; Google Sheets becomes a
read-only export artifact written from the app on demand.
**Rationale**: Spreadsheets are a poor decision-support surface (no
versioning, no scenario branching, no integration with actuals). Moving the
plan in-app unlocks what-if scenarios, plan rollback, and tighter
plan-vs-actual loops, while preserving Sheets as the household-readable
export. Importer remains as a one-way migration path.
**Constraint**: Strict data integrity and exact-match reconciliation are not
weakened — the new model still validates totals and treats plan edits as
discrete versioned snapshots.

## [2026-04-18] Reconcile preview filters hidden + deleted YNAB rows

**Context**: When implementing `/api/reconcile/preview` we needed a rule for
which YNAB categories count as "extra in YNAB". YNAB exposes an Internal
Master Category group (Inflow: Ready to Assign, etc.) and users can hide
old categories.
**Decision**: Filter to `categories.hidden = 0 AND categories.deleted = 0
AND category_groups.hidden = 0 AND category_groups.deleted = 0`. No
hard-coded name list.
**Rationale**: Hidden=true is YNAB's universal "don't show me this" signal
and naturally excludes the Internal Master Category group. Hard-coding
group names would drift if YNAB changes its conventions. Trade-off: Credit
Card Payments categories (which are not hidden) will show up as
"extra_in_ynab" if the user doesn't plan them; if this becomes noisy, we
revisit.

## [2026-04-18] Failure-cause card is read-only on Overview, retry-enabled on Operations

**Context**: Phase 1 needed failure visibility on both Overview (the
default landing page) and Operations (the control panel).
**Decision**: One reusable `FailureCauseCard` component that renders on
both surfaces. On Operations it accepts an `onRetry` handler and renders
Retry buttons; on Overview the prop is omitted, leaving only the "Open
run" deep link.
**Rationale**: Keeps mutation logic on the page that owns the operation
mutations (Operations). Overview stays a "what's going on" surface rather
than gaining a parallel control panel. Single component, no duplication.

## [2026-04-19] Plan model lives alongside legacy tables; view is the seam

**Context**: Phase 2.5a moves the canonical plan from a Google Sheet into
SQLite. Multiple existing consumers (`ReconciliationService`,
`ReportService.summary`, `AnalyticsService.year_end_projection`) read plan
data via `v_latest_planned_categories`. Rewriting all of them at once was
not warranted for the smallest coherent slice.
**Decision**: New `plans` + `plan_categories` tables added alongside the
existing `planned_groups` / `planned_categories`. The view is rebuilt to
read from the active plan, returning the same column shape consumers
expect. Importer keeps writing the legacy tables (audit) and now also
mirrors into the new model.
**Rationale**: Single seam to migrate. Existing 71 backend tests pass
unchanged after the schema swap, proving the shim is correct. Lets future
slices (2.5b/c/d) replace consumers piecemeal without an
all-at-once rewrite.
**Critical detail**: `CREATE VIEW IF NOT EXISTS` is sticky in SQLite, so
the schema script must `DROP VIEW IF EXISTS v_latest_planned_categories`
before the new `CREATE VIEW`, or upgrades silently keep the old
definition.

## [2026-04-19] Renames are gated behind an opt-in checkbox

**Context**: The plan editor lets users edit category rows. A rename of
group_name or category_name immediately breaks reconciliation (which is
exact-match against YNAB).
**Decision**: Group and category name fields are disabled in the edit
Sheet by default. A checkbox labeled "Allow renaming group / category
(breaks reconciliation until YNAB matches)" enables them. The API
mirrors this — the standard `update_category` whitelist excludes the name
fields; renames must come through `rename_category` (exposed as a
`rename: { group_name, category_name }` sub-block on PATCH).
**Rationale**: Keeps the common case (adjust planned amount, notes) safe
from accidental reconciliation breakage while still supporting the
deliberate rename workflow. Two-tier API contract makes the intent
auditable in run history.

## [2026-04-19] Editor saves do not share OperationLock

**Context**: `OperationLock` is a single global mutex held during budget
import / YNAB sync / reconcile (typically 30+ seconds for sync). Editor
saves are sub-millisecond SQLite writes.
**Decision**: `PlanService` does not acquire the operation lock. Editor
saves can land during a long sync without contention. SQLite serializes
the writes at the connection level, so the result is consistent (no torn
rows). When `status.busy && current_operation === 'budget_import'` the
planning page renders a non-blocking `aria-live=polite` banner warning
that saved edits may be overwritten.
**Rationale**: Blocking editor saves on a 30-second sync would feel
broken. The lost-edit window is bounded by the importer's transaction
length and addressed structurally in 2.5b (versioning).

## [2026-04-18] Reconcile diagnostics: deterministic preview now, suggestions later

**Context**: Operator wants reconcile failures easier to diagnose without
weakening exact-match.
**Decision**: Phase 1 ships a deterministic `/api/reconcile/preview` (no
mutations, no fuzzy matching) that classifies each planned name as
exact-match / missing-in-YNAB / extra-in-YNAB. Phase 3 adds ranked rename
suggestions, still requiring explicit user confirmation before any rename is
applied.
**Rationale**: Splits the work to deliver the diagnostic value immediately
without coupling it to the harder problem of safe candidate ranking. Keeps
the integrity rule that no fuzzy matching ever runs silently.

## [2026-04-23] Flask frontend proxy requests identity-encoded assets

**Context**: Docker smoke of the Svelte migration showed a blank page in
Chrome. The browser requested `Accept-Encoding: gzip, deflate, br, zstd`;
SvelteKit returned compressed JavaScript; the Flask proxy stripped
`Content-Encoding` while returning bytes that were still compressed. Chrome
then parsed compressed bytes as JavaScript and aborted module loading.
**Decision**: The Flask reverse proxy forces `Accept-Encoding: identity`
for upstream requests to the SvelteKit container.
**Rationale**: The proxy returns `upstream_response.content` and filters
encoding headers, so the safest contract is to avoid upstream compression at
this hop. This keeps static assets usable for browsers without relying on
optional httpx decoder support for every encoding Chrome advertises.
