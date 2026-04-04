# Decisions

> Architecture decision records. Append-only — one entry per decision.

## [2026-04-04] Tiered backlog with Codex as tier3_owner

**Context**: Setting up standardized AI handoff docs across repos.
**Decision**: Codex owns Tier 3 (Opus-level) backlog items for this repo. Claude and other agents work Haiku and Sonnet tiers.
**Rationale**: Codex is the primary architect for finclaide. Tier 3 items (tests, API design, complex refactors) need architectural continuity.
