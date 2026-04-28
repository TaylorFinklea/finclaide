<script lang="ts">
  import { Check } from 'lucide-svelte'

  import Button from '$components/ui/button.svelte'
  import Card from '$components/ui/card.svelte'
  import CardContent from '$components/ui/card-content.svelte'
  import CardHeader from '$components/ui/card-header.svelte'
  import CardTitle from '$components/ui/card-title.svelte'
  import { THEMES } from '$lib/theme/themes'
  import { setAccent, setTheme, themeState } from '$lib/theme/theme-service'
  import { ACCENT_SLOTS, type AccentSlot, type Theme, type ThemeMode } from '$lib/theme/types'
  import { cn } from '$lib/utils'

  type ModeFilter = 'all' | ThemeMode
  let modeFilter: ModeFilter = $state('all')

  let visibleThemes = $derived(
    modeFilter === 'all' ? THEMES : THEMES.filter((t) => t.mode === modeFilter),
  )

  function isCurrentTheme(theme: Theme, currentId: string): boolean {
    return theme.id === currentId
  }
</script>

<div class="space-y-6">
  <Card class="border-border/40 bg-card">
    <CardHeader>
      <CardTitle>Settings</CardTitle>
      <p class="mt-2 text-sm text-muted-foreground">
        Tune how Finclaide looks. Changes apply immediately and save to this browser.
      </p>
    </CardHeader>
  </Card>

  <Card class="border-border/40 bg-card" data-testid="theme-section">
    <CardHeader class="space-y-3">
      <div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <CardTitle>Theme</CardTitle>
          <p class="mt-1 text-sm text-muted-foreground">
            Pick the palette. Switching keeps your accent slot — if the new theme has it.
          </p>
        </div>
        <div class="flex items-center gap-1 rounded-lg border border-border/60 bg-muted/30 p-1 text-xs">
          {#each (['all', 'dark', 'light'] as ModeFilter[]) as filter (filter)}
            <button
              type="button"
              class={cn(
                'rounded-md px-3 py-1.5 capitalize transition-colors',
                modeFilter === filter
                  ? 'bg-card text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground',
              )}
              aria-pressed={modeFilter === filter}
              data-mode-chip={filter}
              onclick={() => (modeFilter = filter)}
            >
              {filter}
            </button>
          {/each}
        </div>
      </div>
    </CardHeader>
    <CardContent>
      <div
        class="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
        data-testid="theme-grid"
      >
        {#each visibleThemes as theme (theme.id)}
          {@const current = isCurrentTheme(theme, $themeState.theme.id)}
          <button
            type="button"
            class={cn(
              'group relative flex flex-col gap-3 rounded-xl border p-3 text-left transition-all',
              current
                ? 'border-primary ring-2 ring-primary/40'
                : 'border-border/60 hover:border-border',
            )}
            aria-pressed={current}
            data-theme-card={theme.id}
            onclick={() => setTheme(theme.id)}
          >
            {#if current}
              <span
                class="absolute right-3 top-3 flex h-5 w-5 items-center justify-center rounded-full bg-primary text-primary-foreground"
                aria-hidden="true"
              >
                <Check class="h-3 w-3" />
              </span>
            {/if}
            <div
              class="h-16 overflow-hidden rounded-lg border border-border/40"
              style="background: {theme.tokens.background}"
              aria-hidden="true"
            >
              <div class="flex h-full items-center justify-between px-3">
                <span
                  class="font-mono text-xs"
                  style="color: {theme.tokens.foreground}"
                >Aa</span>
                <span
                  class="h-3 w-3 rounded-full"
                  style="background: {theme.accents[theme.defaultAccent]}"
                ></span>
              </div>
            </div>
            <div>
              <div class="text-sm font-medium text-foreground">{theme.name}</div>
              <div class="mt-0.5 text-xs capitalize text-muted-foreground">{theme.mode}</div>
            </div>
          </button>
        {/each}
      </div>
    </CardContent>
  </Card>

  <Card class="border-border/40 bg-card" data-testid="accent-section">
    <CardHeader>
      <CardTitle>Accent</CardTitle>
      <p class="mt-1 text-sm text-muted-foreground">
        Tints buttons, links, focus rings, and the chart highlight. Each theme exposes its own native palette.
      </p>
    </CardHeader>
    <CardContent>
      <div class="flex flex-wrap gap-3" data-testid="accent-swatches">
        {#each ACCENT_SLOTS as slot (slot)}
          {@const value = $themeState.theme.accents[slot]}
          {@const current = $themeState.accent === slot}
          <button
            type="button"
            class={cn(
              'group flex flex-col items-center gap-2 transition-transform',
              'hover:scale-105 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
            )}
            aria-pressed={current}
            aria-label={slot}
            data-accent-slot={slot}
            onclick={() => setAccent(slot)}
          >
            <span
              class={cn(
                'flex h-10 w-10 items-center justify-center rounded-full transition-shadow',
                current ? 'ring-2 ring-foreground/80 ring-offset-2 ring-offset-card' : '',
              )}
              style="background: {value}"
            >
              {#if current}
                <Check class="h-4 w-4 text-primary-foreground" />
              {/if}
            </span>
            <span class="text-xs capitalize text-muted-foreground">{slot}</span>
          </button>
        {/each}
      </div>
    </CardContent>
  </Card>

  <Card class="border-border/40 bg-card" data-testid="preview-section">
    <CardHeader>
      <CardTitle>Preview</CardTitle>
      <p class="mt-1 text-sm text-muted-foreground">
        Live sample so you can sanity-check before navigating away.
      </p>
    </CardHeader>
    <CardContent>
      <div class="space-y-4 rounded-xl border border-border/60 bg-background p-5">
        <div class="space-y-2">
          <div class="text-xs uppercase tracking-wide text-muted-foreground">Body sample</div>
          <p class="text-sm text-foreground">
            The quick brown fox jumps over the lazy dog. Reconcile is healthy. Last sync 12 minutes ago.
          </p>
          <p class="text-xs text-muted-foreground">
            Muted secondary text — used for labels, captions, and subtle metadata.
          </p>
        </div>

        <div class="flex flex-wrap items-center gap-3">
          <Button>Primary action</Button>
          <Button variant="outline">Outline</Button>
          <a href="#preview" class="text-sm font-medium text-primary hover:underline"
            >A link styled with the accent</a
          >
        </div>

        <div>
          <div class="text-xs uppercase tracking-wide text-muted-foreground">Chart sample</div>
          <div class="mt-2 flex items-end gap-1.5" aria-hidden="true">
            {#each [0.4, 0.7, 0.5, 0.85, 0.6, 0.95, 0.7] as h, i (i)}
              <div
                class="w-6 rounded-sm"
                style="height: {h * 56}px; background: var(--chart-1)"
              ></div>
            {/each}
          </div>
        </div>
      </div>
    </CardContent>
  </Card>
</div>
