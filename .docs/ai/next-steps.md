# Next Steps

> Short checklist of exact next actions. Updated at end of every session.

## Immediate

- [x] Phase 2.5b Slice 1 — `plan_revisions` table + PlanService
      instrumentation + retention prune + tests (commit `4ea952c`).
- [x] Phase 2.5b Slice 2 — three revision API endpoints + importer
      snapshot hook + tests (commit `39cccd1`).
- [x] Phase 2.5b Slice 3 — History sheet UI + restore confirm + tests
      (this session).
- [ ] Optional: docker-compose + browser smoke of the History flow.
      Edit a category, open History, click the just-created revision,
      confirm Restore, verify the planning page reverts and a new
      `restore` revision lands at the top of the list.

## Soon

- [x] Theming — Brainstorm + spec at
      `docs/superpowers/specs/2026-04-28-theming-design.md`.
- [x] Theming Slice 1 — Tokyo Night default + theme infrastructure
      (types, themes.ts, theme-service, themes.css, app.html
      pre-hydrate script, app.css tokenization, drift-check vitest).
- [ ] Theming Slice 2 — `/settings` page + 11 more themes + accent
      picker. Theme grid (4×3 cards with mini swatches), mode filter
      chips, 8 accent swatches per theme, live preview card. Sidebar
      gains "Settings" link. theme-service exposes `setTheme()` +
      `setAccent()` (already implemented in slice 1; just wire UI).
      Vitest cases for click-to-apply + theme list parity.
- [ ] Theming Slice 3 — polish: per-theme `--card-elevated` /
      `--surface-inset` tuning; per-theme body gradient (currently
      single hardcoded); WCAG AA contrast vitest case across every
      theme × every fg-on-bg combo; manual smoke of all 12 themes.
- [x] Phase 2.5c — Brainstorm + spec (earlier session, mockup-driven).
      Spec at `docs/superpowers/specs/2026-04-26-phase-2.5c-scenarios-design.md`.
- [x] Phase 2.5c Slice 1 — Sandbox in place. DB migration + PlanService
      scenario methods + `/ui-api/scenarios/...` routes + Sandbox mode
      on `/planning` + 21 pytest cases.
- [x] Manual smoke of 2.5c Slice 1 — green via chrome-devtools.
      Sandbox → edit Claude $200 → $250 → Commit. Active plan now
      reflects the edit; prior active is archived with attribution
      revision "Replaced by sandbox"; new active has the post-commit
      "Committed sandbox to active" revision. Zero console errors.
- [ ] Phase 2.5c Slice 2 — Saved scenarios + `/scenarios` route.
      `POST /ui-api/scenarios/{id}/save`, `/fork`. New route lists
      Saved with Open/Compare placeholders. Sandbox banner gains Save
      button → name modal. Edit-on-Saved forks into a new Sandbox.
- [ ] Phase 2.5c Slice 3 — Comparison view. `POST /ui-api/scenarios/compare`
      returns per-category rows with planned (active vs scenario),
      6-month actuals avg, variance, sparkline. Drawer shared by Sandbox
      + Saved. Sortable.
- [ ] Phase 2.5c Slice 4 — Pure projection panel on `/scenarios`
      (per-category sliders + add-line). `POST .../projection/apply-to-sandbox`
      materializes axis state into Sandbox edits.
- [ ] Phase 2.5d — Publish-to-Sheets export. Round-trip the active
      plan back into the configured Google Sheet using the importer-
      compatible 4-block layout. `.xlsx` download path for offline
      sharing.

## Deferred

- Phase 3 (analytics surfacing pages, suggested-mapping reconcile,
  configurable thresholds).
- Phase 7 (iOS / household visibility) — no movement planned.
- React-era Sonnet backlog items — re-frame against the Svelte file
  paths now that the migration has merged.
