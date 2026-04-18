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
