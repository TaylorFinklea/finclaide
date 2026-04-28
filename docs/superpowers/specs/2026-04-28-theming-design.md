# Theming — 12-theme catalogue with per-theme accent palettes

## Context

The current Finclaide palette (a custom dark scheme defined in
`frontend/src/app.css`) feels too dark and low-contrast. The fix is
to ship a 12-theme catalogue with **Tokyo Night** as the new default
and a `/settings` page that lets the user switch themes and pick an
accent slot. Tailwind v4's `@theme inline` is already wired through
CSS variables, so the existing tokens are reusable; the work is
mostly populating themes, building the settings UI, and avoiding
FOUC.

## Locked design decisions (from brainstorming)

- **Mix of dark + light** themes. 9 dark, 3 light.
- **Default theme**: Tokyo Night (replaces the current finclaide
  palette outright; the old palette is removed).
- **Selector lives on a dedicated `/settings` page** (new
  top-level route + sidebar nav item, structured to grow with
  Data / About sections later).
- **Accent picker**: per-theme native palette. Each theme exposes 8
  accent slots (`blue, purple, green, cyan, yellow, red, teal,
  orange`); the user picks a slot name; switching themes carries
  the slot name and re-tints to the new theme's value for that slot.
- **Implementation**: CSS-var runtime swap. Themes are TS objects;
  `theme-service.ts` writes vars on `document.documentElement`.
- **Persistence**: two `localStorage` keys (`finclaide.theme`,
  `finclaide.accent`). Per-browser, no cross-device sync.

## Architecture

### Data model

```ts
type ThemeMode = 'dark' | 'light'
type AccentSlot = 'blue' | 'purple' | 'green' | 'cyan'
                | 'yellow' | 'red' | 'teal' | 'orange'

interface Theme {
  id: string                      // 'tokyo-night'
  name: string                    // 'Tokyo Night'
  mode: ThemeMode
  defaultAccent: AccentSlot
  tokens: {
    background: string
    foreground: string
    card: string
    cardElevated: string
    surfaceInset: string
    popover: string
    popoverForeground: string
    primaryForeground: string     // text-on-accent
    secondary: string
    secondaryForeground: string
    muted: string
    mutedForeground: string
    accent: string                // semantic surface, NOT user accent
    accentForeground: string
    destructive: string
    border: string
    input: string
    chart2: string                // chart-1 == active accent slot
    chart3: string
    chart4: string
    chart5: string
    bodyGradientFrom: string
    bodyGradientTo: string
    bodyGradientFromAlt: string
  }
  accents: Record<AccentSlot, string>
}
```

### Token semantics

The existing CSS var `--accent` is a *semantic surface* (used by
shadcn-style hover states, dropdowns, etc.) — distinct from "the
accent color" the user picks. To avoid the collision, the
user-chosen accent maps to `--primary` + `--ring` + `--chart-1`.
The existing `--accent` token stays a neutral surface managed by
each theme's `tokens.accent`.

### Apply pipeline

`themeService.apply(theme, accentSlot)` does:

1. For each `tokens.<key>`: `root.style.setProperty('--<kebab>',
   value)`.
2. `root.style.setProperty('--primary', theme.accents[accentSlot])`.
3. `root.style.setProperty('--ring', theme.accents[accentSlot])`.
4. `root.style.setProperty('--chart-1', theme.accents[accentSlot])`.
5. `root.dataset.theme = theme.id`.
6. `root.dataset.accent = accentSlot`.
7. `root.className` toggles `dark`/`light` so Tailwind's `dark:`
   variant resolves correctly.

### First-paint / FOUC strategy

`app.html` gets two additions in `<head>`:

1. **A static `themes.css`** (~120 lines for 12 themes) shipped
   alongside `themes.ts`, structured as
   `[data-theme="tokyo-night"] { --background: ...; --foreground:
   ...; ... }`. A vitest drift-check compares `themes.ts` ↔
   `themes.css` and fails CI if they're out of sync.
2. **An inline `<script>`** that runs before SvelteKit hydrates,
   reads `localStorage`, and sets `root.dataset.theme` +
   `root.className` so the right CSS rules resolve on first paint.

After hydrate, the theme service takes over for runtime
slot/accent writes (slots are dynamic — they don't live in
`themes.css`, just `--primary` etc. set via JS).

For unauthenticated first-load (no localStorage), the default is
Tokyo Night.

### Files added / modified

**Added:**

- `frontend/src/lib/theme/types.ts` — interfaces above.
- `frontend/src/lib/theme/themes.ts` — 12 theme objects.
- `frontend/src/lib/theme/theme-service.ts` — `apply()`,
  `setTheme()`, `setAccent()`, `getCurrent()`, `subscribe()`
  (Svelte writable store).
- `frontend/src/themes.css` — static per-theme CSS blocks.
- `frontend/src/routes/settings/+page.svelte` — theme grid,
  accent swatches, mode filter chips, live preview.
- `frontend/src/routes/settings/+page.test.ts` — vitest cases.
- `frontend/src/lib/theme/themes.test.ts` — drift-check + WCAG
  contrast asserts.

**Modified:**

- `frontend/src/app.css` — replace hardcoded `:root` with a
  `[data-theme]`-namespaced default; tokenize body gradient.
- `frontend/src/app.html` — inline pre-hydrate script + import
  `themes.css`.
- `frontend/src/routes/+layout.svelte` — sidebar gains "Settings"
  link.

## The 12 themes

| # | id | Name | Mode | Default accent |
|---|---|---|---|---|
| 1 | `tokyo-night` | Tokyo Night | dark | blue |
| 2 | `tokyo-night-storm` | Tokyo Night Storm | dark | blue |
| 3 | `catppuccin-mocha` | Catppuccin Mocha | dark | purple |
| 4 | `nord` | Nord | dark | blue |
| 5 | `dracula` | Dracula | dark | purple |
| 6 | `one-dark` | One Dark | dark | blue |
| 7 | `rose-pine` | Rosé Pine | dark | red |
| 8 | `gruvbox-dark` | Gruvbox Dark | dark | yellow |
| 9 | `kanagawa` | Kanagawa | dark | blue |
| 10 | `catppuccin-latte` | Catppuccin Latte | light | purple |
| 11 | `solarized-light` | Solarized Light | light | blue |
| 12 | `gruvbox-light` | Gruvbox Light | light | orange |

Each theme provides 8 accent slots. Slots that aren't authored by
the source palette fall back to the closest hue (e.g. Solarized's
`teal` slot maps to its `cyan`). When switching themes, if the
current accent slot isn't authored on the new theme, fall back to
that theme's `defaultAccent`.

## `/settings` page UX

Single page, structured for growth (only Appearance section in
v1; Data / About to follow).

**Theme grid:** 4-column responsive grid of 12 cards. Each card
shows a 3-stripe mini swatch (background / foreground / accent
dot) plus the theme name. Click applies + persists. Current theme
is ringed.

**Mode filter chips:** above the grid — `Dark | Light | All`
(default `All`). Filter is local UI state only, not persisted.

**Accent swatches:** 8 circles using the *current theme's* native
palette. Selected slot is ringed. Click applies + persists.
Hovering shows the slot name in a tooltip.

**Live preview card:** small embedded card on the same page
showing primary button, outline button, a small bar chart in
chart-1 colors, and a body-text sample on the active background.

**Sidebar:** add a "Settings" nav item at the bottom (after
Operations) with a `Settings` icon from `lucide-svelte`.

## Slicing — 3 commits

### Slice 1 — Infrastructure + Tokyo Night default

- Add `types.ts`, `themes.ts` (Tokyo Night only),
  `theme-service.ts`.
- Add `themes.css` (Tokyo Night block only) + drift-check vitest.
- `app.html` inline script + import.
- `app.css` rewrite: namespace default under `[data-theme]`,
  tokenize body gradient.
- Tokyo Night replaces current default; old palette removed.
- Tests: vitest drift-check; existing 31 frontend cases stay
  green.
- Pass gate: docker stack boots, `/planning` renders in Tokyo
  Night, no FOUC, zero console errors.

### Slice 2 — Settings page + 11 more themes + accent

- Add remaining 11 themes to `themes.ts` and `themes.css`.
- Add `/settings/+page.svelte` with theme grid, mode chips,
  accent swatches, preview card.
- Sidebar gets "Settings" link.
- `theme-service.ts`: full `setTheme()`, `setAccent()`,
  localStorage persistence, Svelte store.
- Tests: vitest cases for theme grid render, click-to-apply
  (asserts `data-theme` attribute), accent swatch click (asserts
  `--primary` matches expected slot value), full theme parity
  test.
- Pass gate: navigate to `/settings`, click through every theme
  and every accent on at least 3 themes; nothing visually breaks.

### Slice 3 — Polish

- Per-theme tuning of `--card-elevated`, `--surface-inset` where
  defaults don't pop.
- Per-theme body gradient (currently the same hardcoded gradient
  for all themes — needs to feel native to each).
- WCAG AA contrast check vitest case: every theme × every
  foreground-on-background combo must meet 4.5:1.
- Manual smoke: light themes (Solarized Light, Catppuccin Latte,
  Gruvbox Light) checked against every page (Overview, Planning,
  Categories, Transactions, Operations).
- Pass gate: contrast test green; no readability regressions on
  any page in any theme.

## Verification

- After each slice: `make test` 146/146 (no backend changes);
  `npm run check` 0/0; `npx vitest run` green; manual click-through
  of the slice's pass gate; commit.
- After slice 3: full smoke covering all 12 themes × every page,
  + accent picker on at least Tokyo Night and Catppuccin Latte
  (one dark, one light).

## Out of scope

- Cross-device theme sync (single-household, localStorage is
  fine).
- Custom user-authored themes / theme import.
- Free-form hex accent picker (curated per-theme palette only).
- Per-page or per-section theme overrides.
- Auto-switch by time-of-day or system preference (always
  user-chosen).
- High-contrast accessibility theme variants beyond what each
  theme already provides.
