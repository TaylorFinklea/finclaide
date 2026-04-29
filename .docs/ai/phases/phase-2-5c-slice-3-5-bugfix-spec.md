# Phase 2.5c Slice 3.5 — Post-Slice-3 smoke bug fixes (spec)

**Status**: Done — shipped 2026-04-29
**Owner**: implementation agent (Sonnet for Issue 2, Haiku acceptable for Issues 1+3)
**Depends on**: Phase 2.5c Slice 2 (b23ba2b) and Slice 3 (b083058) — both shipped on `main` 2026-04-29
**Blocks**: nothing. Slice 4 (projection panel) remains deferred independently.

## Product Overview

A small, slice-shaped follow-up that closes three cosmetic gaps surfaced by today's manual Playwright smoke of Phase 2.5c Slices 2 + 3. All five smoke flows passed functionally; this slice ties off the rough edges so the operator's first impression of the new Saved-scenarios + Comparison surface matches the polish elsewhere in the app. No schema delta, no API change, no roadmap movement — just bug fixes plus one small auto-park redirect-with-id improvement so users land directly inside the forked sandbox after Save&open / Discard&open.

## Current State

- `frontend/src/routes/scenarios/+page.svelte` — Saved Scenarios route shipped in Slice 2. Auto-park modal at lines 274–332 calls `saveScenario` then `forkScenario` then `goto(withBasePath('/planning'))` (lines 128–185). The new sandbox id returned by `forkScenario` is **discarded** before `goto`. Make-active confirm at lines 335–376 has the multi-line `DialogDescription` body that renders a literal newline (lines 350–354). Delete confirm at lines 384–426 has a single-line description and is fine; auto-park modal description (lines 290–294) is multi-line but reads as a paragraph after collapse — verify in the smoke step.
- `frontend/src/routes/planning/+page.svelte` — Sandbox banner copy at lines 274–276 always renders the generic `"Edits go to a scenario, not the active plan. Commit to make it live, or discard to throw it away."` and the muted-text subtitle at lines 333–337 always renders `"Sandboxed edits will not affect your active plan until you commit."` There is **no** `displayedPlan.plan.label !== null` branch in the file today; the variant the user expected was never wired up. The `viewedScenarioId` `$state` at line 89 is local-only and starts as `null` on every mount — there is no query-param plumbing.
- `frontend/src/lib/api.ts` — `forkScenario` at lines 606–619 already returns `ActivePlanResponse` whose `plan.id` is the new sandbox id. No API change is needed for any option below.
- `frontend/src/test/setup.ts` — already mocks `$app/stores` with `setMockPage` (lines 27–29), `$app/navigation.goto` (lines 61–62). The vitest harness can drive both query-param page state and assert on `goto(...)` calls.
- Existing tests: `frontend/src/routes/scenarios/page.test.ts` (8 cases, all passing) and `frontend/src/routes/planning/page.test.ts` (planning + sandbox flow). Backend `pytest` suite is green at b083058.

Recent commits for context:
```
b083058 Add Phase 2.5c Slice 3: Comparison view with per-category drilldown + 6-month actuals
b23ba2b Add Phase 2.5c Slice 2: Saved scenarios + /scenarios route + auto-park flow
```

## Locked Decisions

### Issue 1 — Saved-fork banner subtitle: pick **A (drop the dead variant)**

The codebase does not currently contain a `displayedPlan.plan.label !== null` branch — the variant was scoped but never landed. Options:

- **A. Don't add the variant. Leave the banner generic and write the decision down.** Cheap; preserves the slice's "bug fix only" shape; matches what the operator already sees. Lineage was never persisted on the sandbox row anyway, so even if we wanted to render `forked from 'Smoke A'` we have nothing to read.
- **B. Persist `source_plan_id` on `plans` when `fork_scenario` creates a sandbox.** Schema delta, migration, `PlanService.fork` change, banner update. Real lineage value for future projection→sandbox apply (Slice 4 ish), but pulls in scope this slice should not absorb.

**Locked: A.** Rationale: the slice is a bugfix tie-off. The operator does not lose information — they see "Sandbox mode" plus the plan label in the title (`Planning — 2026 Budget (sandbox)`), and they always know which saved scenario they opened because they just clicked Open on it. Lineage-on-disk pairs better with Slice 4's projection→sandbox flow; capture the want there, not here. Recorded under "Out of scope / future" below.

### Issue 2 — Auto-park redirect lands without the new sandbox id: pick **C (query string)**

The user's hand-off framing in priority order: C, D, E. C is the cleanest — query strings are SvelteKit-native, no new module-level store, deeplinks become possible.

- **C. `goto('/planning?scenario=<id>')`; `/planning` reads `$page.url.searchParams.get('scenario')` in an `$effect` and sets `viewedScenarioId`.** Bonus: `/planning?scenario=N` becomes a valid deeplink for any future "share a sandbox view" need. No new dependencies; the test harness already supports `setMockPage({ url: ... })`.
- D. Module-level writable store. Hidden state machine; no deeplink win.
- E. Auto-enter most-recent sandbox. Action-at-a-distance: a user navigating to `/planning` after the smoke flow would jump into a sandbox they didn't open.

**Locked: C.** Implementation guard rails in §Implementation Plan below ensure the param is consumed once and validated against the scenarios list (so an invalid or stale id is silently ignored, not exploded).

### Issue 3 — Multi-line dialog copy: collapse to single-line strings

Cheapest, safest, no CSS rule needed. Find every `DialogDescription` body that spans multiple Svelte template lines via indentation and collapse to a single line. Verified via grep before writing. The render harness will surface any regression.

## Implementation Plan

### Step 1 — Issue 3: collapse multi-line dialog copy (Haiku-friendly)

In `frontend/src/routes/scenarios/+page.svelte`:

1. Lines 350–354 ("Make active" confirm description) — collapse to a single line:
   ```svelte
   <DialogDescription>
     Replaces your active plan with this scenario. The previous active plan is archived and remains accessible from History (where you can restore it).
   </DialogDescription>
   ```
2. Lines 290–294 (auto-park modal description) — same treatment, collapse to one line. The current text is acceptable as-is content-wise.
3. Lines 400–402 (Delete confirm) — already a single line, leave alone.

Then grep the rest of the routes for the same antipattern in other dialogs:

```
grep -rn "<DialogDescription>" frontend/src/ | xargs -I{} ...
```

Targets to inspect: `frontend/src/routes/planning/+page.svelte` lines 430–433 (Discard sandbox), 463–467 (Save scenario), 517–521 (Commit sandbox to active). Collapse any that are multi-line into single-line bodies. Do not change the wording — only the whitespace.

This is mechanical. No tests change.

### Step 2 — Issue 2: auto-park redirect with new sandbox id (Sonnet)

#### 2a. Update the three `goto` call sites in `frontend/src/routes/scenarios/+page.svelte`

Three places construct `goto(withBasePath('/planning'))`:

- Line 63: `forkMutation.onSuccess` (direct fork, no sandbox-park needed). The mutation receives the response — change the handler to read `response.plan.id` and append `?scenario=<id>`.
- Line 151: `handleSaveAndOpen` after the second `forkScenario(target.id)` resolves. Capture the response from `forkScenario` (currently discarded) and use its `plan.id`.
- Line 178: `handleDiscardAndOpen` after `forkScenario(parkingFor.id)` resolves. Same treatment.

Concrete deltas:

```ts
// Line 59-66
const forkMutation = createMutation({
  mutationFn: (saved_id: number) => forkScenario(saved_id),
  onSuccess: async (response) => {
    await invalidate()
    goto(withBasePath(`/planning?scenario=${response.plan.id}`))
  },
  onError: (error) => toast.error(getErrorMessage(error)),
})
```

```ts
// Inside handleSaveAndOpen, replacing the discarded fork call ~line 147
try {
  const forked = await forkScenario(target.id)
  parkingFor = null
  parkBusy = false
  await invalidate()
  goto(withBasePath(`/planning?scenario=${forked.plan.id}`))
} catch (error) { ... unchanged ... }
```

```ts
// Inside handleDiscardAndOpen, replacing the discarded fork call ~line 174
try {
  const forked = await forkScenario(parkingFor.id)
  parkingFor = null
  parkBusy = false
  await invalidate()
  goto(withBasePath(`/planning?scenario=${forked.plan.id}`))
} catch (error) { ... unchanged ... }
```

Use a string-template literal — a `URLSearchParams` round-trip is overkill for one numeric param. Do not encode the id; it's an integer.

#### 2b. Consume `?scenario=<id>` in `frontend/src/routes/planning/+page.svelte`

1. Add the import alongside the existing `$app/environment` import at line 2:
   ```ts
   import { page } from '$app/stores'
   ```
2. After the `viewedScenarioId` declaration (line 89) and after the `scenariosQuery` line (~line 87), add an `$effect` that reads the search param and applies it once per URL:
   ```ts
   let consumedScenarioParam: string | null = $state(null)
   $effect(() => {
     const raw = $page.url.searchParams.get('scenario')
     if (raw === null) {
       consumedScenarioParam = null
       return
     }
     // Idempotency: only act on a given param value once. Re-runs of the
     // effect (e.g. scenariosQuery refetch) must not re-enter sandbox mode
     // after the user explicitly discarded or committed it.
     if (consumedScenarioParam === raw) return
     consumedScenarioParam = raw
     const id = Number.parseInt(raw, 10)
     if (!Number.isFinite(id) || id <= 0) return
     // Validate: only accept ids that the scenarios list confirms are
     // unnamed sandboxes (label === null). A stale id from an old link
     // is silently ignored.
     const list = $scenariosQuery.data?.scenarios ?? []
     const match = list.find((s) => s.id === id && s.label === null)
     if (!match) return
     viewedScenarioId = id
   })
   ```

   **Why the idempotency guard**: the effect re-runs whenever `$scenariosQuery.data` updates. After the user clicks Discard, `viewedScenarioId` resets to `null` — without the guard, the next refetch would re-enter sandbox mode on the same URL. The guard ties consumption to the literal string value of the param; if the user navigates back to the same URL, that's a fresh page mount and the guard resets.

   **Why the `label === null` validation**: only the unnamed sandbox row is openable as `viewedScenarioId`. A saved (`label !== null`) id navigated to via `?scenario=N` should not auto-enter sandbox mode — the user opens those via the Open button, not via direct deeplink (yet).

3. After successfully consuming the param, the URL still says `?scenario=<id>`. Optional polish: replace the URL with the bare path so a refresh doesn't re-bind. Decision: **do not** strip the param. Reason: refresh-as-resume is a feature here — if the operator hard-refreshes, they expect to land back on the sandbox. The idempotency guard prevents the re-enter-after-discard issue without needing to mutate the URL. Document this in a code comment alongside the effect.

#### 2c. Smoke and self-check

The Playwright smoke flow becomes:

1. From `/scenarios`, with no sandbox: click Open on a saved row → page goes to `/planning?scenario=<n>` → sandbox banner is visible immediately, no Continue-sandbox button.
2. From `/scenarios`, with a sandbox: click Open → auto-park modal → Save&open → page goes to `/planning?scenario=<n2>` → sandbox banner visible immediately, plan label matches.
3. From `/planning?scenario=<id>` directly (refresh): sandbox banner visible immediately on mount.

### Step 3 — Tests (Sonnet, paired with Step 2)

Add to `frontend/src/routes/scenarios/page.test.ts`:

- New test: `'Save & open redirects to /planning with the new sandbox id'`. Set `apiMocks.forkScenario.mockResolvedValue({ ...FORKED_PLAN, plan: { ...FORKED_PLAN.plan, id: 200 } })`. After Save&open, assert `navMocks.goto` was called with a path matching `/planning?scenario=200`.
- New test: `'Discard & open redirects to /planning with the new sandbox id'`. Same shape, via the Discard path.
- New test: `'direct Open without a sandbox redirects with the new id'`. Cover the `forkMutation.onSuccess` path.

Update existing test `'Save & open chains saveScenario then forkScenario in order'` (lines 109–138) to also assert the redirect URL pattern, since the original test only asserted invocation order.

Add to `frontend/src/routes/planning/page.test.ts`:

- New test: `'enters sandbox mode when ?scenario=<id> matches an unnamed sandbox'`. Use `setMockPage({ url: new URL('http://localhost/planning?scenario=99') })` before render. Mock `apiMocks.listScenarios` to return `[{ id: 99, label: null, ... }]` and `apiMocks.getScenario` to return a sandbox plan fixture. Assert the sandbox banner ("Sandbox mode" CardTitle from line 273) is present.
- New test: `'ignores ?scenario=<id> when the id is not an unnamed sandbox'`. Mock listScenarios with only saved scenarios. Assert the active-plan view renders (no sandbox banner).
- New test: `'does not re-enter sandbox after discard while ?scenario=<id> is still in the URL'`. After discard mutation succeeds, assert the banner disappears and stays gone after the scenarios query refetches.

Use `setMockPage` from `frontend/src/test/setup.ts`. The harness already exports `resetMockPage`, called by `renderPage`, so each test starts with a clean URL.

### Step 4 — Issue 1: lock the decision in code via a one-line comment

Drop a one-line comment near the sandbox subtitle (line 333–337 area) noting that the lineage-aware copy is intentionally deferred:

```svelte
<!-- Sandbox banner subtitle is intentionally generic. Lineage (e.g.
     "forked from 'Smoke A'") would require persisting source_plan_id on
     plans rows; deferred to a future slice that needs lineage anyway. -->
```

No code change beyond the comment. This is the visible record of the locked decision so a future reader doesn't re-derive it.

## Interfaces and Data Flow

- New URL contract: `/planning?scenario=<integer>` is now an officially supported entry point. When the param matches an unnamed sandbox row in the user's scenarios list, the page mounts directly into sandbox view. When it doesn't match, the param is ignored and the active plan view renders.
- No backend changes.
- No `/api/*` or `/ui-api/*` changes.
- No schema delta. `plans.source_plan_id` is **not** introduced this slice (see Out of Scope).
- No new exported function from `$lib/api`. Existing `forkScenario` already returns the needed `plan.id`.

## Edge Cases and Failure Modes

- **Stale deeplink to a deleted sandbox.** `?scenario=<id>` where the row no longer exists: validation in step 2b filters by `id === param && label === null`; missing match silently falls through to active-plan view. No error toast — a stale URL should not yell at the user.
- **Param refers to a saved (`label !== null`) scenario id.** Same fall-through behavior. The Open button on `/scenarios` is still the canonical entry point for saved scenarios; we do not auto-fork on direct deeplink in this slice.
- **Param refers to a non-numeric or negative id.** `Number.parseInt(...)` produces `NaN` or negative; `Number.isFinite && id > 0` filters both.
- **Race: user lands on `/planning?scenario=N` before scenariosQuery resolves.** The effect re-runs when `$scenariosQuery.data` populates; first run sees `list` empty and falls through; second run finds the match and sets `viewedScenarioId`. Idempotency guard tied to the string param value handles this — the second consumption is allowed because `consumedScenarioParam` was never updated past null on the first run (we move `consumedScenarioParam = raw` *before* the validation, so re-runs after discard skip; but the first run with empty list also moves it). **Refinement:** move the `consumedScenarioParam = raw` write to after the validation passes (i.e. inside the `if (match)` branch). This way an early-render run with empty scenarios list doesn't burn the guard.

  Final shape:
  ```ts
  $effect(() => {
    const raw = $page.url.searchParams.get('scenario')
    if (raw === null) { consumedScenarioParam = null; return }
    if (consumedScenarioParam === raw) return
    const id = Number.parseInt(raw, 10)
    if (!Number.isFinite(id) || id <= 0) return
    const list = $scenariosQuery.data?.scenarios ?? []
    const match = list.find((s) => s.id === id && s.label === null)
    if (!match) return
    consumedScenarioParam = raw
    viewedScenarioId = id
  })
  ```
  This is the version to ship. Add a test that proves the race-then-resolve case (start with empty scenarios list, then update the mock and re-render — assert sandbox banner appears).

- **User navigates `/planning` → discards sandbox → refreshes.** Refresh re-runs the effect; the URL no longer has `?scenario=<id>` (the user discarded; we leave the URL alone, but note: the discard mutation does NOT mutate the URL today). If the URL still has the param, the validation finds no unnamed sandbox with that id (it was discarded) → fall through → active view. Guarded.

- **`/planning?scenario=<id>` deeplink while a different sandbox already exists.** Theoretically only one unnamed sandbox can exist per plan year (partial-unique index in 2.5c-1). The effect resolves to that one sandbox by id; if id matches, we open it; if not, we fall through. Operator can still open the existing sandbox via Continue-sandbox.

- **Multi-line copy on a dialog that legitimately needs paragraphs.** Not present today, but if a future dialog wants two paragraphs, it should use two `<p>` children inside `DialogDescription` rather than relying on whitespace preservation.

## Test Plan

Backend: no changes to backend code, so no new pytest cases. Run `make test` to confirm no regression.

Frontend:
```bash
cd frontend
npm run check
npx vitest run
```

Acceptance criteria:
- All existing scenarios + planning tests still pass.
- Three new scenarios tests assert `goto` is called with `/planning?scenario=<id>` for each redirect path.
- Three new planning tests assert the URL-driven sandbox-entry behavior, including the race-then-resolve case and the "ignore stale id" case.
- `npm run check` (svelte-check) reports zero new errors.

Manual smoke (rerun the same Playwright flow Taylor and I just ran):
1. Boot stack (`docker compose up --build -d`), seed the active plan.
2. Open `/scenarios`. Open a saved scenario (no sandbox present): browser URL becomes `/planning?scenario=<n>`, sandbox banner is immediately visible.
3. Make an edit, return to `/scenarios`, click Open on a different saved row: auto-park modal appears.
4. Save&open with a fresh label: URL becomes `/planning?scenario=<m>`, banner visible immediately, plan title shows the right plan label, and the previously-edited row was saved (visible from `/scenarios` after navigating back).
5. Discard the new sandbox; refresh `/planning?scenario=<m>` (the URL still has the param). Page renders the active plan view without flashing into sandbox mode.
6. Confirm Make active dialog text is one continuous paragraph (no mid-paragraph linebreak).

## Handoff

- **Recommended tier**: split. Issue 1 (one-line comment) and Issue 3 (whitespace collapse) are appropriate for the **mechanical / Haiku** tier. Issue 2 (auto-park redirect with id, $effect with race + idempotency, three vitest cases) needs **Sonnet medium reasoning** — there's bounded judgment around the effect ordering and the validation predicate. If running as one pass, Sonnet handles all three; if splitting commits, do Issues 1+3 first as a single small commit (~10 LOC) and Issue 2 as a second commit (~50 LOC + tests).
- **Files likely touched**:
  - `frontend/src/routes/scenarios/+page.svelte` — three goto sites, one DialogDescription whitespace collapse.
  - `frontend/src/routes/planning/+page.svelte` — one new import, one `$effect`, one `$state`, optional comment near subtitle, possibly DialogDescription whitespace collapses.
  - `frontend/src/routes/scenarios/page.test.ts` — three new cases, one updated case.
  - `frontend/src/routes/planning/page.test.ts` — three new cases.
- **Constraints**:
  - Do not introduce new exports from `$lib/api`.
  - Do not strip the `?scenario=<id>` param from the URL after consumption — refresh-as-resume is intentional.
  - Do not auto-fork on direct deeplink to a saved (label !== null) scenario id — that's a separate UX decision and not in scope.
  - Keep the sandbox banner subtitle generic; the locked decision is documented in code via a one-line comment (Step 4).
  - One PR, one or two commits ("Phase 2.5c Slice 3.5: post-smoke bug fixes" or split into "...whitespace + decision lock" + "...auto-park redirect deeplink").
  - Pass gate: `make test`, `npm run check`, `npx vitest run`, manual Playwright smoke from §Test Plan.

## Out of Scope / Future

- **Persisting `source_plan_id` on the `plans` row.** Pairs with Slice 4 (projection panel → sandbox apply) where lineage actually unlocks UX, not just decoration. Re-evaluate when Slice 4 is unblocked.
- **Auto-fork deeplink for saved scenarios** (`/planning?fork=<saved_id>` → fork-then-enter). Tempting once query-param plumbing exists, but it's a new entry-point UX, not a bug fix, and it intersects with the auto-park modal logic. Capture as a separate backlog item if needed.
- **Strip `?scenario=<id>` from the URL after the user commits / discards / saves.** Cosmetic. Refresh-as-resume covers the common case; URL hygiene is a separable polish item.
- **Per-Dialog whitespace lint.** A repo-wide lint rule that disallows multi-line text nodes inside `DialogDescription` would prevent regressions, but it's overkill for a three-instance fix today.
- **Slice 4 (projection panel).** Stays deferred. This slice does not touch projection logic.
